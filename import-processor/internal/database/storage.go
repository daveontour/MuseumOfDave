package database

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// MessageStorage handles message storage operations
type MessageStorage struct {
	db              *DB
	subjectName     string
	familyName      string
	subjectFullName string
}

// NewMessageStorage creates a new message storage instance and initializes subject name from subject_configuration
func NewMessageStorage(db *DB) *MessageStorage {
	s := &MessageStorage{db: db}
	ctx := context.Background()
	query := `SELECT subject_name, family_name FROM subject_configuration LIMIT 1`
	var subjectName, familyName string
	if err := db.Pool.QueryRow(ctx, query).Scan(&subjectName, &familyName); err == nil {
		s.subjectName = subjectName
		s.familyName = familyName
		s.subjectFullName = subjectName + " " + familyName
	}
	return s
}

// MessageData represents message data for saving
type MessageData struct {
	ChatSession   *string
	MessageDate   *time.Time
	DeliveredDate *time.Time
	ReadDate      *time.Time
	EditedDate    *time.Time
	Service       *string
	Type          *string
	SenderID      *string
	SenderName    *string
	Status        *string
	ReplyingTo    *string
	Subject       *string
	Text          *string
	IsGroupChat   bool
}

// SaveIMessage saves a message to the database
// Returns the message ID and whether it was an update (true) or create (false)
func (s *MessageStorage) SaveIMessage(ctx context.Context, data MessageData, attachmentData []byte, attachmentFilename, attachmentType, source string) (int64, bool, error) {
	tx, err := s.db.Pool.Begin(ctx)
	if err != nil {
		return 0, false, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	if _, err = tx.Exec(ctx, "SET LOCAL synchronous_commit = off"); err != nil {
		return 0, false, fmt.Errorf("failed to set synchronous_commit: %w", err)
	}

	// Check if message already exists
	var existingID int64
	var isUpdate bool

	checkQuery := `SELECT id FROM messages 
		WHERE chat_session = $1 
		AND message_date = $2 
		AND sender_id = $3 
		AND type = $4 
		LIMIT 1`

	err = tx.QueryRow(ctx, checkQuery,
		data.ChatSession,
		data.MessageDate,
		data.SenderID,
		data.Type,
	).Scan(&existingID)

	if err == nil {
		// Message exists, update it
		isUpdate = true
		updateQuery := `UPDATE messages SET
			delivered_date = $1,
			read_date = $2,
			edited_date = $3,
			service = $4,
			sender_name = $5,
			status = $6,
			replying_to = $7,
			subject = $8,
			text = $9,
			is_group_chat = $10,
			updated_at = NOW()
			WHERE id = $11`

		_, err = tx.Exec(ctx, updateQuery,
			data.DeliveredDate,
			data.ReadDate,
			data.EditedDate,
			data.Service,
			data.SenderName,
			data.Status,
			data.ReplyingTo,
			data.Subject,
			data.Text,
			data.IsGroupChat,
			existingID,
		)
		if err != nil {
			return 0, false, fmt.Errorf("failed to update message: %w", err)
		}

		// Delete existing message attachments
		_, err = tx.Exec(ctx, "DELETE FROM message_attachments WHERE message_id = $1", existingID)
		if err != nil {
			return 0, false, fmt.Errorf("failed to delete existing attachments: %w", err)
		}

	} else if err == pgx.ErrNoRows {
		// Message doesn't exist, create it
		isUpdate = false
		insertQuery := `INSERT INTO messages (
			chat_session, message_date, delivered_date, read_date, edited_date,
			service, type, sender_id, sender_name, status, replying_to,
			subject, text, is_group_chat, processed, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), NOW())
		RETURNING id`

		err = tx.QueryRow(ctx, insertQuery,
			data.ChatSession,
			data.MessageDate,
			data.DeliveredDate,
			data.ReadDate,
			data.EditedDate,
			data.Service,
			data.Type,
			data.SenderID,
			data.SenderName,
			data.Status,
			data.ReplyingTo,
			data.Subject,
			data.Text,
			data.IsGroupChat,
			false, // processed
		).Scan(&existingID)
		if err != nil {
			return 0, false, fmt.Errorf("failed to insert message: %w", err)
		}
	} else {
		return 0, false, fmt.Errorf("failed to check for existing message: %w", err)
	}

	// Handle attachment if provided
	if len(attachmentData) > 0 {
		err = s.saveAttachment(ctx, tx, existingID, attachmentData, attachmentFilename, attachmentType, source, data)
		if err != nil {
			// Log error but don't fail the entire operation
			fmt.Fprintf(os.Stderr, "Warning: Could not save attachment: %v\n", err)
		}
	}

	// Commit transaction
	if err = tx.Commit(ctx); err != nil {
		return 0, false, fmt.Errorf("failed to commit transaction: %w", err)
	}

	return existingID, isUpdate, nil
}

// saveAttachment saves an attachment for a message
func (s *MessageStorage) saveAttachment(ctx context.Context, tx pgx.Tx, messageID int64, attachmentData []byte, attachmentFilename, attachmentType, source string, messageData MessageData) error {
	// For now, we'll skip thumbnail creation and EXIF extraction
	// These can be added later if needed using Go image libraries
	var thumbnailData []byte = nil

	// Create MediaBlob
	var blobID int64
	insertBlobQuery := `INSERT INTO media_blob (image_data, thumbnail_data) VALUES ($1, $2) RETURNING id`
	err := tx.QueryRow(ctx, insertBlobQuery, attachmentData, thumbnailData).Scan(&blobID)
	if err != nil {
		return fmt.Errorf("failed to insert media blob (filename: %s, size: %d bytes, type: %s): %w",
			attachmentFilename, len(attachmentData), attachmentType, err)
	}

	// Extract year and month from message date
	var year, month *int
	if messageData.MessageDate != nil {
		y := messageData.MessageDate.Year()
		m := int(messageData.MessageDate.Month())
		year = &y
		month = &m
	}

	// Set default source if not provided
	if source == "" {
		source = "message_attachment"
	}

	// Create MediaMetadata
	var mediaItemID int64
	chatSessionStr := ""
	if messageData.ChatSession != nil {
		chatSessionStr = *messageData.ChatSession
	}
	messageIDStr := fmt.Sprintf("%d", messageID)

	insertMetadataQuery := `INSERT INTO media_items (
		media_blob_id, tags, source, source_reference, title, description,
		media_type, year, month, latitude, longitude, altitude, has_gps,
		processed, available_for_task, rating, is_personal, is_business,
		is_social, is_promotional, is_spam, is_important, created_at, updated_at, is_referenced
	) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, NOW(), NOW(), False)
	RETURNING id`

	err = tx.QueryRow(ctx, insertMetadataQuery,
		blobID,
		chatSessionStr,
		source,
		messageIDStr,
		attachmentFilename,
		nil, // description
		attachmentType,
		year,
		month,
		nil,   // latitude
		nil,   // longitude
		nil,   // altitude
		false, // has_gps
		false, // processed
		false, // available_for_task
		5,     // rating (default value)
		false, // is_personal
		false, // is_business
		false, // is_social
		false, // is_promotional
		false, // is_spam
		false, // is_important
	).Scan(&mediaItemID)
	if err != nil {
		return fmt.Errorf("failed to insert media metadata (blob_id: %d, filename: %s, type: %s): %w",
			blobID, attachmentFilename, attachmentType, err)
	}

	// Create MessageAttachment junction entry
	insertJunctionQuery := `INSERT INTO message_attachments (message_id, media_item_id) VALUES ($1, $2)`
	_, err = tx.Exec(ctx, insertJunctionQuery, messageID, mediaItemID)
	if err != nil {
		return fmt.Errorf("failed to insert message attachment junction (message_id: %d, media_item_id: %d, filename: %s): %w",
			messageID, mediaItemID, attachmentFilename, err)
	}

	return nil
}

// SetIsGroupChat sets the is_group_chat flag for group chats
func (s *MessageStorage) SetIsGroupChat(ctx context.Context) error {
	query := `WITH GroupSessions AS (
		SELECT 
			chat_session,
			service
		FROM 
			messages
		WHERE 
			service IN ('WhatsApp', 'Facebook Messenger')
		GROUP BY 
			chat_session, service
		HAVING 
			COUNT(DISTINCT sender_id) > 2
	)
	UPDATE messages m
	SET is_group_chat = TRUE
	FROM GroupSessions gs
	WHERE m.chat_session = gs.chat_session 
	AND m.service = gs.service`

	_, err := s.db.Pool.Exec(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to set is_group_chat flag: %w", err)
	}

	return nil
}

// DeleteOrphanFacebookConversations deletes messages from Facebook Messenger chats with fewer than 2 messages
func (s *MessageStorage) DeleteOrphanFacebookConversations(ctx context.Context) error {
	query := `DELETE FROM messages WHERE service = 'Facebook Messenger' AND chat_session IN (
		SELECT chat_session FROM messages WHERE service = 'Facebook Messenger'
		GROUP BY chat_session HAVING COUNT(*) < 2
	)`
	_, err := s.db.Pool.Exec(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to delete orphan Facebook conversations: %w", err)
	}
	return nil
}

// MessageWithAttachment represents a message with its attachment data
type MessageWithAttachment struct {
	MessageData        MessageData
	AttachmentData     []byte
	AttachmentFilename string
	AttachmentType     string
	Source             string
}

// BatchSaveResult contains the results of a batch save operation
type BatchSaveResult struct {
	Created                        int
	Updated                        int
	Errors                         int
	AttachmentErrorsBlobInsert     int
	AttachmentErrorsMetadataInsert int
	AttachmentErrorsJunctionInsert int
}

// SaveMessagesBatch saves multiple messages in a single transaction using bulk operations
// This is much faster than saving messages individually
func (s *MessageStorage) SaveMessagesBatch(ctx context.Context, messages []MessageWithAttachment) (*BatchSaveResult, error) {
	if len(messages) == 0 {
		return &BatchSaveResult{}, nil
	}

	result := &BatchSaveResult{}
	tx, err := s.db.Pool.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	if _, err = tx.Exec(ctx, "SET LOCAL synchronous_commit = off"); err != nil {
		return nil, fmt.Errorf("failed to set synchronous_commit: %w", err)
	}

	// Build a map to check for existing messages efficiently
	type messageKey struct {
		chatSession string
		messageDate time.Time
		senderID    string
		msgType     string
	}

	// Apply SenderID rewrite for outgoing messages before building existingMap,
	// so the query matches what's stored in DB (inserts/updates use rewritten SenderID)
	for i := range messages {
		if messages[i].MessageData.Type != nil && *messages[i].MessageData.Type == "Outgoing" {
			messages[i].MessageData.SenderID = &s.subjectFullName
			messages[i].MessageData.SenderName = &s.subjectFullName
		}
	}

	// First, check which messages already exist using a single query
	existingMap := make(map[messageKey]int64)
	if len(messages) > 0 {
		// Build query to check all messages at once
		var checkQuery strings.Builder
		checkQuery.WriteString(`SELECT id, chat_session, message_date, sender_id, type 
			FROM messages 
			WHERE (chat_session, message_date, sender_id, type) IN (`)

		args := make([]interface{}, 0, len(messages)*4)
		placeholders := make([]string, 0, len(messages))
		argIndex := 1

		for _, msg := range messages {
			if msg.MessageData.ChatSession != nil && msg.MessageData.MessageDate != nil &&
				msg.MessageData.SenderID != nil && msg.MessageData.Type != nil {
				placeholders = append(placeholders, fmt.Sprintf("($%d, $%d, $%d, $%d)",
					argIndex, argIndex+1, argIndex+2, argIndex+3))
				args = append(args, *msg.MessageData.ChatSession, *msg.MessageData.MessageDate,
					*msg.MessageData.SenderID, *msg.MessageData.Type)
				argIndex += 4
			}
		}

		if len(placeholders) > 0 {
			checkQuery.WriteString(strings.Join(placeholders, ", "))
			checkQuery.WriteString(")")
			rows, err := tx.Query(ctx, checkQuery.String(), args...)
			if err == nil {
				defer rows.Close()
				for rows.Next() {
					var id int64
					var chatSession string
					var messageDate time.Time
					var senderID string
					var msgType string
					if err := rows.Scan(&id, &chatSession, &messageDate, &senderID, &msgType); err == nil {
						key := messageKey{chatSession: chatSession, messageDate: messageDate, senderID: senderID, msgType: msgType}
						existingMap[key] = id
					}
				}
			}
		}
	}

	// Separate messages into inserts and updates
	var toInsert []MessageWithAttachment
	var toUpdate []struct {
		msg MessageWithAttachment
		id  int64
	}

	for _, msg := range messages {
		if msg.MessageData.ChatSession == nil || msg.MessageData.MessageDate == nil ||
			msg.MessageData.SenderID == nil || msg.MessageData.Type == nil {
			result.Errors++
			// Log which fields are missing for debugging
			var missingFields []string
			if msg.MessageData.ChatSession == nil {
				missingFields = append(missingFields, "ChatSession")
			}
			if msg.MessageData.MessageDate == nil {
				missingFields = append(missingFields, "MessageDate")
			}
			if msg.MessageData.SenderID == nil {
				missingFields = append(missingFields, "SenderID")
			}
			if msg.MessageData.Type == nil {
				missingFields = append(missingFields, "Type")
			}
			if len(missingFields) > 0 && result.Errors <= 10 {
				// Only log first 10 to avoid spam
				fmt.Fprintf(os.Stderr, "Warning: Skipping message with missing required fields: %v\n", missingFields)
			}
			continue
		}

		key := messageKey{
			chatSession: *msg.MessageData.ChatSession,
			messageDate: *msg.MessageData.MessageDate,
			senderID:    *msg.MessageData.SenderID,
			msgType:     *msg.MessageData.Type,
		}

		if existingID, exists := existingMap[key]; exists {
			toUpdate = append(toUpdate, struct {
				msg MessageWithAttachment
				id  int64
			}{msg: msg, id: existingID})
		} else {
			toInsert = append(toInsert, msg)
		}
	}

	// Batch insert new messages
	if len(toInsert) > 0 {
		insertedIDs, err := s.batchInsertMessages(ctx, tx, toInsert)
		if err != nil {
			return nil, fmt.Errorf("failed to batch insert messages: %w", err)
		}

		// Process attachments for inserted messages
		for i, msg := range toInsert {
			if len(msg.AttachmentData) > 0 && i < len(insertedIDs) {
				if err := s.saveAttachment(ctx, tx, insertedIDs[i], msg.AttachmentData,
					msg.AttachmentFilename, msg.AttachmentType, msg.Source, msg.MessageData); err != nil {
					// Log detailed error information
					errorMsg := fmt.Sprintf("Message ID %d | Filename: %s | Type: %s | Size: %d bytes | Error: %v",
						insertedIDs[i], msg.AttachmentFilename, msg.AttachmentType, len(msg.AttachmentData), err)
					fmt.Fprintf(os.Stderr, "Error: Failed to save attachment - %s\n", errorMsg)
					// Track error type based on error message content
					errorTextLower := strings.ToLower(err.Error())
					if strings.Contains(errorTextLower, "failed to insert media blob") {
						result.AttachmentErrorsBlobInsert++
					} else if strings.Contains(errorTextLower, "failed to insert media metadata") {
						result.AttachmentErrorsMetadataInsert++
					} else if strings.Contains(errorTextLower, "failed to insert message attachment junction") {
						result.AttachmentErrorsJunctionInsert++
					} else {
						// Unknown database error, default to blob insert
						result.AttachmentErrorsBlobInsert++
					}
				}
			}
		}
		result.Created = len(toInsert)
	}

	// Batch update existing messages
	if len(toUpdate) > 0 {
		if err := s.batchUpdateMessages(ctx, tx, toUpdate); err != nil {
			return nil, fmt.Errorf("failed to batch update messages: %w", err)
		}

		// Delete old attachments and add new ones for updated messages
		for _, item := range toUpdate {
			// Delete existing attachments
			_, _ = tx.Exec(ctx, "DELETE FROM message_attachments WHERE message_id = $1", item.id)

			// Add new attachment if present
			if len(item.msg.AttachmentData) > 0 {
				if err := s.saveAttachment(ctx, tx, item.id, item.msg.AttachmentData,
					item.msg.AttachmentFilename, item.msg.AttachmentType, item.msg.Source, item.msg.MessageData); err != nil {
					errorMsg := fmt.Sprintf("Message ID %d | Filename: %s | Type: %s | Size: %d bytes | Error: %v",
						item.id, item.msg.AttachmentFilename, item.msg.AttachmentType, len(item.msg.AttachmentData), err)
					fmt.Fprintf(os.Stderr, "Error: Failed to save attachment - %s\n", errorMsg)
					// Track error type based on error message content
					errorTextLower := strings.ToLower(err.Error())
					if strings.Contains(errorTextLower, "failed to insert media blob") {
						result.AttachmentErrorsBlobInsert++
					} else if strings.Contains(errorTextLower, "failed to insert media metadata") {
						result.AttachmentErrorsMetadataInsert++
					} else if strings.Contains(errorTextLower, "failed to insert message attachment junction") {
						result.AttachmentErrorsJunctionInsert++
					} else {
						// Unknown database error, default to blob insert
						result.AttachmentErrorsBlobInsert++
					}
				}
			}
		}
		result.Updated = len(toUpdate)
	}

	// Commit transaction
	if err = tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	return result, nil
}

func (s *MessageStorage) GetSubjectFullName(ctx context.Context) (*string, *string) {
	query := `SELECT subject_name, family_name FROM subject_configuration LIMIT 1`
	var subjectName string
	var familyName string
	err := s.db.Pool.QueryRow(ctx, query).Scan(&subjectName, &familyName)
	if err != nil {
		return nil, nil
	}
	return &subjectName, &familyName
}

// batchInsertMessages inserts multiple messages using a single query
func (s *MessageStorage) batchInsertMessages(ctx context.Context, tx pgx.Tx, messages []MessageWithAttachment) ([]int64, error) {
	if len(messages) == 0 {
		return []int64{}, nil
	}

	// Use multi-value INSERT for better performance
	var insertQuery strings.Builder
	insertQuery.WriteString(`INSERT INTO messages (
		chat_session, message_date, delivered_date, read_date, edited_date,
		service, type, sender_id, sender_name, status, replying_to,
		subject, text, is_group_chat, processed, created_at, updated_at
	) VALUES `)

	args := make([]interface{}, 0)
	placeholders := make([]string, 0, len(messages))
	argIndex := 1

	for _, msg := range messages {
		placeholder := fmt.Sprintf("($%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, $%d, NOW(), NOW())",
			argIndex, argIndex+1, argIndex+2, argIndex+3, argIndex+4, argIndex+5, argIndex+6, argIndex+7,
			argIndex+8, argIndex+9, argIndex+10, argIndex+11, argIndex+12, argIndex+13, argIndex+14)
		placeholders = append(placeholders, placeholder)

		args = append(args,
			msg.MessageData.ChatSession,
			msg.MessageData.MessageDate,
			msg.MessageData.DeliveredDate,
			msg.MessageData.ReadDate,
			msg.MessageData.EditedDate,
			msg.MessageData.Service,
			msg.MessageData.Type,
			msg.MessageData.SenderID,
			msg.MessageData.SenderName,
			msg.MessageData.Status,
			msg.MessageData.ReplyingTo,
			msg.MessageData.Subject,
			msg.MessageData.Text,
			msg.MessageData.IsGroupChat,
			false, // processed
		)
		argIndex += 15
	}

	insertQuery.WriteString(strings.Join(placeholders, ", "))
	insertQuery.WriteString(" RETURNING id")

	rows, err := tx.Query(ctx, insertQuery.String(), args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}

	return ids, rows.Err()
}

// batchUpdateMessages updates multiple messages using a single query
func (s *MessageStorage) batchUpdateMessages(ctx context.Context, tx pgx.Tx, updates []struct {
	msg MessageWithAttachment
	id  int64
}) error {
	if len(updates) == 0 {
		return nil
	}

	// Update messages one by one (PostgreSQL doesn't have great multi-row UPDATE syntax)
	// But we do it in a single transaction, so it's still much faster
	updateQuery := `UPDATE messages SET
		delivered_date = $1,
		read_date = $2,
		edited_date = $3,
		service = $4,
		sender_name = $5,
		status = $6,
		replying_to = $7,
		subject = $8,
		text = $9,
		is_group_chat = $10,
		updated_at = NOW()
		WHERE id = $11`

	for _, item := range updates {
		_, err := tx.Exec(ctx, updateQuery,
			item.msg.MessageData.DeliveredDate,
			item.msg.MessageData.ReadDate,
			item.msg.MessageData.EditedDate,
			item.msg.MessageData.Service,
			item.msg.MessageData.SenderName,
			item.msg.MessageData.Status,
			item.msg.MessageData.ReplyingTo,
			item.msg.MessageData.Subject,
			item.msg.MessageData.Text,
			item.msg.MessageData.IsGroupChat,
			item.id,
		)
		if err != nil {
			return fmt.Errorf("failed to update message %d: %w", item.id, err)
		}
	}

	return nil
}
