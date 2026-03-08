package facebookalbumsimport

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
	facebookimport "import-processor/internal/import/facebook"
)

const albumImageBatchSize = 25

// ImportStats holds statistics about the import process
type ImportStats struct {
	AlbumsProcessed       int
	TotalAlbums           int
	AlbumsImported        int
	ImagesImported        int
	ImagesFound           int
	ImagesMissing         int
	MissingImageFilenames []string
	missingImageSet       map[string]struct{} // O(1) dedup; not exported
	Errors                int
	CurrentAlbum          string
	mu                    sync.Mutex
}

func (s *ImportStats) copyStats() ImportStats {
	s.mu.Lock()
	defer s.mu.Unlock()
	return ImportStats{
		AlbumsProcessed:       s.AlbumsProcessed,
		TotalAlbums:           s.TotalAlbums,
		AlbumsImported:        s.AlbumsImported,
		ImagesImported:        s.ImagesImported,
		ImagesFound:           s.ImagesFound,
		ImagesMissing:         s.ImagesMissing,
		MissingImageFilenames: append([]string(nil), s.MissingImageFilenames...),
		Errors:                s.Errors,
		CurrentAlbum:          s.CurrentAlbum,
	}
}

// ProgressCallback is called after each album is processed
type ProgressCallback func(ImportStats)

// CancelledCheck returns true if the import should be cancelled
type CancelledCheck func() bool

// ImportFacebookAlbumsFromDirectory imports Facebook albums from a directory structure.
// The directory should contain an "album" subdirectory with JSON files, or be the album directory directly.
func ImportFacebookAlbumsFromDirectory(
	ctx context.Context,
	db *database.DB,
	directoryPath string,
	progressCallback ProgressCallback,
	cancelledCheck CancelledCheck,
	exportRootOverride string,
) (*ImportStats, error) {
	dirInfo, err := os.Stat(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("directory does not exist or is not accessible: %w", err)
	}
	if !dirInfo.IsDir() {
		return nil, fmt.Errorf("path is not a directory: %s", directoryPath)
	}

	albumDirs, err := findAlbumDirsRecursive(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to walk directory: %w", err)
	}

	var jsonFiles []string
	for _, files := range albumDirs {
		jsonFiles = append(jsonFiles, files...)
	}
	sort.Strings(jsonFiles)

	stats := &ImportStats{
		TotalAlbums:           len(jsonFiles),
		MissingImageFilenames: []string{},
		missingImageSet:       make(map[string]struct{}),
	}

	exportRoot := exportRootOverride
	if exportRoot == "" {
		if root, ok := facebookimport.DetectFacebookExportRoot(directoryPath, ""); ok {
			exportRoot = root
			fmt.Fprintf(os.Stderr, "Auto-detected Facebook export root: %s\n", exportRoot)
		}
	}

	// Build filename cache once to avoid repeated WalkDir (major perf win)
	searchDirs := []string{directoryPath}
	if exportRoot != "" && exportRoot != directoryPath {
		searchDirs = append(searchDirs, exportRoot)
	}
	filenameCache := BuildFilenameCache(searchDirs)

	storage := database.NewFacebookAlbumStorage(db)

	numWorkers := runtime.NumCPU()
	if numWorkers > len(jsonFiles) {
		numWorkers = len(jsonFiles)
	}
	if numWorkers < 1 {
		numWorkers = 1
	}

	type albumWork struct {
		jsonFile string
		albumDir string
	}
	workChan := make(chan albumWork, len(jsonFiles))
	for albumDir, files := range albumDirs {
		for _, jf := range files {
			workChan <- albumWork{jsonFile: jf, albumDir: albumDir}
		}
	}
	close(workChan)

	var wg sync.WaitGroup
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
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
				stats.AlbumsProcessed++
				stats.CurrentAlbum = filepath.Base(work.jsonFile)
				stats.mu.Unlock()

				err := processAlbumJSONFile(ctx, storage, work.jsonFile, work.albumDir, stats, exportRoot, filenameCache, cancelledCheck)
				if err != nil {
					fmt.Fprintf(os.Stderr, "Error processing album file %s: %v\n", work.jsonFile, err)
					stats.mu.Lock()
					stats.Errors++
					stats.mu.Unlock()
				}

				if progressCallback != nil {
					progressCallback(stats.copyStats())
				}
			}
		}()
	}
	wg.Wait()

	return stats, nil
}

// findAlbumDirsRecursive walks directoryPath and returns a map of album directory
// paths to their *.json file paths. Album directories are subdirs with "album" in their name.
func findAlbumDirsRecursive(directoryPath string) (map[string][]string, error) {
	var albumDirPaths []string
	err := filepath.WalkDir(directoryPath, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !d.IsDir() {
			return nil
		}
		if !strings.Contains(strings.ToLower(d.Name()), "album") {
			return nil
		}
		albumDirPaths = append(albumDirPaths, path)
		return nil
	})
	if err != nil {
		return nil, err
	}

	albumDirs := make(map[string][]string)
	for _, dirPath := range albumDirPaths {
		entries, err := os.ReadDir(dirPath)
		if err != nil {
			continue
		}
		var jsonFiles []string
		for _, e := range entries {
			if e.IsDir() {
				continue
			}
			if strings.HasSuffix(e.Name(), ".json") {
				jsonFiles = append(jsonFiles, filepath.Join(dirPath, e.Name()))
			}
		}
		if len(jsonFiles) > 0 {
			albumDirs[dirPath] = jsonFiles
		}
	}
	return albumDirs, nil
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

	albumDirs, err := findAlbumDirsRecursive(directoryPath)
	if err != nil {
		return fmt.Errorf("failed to walk directory: %w", err)
	}

	var albumPaths []string
	for dir := range albumDirs {
		albumPaths = append(albumPaths, dir)
	}
	sort.Strings(albumPaths)

	var totalJSON int
	fmt.Printf("\nFound %d album directory(ies)\n\n", len(albumPaths))
	for _, albumDir := range albumPaths {
		jsonFiles := albumDirs[albumDir]
		sort.Strings(jsonFiles)
		totalJSON += len(jsonFiles)
		relName, _ := filepath.Rel(directoryPath, albumDir)
		if relName == "." {
			relName = filepath.Base(albumDir)
		}
		fmt.Printf("Album dir: %s\n  JSON files (%d):\n", relName, len(jsonFiles))
		for _, jf := range jsonFiles {
			fmt.Printf("    - %s\n", filepath.Base(jf))
		}
		fmt.Println()
	}
	fmt.Printf("Total: %d album dir(s), %d JSON file(s)\n", len(albumPaths), totalJSON)
	return nil
}

