package imessageimport

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"

	"import-processor/internal/database"
	"import-processor/internal/services"
	"import-processor/pkg/utils"
)

var cleanStringRegex = regexp.MustCompile(`[^\w\s]`)

// ImportStats holds statistics about the import process
type ImportStats struct {
	ConversationsProcessed         int      `json:"conversations_processed"`
	TotalConversations             int      `json:"total_conversations"`
	MessagesImported               int      `json:"messages_imported"`
	MessagesUpdated                int      `json:"messages_updated"`
	MessagesCreated                int      `json:"messages_created"`
	Errors                         int      `json:"errors"`
	AttachmentsFound               int      `json:"attachments_found"`
	AttachmentsMissing             int      `json:"attachments_missing"`
	AttachmentErrorsFileNotFound   int      `json:"attachment_errors_file_not_found"`
	AttachmentErrorsFileRead       int      `json:"attachment_errors_file_read"`
	AttachmentErrorsBlobInsert     int      `json:"attachment_errors_blob_insert"`
	AttachmentErrorsMetadataInsert int      `json:"attachment_errors_metadata_insert"`
	AttachmentErrorsJunctionInsert int      `json:"attachment_errors_junction_insert"`
	MissingAttachmentFilenames     []string `json:"missing_attachment_filenames"`
	AttachmentErrors               []string `json:"attachment_errors"`
	CurrentConversation            string   `json:"current_conversation,omitempty"`
	mu                             sync.Mutex
}

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

var imessageCancelledCheck CancelledCheck

// ImportIMessagesFromDirectory imports iMessage conversations from a directory structure
func ImportIMessagesFromDirectory(ctx context.Context, db *database.DB, directoryPath string, progressCallback ProgressCallback, checkFunc CancelledCheck) (*ImportStats, error) {
	imessageCancelledCheck = checkFunc

	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return nil, fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	storage := database.NewMessageStorage(db)
	subjectService := services.NewSubjectConfigurationService(db)

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

	_, err = subjectService.GetConfiguration(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Could not get subject configuration: %v\n", err)
	}

	subjectFullName, _ := subjectService.GetSubjectFullName(ctx)

	var conversationDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			conversationDirs = append(conversationDirs, entry.Name())
		}
	}

	numWorkers := runtime.NumCPU()
	if numWorkers > len(conversationDirs) {
		numWorkers = len(conversationDirs)
	}
	if numWorkers < 1 {
		numWorkers = 1
	}

	conversationChan := make(chan string, len(conversationDirs))
	var wg sync.WaitGroup

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for conversationName := range conversationChan {
				if imessageCancelledCheck != nil && imessageCancelledCheck() {
					return
				}
				select {
				case <-ctx.Done():
					return
				default:
				}

				stats.mu.Lock()
				stats.ConversationsProcessed++
				stats.CurrentConversation = conversationName
				stats.mu.Unlock()

				subdirPath := filepath.Join(directoryPath, conversationName)

				csvFiles, err := filepath.Glob(filepath.Join(subdirPath, "*.csv"))
				if err != nil {
					fmt.Fprintf(os.Stderr, "Error finding CSV files in %s: %v\n", conversationName, err)
					stats.mu.Lock()
					stats.Errors++
					stats.mu.Unlock()
					continue
				}

				if len(csvFiles) == 0 {
					fmt.Fprintf(os.Stderr, "No CSV file found in subdirectory: %s\n", conversationName)
					if progressCallback != nil {
						progressCallback(stats.copyStats())
					}
					continue
				}

				for _, csvFile := range csvFiles {
					if imessageCancelledCheck != nil && imessageCancelledCheck() {
						return
					}
					select {
					case <-ctx.Done():
						return
					default:
					}

					fmt.Fprintf(os.Stderr, "Processing CSV file: %s\n", csvFile)
					err := processIMessageCSVFile(ctx, storage, csvFile, conversationName, stats, subjectFullName)
					if err != nil {
						fmt.Fprintf(os.Stderr, "Error reading CSV file %s: %v\n", csvFile, err)
						stats.mu.Lock()
						stats.Errors++
						stats.mu.Unlock()
						continue
					}
				}

				if progressCallback != nil {
					progressCallback(stats.copyStats())
				}
			}
		}()
	}

	for _, conversationName := range conversationDirs {
		conversationChan <- conversationName
	}
	close(conversationChan)

	wg.Wait()

	return stats, nil
}

