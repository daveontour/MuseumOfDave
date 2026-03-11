package repository

import (
	"context"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/museum-of-dave/app/internal/model"
)

// ImageRepo runs queries against media_items, media_blob, and facebook_albums tables.
type ImageRepo struct {
	pool *pgxpool.Pool
}

// NewImageRepo creates an ImageRepo backed by the given pool.
func NewImageRepo(pool *pgxpool.Pool) *ImageRepo {
	return &ImageRepo{pool: pool}
}

// ── media_items queries ───────────────────────────────────────────────────────

const mediaItemColumns = `
	id, media_blob_id, description, title, author, tags, categories, notes,
	available_for_task, media_type, processed, created_at, updated_at, embedding,
	year, month, latitude, longitude, altitude, rating, has_gps, google_maps_url,
	region, is_personal, is_business, is_social, is_promotional, is_spam,
	is_important, use_by_ai, is_referenced, source, source_reference`

// GetMediaItemByID returns a media_items row by primary key.
func (r *ImageRepo) GetMediaItemByID(ctx context.Context, id int64) (*model.MediaItem, error) {
	row := r.pool.QueryRow(ctx,
		`SELECT `+mediaItemColumns+` FROM media_items WHERE id = $1`, id)
	return scanMediaItem(row)
}

// GetBlobByID returns a media_blob row by primary key.
func (r *ImageRepo) GetBlobByID(ctx context.Context, blobID int64) (*model.MediaBlob, error) {
	b := &model.MediaBlob{}
	err := r.pool.QueryRow(ctx,
		`SELECT id, image_data, thumbnail_data FROM media_blob WHERE id = $1`, blobID,
	).Scan(&b.ID, &b.ImageData, &b.ThumbnailData)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("GetBlobByID %d: %w", blobID, err)
	}
	return b, nil
}

// GetBlobByMetadataID returns the media_blob row for a given media_items.id.
func (r *ImageRepo) GetBlobByMetadataID(ctx context.Context, metaID int64) (*model.MediaBlob, error) {
	b := &model.MediaBlob{}
	err := r.pool.QueryRow(ctx, `
		SELECT mb.id, mb.image_data, mb.thumbnail_data
		FROM media_blob mb
		JOIN media_items mi ON mi.media_blob_id = mb.id
		WHERE mi.id = $1`, metaID,
	).Scan(&b.ID, &b.ImageData, &b.ThumbnailData)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("GetBlobByMetadataID %d: %w", metaID, err)
	}
	return b, nil
}

// GetMediaItemByBlobID returns the media_items row for a given media_blob.id.
func (r *ImageRepo) GetMediaItemByBlobID(ctx context.Context, blobID int64) (*model.MediaItem, error) {
	row := r.pool.QueryRow(ctx,
		`SELECT `+mediaItemColumns+` FROM media_items WHERE media_blob_id = $1`, blobID)
	return scanMediaItem(row)
}

