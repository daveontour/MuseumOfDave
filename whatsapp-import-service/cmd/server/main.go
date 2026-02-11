package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"syscall"

	"whatsapp-import-service/internal/config"
	"whatsapp-import-service/internal/database"
	whatsappimport "whatsapp-import-service/internal/import"
)

func main() {
	// Parse command line flags
	listFiles := flag.Bool("list", false, "List all files that would be processed without importing")
	flag.Parse()

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// If list flag is set, list files and exit
	if *listFiles {
		if err := listFilesToProcess(cfg.DirectoryPath); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	// Initialize database connection
	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Println("Database connection established successfully")
	fmt.Printf("Starting WhatsApp import from: %s\n", cfg.DirectoryPath)

	// Create context with cancellation support
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Set up signal handling for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Track cancellation
	cancelled := false
	var cancelMutex sync.Mutex

	// Start goroutine to handle signals
	go func() {
		<-sigChan
		fmt.Println("\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	// Progress callback function
	progressCallback := func(stats whatsappimport.ImportStats) {
		if stats.TotalConversations > 0 {
			fmt.Printf("\rProcessing conversation %d of %d: %s | Messages: %d (%d created, %d updated) | Attachments: %d found, %d missing | Errors: %d",
				stats.ConversationsProcessed,
				stats.TotalConversations,
				stats.CurrentConversation,
				stats.MessagesImported,
				stats.MessagesCreated,
				stats.MessagesUpdated,
				stats.AttachmentsFound,
				stats.AttachmentsMissing,
				stats.Errors,
			)
		}
	}

	// Cancellation check function
	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	// Run the import
	stats, err := whatsappimport.ImportWhatsAppFromDirectory(
		ctx,
		db,
		cfg.DirectoryPath,
		progressCallback,
		cancelledCheck,
	)

	// Print final newline after progress updates
	fmt.Println()

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Println("Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	// Print final statistics
	fmt.Println("\nImport completed successfully")
	fmt.Printf("Processed %d conversation(s)\n", stats.ConversationsProcessed)
	fmt.Printf("Imported %d message(s) (%d created, %d updated)\n",
		stats.MessagesImported,
		stats.MessagesCreated,
		stats.MessagesUpdated)
	fmt.Printf("Found %d attachment(s), %d missing\n", stats.AttachmentsFound, stats.AttachmentsMissing)
	if stats.AttachmentErrorsFileNotFound > 0 || stats.AttachmentErrorsFileRead > 0 ||
		stats.AttachmentErrorsBlobInsert > 0 || stats.AttachmentErrorsMetadataInsert > 0 ||
		stats.AttachmentErrorsJunctionInsert > 0 {
		fmt.Printf("Attachment errors: %d file not found, %d file read errors, %d blob insert errors, %d metadata insert errors, %d junction insert errors\n",
			stats.AttachmentErrorsFileNotFound,
			stats.AttachmentErrorsFileRead,
			stats.AttachmentErrorsBlobInsert,
			stats.AttachmentErrorsMetadataInsert,
			stats.AttachmentErrorsJunctionInsert)
	}
	if stats.Errors > 0 {
		fmt.Printf("Skipped invalid messages (missing required fields): %d\n", stats.Errors)
		fmt.Printf("Note: These are messages with empty ChatSession, Type, SenderID, or MessageDate that were skipped, not processing errors.\n")
	}

	if len(stats.MissingAttachmentFilenames) > 0 {
		fmt.Println("\nMissing attachment files:")
		for _, filename := range stats.MissingAttachmentFilenames {
			fmt.Printf("  - %s\n", filename)
		}
	}

	if len(stats.AttachmentErrors) > 0 {
		fmt.Println("\nAttachment processing errors:")
		for _, errorMsg := range stats.AttachmentErrors {
			fmt.Printf("  - %s\n", errorMsg)
		}
	}
}

// listFilesToProcess scans the directory and lists all CSV files that would be processed
func listFilesToProcess(directoryPath string) error {
	fmt.Printf("Scanning directory: %s\n", directoryPath)
	fmt.Println(strings.Repeat("=", 60))

	// Validate directory exists
	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	// Read directory entries
	entries, err := os.ReadDir(directoryPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	// Collect conversation directories
	var conversationDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			conversationDirs = append(conversationDirs, entry.Name())
		}
	}

	// Sort for consistent output
	sort.Strings(conversationDirs)

	fmt.Printf("\nFound %d conversation directory(ies)\n\n", len(conversationDirs))

	var totalCSVFiles int
	var allCSVFiles []string

	// Scan each conversation directory for CSV files
	for _, conversationName := range conversationDirs {
		subdirPath := filepath.Join(directoryPath, conversationName)

		// Find CSV files in the subdirectory
		csvFiles, err := filepath.Glob(filepath.Join(subdirPath, "*.csv"))
		if err != nil {
			fmt.Printf("Error finding CSV files in %s: %v\n", conversationName, err)
			continue
		}

		if len(csvFiles) == 0 {
			fmt.Printf("Conversation: %s\n", conversationName)
			fmt.Printf("  No CSV files found\n\n")
			continue
		}

		// Sort CSV files for consistent output
		sort.Strings(csvFiles)

		fmt.Printf("Conversation: %s\n", conversationName)
		fmt.Printf("  CSV files (%d):\n", len(csvFiles))
		for _, csvFile := range csvFiles {
			// Get relative path for cleaner output
			relPath, err := filepath.Rel(directoryPath, csvFile)
			if err != nil {
				relPath = csvFile
			}
			fmt.Printf("    - %s\n", relPath)
			allCSVFiles = append(allCSVFiles, csvFile)
		}
		fmt.Println()

		totalCSVFiles += len(csvFiles)
	}

	// Summary
	fmt.Println(strings.Repeat("=", 60))
	fmt.Printf("\nSummary:\n")
	fmt.Printf("  Total conversations: %d\n", len(conversationDirs))
	fmt.Printf("  Total CSV files: %d\n", totalCSVFiles)

	if totalCSVFiles == 0 {
		fmt.Println("\nNo CSV files found to process.")
	} else {
		fmt.Printf("\nFiles that would be processed:\n")
		for i, csvFile := range allCSVFiles {
			relPath, err := filepath.Rel(directoryPath, csvFile)
			if err != nil {
				relPath = csvFile
			}
			fmt.Printf("  %d. %s\n", i+1, relPath)
		}
	}

	return nil
}
