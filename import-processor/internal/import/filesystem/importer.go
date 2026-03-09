package filesystemimport

import (
	"context"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"

	"import-processor/internal/database"
	"import-processor/pkg/utils"
)

var imageExtensions = map[string]bool{
	".jpg": true, ".jpeg": true, ".png": true, ".gif": true,
	".bmp": true, ".tiff": true, ".tif": true, ".webp": true,
	".heic": true, ".heif": true, ".avif": true, ".ico": true,
}

// Hardcoded paths/names to skip
func shouldSkipPath(path string, name string) bool {
	if strings.Contains(path, ".photostructure") {
		return true
	}
	if strings.HasPrefix(name, "._") {
		return true
	}
	switch strings.ToLower(name) {
	case "thumbs.db", "desktop.ini", "ehthumbs.db", "ehthumbs.db-shm":
		return true
	}
	return false
}

func shouldExcludeDirectory(dirPath string, dirName string, patterns []string) bool {
	if len(patterns) == 0 {
		return false
	}
	for _, pattern := range patterns {
		pattern = strings.TrimSpace(pattern)
		if pattern == "" {
			continue
		}
		matched, _ := filepath.Match(pattern, dirName)
		if matched {
			return true
		}
		matched, _ = filepath.Match(pattern, dirPath)
		if matched {
			return true
		}
		if strings.Contains(dirPath, pattern) || strings.Contains(dirName, pattern) {
			return true
		}
	}
	return false
}

// ImportStats holds statistics about the import process
type ImportStats struct {
	TotalFiles       int      `json:"total_files"`
	FilesProcessed   int      `json:"files_processed"`
	ImagesImported   int      `json:"images_imported"`
	ImagesUpdated    int      `json:"images_updated"`
	ImagesReferenced int      `json:"images_referenced"`
	Errors           int      `json:"errors"`
	ErrorMessages    []string `json:"error_messages"`
	CurrentFile      string   `json:"current_file,omitempty"`
	mu               sync.Mutex
}

func (s *ImportStats) copyStats() ImportStats {
	s.mu.Lock()
	defer s.mu.Unlock()
	return ImportStats{
		TotalFiles:       s.TotalFiles,
		FilesProcessed:   s.FilesProcessed,
		ImagesImported:   s.ImagesImported,
		ImagesUpdated:    s.ImagesUpdated,
		ImagesReferenced: s.ImagesReferenced,
		Errors:           s.Errors,
		ErrorMessages:    append([]string(nil), s.ErrorMessages...),
		CurrentFile:      s.CurrentFile,
	}
}

// ProgressCallback is called after each image is processed (throttled to every N items)
type ProgressCallback func(ImportStats)

const progressCallbackInterval = 25 // call progress callback every N items
const imageBatchSize = 25           // batch size for SaveImagesBatch

// CancelledCheck returns true if the import should be cancelled
type CancelledCheck func() bool

type imageWork struct {
	Path     string
	RootPath string
	Name     string
}

