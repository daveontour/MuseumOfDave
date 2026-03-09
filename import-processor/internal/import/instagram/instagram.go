package instagramimport

import (
	"context"
	"encoding/json"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"import-processor/internal/database"
	"import-processor/internal/services"
)

const instagramService = "Instagram"
const instagramSource = "Instagram"

// ImportStats holds statistics about the import process
type ImportStats struct {
	ConversationsProcessed         int
	TotalConversations             int
	MessagesImported               int
	MessagesUpdated                int
	MessagesCreated                int
	Errors                         int
	AttachmentsFound               int
	AttachmentsMissing             int
	AttachmentErrorsBlobInsert     int
	AttachmentErrorsMetadataInsert int
	AttachmentErrorsJunctionInsert int
	MissingAttachmentFilenames     []string
	AttachmentErrors               []string
	CurrentConversation            string
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

// findConversationDirs walks the directory tree and returns relative paths (from rootPath)
// of all directories that directly contain message_*.json files.
func findConversationDirs(rootPath string) ([]string, error) {
	rootAbs, err := filepath.Abs(rootPath)
	if err != nil {
		return nil, err
	}
	var dirs []string
	err = filepath.WalkDir(rootAbs, func(path string, d fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return nil
		}
		if !d.IsDir() {
			return nil
		}
		entries, err := os.ReadDir(path)
		if err != nil {
			return nil
		}
		hasMessageJSON := false
		for _, e := range entries {
			if !e.IsDir() && strings.HasPrefix(e.Name(), "message_") && strings.HasSuffix(e.Name(), ".json") {
				hasMessageJSON = true
				break
			}
		}
		if hasMessageJSON {
			rel, err := filepath.Rel(rootAbs, path)
			if err != nil {
				return nil
			}
			dirs = append(dirs, rel)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(dirs)
	return dirs, nil
}

// ImportInstagramFromDirectory imports Instagram messages from a directory structure.
// Each subdirectory is a conversation containing message_1.json, message_2.json, etc.
func ImportInstagramFromDirectory(
	ctx context.Context,
	db *database.DB,
	directoryPath string,
	progressCallback ProgressCallback,
	cancelledCheck CancelledCheck,
	exportRootOverride string,
	userName string,
) (*ImportStats, error) {
	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return nil, fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	storage := database.NewMessageStorage(db)
	subjectService := services.NewSubjectConfigurationService(db)

	conversationDirs, err := findConversationDirs(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to find conversation directories: %w", err)
	}

	stats := &ImportStats{
		TotalConversations:         len(conversationDirs),
		MissingAttachmentFilenames: []string{},
		AttachmentErrors:           []string{},
	}

	_, _ = subjectService.GetConfiguration(ctx)
	if userName == "" {
		subjectFullName, _ := subjectService.GetSubjectFullName(ctx)
		if subjectFullName != nil && *subjectFullName != "" {
			userName = *subjectFullName
		}
	}

	exportRoot := exportRootOverride
	if exportRoot == "" {
		if root, ok := DetectInstagramExportRoot(directoryPath, ""); ok {
			exportRoot = root
			fmt.Fprintf(os.Stderr, "Auto-detected Instagram export root: %s\n", exportRoot)
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
				if cancelledCheck != nil && cancelledCheck() {
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

				jsonFiles, err := filepath.Glob(filepath.Join(subdirPath, "message_*.json"))
				if err != nil {
					fmt.Fprintf(os.Stderr, "Error finding JSON files in %s: %v\n", conversationName, err)
					stats.mu.Lock()
					stats.Errors++
					stats.mu.Unlock()
					continue
				}

				if len(jsonFiles) == 0 {
					if progressCallback != nil {
						progressCallback(stats.copyStats())
					}
					continue
				}

				sort.Slice(jsonFiles, func(i, j int) bool {
					return extractMessageNumber(jsonFiles[i]) < extractMessageNumber(jsonFiles[j])
				})

				for _, jsonFile := range jsonFiles {
					if cancelledCheck != nil && cancelledCheck() {
						return
					}
					select {
					case <-ctx.Done():
						return
					default:
					}

					err := processInstagramJSONFile(ctx, storage, jsonFile, subdirPath, conversationName, stats, userName, exportRoot, cancelledCheck)
					if err != nil {
						fmt.Fprintf(os.Stderr, "Error processing JSON file %s: %v\n", jsonFile, err)
						stats.mu.Lock()
						stats.Errors++
						stats.mu.Unlock()
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

// ListFilesToProcess lists JSON files that would be processed
func ListFilesToProcess(directoryPath string) error {
	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	conversationDirs, err := findConversationDirs(directoryPath)
	if err != nil {
		return fmt.Errorf("failed to find conversation directories: %w", err)
	}

	fmt.Printf("\nFound %d conversation directory(ies)\n\n", len(conversationDirs))

	var totalJSON int
	for _, name := range conversationDirs {
		subdirPath := filepath.Join(directoryPath, name)
		jsonFiles, _ := filepath.Glob(filepath.Join(subdirPath, "message_*.json"))
		sort.Slice(jsonFiles, func(i, j int) bool {
			return extractMessageNumber(jsonFiles[i]) < extractMessageNumber(jsonFiles[j])
		})

		if len(jsonFiles) == 0 {
			fmt.Printf("Conversation: %s\n  No JSON files found\n\n", name)
			continue
		}

		fmt.Printf("Conversation: %s\n  JSON files (%d):\n", name, len(jsonFiles))
		for _, jf := range jsonFiles {
			rel, _ := filepath.Rel(directoryPath, jf)
			fmt.Printf("    - %s\n", rel)
		}
		fmt.Println()
		totalJSON += len(jsonFiles)
	}

	fmt.Printf("Total: %d conversation(s), %d JSON file(s)\n", len(conversationDirs), totalJSON)
	return nil
}

func extractMessageNumber(path string) int {
	base := filepath.Base(path)
	base = strings.TrimSuffix(base, filepath.Ext(base))
	parts := strings.Split(base, "_")
	if len(parts) >= 2 {
		var n int
		fmt.Sscanf(parts[1], "%d", &n)
		return n
	}
	return 0
}

func processInstagramJSONFile(ctx context.Context, storage *database.MessageStorage, jsonFilePath, subdirPath, conversationName string, stats *ImportStats, userName, exportRoot string, cancelledCheck CancelledCheck) error {
	data, err := os.ReadFile(jsonFilePath)
	if err != nil {
		return fmt.Errorf("failed to read JSON file: %w", err)
	}

	export := &InstagramExport{}
	if err := json.Unmarshal(data, export); err != nil {
		return fmt.Errorf("failed to parse JSON: %w", err)
	}

	chatSession := export.Title
	if chatSession == "" {
		chatSession = conversationName
	}
	chatSession = CleanString(chatSession)
	participants := export.Participants

	const batchSize = 100
	var batch []database.MessageWithAttachment

	for _, msg := range export.Messages {
		if cancelledCheck != nil && cancelledCheck() {
			return context.Canceled
		}

		// Skip messages with no content and no photos (reactions/shares ignored)
		if msg.Content == "" && len(msg.Photos) == 0 {
			continue
		}

		messageDate, err := ParseTimestampMs(msg.TimestampMs)
		if err != nil || messageDate == nil {
			continue
		}

		msgType := DetermineMessageType(msg.SenderName, userName, participants)
		senderName := CleanString(msg.SenderName)
		if senderName == "" {
			continue
		}

		var text *string
		if msg.Content != "" {
			t := msg.Content
			text = &t
		}

		status := "Sent"
		if msgType == "Incoming" {
			status = "Received"
		}

		baseData := database.MessageData{
			ChatSession:   &chatSession,
			MessageDate:   messageDate,
			DeliveredDate: messageDate,
			ReadDate:      nil,
			EditedDate:    nil,
			Service:       strPtr(instagramService),
			Type:          &msgType,
			SenderID:      &senderName,
			SenderName:    &senderName,
			Status:        &status,
			ReplyingTo:    nil,
			Subject:       nil,
			IsGroupChat:   false,
		}

		if len(msg.Photos) > 0 {
			// Each photo is a separate message
			for idx, photo := range msg.Photos {
				if cancelledCheck != nil && cancelledCheck() {
					return context.Canceled
				}

				photoPath, ok := FindPhotoFile(subdirPath, photo.URI, exportRoot)
				var attachmentData []byte
				var attachmentFilename, attachmentType string

				if ok {
					attachmentData, _ = os.ReadFile(photoPath)
					attachmentFilename = filepath.Base(photoPath)
					attachmentType = GuessMIMEType(attachmentFilename)
					if attachmentType == "" {
						attachmentType = "image/jpeg"
					}
				}

				stats.mu.Lock()
				if len(attachmentData) > 0 {
					stats.AttachmentsFound++
				} else if photo.URI != "" {
					stats.AttachmentsMissing++
					missingKey := conversationName + "/" + FilenameFromURI(photo.URI)
					if !contains(stats.MissingAttachmentFilenames, missingKey) {
						stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingKey)
					}
				}
				stats.mu.Unlock()

				// Skip if no attachment and we expected one
				if len(attachmentData) == 0 && photo.URI != "" {
					continue
				}

				// Slightly adjust message_date for each photo to keep them distinct
				adjDate := messageDate.Add(time.Duration(idx) * time.Millisecond)

				batch = append(batch, database.MessageWithAttachment{
					MessageData: database.MessageData{
						ChatSession:   baseData.ChatSession,
						MessageDate:   &adjDate,
						DeliveredDate: &adjDate,
						ReadDate:      baseData.ReadDate,
						EditedDate:    baseData.EditedDate,
						Service:       baseData.Service,
						Type:          baseData.Type,
						SenderID:      baseData.SenderID,
						SenderName:    baseData.SenderName,
						Status:        baseData.Status,
						ReplyingTo:    baseData.ReplyingTo,
						Subject:       baseData.Subject,
						Text:          text,
						IsGroupChat:   baseData.IsGroupChat,
					},
					AttachmentData:     attachmentData,
					AttachmentFilename: attachmentFilename,
					AttachmentType:     attachmentType,
					Source:             instagramSource,
				})

				if len(batch) >= batchSize {
					flushBatch(ctx, storage, batch, stats)
					batch = batch[:0]
				}
			}
		} else {
			// Message without attachment
			batch = append(batch, database.MessageWithAttachment{
				MessageData: database.MessageData{
					ChatSession:   baseData.ChatSession,
					MessageDate:   baseData.MessageDate,
					DeliveredDate: baseData.DeliveredDate,
					ReadDate:      baseData.ReadDate,
					EditedDate:    baseData.EditedDate,
					Service:       baseData.Service,
					Type:          baseData.Type,
					SenderID:      baseData.SenderID,
					SenderName:    baseData.SenderName,
					Status:        baseData.Status,
					ReplyingTo:    baseData.ReplyingTo,
					Subject:       baseData.Subject,
					Text:          text,
					IsGroupChat:   baseData.IsGroupChat,
				},
				AttachmentData:     nil,
				AttachmentFilename: "",
				AttachmentType:     "",
				Source:             instagramSource,
			})

			if len(batch) >= batchSize {
				flushBatch(ctx, storage, batch, stats)
				batch = batch[:0]
			}
		}
	}

	if len(batch) > 0 {
		flushBatch(ctx, storage, batch, stats)
	}

	return nil
}

func contains(slice []string, s string) bool {
	for _, v := range slice {
		if v == s {
			return true
		}
	}
	return false
}

func strPtr(s string) *string {
	return &s
}

func flushBatch(ctx context.Context, storage *database.MessageStorage, batch []database.MessageWithAttachment, stats *ImportStats) {
	result, err := storage.SaveMessagesBatch(ctx, batch)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error saving message batch: %v\n", err)
		stats.mu.Lock()
		stats.Errors += len(batch)
		stats.mu.Unlock()
		return
	}
	stats.mu.Lock()
	stats.MessagesImported += result.Created + result.Updated
	stats.MessagesCreated += result.Created
	stats.MessagesUpdated += result.Updated
	stats.Errors += result.Errors
	stats.AttachmentErrorsBlobInsert += result.AttachmentErrorsBlobInsert
	stats.AttachmentErrorsMetadataInsert += result.AttachmentErrorsMetadataInsert
	stats.AttachmentErrorsJunctionInsert += result.AttachmentErrorsJunctionInsert
	stats.mu.Unlock()
}
