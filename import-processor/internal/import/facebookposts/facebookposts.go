package facebookpostsimport

import (
	"context"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"sync"

	"import-processor/internal/database"
	facebookimport "import-processor/internal/import/facebook"
	facebookalbumsimport "import-processor/internal/import/facebookalbums"
)

const postImageBatchSize = 25

var postsFilePattern = regexp.MustCompile(`your_posts__check_ins__photos_and_videos_\d+\.json`)

// ImportStats holds statistics about the import process
type ImportStats struct {
	PostsProcessed int
	TotalPosts     int
	PostsImported  int
	PostsUpdated   int
	WithMedia      int
	ImagesImported int
	ImagesFound    int
	ImagesMissing  int
	Errors         int
	CurrentPost    string
	mu             sync.Mutex
}

func (s *ImportStats) copyStats() ImportStats {
	s.mu.Lock()
	defer s.mu.Unlock()
	return ImportStats{
		PostsProcessed: s.PostsProcessed,
		TotalPosts:     s.TotalPosts,
		PostsImported:  s.PostsImported,
		PostsUpdated:   s.PostsUpdated,
		WithMedia:      s.WithMedia,
		ImagesImported: s.ImagesImported,
		ImagesFound:    s.ImagesFound,
		ImagesMissing:  s.ImagesMissing,
		Errors:         s.Errors,
		CurrentPost:    s.CurrentPost,
	}
}

// ProgressCallback is called after each post is processed
type ProgressCallback func(ImportStats)

// CancelledCheck returns true if the import should be cancelled
type CancelledCheck func() bool

// ImportFacebookPostsFromPath imports Facebook posts from a JSON file or directory.
// If path is a directory, all matching your_posts__check_ins__photos_and_videos_*.json files are imported.
func ImportFacebookPostsFromPath(
	ctx context.Context,
	db *database.DB,
	path string,
	exportRootOverride string,
	progressCallback ProgressCallback,
	cancelledCheck CancelledCheck,
) (*ImportStats, error) {
	// Collect JSON files to process
	jsonFiles, err := collectPostsFiles(path)
	if err != nil {
		return nil, err
	}
	if len(jsonFiles) == 0 {
		return nil, fmt.Errorf("no posts JSON files found at path: %s", path)
	}

	// Determine export root for resolving media URIs
	exportRoot := exportRootOverride
	if exportRoot == "" {
		if root, ok := facebookimport.DetectFacebookExportRoot(path, ""); ok {
			exportRoot = root
			fmt.Fprintf(os.Stderr, "Auto-detected Facebook export root: %s\n", exportRoot)
		}
	}

	// Build filename cache once (major perf win for large exports)
	searchDirs := []string{path}
	if exportRoot != "" && exportRoot != path {
		searchDirs = append(searchDirs, exportRoot)
	}
	filenameCache := facebookalbumsimport.BuildFilenameCache(searchDirs)

	storage := database.NewFacebookPostStorage(db)

	// Count total posts across all files for progress reporting
	var totalPosts int
	allParsed := make([]PostsExport, len(jsonFiles))
	for i, jf := range jsonFiles {
		data, err := os.ReadFile(jf)
		if err != nil {
			return nil, fmt.Errorf("failed to read %s: %w", jf, err)
		}
		posts, err := ParsePostsJSON(data)
		if err != nil {
			return nil, fmt.Errorf("failed to parse %s: %w", jf, err)
		}
		allParsed[i] = posts
		totalPosts += len(posts)
	}

	stats := &ImportStats{TotalPosts: totalPosts}

	for _, posts := range allParsed {
		for _, post := range posts {
			if cancelledCheck != nil && cancelledCheck() {
				return stats, context.Canceled
			}
			select {
			case <-ctx.Done():
				return stats, ctx.Err()
			default:
			}

			if err := processPost(ctx, storage, post, exportRoot, filenameCache, stats, cancelledCheck); err != nil {
				fmt.Fprintf(os.Stderr, "Error processing post (ts=%v): %v\n", post.Timestamp, err)
				stats.mu.Lock()
				stats.Errors++
				stats.mu.Unlock()
			}

			if progressCallback != nil {
				progressCallback(stats.copyStats())
			}
		}
	}

	return stats, nil
}