func processAlbumJSONFile(ctx context.Context, storage *database.FacebookAlbumStorage, jsonFilePath, albumDir string, stats *ImportStats, exportRoot string, filenameCache map[string]string, cancelledCheck CancelledCheck) error {
	data, err := os.ReadFile(jsonFilePath)
	if err != nil {
		return fmt.Errorf("failed to read JSON: %w", err)
	}

	export, err := ParseAlbumJSON(data)
	if err != nil {
		return err
	}

	albumName := export.Name
	if albumName == "" {
		albumName = strings.TrimSuffix(filepath.Base(jsonFilePath), filepath.Ext(jsonFilePath))
	}

	// Count photos with non-empty URI - skip album if none
	photosWithURI := 0
	for _, p := range export.Photos {
		if p.URI != "" {
			photosWithURI++
		}
	}
	if photosWithURI == 0 {
		return nil // Skip albums with no photos
	}

	var coverPhotoURI string
	if export.CoverPhoto != nil {
		coverPhotoURI = export.CoverPhoto.URI
	}

	albumID, wasCreated, err := storage.SaveOrUpdateAlbum(ctx, albumName, export.Description, coverPhotoURI, ParseTimestampMs(export.LastModifiedTimestamp))
	if err != nil {
		return fmt.Errorf("failed to save album: %w", err)
	}

	if wasCreated {
		stats.mu.Lock()
		stats.AlbumsImported++
		stats.mu.Unlock()
	}

	var batch []database.BatchAlbumImageItem
	flushBatch := func() {
		if len(batch) == 0 {
			return
		}
		n, err := storage.SaveAlbumImagesBatch(ctx, batch)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error saving album images batch: %v\n", err)
			stats.mu.Lock()
			stats.Errors += len(batch)
			stats.mu.Unlock()
		} else {
			stats.mu.Lock()
			stats.ImagesImported += n
			stats.mu.Unlock()
		}
		batch = batch[:0]
	}

	for _, photo := range export.Photos {
		if cancelledCheck != nil && cancelledCheck() {
			flushBatch()
			return context.Canceled
		}
		select {
		case <-ctx.Done():
			flushBatch()
			return ctx.Err()
		default:
		}

		uri := photo.URI
		if uri == "" {
			continue
		}

		imagePath, ok := FindImageFile(albumDir, uri, exportRoot, filenameCache)
		if !ok {
			// Try .heic -> .jpg fallback
			if jpgURI := TryHEICFallback(uri); jpgURI != "" {
				imagePath, ok = FindImageFile(albumDir, jpgURI, exportRoot, filenameCache)
				if ok {
					uri = jpgURI
				}
			}
		}
		if !ok {
			// Try .opus -> .mp3 fallback
			if mp3URI := TryOpusFallback(uri); mp3URI != "" {
				imagePath, ok = FindImageFile(albumDir, mp3URI, exportRoot, filenameCache)
				if ok {
					uri = mp3URI
				}
			}
		}

		var filename, imageType string
		var imageData []byte

		if ok {
			filename, imageType, imageData = ReadImageFile(imagePath, uri)
			if len(imageData) > 0 {
				stats.mu.Lock()
				stats.ImagesFound++
				stats.mu.Unlock()
			} else {
				stats.mu.Lock()
				stats.ImagesMissing++
				missingKey := albumName + "/" + filepath.Base(uri)
				if _, exists := stats.missingImageSet[missingKey]; !exists {
					stats.missingImageSet[missingKey] = struct{}{}
					stats.MissingImageFilenames = append(stats.MissingImageFilenames, missingKey)
				}
				stats.mu.Unlock()
			}
		} else {
			stats.mu.Lock()
			stats.ImagesMissing++
			missingKey := albumName + "/" + filepath.Base(uri)
			if _, exists := stats.missingImageSet[missingKey]; !exists {
				stats.missingImageSet[missingKey] = struct{}{}
				stats.MissingImageFilenames = append(stats.MissingImageFilenames, missingKey)
			}
			stats.mu.Unlock()
		}

		creationTs := ParseTimestampMs(photo.CreationTimestamp)
		title := photo.Title
		description := photo.Description
		if filename == "" {
			filename = filepath.Base(uri)
		}

		batch = append(batch, database.BatchAlbumImageItem{
			AlbumID:           albumID,
			URI:               uri,
			Filename:          filename,
			CreationTimestamp: creationTs,
			Title:             title,
			Description:       description,
			ImageData:         imageData,
			ImageType:         imageType,
			AlbumName:         albumName,
		})

		if len(batch) >= albumImageBatchSize {
			flushBatch()
		}
	}

	flushBatch()
	return nil
}