// Search returns media_items matching all provided filters (AND logic),
// always filtered to media_type LIKE 'image/%', ordered by created_at DESC.
func (r *ImageRepo) Search(ctx context.Context, p model.ImageSearchParams) ([]*model.MediaItem, error) {
	var conds []string
	var args []any
	n := 1

	addLike := func(col, val string) {
		conds = append(conds, fmt.Sprintf("%s ILIKE $%d", col, n))
		args = append(args, "%"+val+"%")
		n++
	}
	addExact := func(col, val string) {
		conds = append(conds, fmt.Sprintf("%s ILIKE $%d", col, n))
		args = append(args, val) // no wildcards — mirrors Python .ilike(filters.source)
		n++
	}
	addEq := func(col string, val any) {
		conds = append(conds, fmt.Sprintf("%s = $%d", col, n))
		args = append(args, val)
		n++
	}

	if p.Title != nil {
		addLike("title", *p.Title)
	}
	if p.Description != nil {
		addLike("description", *p.Description)
	}
	if p.Author != nil {
		addLike("author", *p.Author)
	}
	if p.Tags != nil {
		// Each comma-separated tag is OR'd: tag1 OR tag2 OR ...
		tagList := splitTrim(*p.Tags, ',')
		if len(tagList) > 0 {
			var orParts []string
			for _, tag := range tagList {
				orParts = append(orParts, fmt.Sprintf("tags ILIKE $%d", n))
				args = append(args, "%"+tag+"%")
				n++
			}
			conds = append(conds, "("+strings.Join(orParts, " OR ")+")")
		}
	}
	if p.Categories != nil {
		addLike("categories", *p.Categories)
	}
	if p.Source != nil {
		addExact("source", *p.Source)
	}
	if p.SourceReference != nil {
		addLike("source_reference", *p.SourceReference)
	}
	if p.MediaType != nil {
		addLike("media_type", *p.MediaType)
	}
	if p.Region != nil {
		addLike("region", *p.Region)
	}
	if p.Year != nil {
		addEq("year", *p.Year)
	}
	if p.Month != nil {
		addEq("month", *p.Month)
	}
	if p.Rating != nil {
		addEq("rating", *p.Rating)
	} else {
		if p.RatingMin != nil {
			conds = append(conds, fmt.Sprintf("rating >= $%d", n))
			args = append(args, *p.RatingMin)
			n++
		}
		if p.RatingMax != nil {
			conds = append(conds, fmt.Sprintf("rating <= $%d", n))
			args = append(args, *p.RatingMax)
			n++
		}
	}
	if p.HasGPS != nil {
		addEq("has_gps", *p.HasGPS)
	}
	if p.AvailableForTask != nil {
		addEq("available_for_task", *p.AvailableForTask)
	}
	if p.Processed != nil {
		addEq("processed", *p.Processed)
	}

	// Always restrict to image/* media types
	conds = append(conds, "media_type LIKE 'image/%'")

	sql := `SELECT ` + mediaItemColumns + ` FROM media_items`
	if len(conds) > 0 {
		sql += " WHERE " + strings.Join(conds, " AND ")
	}
	sql += " ORDER BY created_at DESC"

	rows, err := r.pool.Query(ctx, sql, args...)
	if err != nil {
		return nil, fmt.Errorf("image Search: %w", err)
	}
	defer rows.Close()
	return scanMediaItems(rows)
}

// GetDistinctYears returns distinct non-null years ordered DESC.
func (r *ImageRepo) GetDistinctYears(ctx context.Context) ([]int, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT DISTINCT year FROM media_items WHERE year IS NOT NULL ORDER BY year DESC`)
	if err != nil {
		return nil, fmt.Errorf("GetDistinctYears: %w", err)
	}
	defer rows.Close()

	var years []int
	for rows.Next() {
		var y int
		if err := rows.Scan(&y); err != nil {
			return nil, err
		}
		years = append(years, y)
	}
	return years, rows.Err()
}

// GetAllTagStrings returns all non-empty tags column values (un-split).
// Caller is responsible for splitting and deduplicating.
func (r *ImageRepo) GetAllTagStrings(ctx context.Context) ([]string, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT tags FROM media_items WHERE tags IS NOT NULL AND tags != ''`)
	if err != nil {
		return nil, fmt.Errorf("GetAllTagStrings: %w", err)
	}
	defer rows.Close()

	var all []string
	for rows.Next() {
		var t string
		if err := rows.Scan(&t); err != nil {
			return nil, err
		}
		all = append(all, t)
	}
	return all, rows.Err()
}

