package whatsappimport

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"

	"whatsapp-import-service/internal/database"
	"whatsapp-import-service/internal/services"
	"whatsapp-import-service/pkg/utils"
)

// Non-group chat notification patterns
var nonGroupChatNotificationPatterns = []string{
	"Messages to this chat and calls are now secured with end-to-end encryption",
	"You started a call",
	"You ended a call",
	"You joined a call",
	"You left a call",
	"You missed a call",
	"You rejected a call",
	"You accepted a call",
	"You declined a call",
	"You blocked a call",
	"changed their phone number to a new number",
	"is a contact",
	"This chat is now end-to-end encrypted",
	"Voice call -",
	"Video call -",
	"Missed video",
	"Missed voice",
	"This chat is with a business account",
	"turned on disappearing messages",
	"This business account has now registered as a standard account",
}

// Pre-compiled regex for string cleaning (compiled once at package level)
var cleanStringRegex = regexp.MustCompile(`[^\w\s]`)

// ImportStats holds statistics about the import process
type ImportStats struct {
	ConversationsProcessed         int        `json:"conversations_processed"`
	TotalConversations             int        `json:"total_conversations"`
	MessagesImported               int        `json:"messages_imported"`
	MessagesUpdated                int        `json:"messages_updated"`
	MessagesCreated                int        `json:"messages_created"`
	Errors                         int        `json:"errors"`
	AttachmentsFound               int        `json:"attachments_found"`
	AttachmentsMissing             int        `json:"attachments_missing"`
	AttachmentErrorsFileNotFound   int        `json:"attachment_errors_file_not_found"`
	AttachmentErrorsFileRead       int        `json:"attachment_errors_file_read"`
	AttachmentErrorsBlobInsert     int        `json:"attachment_errors_blob_insert"`
	AttachmentErrorsMetadataInsert int        `json:"attachment_errors_metadata_insert"`
	AttachmentErrorsJunctionInsert int        `json:"attachment_errors_junction_insert"`
	MissingAttachmentFilenames     []string   `json:"missing_attachment_filenames"`
	AttachmentErrors               []string   `json:"attachment_errors"`
	CurrentConversation            string     `json:"current_conversation,omitempty"`
	mu                             sync.Mutex // Mutex for thread-safe stats updates
}

// copyStats creates a copy of ImportStats without the mutex for safe passing to callbacks
func (s *ImportStats) copyStats() ImportStats {
	s.mu.Lock()
	defer s.mu.Unlock()
	return ImportStats{
		ConversationsProcessed:         s.ConversationsProcessed,
		TotalConversations:             s.TotalConversations,
		MessagesImported:               s.MessagesImported,
		MessagesUpdated:                s.MessagesUpdated,
		MessagesCreated:                s.MessagesCreated,
		Errors:                         s.Errors,
		AttachmentsFound:               s.AttachmentsFound,
		AttachmentsMissing:             s.AttachmentsMissing,
		AttachmentErrorsFileNotFound:   s.AttachmentErrorsFileNotFound,
		AttachmentErrorsFileRead:       s.AttachmentErrorsFileRead,
		AttachmentErrorsBlobInsert:     s.AttachmentErrorsBlobInsert,
		AttachmentErrorsMetadataInsert: s.AttachmentErrorsMetadataInsert,
		AttachmentErrorsJunctionInsert: s.AttachmentErrorsJunctionInsert,
		MissingAttachmentFilenames:     append([]string(nil), s.MissingAttachmentFilenames...),
		AttachmentErrors:               append([]string(nil), s.AttachmentErrors...),
		CurrentConversation:            s.CurrentConversation,
	}
}

// ProgressCallback is called after each conversation is processed
type ProgressCallback func(ImportStats)

// CancelledCheck returns true if the import should be cancelled
type CancelledCheck func() bool

