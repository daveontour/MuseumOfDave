package database

import (
	"context"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/jackc/pgx/v5"
)

const facebookAlbumSource = "facebook_album"

// BatchAlbumImageItem represents a single album image for batch save
type BatchAlbumImageItem struct {
	AlbumID           int64
	URI               string
	Filename          string
	CreationTimestamp *time.Time
	Title             string
	Description       string
	ImageData         []byte
	ImageType         string
	AlbumName         string
}

// FacebookAlbumStorage handles Facebook album storage operations
type FacebookAlbumStorage struct {
	db *DB
}

// NewFacebookAlbumStorage creates a new Facebook album storage instance
func NewFacebookAlbumStorage(db *DB) *FacebookAlbumStorage {
	return &FacebookAlbumStorage{db: db}
}

// FindAlbumByName looks up an album by name. Returns (album_id, true) if found, (0, false) otherwise.
func (s *FacebookAlbumStorage) FindAlbumByName(ctx context.Context, name string) (int64, bool, error) {
	var albumID int64
	err := s.db.Pool.QueryRow(ctx, `SELECT id FROM facebook_albums WHERE name = $1 LIMIT 1`, name).Scan(&albumID)
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			return 0, false, nil
		}
		return 0, false, fmt.Errorf("failed to find album by name: %w", err)
	}
	return albumID, true, nil
}

// SaveOrUpdateAlbum creates a new album or updates an existing one by name.
// Returns (album_id, was_created, error).
func (s *FacebookAlbumStorage) SaveOrUpdateAlbum(ctx context.Context, name, description, coverPhotoURI string, lastModified *time.Time) (int64, bool, error) {
	existingID, found, err := s.FindAlbumByName(ctx, name)
	if err != nil {
		return 0, false, err
	}
	if found {
		_, err = s.db.Pool.Exec(ctx, `UPDATE facebook_albums SET
			description = $1, cover_photo_uri = $2, last_modified_timestamp = $3, updated_at = NOW()
			WHERE id = $4`,
			nullIfEmpty(description),
			nullIfEmpty(coverPhotoURI),
			lastModified,
			existingID,
		)
		if err != nil {
			return 0, false, fmt.Errorf("failed to update album: %w", err)
		}
		return existingID, false, nil
	}
	var albumID int64
	query := `INSERT INTO facebook_albums (name, description, cover_photo_uri, last_modified_timestamp, created_at, updated_at)
		VALUES ($1, $2, $3, $4, NOW(), NOW()) RETURNING id`
	err = s.db.Pool.QueryRow(ctx, query,
		name,
		nullIfEmpty(description),
		nullIfEmpty(coverPhotoURI),
		lastModified,
	).Scan(&albumID)
	if err != nil {
		return 0, false, fmt.Errorf("failed to insert album: %w", err)
	}
	return albumID, true, nil
}