// ImportImagesFromDirectories imports images from one or more directory trees using a worker pool.
// When referenceMode is true, image binary data is not read or stored; only metadata and the
// filesystem path are recorded in the database.
func ImportImagesFromDirectories(
	ctx context.Context,
	db *database.DB,
	directories []string,
	excludePatterns []string,
	maxImages *int,
	referenceMode bool,
	progressCallback ProgressCallback,
	cancelledCheck CancelledCheck,
) (*ImportStats, error) {
	storage := database.NewImageStorage(db)
	stats := &ImportStats{
		ErrorMessages: []string{},
	}

	// First pass: collect image paths
	var workItems []imageWork
	for _, rootDir := range directories {
		if maxImages != nil && len(workItems) >= *maxImages {
			break
		}

		rootPath, err := filepath.Abs(rootDir)
		if err != nil {
			return nil, fmt.Errorf("invalid path %s: %w", rootDir, err)
		}
		info, err := os.Stat(rootPath)
		if err != nil {
			return nil, fmt.Errorf("directory does not exist or is not accessible: %s: %w", rootPath, err)
		}
		if !info.IsDir() {
			return nil, fmt.Errorf("path is not a directory: %s", rootPath)
		}

		filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
			if cancelledCheck != nil && cancelledCheck() {
				return fmt.Errorf("cancelled")
			}
			select {
			case <-ctx.Done():
				return ctx.Err()
			default:
			}

			if err != nil {
				return nil
			}
			if d.IsDir() {
				if shouldExcludeDirectory(path, d.Name(), excludePatterns) {
					return filepath.SkipDir
				}
				return nil
			}
			if shouldSkipPath(path, d.Name()) {
				return nil
			}
			ext := strings.ToLower(filepath.Ext(d.Name()))
			if !imageExtensions[ext] {
				return nil
			}

			workItems = append(workItems, imageWork{Path: path, RootPath: rootPath, Name: d.Name()})
			stats.TotalFiles++

			if maxImages != nil && len(workItems) >= *maxImages {
				return filepath.SkipAll
			}
			return nil
		})
	}

	if len(workItems) == 0 {
		return stats, nil
	}

	// Switch tables to UNLOGGED for faster bulk inserts; restore to LOGGED when done
	if _, err := db.Pool.Exec(ctx, "ALTER TABLE media_blob SET UNLOGGED"); err != nil {
		return nil, fmt.Errorf("failed to set media_blob UNLOGGED: %w", err)
	}
	if _, err := db.Pool.Exec(ctx, "ALTER TABLE media_items SET UNLOGGED"); err != nil {
		db.Pool.Exec(ctx, "ALTER TABLE media_blob SET LOGGED") // best-effort restore
		return nil, fmt.Errorf("failed to set media_items UNLOGGED: %w", err)
	}
	defer func() {
		restoreCtx := context.Background()
		db.Pool.Exec(restoreCtx, "ALTER TABLE media_blob SET LOGGED")
		db.Pool.Exec(restoreCtx, "ALTER TABLE media_items SET LOGGED")
	}()

	// Worker pool
	numWorkers := runtime.NumCPU()
	if numWorkers < 1 {
		numWorkers = 1
	}
	if numWorkers > len(workItems) {
		numWorkers = len(workItems)
	}

	workChan := make(chan imageWork, len(workItems))
	var wg sync.WaitGroup

	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var batch []database.BatchImageItem
			flushBatch := func() {
				if len(batch) == 0 {
					return
				}
				imp, upd, err := storage.SaveImagesBatch(ctx, batch)
				if err != nil {
					for _, item := range batch {
						_, isUpdate, saveErr := storage.SaveImage(ctx, item.SourceRef, item.ImageData, item.MediaType, item.Title, item.Tags, item.IsReferenced)
						if saveErr != nil {
							stats.mu.Lock()
							stats.Errors++
							stats.ErrorMessages = append(stats.ErrorMessages, fmt.Sprintf("Error processing %s: %v", item.SourceRef, saveErr))
							stats.mu.Unlock()
						} else {
							stats.mu.Lock()
							if isUpdate {
								stats.ImagesUpdated++
							} else if item.IsReferenced {
								stats.ImagesReferenced++
							} else {
								stats.ImagesImported++
							}
							stats.mu.Unlock()
						}
					}
				} else {
					stats.mu.Lock()
					stats.ImagesImported += imp
					stats.ImagesUpdated += upd
					stats.mu.Unlock()
				}
				batch = batch[:0]
			}

			for work := range workChan {
				if cancelledCheck != nil && cancelledCheck() {
					return
				}
				select {
				case <-ctx.Done():
					return
				default:
				}

				stats.mu.Lock()
				stats.FilesProcessed++
				stats.CurrentFile = work.Path
				stats.mu.Unlock()

				absPath, _ := filepath.Abs(work.Path)
				mediaType := utils.DetectMIMEType(work.Name)
				title := strings.TrimSuffix(work.Name, filepath.Ext(work.Name))
				tags := generateDirectoryTags(work.Path, work.RootPath)

				var imageData []byte
				if !referenceMode {
					var err error
					imageData, err = os.ReadFile(work.Path)
					if err != nil {
						stats.mu.Lock()
						stats.Errors++
						stats.ErrorMessages = append(stats.ErrorMessages, fmt.Sprintf("Error reading %s: %v", work.Path, err))
						stats.mu.Unlock()
						if progressCallback != nil {
							progressCallback(stats.copyStats())
						}
						continue
					}
				}

				batch = append(batch, database.BatchImageItem{
					SourceRef:    absPath,
					ImageData:    imageData,
					MediaType:    mediaType,
					Title:        title,
					Tags:         tags,
					IsReferenced: referenceMode,
				})

				if len(batch) >= imageBatchSize {
					flushBatch()
					stats.mu.Lock()
					current := stats.FilesProcessed
					stats.mu.Unlock()
					if progressCallback != nil && (current%progressCallbackInterval == 0) {
						progressCallback(stats.copyStats())
					}
				}
			}
			flushBatch()
		}()
	}

	// Send work items
	for _, work := range workItems {
		workChan <- work
	}
	close(workChan)
	wg.Wait()

	if progressCallback != nil {
		progressCallback(stats.copyStats())
	}

	return stats, nil
}

func generateDirectoryTags(filePath, rootPath string) string {
	rel, err := filepath.Rel(rootPath, filepath.Dir(filePath))
	if err != nil {
		return ""
	}
	if rel == "." || rel == ".." {
		return ""
	}
	return strings.ReplaceAll(rel, string(filepath.Separator), ",")
}

// ListFilesToProcess walks directories and prints file counts per directory and total
func ListFilesToProcess(directories []string, excludePatterns []string) error {
	filesPerDir := make(map[string]int)
	var total int

	for _, rootDir := range directories {
		rootPath, err := filepath.Abs(rootDir)
		if err != nil {
			return fmt.Errorf("invalid path %s: %w", rootDir, err)
		}
		info, err := os.Stat(rootPath)
		if err != nil {
			return fmt.Errorf("directory does not exist: %s: %w", rootPath, err)
		}
		if !info.IsDir() {
			return fmt.Errorf("path is not a directory: %s", rootPath)
		}

		filepath.WalkDir(rootPath, func(path string, d fs.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			if d.IsDir() {
				if shouldExcludeDirectory(path, d.Name(), excludePatterns) {
					return filepath.SkipDir
				}
				return nil
			}
			if shouldSkipPath(path, d.Name()) {
				return nil
			}
			ext := strings.ToLower(filepath.Ext(d.Name()))
			if imageExtensions[ext] {
				dir := filepath.Dir(path)
				filesPerDir[dir]++
				total++
			}
			return nil
		})
	}

	type kv struct {
		k string
		v int
	}
	var sorted []kv
	for k, v := range filesPerDir {
		sorted = append(sorted, kv{k, v})
	}
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].v > sorted[j].v })

	fmt.Println("\nFiles per directory:")
	fmt.Println(strings.Repeat("-", 80))
	for _, kv := range sorted {
		fmt.Printf("%s: %d file(s)\n", kv.k, kv.v)
	}
	fmt.Println(strings.Repeat("-", 80))
	fmt.Printf("Total files: %d\n\n", total)
	return nil
}