// collectPostsFiles returns the list of posts JSON files to process.
func collectPostsFiles(path string) ([]string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return nil, fmt.Errorf("path not accessible: %w", err)
	}

	if !info.IsDir() {
		// Single file
		return []string{path}, nil
	}

	// Directory: walk tree to find all matching files
	var files []string
	err = filepath.WalkDir(path, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if postsFilePattern.MatchString(d.Name()) {
			files = append(files, p)
		}
		return nil
	})
	if err != nil {
		return nil, fmt.Errorf("failed to walk directory: %w", err)
	}
	sort.Strings(files)
	return files, nil
}

func processPost(
	ctx context.Context,
	storage *database.FacebookPostStorage,
	entry PostEntry,
	exportRoot string,
	filenameCache map[string]string,
	stats *ImportStats,
	cancelledCheck CancelledCheck,
) error {
	ts := ParseTimestampSec(entry.Timestamp)
	postText := ExtractPostText(entry)
	externalURL := ExtractExternalURL(entry)
	postType := DeterminePostType(entry)
	mediaItems := ExtractMediaItems(entry)

	// Use directory of first media item as albumDir hint for FindImageFile
	albumDir := exportRoot

	titlePreview := entry.Title
	if len(titlePreview) > 50 {
		titlePreview = titlePreview[:50] + "..."
	}

	stats.mu.Lock()
	stats.PostsProcessed++
	stats.CurrentPost = titlePreview
	stats.mu.Unlock()

	postID, wasCreated, err := storage.SaveOrUpdatePost(ctx, ts, entry.Title, postText, externalURL, postType)
	if err != nil {
		return fmt.Errorf("failed to save post: %w", err)
	}

	stats.mu.Lock()
	if wasCreated {
		stats.PostsImported++
	} else {
		stats.PostsUpdated++
	}
	if len(mediaItems) > 0 {
		stats.WithMedia++
	}
	stats.mu.Unlock()

	if len(mediaItems) == 0 {
		return nil
	}

	// Process media in batches
	var batch []database.BatchPostImageItem
	flushBatch := func() {
		if len(batch) == 0 {
			return
		}
		n, err := storage.SavePostImagesBatch(ctx, batch)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error saving post images batch: %v\n", err)
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

	for _, mi := range mediaItems {
		if cancelledCheck != nil && cancelledCheck() {
			flushBatch()
			return context.Canceled
		}

		uri := mi.URI
		if uri == "" {
			continue
		}

		imagePath, ok := facebookalbumsimport.FindImageFile(albumDir, uri, exportRoot, filenameCache)
		if !ok {
			if jpgURI := facebookalbumsimport.TryHEICFallback(uri); jpgURI != "" {
				imagePath, ok = facebookalbumsimport.FindImageFile(albumDir, jpgURI, exportRoot, filenameCache)
				if ok {
					uri = jpgURI
				}
			}
		}
		if !ok {
			if mp3URI := facebookalbumsimport.TryOpusFallback(uri); mp3URI != "" {
				imagePath, ok = facebookalbumsimport.FindImageFile(albumDir, mp3URI, exportRoot, filenameCache)
				if ok {
					uri = mp3URI
				}
			}
		}

		var filename, imageType string
		var imageData []byte

		if ok {
			filename, imageType, imageData = facebookalbumsimport.ReadImageFile(imagePath, uri)
			stats.mu.Lock()
			if len(imageData) > 0 {
				stats.ImagesFound++
			} else {
				stats.ImagesMissing++
			}
			stats.mu.Unlock()
		} else {
			stats.mu.Lock()
			stats.ImagesMissing++
			stats.mu.Unlock()
		}

		creationTs := ParseTimestampSec(mi.CreationTimestamp)
		if filename == "" {
			filename = filepath.Base(uri)
		}

		batch = append(batch, database.BatchPostImageItem{
			PostID:            postID,
			URI:               uri,
			Filename:          filename,
			CreationTimestamp: creationTs,
			Title:             mi.Title,
			Description:       mi.Description,
			ImageData:         imageData,
			ImageType:         imageType,
			PostTitle:         entry.Title,
		})

		if len(batch) >= postImageBatchSize {
			flushBatch()
		}
	}

	flushBatch()
	return nil
}

// ListFilesToProcess lists the JSON files that would be processed
func ListFilesToProcess(path string) error {
	files, err := collectPostsFiles(path)
	if err != nil {
		return err
	}
	fmt.Printf("\nFound %d posts JSON file(s):\n", len(files))
	for _, f := range files {
		fmt.Printf("  - %s\n", f)
	}
	return nil
}
