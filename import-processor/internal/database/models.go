package database

import "time"

// Message represents a message in the messages table
type Message struct {
	ID            int64      `db:"id"`
	ChatSession   *string    `db:"chat_session"`
	MessageDate   *time.Time `db:"message_date"`
	IsGroupChat   bool       `db:"is_group_chat"`
	DeliveredDate *time.Time `db:"delivered_date"`
	ReadDate      *time.Time `db:"read_date"`
	EditedDate    *time.Time `db:"edited_date"`
	Service       *string    `db:"service"`
	Type          *string    `db:"type"`
	SenderID      *string    `db:"sender_id"`
	SenderName    *string    `db:"sender_name"`
	Status        *string    `db:"status"`
	ReplyingTo    *string    `db:"replying_to"`
	Subject       *string    `db:"subject"`
	Text          *string    `db:"text"`
	Processed     bool       `db:"processed"`
	CreatedAt     *time.Time `db:"created_at"`
	UpdatedAt     *time.Time `db:"updated_at"`
}

// MediaBlob represents a media blob in the media_blob table
type MediaBlob struct {
	ID            int64  `db:"id"`
	ImageData     []byte `db:"image_data"`
	ThumbnailData []byte `db:"thumbnail_data"`
}

// MediaMetadata represents media metadata in the media_items table
type MediaMetadata struct {
	ID              int64      `db:"id"`
	MediaBlobID     int64      `db:"media_blob_id"`
	Tags            *string    `db:"tags"`
	Source          *string    `db:"source"`
	SourceReference *string    `db:"source_reference"`
	Title           *string    `db:"title"`
	Description     *string    `db:"description"`
	MediaType       *string    `db:"media_type"`
	Year            *int       `db:"year"`
	Month           *int       `db:"month"`
	Latitude        *float64   `db:"latitude"`
	Longitude       *float64   `db:"longitude"`
	Altitude        *float64   `db:"altitude"`
	HasGPS          *bool      `db:"has_gps"`
	Processed       bool       `db:"processed"`
	CreatedAt       *time.Time `db:"created_at"`
	UpdatedAt       *time.Time `db:"updated_at"`
}

// MessageAttachment represents the junction table linking messages to media items
type MessageAttachment struct {
	ID          int64 `db:"id"`
	MessageID   int64 `db:"message_id"`
	MediaItemID int64 `db:"media_item_id"`
}

// SubjectConfiguration represents the subject_configuration table
type SubjectConfiguration struct {
	ID                    int64      `db:"id"`
	SubjectName           string     `db:"subject_name"`
	Gender                string     `db:"gender"`
	FamilyName            *string    `db:"family_name"`
	OtherNames            *string    `db:"other_names"`
	EmailAddresses        *string    `db:"email_addresses"`
	PhoneNumbers          *string    `db:"phone_numbers"`
	WhatsAppHandle        *string    `db:"whatsapp_handle"`
	InstagramHandle       *string    `db:"instagram_handle"`
	SystemInstructions    string     `db:"system_instructions"`
	CoreSystemInstructions string   `db:"core_system_instructions"`
	CreatedAt             *time.Time `db:"created_at"`
	UpdatedAt             *time.Time `db:"updated_at"`
}
