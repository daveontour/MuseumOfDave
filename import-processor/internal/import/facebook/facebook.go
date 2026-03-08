package facebookimport

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

const facebookService = "Facebook Messenger"
const facebookSource = "Facebook"

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
	AttachmentErrorsFileNotFound   int
	AttachmentErrorsFileRead       int
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

// ImportFacebookFromDirectory imports Facebook Messenger messages from a directory structure.
// Each subdirectory is a conversation containing message_1.json, message_2.json, etc.
func ImportFacebookFromDirectory(
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

	convDirs, err := findConversationDirsRecursive(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to walk directory: %w", err)
	}

	var conversationPaths []string
	for dir := range convDirs {
		conversationPaths = append(conversationPaths, dir)
	}
	sort.Strings(conversationPaths)

	stats := &ImportStats{
		TotalConversations:         len(conversationPaths),
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
		if root, ok := DetectFacebookExportRoot(directoryPath, ""); ok {
			exportRoot = root
			fmt.Fprintf(os.Stderr, "Auto-detected Facebook export root: %s\n", exportRoot)
		}
	}

	numWorkers := runtime.NumCPU()
	if numWorkers > len(conversationPaths) {
		numWorkers = len(conversationPaths)
	}
	if numWorkers < 1 {
		numWorkers = 1
	}

	type conversationWork struct {
		subdirPath       string
		conversationName string
		jsonFiles        []string
	}
	conversationChan := make(chan conversationWork, len(conversationPaths))
	var wg sync.WaitGroup

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for work := range conversationChan {
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
				stats.CurrentConversation = work.conversationName
				stats.mu.Unlock()

				subdirPath := work.subdirPath
				conversationName := work.conversationName
				jsonFiles := work.jsonFiles

				if len(jsonFiles) == 0 {
					if progressCallback != nil {
						progressCallback(stats.copyStats())
					}
					continue
				}

				// Sort by message number
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

					err := processFacebookJSONFile(ctx, storage, jsonFile, subdirPath, conversationName, stats, userName, exportRoot, cancelledCheck)
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

	for _, subdirPath := range conversationPaths {
		jsonFiles := convDirs[subdirPath]
		relName, _ := filepath.Rel(directoryPath, subdirPath)
		if relName == "." {
			relName = filepath.Base(subdirPath)
		}
		conversationChan <- conversationWork{subdirPath: subdirPath, conversationName: relName, jsonFiles: jsonFiles}
	}
	close(conversationChan)
	wg.Wait()

	// Set is_group_chat flag
	fmt.Fprintln(os.Stderr, "Setting is_group_chat flag")
	if err := storage.SetIsGroupChat(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Could not set is_group_chat flag: %v\n", err)
	}

	// Delete orphan Facebook conversations (< 2 messages)
	if err := storage.DeleteOrphanFacebookConversations(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Could not delete orphan conversations: %v\n", err)
	}

	return stats, nil
}

// findConversationDirsRecursive walks directoryPath recursively and returns a map of
// conversation directory paths (absolute) to their message_*.json file paths.
func findConversationDirsRecursive(directoryPath string) (map[string][]string, error) {
	convDirs := make(map[string][]string)
	err := filepath.WalkDir(directoryPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		name := d.Name()
		if strings.HasPrefix(name, "message_") && strings.HasSuffix(name, ".json") {
			dir := filepath.Dir(path)
			convDirs[dir] = append(convDirs[dir], path)
		}
		return nil
	})
	if err != nil {
		return nil, err
	}
	return convDirs, nil
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

	convDirs, err := findConversationDirsRecursive(directoryPath)
	if err != nil {
		return fmt.Errorf("failed to walk directory: %w", err)
	}

	var conversationPaths []string
	for dir := range convDirs {
		conversationPaths = append(conversationPaths, dir)
	}
	sort.Strings(conversationPaths)

	fmt.Printf("\nFound %d conversation directory(ies)\n\n", len(conversationPaths))

	var totalJSON int
	for _, subdirPath := range conversationPaths {
		jsonFiles := convDirs[subdirPath]
		sort.Slice(jsonFiles, func(i, j int) bool {
			return extractMessageNumber(jsonFiles[i]) < extractMessageNumber(jsonFiles[j])
		})

		relName, _ := filepath.Rel(directoryPath, subdirPath)
		if relName == "." {
			relName = filepath.Base(subdirPath)
		}

		// fmt.Printf("Conversation: %s\n  JSON files (%d):\n", relName, len(jsonFiles))
		for _, jf := range jsonFiles {
			rel, _ := filepath.Rel(directoryPath, jf)
			// fmt.Printf("    - %s\n", rel)
			fmt.Printf("Process File: %s\n", rel)
		}
		fmt.Println()
		totalJSON += len(jsonFiles)
	}

	fmt.Printf("Total: %d conversation(s), %d JSON file(s)\n", len(conversationPaths), totalJSON)
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

func processFacebookJSONFile(ctx context.Context, storage *database.MessageStorage, jsonFilePath, subdirPath, conversationName string, stats *ImportStats, userName, exportRoot string, cancelledCheck CancelledCheck) error {
	data, err := os.ReadFile(jsonFilePath)
	if err != nil {
		return fmt.Errorf("failed to read JSON file: %w", err)
	}

	export := &FacebookExport{}
	if err := parseFacebookJSON(data, export); err != nil {
		return fmt.Errorf("failed to parse JSON: %w", err)
	}

	chatSession := export.Title
	if chatSession == "" {
		chatSession = conversationName
	}
	participants := export.Participants

	const batchSize = 100
	var batch []database.MessageWithAttachment

	for _, msg := range export.Messages {
		if cancelledCheck != nil && cancelledCheck() {
			return context.Canceled
		}

		// Skip sticker-only messages
		if msg.Sticker != nil && msg.Content == "" && len(msg.Photos) == 0 && len(msg.Videos) == 0 && len(msg.Files) == 0 {
			continue
		}

		messageDate, err := ParseTimestampMs(msg.TimestampMs)
		if err != nil || messageDate == nil {
			continue
		}

		msgType := DetermineMessageType(msg.SenderName, userName, participants)
		var text *string
		if msg.Content != "" {
			text = &msg.Content
		}
		subject := ExtractSubject(msg.Share)

		attachmentFilename, attachmentType, attachmentData, additionalAttachments := GetFirstAttachment(msg, subdirPath, exportRoot)

		stats.mu.Lock()
		if len(attachmentData) > 0 {
			stats.AttachmentsFound++
		} else if attachmentFilename != "" {
			stats.AttachmentsMissing++
			missingKey := conversationName + "/" + attachmentFilename
			if !contains(stats.MissingAttachmentFilenames, missingKey) {
				stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingKey)
			}
		}
		stats.mu.Unlock()

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
			Service:       strPtr(facebookService),
			Type:          &msgType,
			SenderID:      &msg.SenderName,
			SenderName:    &msg.SenderName,
			Status:        &status,
			ReplyingTo:    nil,
			Subject:       subject,
			IsGroupChat:   false,
		}

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
			AttachmentData:     attachmentData,
			AttachmentFilename: attachmentFilename,
			AttachmentType:     attachmentType,
			Source:             facebookSource,
		})

		// Flush batch
		if len(batch) >= batchSize {
			flushBatch(ctx, storage, batch, stats)
			batch = batch[:0]
		}

		// Additional attachments as separate messages
		for idx, addAtt := range additionalAttachments {
			stats.mu.Lock()
			if len(addAtt.Data) > 0 {
				stats.AttachmentsFound++
			} else {
				stats.AttachmentsMissing++
				missingKey := conversationName + "/" + addAtt.Filename
				if !contains(stats.MissingAttachmentFilenames, missingKey) {
					stats.MissingAttachmentFilenames = append(stats.MissingAttachmentFilenames, missingKey)
				}
			}
			stats.mu.Unlock()

			adjDate := messageDate.Add(time.Duration(idx+1) * time.Millisecond)
			batch = append(batch, database.MessageWithAttachment{
				MessageData: database.MessageData{
					ChatSession:   baseData.ChatSession,
					MessageDate:   &adjDate,
					DeliveredDate: &adjDate,
					ReadDate:      nil,
					EditedDate:    nil,
					Service:       baseData.Service,
					Type:          baseData.Type,
					SenderID:      baseData.SenderID,
					SenderName:    baseData.SenderName,
					Status:        baseData.Status,
					ReplyingTo:    baseData.ReplyingTo,
					Subject:       baseData.Subject,
					Text:          nil,
					IsGroupChat:   baseData.IsGroupChat,
				},
				AttachmentData:     addAtt.Data,
				AttachmentFilename: addAtt.Filename,
				AttachmentType:     addAtt.Type,
				Source:             facebookSource,
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

func parseFacebookJSON(data []byte, export *FacebookExport) error {
	return json.Unmarshal(data, export)
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