// ImportWhatsAppFromDirectory imports WhatsApp messages from a directory structure
func ImportWhatsAppFromDirectory(ctx context.Context, db *database.DB, directoryPath string, progressCallback ProgressCallback, checkFunc CancelledCheck) (*ImportStats, error) {
	// Set global cancelledCheck for use in processCSVFile
	cancelledCheck = checkFunc
	// Validate directory exists
	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return nil, fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	storage := database.NewMessageStorage(db)
	subjectService := services.NewSubjectConfigurationService(db)

	// Count total conversations
	entries, err := os.ReadDir(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory: %w", err)
	}

	totalConversations := 0
	for _, entry := range entries {
		if entry.IsDir() {
			totalConversations++
		}
	}

	stats := &ImportStats{
		TotalConversations:         totalConversations,
		MissingAttachmentFilenames: []string{},
		AttachmentErrors:           []string{},
	}

	// Get subject configuration
	subjectConfig, err := subjectService.GetConfiguration(ctx)
	if err != nil {
		// Log error but continue
		fmt.Printf("Warning: Could not get subject configuration: %v\n", err)
	}

	// Collect conversation directories
	var conversationDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			conversationDirs = append(conversationDirs, entry.Name())
		}
	}

	// Process conversations in parallel using worker pool
	numWorkers := runtime.NumCPU()
	if numWorkers > len(conversationDirs) {
		numWorkers = len(conversationDirs)
	}
	if numWorkers < 1 {
		numWorkers = 1
	}

	conversationChan := make(chan string, len(conversationDirs))
	var wg sync.WaitGroup

	// Start worker goroutines
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for conversationName := range conversationChan {
				// Check for cancellation
				if cancelledCheck != nil && cancelledCheck() {
					return
				}
				select {
				case <-ctx.Done():
					return
				default:
				}

				// Update current conversation
				stats.mu.Lock()
				stats.ConversationsProcessed++
				stats.CurrentConversation = conversationName
				stats.mu.Unlock()

				subdirPath := filepath.Join(directoryPath, conversationName)

				// Find CSV files in the subdirectory
				csvFiles, err := filepath.Glob(filepath.Join(subdirPath, "*.csv"))
				if err != nil {
					fmt.Printf("Error finding CSV files in %s: %v\n", conversationName, err)
					stats.mu.Lock()
					stats.Errors++
					stats.mu.Unlock()
					continue
				}

				if len(csvFiles) == 0 {
					fmt.Printf("No CSV file found in subdirectory: %s\n", conversationName)
					if progressCallback != nil {
						progressCallback(stats.copyStats())
					}
					continue
				}

				// Process each CSV file sequentially within conversation
				for _, csvFile := range csvFiles {
					// Check for cancellation
					if cancelledCheck != nil && cancelledCheck() {
						return
					}
					select {
					case <-ctx.Done():
						return
					default:
					}

					fmt.Printf("Processing CSV file: %s\n", csvFile)
					err := processCSVFile(ctx, storage, csvFile, conversationName, stats, subjectConfig)
					if err != nil {
						fmt.Printf("Error reading CSV file %s: %v\n", csvFile, err)
						stats.mu.Lock()
						stats.Errors++
						stats.mu.Unlock()
						continue
					}
				}

				// Call progress callback after each conversation is processed
				if progressCallback != nil {
					progressCallback(stats.copyStats())
				}
			}
		}()
	}

	// Send conversations to workers
	for _, conversationName := range conversationDirs {
		conversationChan <- conversationName
	}
	close(conversationChan)

	// Wait for all workers to complete
	wg.Wait()

	// Set is_group_chat flag
	fmt.Println("Setting is_group_chat flag")
	err = storage.SetIsGroupChat(ctx)
	if err != nil {
		fmt.Printf("Warning: Could not set is_group_chat flag: %v\n", err)
	}

	return stats, nil
}

