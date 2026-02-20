package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"syscall"

	"import-processor/internal/config"
	"import-processor/internal/database"
	contactsimport "import-processor/internal/import/contacts"
	facebookimport "import-processor/internal/import/facebook"
	facebookalbumsimport "import-processor/internal/import/facebookalbums"
	facebookplacesimport "import-processor/internal/import/facebookplaces"
	filesystemimport "import-processor/internal/import/filesystem"
	imessageimport "import-processor/internal/import/imessage"
	instagramimport "import-processor/internal/import/instagram"
	whatsappimport "import-processor/internal/import/whatsapp"
	"import-processor/internal/services"
)

const helpSummary = `import-processor - Museum of Dave import processor

Usage:
  import-processor <command> [options]

Commands:
  whatsapp          Import WhatsApp messages from CSV directory
  imessage          Import iMessage conversations from CSV directory
  facebook          Import Facebook Messenger messages from JSON directory
  facebook-albums   Import Facebook albums from JSON directory
  facebook-places   Import Facebook places from posts JSON file(s)
  instagram        Import Instagram messages from JSON directory
  filesystem        Import images from filesystem directories
  thumbnails        Process thumbnails and EXIF for media items
  contacts        Merge contact records (emails/names) into normalized output

Run "import-processor <command> -h" for options per command.
`

func main() {
	if len(os.Args) == 1 {
		fmt.Print(helpSummary)
		os.Exit(0)
	}

	cmd := os.Args[1]
	switch cmd {
	case "whatsapp":
		runWhatsApp()
	case "imessage":
		runIMessage()
	case "facebook":
		runFacebook()
	case "facebook-albums":
		runFacebookAlbums()
	case "facebook-places":
		runFacebookPlaces()
	case "instagram":
		runInstagram()
	case "filesystem":
		runFilesystem()
	case "thumbnails":
		runThumbnails()
	case "contacts":
		runContactsNormalise()
	case "-h", "--help", "help":
		fmt.Print(helpSummary)
		os.Exit(0)
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", cmd)
		fmt.Print(helpSummary)
		os.Exit(0)
	}
}

