package facebookalbumsimport

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"import-processor/pkg/utils"
)

var errFound = errors.New("found")

// AlbumExport represents the structure of a Facebook album JSON file
type AlbumExport struct {
	Name                  string           `json:"name"`
	Description           string           `json:"description"`
	CoverPhoto            *AlbumCoverPhoto `json:"cover_photo"`
	LastModifiedTimestamp *int64           `json:"last_modified_timestamp"`
	Photos                []AlbumPhoto     `json:"photos"`
}

// AlbumCoverPhoto represents the cover photo of an album
type AlbumCoverPhoto struct {
	URI string `json:"uri"`
}

// AlbumPhoto represents a photo in an album
type AlbumPhoto struct {
	URI               string `json:"uri"`
	CreationTimestamp *int64 `json:"creation_timestamp"`
	Title             string `json:"title"`
	Description       string `json:"description"`
}

// ParseTimestampMs converts Unix timestamp in milliseconds to time.Time
func ParseTimestampMs(ts *int64) *time.Time {
	if ts == nil {
		return nil
	}
	t := time.UnixMilli(*ts)
	return &t
}

// GuessMIMEType returns MIME type from filename
func GuessMIMEType(filename string) string {
	mt := utils.DetectMIMEType(filename)
	if mt != "" {
		return mt
	}
	return "image/jpeg"
}

// FindImageFile locates an image file by URI.
// If filenameCache is non-nil, uses it for O(1) lookup instead of WalkDir fallback.
func FindImageFile(albumDir, uri, exportRoot string, filenameCache map[string]string) (string, bool) {
	if uri == "" {
		return "", false
	}

	// Try export root first
	if exportRoot != "" {
		p := filepath.Join(exportRoot, uri)
		if pathExists(p, false) {
			return p, true
		}
	}

	// Try relative to album dir
	relPath := filepath.Join(albumDir, uri)
	if pathExists(relPath, false) {
		return relPath, true
	}

	// Try filename only
	filename := filepath.Base(uri)
	filenamePath := filepath.Join(albumDir, filename)
	if pathExists(filenamePath, false) {
		return filenamePath, true
	}

	// Use cache if available (avoids repeated WalkDir)
	if filenameCache != nil {
		if p, ok := filenameCache[filename]; ok {
			return p, true
		}
		return "", false
	}

	// Fallback: search for file (slow - one full walk per lookup)
	var found string
	filepath.WalkDir(albumDir, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if !d.IsDir() && d.Name() == filename {
			found = p
			return errFound
		}
		return nil
	})
	if found != "" {
		return found, true
	}

	return "", false
}

// BuildFilenameCache walks rootDirs and builds a filename->path map for O(1) lookups.
// Call once per import to avoid repeated WalkDir calls. Walks each root in order;
// first occurrence of a filename wins.
func BuildFilenameCache(rootDirs []string) map[string]string {
	cache := make(map[string]string)
	for _, rootDir := range rootDirs {
		if rootDir == "" {
			continue
		}
		filepath.WalkDir(rootDir, func(p string, d os.DirEntry, err error) error {
			if err != nil {
				return nil
			}
			if !d.IsDir() {
				name := d.Name()
				if _, exists := cache[name]; !exists {
					cache[name] = p
				}
			}
			return nil
		})
	}
	return cache
}

func pathExists(path string, requireDir bool) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	if requireDir {
		return info.IsDir()
	}
	return !info.IsDir()
}

// ReadImageFile reads image data from path
func ReadImageFile(imagePath, uri string) (filename, mimeType string, data []byte) {
	d, err := os.ReadFile(imagePath)
	if err != nil {
		return filepath.Base(uri), "", nil
	}
	fn := filepath.Base(uri)
	mt := GuessMIMEType(fn)
	if mt == "" {
		mt = "image/jpeg"
	}
	return fn, mt, d
}

// ParseAlbumJSON parses an album JSON file
func ParseAlbumJSON(data []byte) (*AlbumExport, error) {
	var export AlbumExport
	if err := json.Unmarshal(data, &export); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}
	return &export, nil
}

// TryHEICFallback tries .heic -> .jpg if original not found
func TryHEICFallback(uri string) string {
	if strings.HasSuffix(strings.ToLower(uri), ".heic") {
		return uri[:len(uri)-5] + ".jpg"
	}
	return ""
}

// TryOpusFallback tries .opus -> .mp3
func TryOpusFallback(uri string) string {
	if strings.HasSuffix(strings.ToLower(uri), ".opus") {
		return uri[:len(uri)-5] + ".mp3"
	}
	return ""
}