// processCSVFile processes a single CSV file
func processCSVFile(ctx context.Context, storage *database.MessageStorage, csvFilePath, conversationName string, stats *ImportStats, subjectConfig *database.SubjectConfiguration) error {
	file, err := os.Open(csvFilePath)
	if err != nil {
		return fmt.Errorf("failed to open CSV file: %w", err)
	}
	defer file.Close()

	messages, err := ParseCSV(file)
	if err != nil {
		return fmt.Errorf("failed to parse CSV: %w", err)
	}

	csvDir := filepath.Dir(csvFilePath)

	// Process messages in batches for better performance
	const batchSize = 100
	for i := 0; i < len(messages); i += batchSize {
		// Check for cancellation
		if cancelledCheck != nil && cancelledCheck() {
			return ctx.Err()
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		end := i + batchSize
		if end > len(messages) {
			end = len(messages)
		}

		batch := messages[i:end]
		batchResults, err := processMessageBatch(ctx, storage, batch, csvDir, conversationName, stats, subjectConfig)
		if err != nil {
			fmt.Printf("Error processing message batch: %v\n", err)
			stats.mu.Lock()
			stats.Errors += len(batch)
			stats.mu.Unlock()
			continue
		}

		// Update stats
		stats.mu.Lock()
		stats.MessagesImported += batchResults.Created + batchResults.Updated
		stats.MessagesCreated += batchResults.Created
		stats.MessagesUpdated += batchResults.Updated
		stats.Errors += batchResults.Errors
		stats.AttachmentErrorsBlobInsert += batchResults.AttachmentErrorsBlobInsert
		stats.AttachmentErrorsMetadataInsert += batchResults.AttachmentErrorsMetadataInsert
		stats.AttachmentErrorsJunctionInsert += batchResults.AttachmentErrorsJunctionInsert
		stats.mu.Unlock()
	}

	return nil
}

// cancelledCheck is set by ImportWhatsAppFromDirectory
var cancelledCheck CancelledCheck

// processMessageBatch processes a batch of messages and saves them to the database
func processMessageBatch(ctx context.Context, storage *database.MessageStorage, messages []WhatsAppMessage, csvDir, conversationName string, stats *ImportStats, subjectConfig *database.SubjectConfiguration) (*database.BatchSaveResult, error) {
	batchMessages := make([]database.MessageWithAttachment, 0, len(messages))

	for _, msg := range messages {
		// Build message data
		messageData, attachmentData, attachmentFilename, attachmentType := prepareMessageData(msg, csvDir, conversationName, stats)

		batchMessages = append(batchMessages, database.MessageWithAttachment{
			MessageData:        messageData,
			AttachmentData:     attachmentData,
			AttachmentFilename: attachmentFilename,
			AttachmentType:     attachmentType,
			Source:             "WhatsApp",
		})
	}

	// Save batch to database
	return storage.SaveMessagesBatch(ctx, batchMessages)
}

// prepareMessageData prepares message data and reads attachment if present
func prepareMessageData(msg WhatsAppMessage, csvDir, conversationName string, stats *ImportStats) (database.MessageData, []byte, string, string) {
	// Clean chat_session and sender_name using regex
	chatSession := cleanString(msg.ChatSession)
	senderName := cleanString(msg.SenderName)

	// Build message data
	messageData := database.MessageData{
		ChatSession:   stringPtr(chatSession),
		MessageDate:   msg.MessageDate,
		DeliveredDate: msg.SentDate,
		ReadDate:      nil,
		EditedDate:    nil,
		Service:       stringPtr("WhatsApp"),
		Type:          stringPtr(msg.Type),
		SenderID:      stringPtr(msg.SenderID),
		SenderName:    stringPtr(senderName),
		Status:        stringPtr(msg.Status),
		ReplyingTo:    stringPtr(msg.ReplyingTo),
		Subject:       nil,
		Text:          stringPtr(msg.Text),
		IsGroupChat:   false,
	}

	// Check if notification indicates a group chat
	if msg.Type == "Notification" && msg.Text != "" {
		isGroupChat := true
		for _, pattern := range nonGroupChatNotificationPatterns {
			if strings.Contains(msg.Text, pattern) {
				isGroupChat = false
				break
			}
		}
		messageData.IsGroupChat = isGroupChat
	}

	// Handle attachments
	var attachmentData []byte
	attachmentFilename := ""
	attachmentType := ""

	if msg.Attachment != "" {
		attachmentFilename = msg.Attachment
		attachmentType = msg.AttachmentType

		// Find attachment file with fallback
		filePath, actualFilename, err := utils.FindAttachmentFileWithFallback(csvDir, attachmentFilename)
		if err == nil {
			// Read attachment data
			data, err := os.ReadFile(filePath)
			if err == nil {
				attachmentData = data
				stats.mu.Lock()
				stats.AttachmentsFound++
				stats.mu.Unlock()

				// Update filename and type if fallback was used
				if actualFilename != attachmentFilename {
					// fmt.Printf("Info: Found alternative version instead of original: %s -> %s (conversation: %s)\n",
					// 	attachmentFilename, actualFilename, conversationName)
					attachmentFilename = actualFilename
					// Update MIME type based on new extension
					if strings.HasSuffix(strings.ToLower(actualFilename), ".jpg") {
						attachmentType = "image/jpeg"
					} else if strings.HasSuffix(strings.ToLower(actualFilename), ".mp3") {
						attachmentType = "audio/mpeg"
					}
				}

				// Normalize MIME type
				attachmentType = utils.NormalizeMIMEType(attachmentType, attachmentFilename)
			} else {
				// File found but could not be read - get file info for better error reporting
				var fileSize int64 = -1
				if fileInfo, statErr := os.Stat(filePath); statErr == nil {
					fileSize = fileInfo.Size()
				}

				errorMsg := fmt.Sprintf("Conversation: %s | Attachment: %s | File path: %s | Size: %d bytes | Error: %v",
					conversationName, attachmentFilename, filePath, fileSize, err)
				fmt.Printf("Error: Could not read attachment file - %s\n", errorMsg)
				stats.mu.Lock()
				stats.AttachmentErrorsFileRead++
				if !contains(stats.AttachmentErrors, errorMsg) {
					stats.AttachmentErrors = append(stats.AttachmentErrors, errorMsg)
				}
				// Also track as missing for backward compatibility
				missingFilename := fmt.Sprintf("%s/%s", conversationName, attachmentFilename)
				stats.AttachmentsMissing++
				if !contains(stats.MissingAttachmentFilenames, missingFilename) {
					stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingFilename)
				}
				stats.mu.Unlock()
			}
		} else {
			// File not found (even with fallback)
			errorMsg := fmt.Sprintf("Conversation: %s | Attachment: %s | Searched in: %s | Error: %v",
				conversationName, attachmentFilename, csvDir, err)
			fmt.Printf("Warning: Attachment file not found - %s\n", errorMsg)
			stats.mu.Lock()
			stats.AttachmentErrorsFileNotFound++
			stats.AttachmentsMissing++
			missingFilename := fmt.Sprintf("%s/%s", conversationName, attachmentFilename)
			if !contains(stats.MissingAttachmentFilenames, missingFilename) {
				stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingFilename)
			}
			stats.mu.Unlock()
		}
	}

	return messageData, attachmentData, attachmentFilename, attachmentType
}