func processIMessageCSVFile(ctx context.Context, storage *database.MessageStorage, csvFilePath, conversationName string, stats *ImportStats, subjectFullName *string) error {
	file, err := os.Open(csvFilePath)
	if err != nil {
		return fmt.Errorf("failed to open CSV file: %w", err)
	}
	defer file.Close()

	messages, err := ParseIMessageCSV(file)
	if err != nil {
		return fmt.Errorf("failed to parse CSV: %w", err)
	}

	csvDir := filepath.Dir(csvFilePath)

	const batchSize = 100
	for i := 0; i < len(messages); i += batchSize {
		if imessageCancelledCheck != nil && imessageCancelledCheck() {
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
		batchResults, err := processIMessageBatch(ctx, storage, batch, csvDir, conversationName, stats, subjectFullName)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error processing message batch: %v\n", err)
			stats.mu.Lock()
			stats.Errors += len(batch)
			stats.mu.Unlock()
			continue
		}

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

func processIMessageBatch(ctx context.Context, storage *database.MessageStorage, messages []IMessageMessage, csvDir, conversationName string, stats *ImportStats, subjectFullName *string) (*database.BatchSaveResult, error) {
	batchMessages := make([]database.MessageWithAttachment, 0, len(messages))

	for _, msg := range messages {
		messageData, attachmentData, attachmentFilename, attachmentType := prepareIMessageData(msg, csvDir, conversationName, stats, subjectFullName)

		batchMessages = append(batchMessages, database.MessageWithAttachment{
			MessageData:        messageData,
			AttachmentData:     attachmentData,
			AttachmentFilename: attachmentFilename,
			AttachmentType:     attachmentType,
			Source:             "iMessage",
		})
	}

	return storage.SaveMessagesBatch(ctx, batchMessages)
}

func prepareIMessageData(msg IMessageMessage, csvDir, conversationName string, stats *ImportStats, subjectFullName *string) (database.MessageData, []byte, string, string) {
	chatSession := cleanString(msg.ChatSession)
	senderName := cleanString(msg.SenderName)

	// Outgoing messages with empty sender_name: use subject_full_name
	if msg.Type == "Outgoing" && senderName == "" && subjectFullName != nil && *subjectFullName != "" {
		senderName = *subjectFullName
	}

	service := msg.Service
	if service == "" {
		service = "iMessage"
	}

	messageData := database.MessageData{
		ChatSession:   stringPtr(chatSession),
		MessageDate:   msg.MessageDate,
		DeliveredDate: msg.DeliveredDate,
		ReadDate:      msg.ReadDate,
		EditedDate:    msg.EditedDate,
		Service:       stringPtr(service),
		Type:          stringPtr(msg.Type),
		SenderID:      stringPtr(msg.SenderID),
		SenderName:    stringPtr(senderName),
		Status:        stringPtr(msg.Status),
		ReplyingTo:    stringPtr(msg.ReplyingTo),
		Subject:       stringPtr(msg.Subject),
		Text:          stringPtr(msg.Text),
		IsGroupChat:   false,
	}

	var attachmentData []byte
	attachmentFilename := ""
	attachmentType := ""

	if msg.Attachment != "" {
		attachmentFilename = msg.Attachment
		attachmentType = msg.AttachmentType

		filePath, actualFilename, err := utils.FindAttachmentFileWithFallback(csvDir, attachmentFilename)
		if err == nil {
			data, err := os.ReadFile(filePath)
			if err == nil {
				attachmentData = data
				stats.mu.Lock()
				stats.AttachmentsFound++
				stats.mu.Unlock()

				if actualFilename != attachmentFilename {
					attachmentFilename = actualFilename
					if strings.HasSuffix(strings.ToLower(actualFilename), ".jpg") {
						attachmentType = "image/jpeg"
					} else if strings.HasSuffix(strings.ToLower(actualFilename), ".mp3") {
						attachmentType = "audio/mpeg"
					}
				}

				attachmentType = utils.NormalizeMIMEType(attachmentType, attachmentFilename)
			} else {
				var fileSize int64 = -1
				if fileInfo, statErr := os.Stat(filePath); statErr == nil {
					fileSize = fileInfo.Size()
				}
				errorMsg := fmt.Sprintf("Conversation: %s | Attachment: %s | File path: %s | Size: %d bytes | Error: %v",
					conversationName, attachmentFilename, filePath, fileSize, err)
				fmt.Fprintf(os.Stderr, "Error: Could not read attachment file - %s\n", errorMsg)
				stats.mu.Lock()
				stats.AttachmentErrorsFileRead++
				if !contains(stats.AttachmentErrors, errorMsg) {
					stats.AttachmentErrors = append(stats.AttachmentErrors, errorMsg)
				}
				missingFilename := fmt.Sprintf("%s/%s", conversationName, attachmentFilename)
				stats.AttachmentsMissing++
				if !contains(stats.MissingAttachmentFilenames, missingFilename) {
					stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingFilename)
				}
				stats.mu.Unlock()
			}
		} else {
			errorMsg := fmt.Sprintf("Conversation: %s | Attachment: %s | Searched in: %s | Error: %v",
				conversationName, attachmentFilename, csvDir, err)
			fmt.Fprintf(os.Stderr, "Warning: Attachment file not found - %s\n", errorMsg)
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

func cleanString(s string) string {
	if s == "" {
		return ""
	}
	return strings.TrimSpace(cleanStringRegex.ReplaceAllString(s, ""))
}

func stringPtr(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

func contains(slice []string, value string) bool {
	for _, v := range slice {
		if v == value {
			return true
		}
	}
	return false
}
