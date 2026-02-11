package database

import "time"

// MediaBlob represents a media blob in the media_blob table
type MediaBlob struct {
	ID            int64  `db:"id"`
	ImageData     []byte `db:"image_data"`
	ThumbnailData []byte `db:"thumbnail_data"`
}

// MediaMetadata represents media metadata in the media_items table
type MediaMetadata struct {
	ID             int64      `db:"id"`
	MediaBlobID    int64      `db:"media_blob_id"`
	Tags           *string    `db:"tags"`
	Source         *string    `db:"source"`
	SourceReference *string   `db:"source_reference"`
	Title          *string    `db:"title"`
	Description    *string    `db:"description"`
	MediaType      *string    `db:"media_type"`
	Year           *int       `db:"year"`
	Month          *int       `db:"month"`
	Latitude       *float64   `db:"latitude"`
	Longitude      *float64   `db:"longitude"`
	Altitude       *float64   `db:"altitude"`
	HasGPS         *bool      `db:"has_gps"`
	Processed      bool       `db:"processed"`
	CreatedAt      *time.Time `db:"created_at"`
	UpdatedAt      *time.Time `db:"updated_at"`
}