// SaveAlbumImage creates a media item for an album image and links it via album_media.
// imageData and imageType may be nil/empty if file was not found.
func (s *FacebookAlbumStorage) SaveAlbumImage(ctx context.Context, albumID int64, uri, filename string, creationTimestamp *time.Time, title, description string, imageData []byte, imageType string, albumName string) (int64, error) {
	tx, err := s.db.Pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	var blobID int64
	if len(imageData) > 0 {
		err = tx.QueryRow(ctx, `INSERT INTO media_blob (image_data, thumbnail_data) VALUES ($1, $2) RETURNING id`,
			imageData, nil).Scan(&blobID)
	} else {
		err = tx.QueryRow(ctx, `INSERT INTO media_blob (image_data, thumbnail_data) VALUES ($1, $2) RETURNING id`,
			nil, nil).Scan(&blobID)
	}
	if err != nil {
		return 0, fmt.Errorf("failed to insert media blob: %w", err)
	}

	var year, month *int
	if creationTimestamp != nil {
		y := creationTimestamp.Year()
		m := int(creationTimestamp.Month())
		year = &y
		month = &m
	}

	displayTitle := title
	if displayTitle == "" {
		displayTitle = filename
	}

	sourceRef := strconv.FormatInt(albumID, 10)
	var mediaItemID int64
	err = tx.QueryRow(ctx, `INSERT INTO media_items (
		media_blob_id, tags, source, source_reference, title, description,
		media_type, year, month, latitude, longitude, altitude, has_gps,
		processed, available_for_task, rating, is_personal, is_business,
		is_social, is_promotional, is_spam, is_important, created_at, updated_at
	) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, NOW(), NOW())
	RETURNING id`,
		blobID,
		nullIfEmpty(albumName),
		facebookAlbumSource,
		sourceRef,
		nullIfEmpty(displayTitle),
		nullIfEmpty(description),
		nullIfEmpty(imageType),
		year, month,
		nil, nil, nil, // latitude, longitude, altitude
		false, false, false, 5, // has_gps, processed, available_for_task, rating
		false, false, false, false, false, false, // is_personal through is_important
	).Scan(&mediaItemID)
	if err != nil {
		return 0, fmt.Errorf("failed to insert media item: %w", err)
	}

	_, err = tx.Exec(ctx, `INSERT INTO album_media (album_id, media_item_id) VALUES ($1, $2)`, albumID, mediaItemID)
	if err != nil {
		return 0, fmt.Errorf("failed to insert album_media: %w", err)
	}

	if err = tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("failed to commit: %w", err)
	}
	return mediaItemID, nil
}

// SaveAlbumImagesBatch saves multiple album images in a single transaction.
// Returns the number of images imported, or an error if any insert fails.
func (s *FacebookAlbumStorage) SaveAlbumImagesBatch(ctx context.Context, items []BatchAlbumImageItem) (int, error) {
	if len(items) == 0 {
		return 0, nil
	}

	tx, err := s.db.Pool.Begin(ctx)
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	imported := 0
	for _, item := range items {
		var blobID int64
		if len(item.ImageData) > 0 {
			err = tx.QueryRow(ctx, `INSERT INTO media_blob (image_data, thumbnail_data) VALUES ($1, $2) RETURNING id`,
				item.ImageData, nil).Scan(&blobID)
		} else {
			err = tx.QueryRow(ctx, `INSERT INTO media_blob (image_data, thumbnail_data) VALUES ($1, $2) RETURNING id`,
				nil, nil).Scan(&blobID)
		}
		if err != nil {
			return imported, fmt.Errorf("failed to insert media blob for %s: %w", item.URI, err)
		}

		var year, month *int
		if item.CreationTimestamp != nil {
			y := item.CreationTimestamp.Year()
			m := int(item.CreationTimestamp.Month())
			year = &y
			month = &m
		}

		displayTitle := item.Title
		if displayTitle == "" {
			displayTitle = item.Filename
		}

		sourceRef := strconv.FormatInt(item.AlbumID, 10)
		var mediaItemID int64
		err = tx.QueryRow(ctx, `INSERT INTO media_items (
			media_blob_id, tags, source, source_reference, title, description,
			media_type, year, month, latitude, longitude, altitude, has_gps,
			processed, available_for_task, rating, is_personal, is_business,
			is_social, is_promotional, is_spam, is_important, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, NOW(), NOW())
		RETURNING id`,
			blobID,
			nullIfEmpty(item.AlbumName),
			facebookAlbumSource,
			sourceRef,
			nullIfEmpty(displayTitle),
			nullIfEmpty(item.Description),
			nullIfEmpty(item.ImageType),
			year, month,
			nil, nil, nil,
			false, false, false, 5,
			false, false, false, false, false, false,
		).Scan(&mediaItemID)
		if err != nil {
			return imported, fmt.Errorf("failed to insert media item for %s: %w", item.URI, err)
		}

		_, err = tx.Exec(ctx, `INSERT INTO album_media (album_id, media_item_id) VALUES ($1, $2)`, item.AlbumID, mediaItemID)
		if err != nil {
			return imported, fmt.Errorf("failed to insert album_media for %s: %w", item.URI, err)
		}
		imported++
	}

	if err = tx.Commit(ctx); err != nil {
		return 0, fmt.Errorf("failed to commit: %w", err)
	}
	return imported, nil
}
