package facebookplacesimport

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"import-processor/internal/database"
)

const facebookSource = "facebook"

// ImportStats holds statistics about the import process
type ImportStats struct {
	PlacesImported int
	PlacesCreated  int
	PlacesUpdated  int
	Errors         []string
}

// ProgressCallback is called after each file is processed (when processing directory)
type ProgressCallback func(ImportStats)

// CancelledCheck returns true if the import should be cancelled
type CancelledCheck func() bool

// ExtractPlacesFromData recursively extracts all 'place' elements from nested JSON structures
func ExtractPlacesFromData(data interface{}, placesList *[]map[string]interface{}) {
	switch v := data.(type) {
	case map[string]interface{}:
		if place, ok := v["place"]; ok {
			if placeMap, ok := place.(map[string]interface{}); ok {
				*placesList = append(*placesList, placeMap)
			}
		}
		for _, val := range v {
			ExtractPlacesFromData(val, placesList)
		}
	case []interface{}:
		for _, item := range v {
			ExtractPlacesFromData(item, placesList)
		}
	}
}

// ImportFacebookPlacesFromFile imports places from a single Facebook posts JSON file
func ImportFacebookPlacesFromFile(ctx context.Context, db *database.DB, filePath string) (*ImportStats, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	var jsonData interface{}
	if err := json.Unmarshal(data, &jsonData); err != nil {
		return nil, fmt.Errorf("failed to parse JSON: %w", err)
	}

	var placesList []map[string]interface{}
	ExtractPlacesFromData(jsonData, &placesList)

	stats := &ImportStats{Errors: []string{}}
	storage := database.NewLocationStorage(db)

	for _, placeData := range placesList {
		select {
		case <-ctx.Done():
			return stats, ctx.Err()
		default:
		}

		nameVal, _ := placeData["name"].(string)
		name := strings.TrimSpace(nameVal)
		if name == "" {
			stats.Errors = append(stats.Errors, fmt.Sprintf("Skipped place with empty name: %v", placeData))
			continue
		}

		var latitude, longitude *float64
		if coord, ok := placeData["coordinate"].(map[string]interface{}); ok {
			if lat, ok := toFloat64(coord["latitude"]); ok {
				latitude = &lat
			}
			if lng, ok := toFloat64(coord["longitude"]); ok {
				longitude = &lng
			}
		}

		address := ""
		if a, ok := placeData["address"].(string); ok {
			address = strings.TrimSpace(a)
		}

		url := ""
		if u, ok := placeData["url"].(string); ok {
			url = strings.TrimSpace(u)
		}

		created, err := storage.SaveOrUpdateLocation(ctx, name, address, latitude, longitude, facebookSource, url)
		if err != nil {
			stats.Errors = append(stats.Errors, fmt.Sprintf("Error processing place %s: %v", name, err))
			continue
		}

		stats.PlacesImported++
		if created {
			stats.PlacesCreated++
		} else {
			stats.PlacesUpdated++
		}
	}

	// Update location regions (may fail if function doesn't exist)
	if err := storage.UpdateLocationRegions(ctx); err != nil {
		stats.Errors = append(stats.Errors, fmt.Sprintf("update_location_regions: %v (non-fatal)", err))
	}

	return stats, nil
}

// ImportFacebookPlacesFromDirectory imports places from all JSON files in a directory
func ImportFacebookPlacesFromDirectory(ctx context.Context, db *database.DB, directoryPath string, progressCallback ProgressCallback, cancelledCheck CancelledCheck) (*ImportStats, error) {
	entries, err := os.ReadDir(directoryPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read directory: %w", err)
	}

	var jsonFiles []string
	for _, e := range entries {
		if !e.IsDir() && strings.HasSuffix(strings.ToLower(e.Name()), ".json") {
			jsonFiles = append(jsonFiles, filepath.Join(directoryPath, e.Name()))
		}
	}

	aggStats := &ImportStats{Errors: []string{}}

	for _, jsonFile := range jsonFiles {
		if cancelledCheck != nil && cancelledCheck() {
			break
		}
		select {
		case <-ctx.Done():
			return aggStats, ctx.Err()
		default:
		}

		stats, err := ImportFacebookPlacesFromFile(ctx, db, jsonFile)
		if err != nil {
			aggStats.Errors = append(aggStats.Errors, fmt.Sprintf("Error processing %s: %v", jsonFile, err))
			continue
		}

		aggStats.PlacesImported += stats.PlacesImported
		aggStats.PlacesCreated += stats.PlacesCreated
		aggStats.PlacesUpdated += stats.PlacesUpdated
		aggStats.Errors = append(aggStats.Errors, stats.Errors...)

		if progressCallback != nil {
			progressCallback(*aggStats)
		}
	}

	// Update location regions once at end (may fail if function doesn't exist)
	storage := database.NewLocationStorage(db)
	if err := storage.UpdateLocationRegions(ctx); err != nil {
		aggStats.Errors = append(aggStats.Errors, fmt.Sprintf("update_location_regions: %v (non-fatal)", err))
	}

	return aggStats, nil
}

// toFloat64 converts various numeric types to float64
func toFloat64(v interface{}) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	default:
		return 0, false
	}
}