// processMessage processes a single message
func processMessage(ctx context.Context, storage *database.MessageStorage, msg WhatsAppMessage, csvDir, conversationName string, stats *ImportStats, subjectConfig *database.SubjectConfiguration) error {
	// Clean chat_session and sender_name using regex (remove non-word, non-space characters)
	chatSession := cleanString(msg.ChatSession)
	senderName := cleanString(msg.SenderName)

	// Build message data
	messageData := database.MessageData{
		ChatSession:   stringPtr(chatSession),
		MessageDate:   msg.MessageDate,
		DeliveredDate: msg.SentDate, // WhatsApp Sent Date maps to delivered_date
		ReadDate:      nil,
		EditedDate:    nil,
		Service:       stringPtr("WhatsApp"),
		Type:          stringPtr(msg.Type),
		SenderID:      stringPtr(msg.SenderID),
		SenderName:    stringPtr(senderName),
		Status:        stringPtr(msg.Status),
		ReplyingTo:    stringPtr(msg.ReplyingTo),
		Subject:       nil,
		Text:          stringPtr(msg.Text),
		IsGroupChat:   false,
	}

	// Check if notification indicates a group chat
	if msg.Type == "Notification" && msg.Text != "" {
		isGroupChat := true
		for _, pattern := range nonGroupChatNotificationPatterns {
			if strings.Contains(msg.Text, pattern) {
				isGroupChat = false
				break
			}
		}
		messageData.IsGroupChat = isGroupChat
	}

	// Handle attachments
	var attachmentData []byte
	attachmentFilename := ""
	attachmentType := ""

	if msg.Attachment != "" {
		attachmentFilename = msg.Attachment
		attachmentType = msg.AttachmentType

		// Find attachment file with fallback
		filePath, actualFilename, err := utils.FindAttachmentFileWithFallback(csvDir, attachmentFilename)
		if err == nil {
			// Read attachment data
			data, err := os.ReadFile(filePath)
			if err == nil {
				attachmentData = data
				stats.AttachmentsFound++

				// Update filename and type if fallback was used
				if actualFilename != attachmentFilename {
					fmt.Printf("Found alternative version instead of original: %s -> %s\n", attachmentFilename, actualFilename)
					attachmentFilename = actualFilename
					// Update MIME type based on new extension
					if strings.HasSuffix(strings.ToLower(actualFilename), ".jpg") {
						attachmentType = "image/jpeg"
					} else if strings.HasSuffix(strings.ToLower(actualFilename), ".mp3") {
						attachmentType = "audio/mpeg"
					}
				}

				// Normalize MIME type
				attachmentType = utils.NormalizeMIMEType(attachmentType, attachmentFilename)
			} else {
				missingFilename := fmt.Sprintf("%s/%s", conversationName, attachmentFilename)
				fmt.Printf("Warning: Could not read attachment file %s: %v\n", filePath, err)
				stats.AttachmentsMissing++
				if !contains(stats.MissingAttachmentFilenames, missingFilename) {
					stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingFilename)
				}
			}
		} else {
			missingFilename := fmt.Sprintf("%s/%s", conversationName, attachmentFilename)
			fmt.Printf("Warning: Attachment file not found: %s\n", attachmentFilename)
			stats.AttachmentsMissing++
			if !contains(stats.MissingAttachmentFilenames, missingFilename) {
				stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingFilename)
			}
		}
	}

	// Save message to database
	messageID, isUpdate, err := storage.SaveIMessage(ctx, messageData, attachmentData, attachmentFilename, attachmentType, "WhatsApp")
	if err != nil {
		return fmt.Errorf("failed to save message: %w", err)
	}

	if isUpdate {
		stats.MessagesUpdated++
	} else {
		stats.MessagesCreated++
	}

	stats.MessagesImported++
	_ = messageID // Message ID not used currently

	return nil
}

// cleanString removes non-word, non-space characters from a string
func cleanString(s string) string {
	if s == "" {
		return ""
	}
	return strings.TrimSpace(cleanStringRegex.ReplaceAllString(s, ""))
}

// stringPtr returns a pointer to a string
func stringPtr(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

// contains checks if a string slice contains a value
func contains(slice []string, value string) bool {
	for _, v := range slice {
		if v == value {
			return true
		}
	}
	return false
}