// GetLocations returns media_items with GPS data (has_gps=true or lat/lng non-null).
func (r *ImageRepo) GetLocations(ctx context.Context) ([]*model.MediaItem, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT `+mediaItemColumns+` FROM media_items
		 WHERE has_gps = TRUE
		    OR (latitude IS NOT NULL AND longitude IS NOT NULL)`)
	if err != nil {
		return nil, fmt.Errorf("GetLocations: %w", err)
	}
	defer rows.Close()
	return scanMediaItems(rows)
}

// ── facebook_albums queries ───────────────────────────────────────────────────

// GetFacebookAlbums returns all albums with their image count.
func (r *ImageRepo) GetFacebookAlbums(ctx context.Context) ([]model.FacebookAlbumResponse, error) {
	rows, err := r.pool.Query(ctx, `
		SELECT fa.id, fa.name, fa.description, fa.cover_photo_uri,
		       COUNT(DISTINCT am.id) AS image_count
		FROM facebook_albums fa
		LEFT JOIN album_media am ON fa.id = am.album_id
		GROUP BY fa.id, fa.name, fa.description, fa.cover_photo_uri
		ORDER BY fa.name`)
	if err != nil {
		return nil, fmt.Errorf("GetFacebookAlbums: %w", err)
	}
	defer rows.Close()

	var albums []model.FacebookAlbumResponse
	for rows.Next() {
		var a model.FacebookAlbumResponse
		if err := rows.Scan(&a.ID, &a.Name, &a.Description, &a.CoverPhotoURI, &a.ImageCount); err != nil {
			return nil, err
		}
		albums = append(albums, a)
	}
	return albums, rows.Err()
}

// GetAlbumImages returns media_items linked to an album, ordered by created_at ASC.
func (r *ImageRepo) GetAlbumImages(ctx context.Context, albumID int64) ([]*model.MediaItem, error) {
	rows, err := r.pool.Query(ctx,
		`SELECT `+mediaItemColumns+`
		 FROM media_items mi
		 JOIN album_media am ON mi.id = am.media_item_id
		 WHERE am.album_id = $1
		 ORDER BY mi.created_at ASC`, albumID)
	if err != nil {
		return nil, fmt.Errorf("GetAlbumImages: %w", err)
	}
	defer rows.Close()
	return scanMediaItems(rows)
}

// GetAlbumImageByID returns a media_items row that is linked to any album.
func (r *ImageRepo) GetAlbumImageByID(ctx context.Context, imageID int64) (*model.MediaItem, error) {
	row := r.pool.QueryRow(ctx,
		`SELECT `+mediaItemColumns+`
		 FROM media_items mi
		 JOIN album_media am ON mi.id = am.media_item_id
		 WHERE mi.id = $1
		 LIMIT 1`, imageID)
	return scanMediaItem(row)
}

// ── scanners ──────────────────────────────────────────────────────────────────

type scanner interface {
	Scan(dest ...any) error
}

func scanMediaItem(row scanner) (*model.MediaItem, error) {
	m := &model.MediaItem{}
	err := row.Scan(
		&m.ID, &m.MediaBlobID, &m.Description, &m.Title, &m.Author, &m.Tags,
		&m.Categories, &m.Notes, &m.AvailableForTask, &m.MediaType, &m.Processed,
		&m.CreatedAt, &m.UpdatedAt, &m.Embedding,
		&m.Year, &m.Month, &m.Latitude, &m.Longitude, &m.Altitude,
		&m.Rating, &m.HasGPS, &m.GoogleMapsURL, &m.Region,
		&m.IsPersonal, &m.IsBusiness, &m.IsSocial, &m.IsPromotional,
		&m.IsSpam, &m.IsImportant, &m.UseByAI, &m.IsReferenced,
		&m.Source, &m.SourceReference,
	)
	if err != nil {
		if isNoRows(err) {
			return nil, nil
		}
		return nil, err
	}
	return m, nil
}

func scanMediaItems(rows interface {
	Next() bool
	Scan(dest ...any) error
	Err() error
}) ([]*model.MediaItem, error) {
	var items []*model.MediaItem
	for rows.Next() {
		m := &model.MediaItem{}
		if err := rows.Scan(
			&m.ID, &m.MediaBlobID, &m.Description, &m.Title, &m.Author, &m.Tags,
			&m.Categories, &m.Notes, &m.AvailableForTask, &m.MediaType, &m.Processed,
			&m.CreatedAt, &m.UpdatedAt, &m.Embedding,
			&m.Year, &m.Month, &m.Latitude, &m.Longitude, &m.Altitude,
			&m.Rating, &m.HasGPS, &m.GoogleMapsURL, &m.Region,
			&m.IsPersonal, &m.IsBusiness, &m.IsSocial, &m.IsPromotional,
			&m.IsSpam, &m.IsImportant, &m.UseByAI, &m.IsReferenced,
			&m.Source, &m.SourceReference,
		); err != nil {
			return nil, err
		}
		items = append(items, m)
	}
	return items, rows.Err()
}