func runWhatsApp() {
	fs := flag.NewFlagSet("whatsapp", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List all files that would be processed without importing")
	path := fs.String("path", "", "Directory containing WhatsApp CSV export (overrides config)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directory := strings.TrimSpace(*path)
	if directory == "" && cfg.WhatsAppDirectoryPath != "" {
		directory = cfg.WhatsAppDirectoryPath
	}
	if directory == "" {
		log.Fatalf("No directory specified. Set WHATSAPP_DIRECTORY_PATH in .env or use --path")
	}

	if *listFiles {
		if err := listFilesToProcess(directory); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting WhatsApp import from: %s\n", directory)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	progressCallback := func(stats whatsappimport.ImportStats) {
		if stats.TotalConversations > 0 {
			fmt.Fprintf(os.Stderr, "\rProcessing conversation %d of %d: %s | Messages: %d (%d created, %d updated) | Attachments: %d found, %d missing | Errors: %d",
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

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := whatsappimport.ImportWhatsAppFromDirectory(
		ctx,
		db,
		directory,
		progressCallback,
		cancelledCheck,
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

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

func runIMessage() {
	fs := flag.NewFlagSet("imessage", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List all files that would be processed without importing")
	path := fs.String("path", "", "Directory containing iMessage CSV export (overrides config)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directory := strings.TrimSpace(*path)
	if directory == "" && cfg.IMessageDirectoryPath != "" {
		directory = cfg.IMessageDirectoryPath
	}
	if directory == "" {
		log.Fatalf("No directory specified. Set IMESSAGE_DIRECTORY_PATH in .env or use --path")
	}

	if *listFiles {
		if err := listFilesToProcess(directory); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting iMessage import from: %s\n", directory)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	progressCallback := func(stats imessageimport.ImportStats) {
		if stats.TotalConversations > 0 {
			fmt.Fprintf(os.Stderr, "\rProcessing conversation %d of %d: %s | Messages: %d (%d created, %d updated) | Attachments: %d found, %d missing | Errors: %d",
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

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := imessageimport.ImportIMessagesFromDirectory(
		ctx,
		db,
		directory,
		progressCallback,
		cancelledCheck,
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

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

func runFacebook() {
	fs := flag.NewFlagSet("facebook", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List all files that would be processed without importing")
	path := fs.String("path", "", "Directory containing Facebook Messenger JSON export (overrides config)")
	exportRoot := fs.String("export-root", "", "Optional path to Facebook export root (for resolving attachment URIs)")
	userName := fs.String("user-name", "", "Optional user's name for incoming/outgoing message classification (overrides subject config)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directory := strings.TrimSpace(*path)
	if directory == "" && cfg.FacebookDirectoryPath != "" {
		directory = cfg.FacebookDirectoryPath
	}
	if directory == "" {
		log.Fatalf("No directory specified. Set FACEBOOK_DIRECTORY_PATH in .env or use --path")
	}

	if *listFiles {
		if err := facebookimport.ListFilesToProcess(directory); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting Facebook Messenger import from: %s\n", directory)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	progressCallback := func(stats facebookimport.ImportStats) {
		if stats.TotalConversations > 0 {
			fmt.Fprintf(os.Stderr, "\rProcessing conversation %d of %d: %s | Messages: %d (%d created, %d updated) | Attachments: %d found, %d missing | Errors: %d",
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

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := facebookimport.ImportFacebookFromDirectory(
		ctx,
		db,
		directory,
		progressCallback,
		cancelledCheck,
		strings.TrimSpace(*exportRoot),
		strings.TrimSpace(*userName),
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Processed %d conversation(s)\n", stats.ConversationsProcessed)
	fmt.Printf("Imported %d message(s) (%d created, %d updated)\n",
		stats.MessagesImported,
		stats.MessagesCreated,
		stats.MessagesUpdated)
	fmt.Printf("Found %d attachment(s), %d missing\n", stats.AttachmentsFound, stats.AttachmentsMissing)
	if stats.AttachmentErrorsBlobInsert > 0 || stats.AttachmentErrorsMetadataInsert > 0 ||
		stats.AttachmentErrorsJunctionInsert > 0 {
		fmt.Printf("Attachment errors: %d blob insert, %d metadata insert, %d junction insert\n",
			stats.AttachmentErrorsBlobInsert,
			stats.AttachmentErrorsMetadataInsert,
			stats.AttachmentErrorsJunctionInsert)
	}
	if stats.Errors > 0 {
		fmt.Printf("Skipped invalid messages: %d\n", stats.Errors)
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

func runFacebookAlbums() {
	fs := flag.NewFlagSet("facebook-albums", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List all files that would be processed without importing")
	path := fs.String("path", "", "Directory containing Facebook albums (posts/album or album) (overrides config)")
	exportRoot := fs.String("export-root", "", "Optional path to Facebook export root (for resolving image URIs)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directory := strings.TrimSpace(*path)
	if directory == "" && cfg.FacebookAlbumsDirectoryPath != "" {
		directory = cfg.FacebookAlbumsDirectoryPath
	}
	if directory == "" {
		log.Fatalf("No directory specified. Set FACEBOOK_ALBUMS_DIRECTORY_PATH in .env or use --path")
	}

	if *listFiles {
		if err := facebookalbumsimport.ListFilesToProcess(directory); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting Facebook Albums import from: %s\n", directory)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	progressCallback := func(stats facebookalbumsimport.ImportStats) {
		if stats.TotalAlbums > 0 {
			fmt.Fprintf(os.Stderr, "\rProcessing album %d of %d: %s | Albums: %d | Images: %d (found: %d, missing: %d) | Errors: %d",
				stats.AlbumsProcessed,
				stats.TotalAlbums,
				stats.CurrentAlbum,
				stats.AlbumsImported,
				stats.ImagesImported,
				stats.ImagesFound,
				stats.ImagesMissing,
				stats.Errors,
			)
		}
	}

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := facebookalbumsimport.ImportFacebookAlbumsFromDirectory(
		ctx,
		db,
		directory,
		progressCallback,
		cancelledCheck,
		strings.TrimSpace(*exportRoot),
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Processed %d album(s)\n", stats.AlbumsProcessed)
	fmt.Printf("Albums imported: %d\n", stats.AlbumsImported)
	fmt.Printf("Images imported: %d (found: %d, missing: %d)\n",
		stats.ImagesImported, stats.ImagesFound, stats.ImagesMissing)
	if stats.Errors > 0 {
		fmt.Printf("Errors: %d\n", stats.Errors)
	}

	if len(stats.MissingImageFilenames) > 0 {
		fmt.Println("\nMissing image files:")
		for _, filename := range stats.MissingImageFilenames {
			fmt.Printf("  - %s\n", filename)
		}
	}
}

func runFacebookPlaces() {
	fs := flag.NewFlagSet("facebook-places", flag.ExitOnError)
	path := fs.String("path", "", "Path to Facebook posts JSON file or directory of JSON files (overrides config)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	pathStr := strings.TrimSpace(*path)
	if pathStr == "" && cfg.FacebookPlacesPath != "" {
		pathStr = cfg.FacebookPlacesPath
	}
	if pathStr == "" {
		log.Fatalf("No path specified. Set FACEBOOK_PLACES_PATH in .env or use --path")
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	info, err := os.Stat(pathStr)
	if err != nil {
		log.Fatalf("Path does not exist or is not accessible: %v", err)
	}

	var stats *facebookplacesimport.ImportStats
	if info.IsDir() {
		fmt.Fprintf(os.Stderr, "Starting Facebook Places import from directory: %s\n", pathStr)
		stats, err = facebookplacesimport.ImportFacebookPlacesFromDirectory(ctx, db, pathStr, nil, cancelledCheck)
	} else {
		fmt.Fprintf(os.Stderr, "Starting Facebook Places import from file: %s\n", pathStr)
		stats, err = facebookplacesimport.ImportFacebookPlacesFromFile(ctx, db, pathStr)
	}

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Places imported: %d (created: %d, updated: %d)\n",
		stats.PlacesImported, stats.PlacesCreated, stats.PlacesUpdated)
	if len(stats.Errors) > 0 {
		fmt.Println("\nErrors/warnings:")
		for _, e := range stats.Errors {
			fmt.Printf("  - %s\n", e)
		}
	}
}

func runInstagram() {
	fs := flag.NewFlagSet("instagram", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List all files that would be processed without importing")
	path := fs.String("path", "", "Directory containing Instagram JSON export (overrides config)")
	exportRoot := fs.String("export-root", "", "Optional path to Instagram export root (for resolving photo URIs)")
	userName := fs.String("user-name", "", "Optional user's name for incoming/outgoing message classification (overrides subject config)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directory := strings.TrimSpace(*path)
	if directory == "" && cfg.InstagramDirectoryPath != "" {
		directory = cfg.InstagramDirectoryPath
	}
	if directory == "" {
		log.Fatalf("No directory specified. Set INSTAGRAM_DIRECTORY_PATH in .env or use --path")
	}

	if *listFiles {
		if err := instagramimport.ListFilesToProcess(directory); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting Instagram import from: %s\n", directory)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	progressCallback := func(stats instagramimport.ImportStats) {
		if stats.TotalConversations > 0 {
			fmt.Fprintf(os.Stderr, "\rProcessing conversation %d of %d: %s | Messages: %d (%d created, %d updated) | Attachments: %d found, %d missing | Errors: %d",
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

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := instagramimport.ImportInstagramFromDirectory(
		ctx,
		db,
		directory,
		progressCallback,
		cancelledCheck,
		strings.TrimSpace(*exportRoot),
		strings.TrimSpace(*userName),
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Processed %d conversation(s)\n", stats.ConversationsProcessed)
	fmt.Printf("Imported %d message(s) (%d created, %d updated)\n",
		stats.MessagesImported,
		stats.MessagesCreated,
		stats.MessagesUpdated)
	fmt.Printf("Found %d attachment(s), %d missing\n", stats.AttachmentsFound, stats.AttachmentsMissing)
	if stats.AttachmentErrorsBlobInsert > 0 || stats.AttachmentErrorsMetadataInsert > 0 ||
		stats.AttachmentErrorsJunctionInsert > 0 {
		fmt.Printf("Attachment errors: %d blob insert, %d metadata insert, %d junction insert\n",
			stats.AttachmentErrorsBlobInsert,
			stats.AttachmentErrorsMetadataInsert,
			stats.AttachmentErrorsJunctionInsert)
	}
	if stats.Errors > 0 {
		fmt.Printf("Skipped invalid messages: %d\n", stats.Errors)
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

func runContactsNormalise() {
	fs := flag.NewFlagSet("contacts-normalise", flag.ExitOnError)
	workers := fs.Int("workers", runtime.NumCPU(), "number of concurrent workers")
	classificationsFile := fs.String("classifications", "email_classifications.json", "JSON file mapping boolean columns to contact names (applied after contacts are written)")
	emailMatchesFile := fs.String("email-matches", "email_matches.json", "JSON file containing sets of email addresses that are absolute matches")
	exclusionsFile := fs.String("exclusions", "", "JSON file containing email and name exclusion patterns (default: built-in list)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Determine input source: positional arg or database
	positionalArg := ""
	if fs.NArg() > 0 {
		positionalArg = fs.Arg(0)
	}
	if fs.NArg() > 1 {
		log.Fatalf("error: too many arguments (flags must come before positional arguments)")
	}

	// File input takes precedence over database when positional arg is provided
	useDB := cfg.ContactsQuery != "" && positionalArg == ""
	if !useDB && positionalArg == "" {
		log.Fatalf("No input specified. Provide input.json or set CONTACTS_QUERY in .env for database mode")
	}

	// Always connect to DB (we always write to contacts table)
	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	contactsQuery := ""
	if useDB {
		contactsQuery = cfg.ContactsQuery
	}
	opts := contactsimport.RunOptions{
		Workers:             *workers,
		InputFile:           positionalArg,
		EmailMatchesFile:    strings.TrimSpace(*emailMatchesFile),
		ExclusionsFile:      strings.TrimSpace(*exclusionsFile),
		ClassificationsFile: strings.TrimSpace(*classificationsFile),
		ContactsQuery:       contactsQuery,
		RelationshipQuery:   cfg.ContactsRelationshipQuery,
		ContactsDB:          db,
	}

	ctx := context.Background()
	if err := contactsimport.RunContactsNormalise(ctx, opts); err != nil {
		log.Fatalf("Contacts normalise failed: %v", err)
	}
	fmt.Fprintln(os.Stderr, "Contacts normalise completed successfully")
}

type stringSlice []string

func (s *stringSlice) String() string { return strings.Join(*s, ",") }

func (s *stringSlice) Set(v string) error {
	*s = append(*s, v)
	return nil
}

func runFilesystem() {
	fs := flag.NewFlagSet("filesystem", flag.ExitOnError)
	listFiles := fs.Bool("list", false, "List files that would be processed without importing")
	var paths stringSlice
	fs.Var(&paths, "path", "Path to import (can be repeated)")
	var excludes stringSlice
	fs.Var(&excludes, "exclude", "Exclude pattern (can be repeated)")
	maxImages := fs.Int("max", 0, "Maximum number of images to import (0 = no limit)")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	directories := paths
	if len(directories) == 0 && cfg.FilesystemImportDirectories != "" {
		for _, p := range strings.Split(cfg.FilesystemImportDirectories, ",") {
			p = strings.TrimSpace(p)
			if p != "" {
				directories = append(directories, p)
			}
		}
	}

	excludePatterns := excludes
	if len(excludePatterns) == 0 && cfg.FilesystemExcludePatterns != "" {
		for _, p := range strings.Split(cfg.FilesystemExcludePatterns, ",") {
			p = strings.TrimSpace(p)
			if p != "" {
				excludePatterns = append(excludePatterns, p)
			}
		}
	}

	if len(directories) == 0 {
		log.Fatalf("No directories specified. Set FILESYSTEM_IMPORT_DIRECTORIES in .env or use --path")
	}

	if *listFiles {
		if err := filesystemimport.ListFilesToProcess(directories, excludePatterns); err != nil {
			log.Fatalf("Failed to list files: %v", err)
		}
		return
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")
	fmt.Fprintf(os.Stderr, "Starting filesystem import from %d director(y/ies)\n", len(directories))

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	cancelled := false
	var cancelMutex sync.Mutex

	go func() {
		<-sigChan
		fmt.Fprintln(os.Stderr, "\nReceived interrupt signal, cancelling import...")
		cancelMutex.Lock()
		cancelled = true
		cancelMutex.Unlock()
		cancel()
	}()

	var maxPtr *int
	if *maxImages > 0 {
		maxPtr = maxImages
	}

	progressCallback := func(stats filesystemimport.ImportStats) {
		fmt.Fprintf(os.Stderr, "\rProcessed: %d | Imported: %d | Updated: %d | Errors: %d",
			stats.FilesProcessed, stats.ImagesImported, stats.ImagesUpdated, stats.Errors)
	}

	cancelledCheck := func() bool {
		cancelMutex.Lock()
		defer cancelMutex.Unlock()
		return cancelled
	}

	stats, err := filesystemimport.ImportImagesFromDirectories(
		ctx,
		db,
		directories,
		excludePatterns,
		maxPtr,
		progressCallback,
		cancelledCheck,
	)

	fmt.Fprintln(os.Stderr)

	if err != nil {
		if ctx.Err() == context.Canceled {
			fmt.Fprintln(os.Stderr, "Import cancelled by user")
			os.Exit(1)
		}
		log.Fatalf("Import failed: %v", err)
	}

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Total files: %d\n", stats.TotalFiles)
	fmt.Printf("Files processed: %d\n", stats.FilesProcessed)
	fmt.Printf("Images imported: %d\n", stats.ImagesImported)
	fmt.Printf("Images updated: %d\n", stats.ImagesUpdated)
	fmt.Printf("Errors: %d\n", stats.Errors)

	if len(stats.ErrorMessages) > 0 {
		fmt.Println("\nError messages:")
		for _, msg := range stats.ErrorMessages {
			fmt.Printf("  - %s\n", msg)
		}
	}
}

func listFilesToProcess(directoryPath string) error {
	fmt.Fprintf(os.Stderr, "Scanning directory: %s\n", directoryPath)
	fmt.Println(strings.Repeat("=", 60))

	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	entries, err := os.ReadDir(directoryPath)
	if err != nil {
		return fmt.Errorf("failed to read directory: %w", err)
	}

	var conversationDirs []string
	for _, entry := range entries {
		if entry.IsDir() {
			conversationDirs = append(conversationDirs, entry.Name())
		}
	}

	sort.Strings(conversationDirs)

	fmt.Printf("\nFound %d conversation directory(ies)\n\n", len(conversationDirs))

	var totalCSVFiles int
	var allCSVFiles []string

	for _, conversationName := range conversationDirs {
		subdirPath := filepath.Join(directoryPath, conversationName)

		csvFiles, err := filepath.Glob(filepath.Join(subdirPath, "*.csv"))
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error finding CSV files in %s: %v\n", conversationName, err)
			continue
		}

		if len(csvFiles) == 0 {
			fmt.Printf("Conversation: %s\n", conversationName)
			fmt.Printf("  No CSV files found\n\n")
			continue
		}

		sort.Strings(csvFiles)

		fmt.Printf("Conversation: %s\n", conversationName)
		fmt.Printf("  CSV files (%d):\n", len(csvFiles))
		for _, csvFile := range csvFiles {
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

// mediaItemWork represents a work item for processing
type mediaItemWork struct {
	MediaItemID int64
	BlobID      int64
	MediaType   *string
}

// processResult represents the result of processing a media item
type processResult struct {
	Success bool
	Error   error
}

func runThumbnails() {
	fs := flag.NewFlagSet("thumbnails", flag.ExitOnError)
	listOnly := fs.Bool("list", false, "List the number of entries that would be processed without processing them")
	reprocess := fs.Bool("reprocess", false, "Reprocess all image items (including already processed) to re-extract EXIF data")
	fs.Parse(os.Args[2:])

	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Fprintln(os.Stderr, "Database connection established successfully")

	ctx := context.Background()

	if *listOnly {
		if err := listEntriesToProcess(ctx, db, *reprocess); err != nil {
			log.Fatalf("Failed to list entries: %v", err)
		}
		return
	}

	if err := processThumbnailsAndExif(ctx, db, *reprocess); err != nil {
		log.Fatalf("Failed to process thumbnails: %v", err)
	}
}

func processThumbnailsAndExif(ctx context.Context, db *database.DB, reprocess bool) error {
	if reprocess {
		fmt.Fprintln(os.Stderr, "Processing thumbnails and EXIF data for media items (reprocess mode - including already processed)...")
	} else {
		fmt.Fprintln(os.Stderr, "Processing thumbnails and EXIF data for media items...")
	}
	fmt.Fprintln(os.Stderr, "Querying database for media items that need processing...")

	var query string
	if reprocess {
		query = `
		SELECT 
			mi.id as media_item_id,
			mi.media_blob_id,
			mi.media_type
		FROM media_items mi
		INNER JOIN media_blob mb ON mi.media_blob_id = mb.id
		WHERE mb.image_data IS NOT NULL AND LENGTH(mb.image_data) > 0
		ORDER BY mi.id
		`
	} else {
		query = `
		SELECT 
			mi.id as media_item_id,
			mi.media_blob_id,
			mi.media_type
		FROM media_items mi
		INNER JOIN media_blob mb ON mi.media_blob_id = mb.id
		WHERE mi.processed = false 
		   OR mb.thumbnail_data IS NULL
		   OR LENGTH(mb.thumbnail_data) = 0
		ORDER BY mi.id
		`
	}

	rows, err := db.Pool.Query(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to query media items: %w", err)
	}
	defer rows.Close()

	fmt.Fprintln(os.Stderr, "Collecting work items from query results...")

	var workItems []mediaItemWork
	var mediaItemID, blobID int64
	var mediaType *string
	var scannedCount, skippedCount int

	for rows.Next() {
		scannedCount++
		if err := rows.Scan(&mediaItemID, &blobID, &mediaType); err != nil {
			fmt.Fprintf(os.Stderr, "Error scanning row %d: %v\n", scannedCount, err)
			continue
		}

		if mediaType == nil || !strings.HasPrefix(strings.ToLower(*mediaType), "image/") {
			skippedCount++
			if scannedCount%500 == 0 {
				fmt.Fprintf(os.Stderr, "  Scanned %d rows, collected %d image items, skipped %d non-image items...\n",
					scannedCount, len(workItems), skippedCount)
			}
			continue
		}

		workItems = append(workItems, mediaItemWork{
			MediaItemID: mediaItemID,
			BlobID:      blobID,
			MediaType:   mediaType,
		})

		if len(workItems)%500 == 0 {
			fmt.Fprintf(os.Stderr, "  Collected %d image items to process...\n", len(workItems))
		}
	}

	if err = rows.Err(); err != nil {
		return fmt.Errorf("error iterating rows: %w", err)
	}

	fmt.Fprintf(os.Stderr, "Query complete. Scanned %d total rows, found %d image items to process (skipped %d non-image items)\n",
		scannedCount, len(workItems), skippedCount)

	if len(workItems) == 0 {
		fmt.Fprintln(os.Stderr, "No media items to process")
		return nil
	}

	numWorkers := runtime.NumCPU()
	if numWorkers < 1 {
		numWorkers = 1
	}

	fmt.Fprintf(os.Stderr, "Starting worker pool with %d workers (CPU cores) to process %d media items...\n", numWorkers, len(workItems))

	workChan := make(chan mediaItemWork, len(workItems))
	resultChan := make(chan processResult, len(workItems))

	var processedCount, errorCount int64
	var statsMutex sync.Mutex

	var wg sync.WaitGroup
	processor := &services.Processor{}

	fmt.Fprintf(os.Stderr, "Starting %d worker goroutines...\n", numWorkers)
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			var workerProcessed int
			for work := range workChan {
				workerProcessed++
				result := processMediaItem(ctx, db, processor, work)
				resultChan <- result

				statsMutex.Lock()
				if result.Success {
					processedCount++
					if processedCount%25 == 0 {
						percentage := float64(processedCount) / float64(len(workItems)) * 100
						fmt.Fprintf(os.Stderr, "Progress: %d/%d items processed (%.1f%%) | Worker %d processed %d items | Errors: %d\n",
							processedCount, len(workItems), percentage, workerID, workerProcessed, errorCount)
					}
				} else {
					errorCount++
					if result.Error != nil {
						fmt.Fprintf(os.Stderr, "Error processing media item %d (blob %d, worker %d): %v\n",
							work.MediaItemID, work.BlobID, workerID, result.Error)
					}
				}
				statsMutex.Unlock()
			}
			fmt.Fprintf(os.Stderr, "Worker %d completed. Processed %d items.\n", workerID, workerProcessed)
		}(i)
	}

	fmt.Fprintf(os.Stderr, "Distributing %d work items to workers...\n", len(workItems))
	for i, work := range workItems {
		workChan <- work
		if (i+1)%1000 == 0 {
			fmt.Fprintf(os.Stderr, "  Distributed %d/%d work items to queue...\n", i+1, len(workItems))
		}
	}
	close(workChan)
	fmt.Fprintln(os.Stderr, "All work items distributed. Workers are processing...")

	fmt.Fprintln(os.Stderr, "Waiting for all workers to complete...")
	wg.Wait()
	close(resultChan)
	fmt.Fprintln(os.Stderr, "All workers completed.")

	fmt.Println("\nImport completed successfully")
	fmt.Printf("Total items to process: %d\n", len(workItems))
	fmt.Printf("Successfully processed: %d\n", processedCount)
	fmt.Printf("Errors: %d\n", errorCount)
	if len(workItems) > 0 {
		successRate := float64(processedCount) / float64(len(workItems)) * 100
		fmt.Printf("Success rate: %.2f%%\n", successRate)
	}

	return nil
}

func processMediaItem(ctx context.Context, db *database.DB, processor *services.Processor, work mediaItemWork) processResult {
	var imageData []byte
	loadImageQuery := `SELECT image_data FROM media_blob WHERE id = $1`
	err := db.Pool.QueryRow(ctx, loadImageQuery, work.BlobID).Scan(&imageData)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to load image data for blob_id=%d: %w",
			work.BlobID, err)}
	}

	if len(imageData) == 0 {
		return processResult{Success: false, Error: fmt.Errorf("image data is empty for blob_id=%d", work.BlobID)}
	}

	thumbData, exifData, err := processor.CreateThumbAndGetExif(imageData, true, true, 200)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("CreateThumbAndGetExif failed for media_item_id=%d blob_id=%d: %w",
			work.MediaItemID, work.BlobID, err)}
	}

	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to begin transaction: %w", err)}
	}
	defer tx.Rollback(ctx)

	if thumbData != nil {
		updateBlobQuery := `UPDATE media_blob SET thumbnail_data = $1 WHERE id = $2`
		_, err = tx.Exec(ctx, updateBlobQuery, thumbData, work.BlobID)
		if err != nil {
			return processResult{Success: false, Error: fmt.Errorf("failed to update thumbnail: %w", err)}
		}
	}

	updateItemQuery := `UPDATE media_items 
		SET processed = true, 
			description = COALESCE(NULLIF($1, ''), description),
			year = COALESCE($2, year),
			month = COALESCE($3, month),
			latitude = COALESCE($4, latitude),
			longitude = COALESCE($5, longitude),
			has_gps = COALESCE($6, has_gps),
			updated_at = NOW()
		WHERE id = $7`

	var description *string
	var year, month *int
	var latitude, longitude *float64
	var hasGPS *bool

	if exifData != nil {
		if exifData.Description != "" {
			description = &exifData.Description
		}
		if exifData.DateTaken != "" {
			parts := strings.Fields(exifData.DateTaken)
			if len(parts) > 0 {
				dateParts := strings.Split(parts[0], ":")
				if len(dateParts) >= 2 {
					var y, m int
					if _, err := fmt.Sscanf(dateParts[0], "%d", &y); err == nil {
						year = &y
					}
					if _, err := fmt.Sscanf(dateParts[1], "%d", &m); err == nil {
						month = &m
					}
				}
			}
		}
		if exifData.LatitudeDecimal != nil && exifData.LongitudeDecimal != nil {
			latitude = exifData.LatitudeDecimal
			longitude = exifData.LongitudeDecimal
			hasGPSVal := true
			hasGPS = &hasGPSVal
		}
	}

	_, err = tx.Exec(ctx, updateItemQuery, description, year, month, latitude, longitude, hasGPS, work.MediaItemID)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to update media item: %w", err)}
	}

	if err = tx.Commit(ctx); err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to commit transaction: %w", err)}
	}

	return processResult{Success: true}
}

func listEntriesToProcess(ctx context.Context, db *database.DB, reprocess bool) error {
	if reprocess {
		fmt.Fprintln(os.Stderr, "Querying database for media items (reprocess mode - including already processed)...")
	} else {
		fmt.Fprintln(os.Stderr, "Querying database for media items that need processing...")
	}

	var query string
	if reprocess {
		query = `
		SELECT 
			mi.id as media_item_id,
			mi.media_blob_id,
			mi.media_type
		FROM media_items mi
		INNER JOIN media_blob mb ON mi.media_blob_id = mb.id
		WHERE mb.image_data IS NOT NULL AND LENGTH(mb.image_data) > 0
		ORDER BY mi.id
		`
	} else {
		query = `
		SELECT 
			mi.id as media_item_id,
			mi.media_blob_id,
			mi.media_type
		FROM media_items mi
		INNER JOIN media_blob mb ON mi.media_blob_id = mb.id
		WHERE mi.processed = false 
		   OR mb.thumbnail_data IS NULL
		   OR LENGTH(mb.thumbnail_data) = 0
		ORDER BY mi.id
		`
	}

	rows, err := db.Pool.Query(ctx, query)
	if err != nil {
		return fmt.Errorf("failed to query media items: %w", err)
	}
	defer rows.Close()

	var mediaItemID, blobID int64
	var mediaType *string
	var totalCount, imageCount, nonImageCount int

	for rows.Next() {
		totalCount++
		if err := rows.Scan(&mediaItemID, &blobID, &mediaType); err != nil {
			fmt.Fprintf(os.Stderr, "Error scanning row %d: %v\n", totalCount, err)
			continue
		}

		if mediaType == nil || !strings.HasPrefix(strings.ToLower(*mediaType), "image/") {
			nonImageCount++
		} else {
			imageCount++
		}
	}

	if err = rows.Err(); err != nil {
		return fmt.Errorf("error iterating rows: %w", err)
	}

	fmt.Println(strings.Repeat("=", 60))
	if reprocess {
		fmt.Printf("Media items (reprocess mode):\n")
	} else {
		fmt.Printf("Media items that need processing:\n")
	}
	fmt.Printf("  Total items: %d\n", totalCount)
	fmt.Printf("  Image items: %d\n", imageCount)
	fmt.Printf("  Non-image items (will be skipped): %d\n", nonImageCount)
	fmt.Println(strings.Repeat("=", 60))
	fmt.Printf("\nNumber of entries that will be processed: %d\n", imageCount)

	if imageCount == 0 {
		fmt.Println("\nNo media items to process.")
	}

	return nil
}
