package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"runtime"
	"strings"
	"sync"

	"thumbnail-processor-service/internal/config"
	"thumbnail-processor-service/internal/database"
	"thumbnail-processor-service/internal/services"
)

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

func main() {
	// Parse command line flags
	listOnly := flag.Bool("list", false, "List the number of entries that would be processed without processing them")
	reprocess := flag.Bool("reprocess", false, "Reprocess all image items (including already processed) to re-extract EXIF data")
	flag.Parse()

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Initialize database connection
	db, err := database.NewDB(cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	fmt.Println("Database connection established successfully")

	ctx := context.Background()

	// If list flag is set, list entries and exit
	if *listOnly {
		if err := listEntriesToProcess(ctx, db, *reprocess); err != nil {
			log.Fatalf("Failed to list entries: %v", err)
		}
		return
	}

	// Process thumbnails
	if err := processThumbnailsAndExif(ctx, db, *reprocess); err != nil {
		log.Fatalf("Failed to process thumbnails: %v", err)
	}
}

// processThumbnailsAndExif processes thumbnails and EXIF data for media items in the database
func processThumbnailsAndExif(ctx context.Context, db *database.DB, reprocess bool) error {
	if reprocess {
		fmt.Println("Processing thumbnails and EXIF data for media items (reprocess mode - including already processed)...")
	} else {
		fmt.Println("Processing thumbnails and EXIF data for media items...")
	}
	fmt.Println("Querying database for media items that need processing...")

	// Query media items - when reprocess=true, include all; otherwise only unprocessed or missing thumbnails
	// Only select IDs and media_type - image_data will be loaded by workers
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

	fmt.Println("Collecting work items from query results...")

	// Collect all work items first (only IDs, no image data)
	var workItems []mediaItemWork
	var mediaItemID, blobID int64
	var mediaType *string
	var scannedCount, skippedCount int

	for rows.Next() {
		scannedCount++
		if err := rows.Scan(&mediaItemID, &blobID, &mediaType); err != nil {
			fmt.Printf("Error scanning row %d: %v\n", scannedCount, err)
			continue
		}

		// Only process images
		if mediaType == nil || !strings.HasPrefix(strings.ToLower(*mediaType), "image/") {
			skippedCount++
			if scannedCount%500 == 0 {
				fmt.Printf("  Scanned %d rows, collected %d image items, skipped %d non-image items...\n",
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
			fmt.Printf("  Collected %d image items to process...\n", len(workItems))
		}
	}

	if err = rows.Err(); err != nil {
		return fmt.Errorf("error iterating rows: %w", err)
	}

	fmt.Printf("Query complete. Scanned %d total rows, found %d image items to process (skipped %d non-image items)\n",
		scannedCount, len(workItems), skippedCount)

	if len(workItems) == 0 {
		fmt.Println("No media items to process")
		return nil
	}

	// Determine number of workers based on CPU cores
	numWorkers := runtime.NumCPU()
	if numWorkers < 1 {
		numWorkers = 1
	}

	fmt.Printf("Starting worker pool with %d workers (CPU cores) to process %d media items...\n", numWorkers, len(workItems))

	// Create channels for work distribution and results
	workChan := make(chan mediaItemWork, len(workItems))
	resultChan := make(chan processResult, len(workItems))

	// Thread-safe counters
	var processedCount, errorCount int64
	var statsMutex sync.Mutex

	var wg sync.WaitGroup
	processor := &services.Processor{}

	fmt.Printf("Starting %d worker goroutines...\n", numWorkers)
	for i := 0; i < numWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			var workerProcessed int
			for work := range workChan {
				workerProcessed++
				result := processMediaItem(ctx, db, processor, work)
				resultChan <- result

				// Update counters thread-safely
				statsMutex.Lock()
				if result.Success {
					processedCount++
					// More frequent progress updates
					if processedCount%25 == 0 {
						percentage := float64(processedCount) / float64(len(workItems)) * 100
						fmt.Printf("Progress: %d/%d items processed (%.1f%%) | Worker %d processed %d items | Errors: %d\n",
							processedCount, len(workItems), percentage, workerID, workerProcessed, errorCount)
					}
				} else {
					errorCount++
					if result.Error != nil {
						fmt.Printf("Error processing media item %d (blob %d, worker %d): %v\n",
							work.MediaItemID, work.BlobID, workerID, result.Error)
					}
				}
				statsMutex.Unlock()
			}
			fmt.Printf("Worker %d completed. Processed %d items.\n", workerID, workerProcessed)
		}(i)
	}

	// Send all work items to the channel
	fmt.Printf("Distributing %d work items to workers...\n", len(workItems))
	for i, work := range workItems {
		workChan <- work
		if (i+1)%1000 == 0 {
			fmt.Printf("  Distributed %d/%d work items to queue...\n", i+1, len(workItems))
		}
	}
	close(workChan)
	fmt.Println("All work items distributed. Workers are processing...")

	// Wait for all workers to complete
	fmt.Println("Waiting for all workers to complete...")
	wg.Wait()
	close(resultChan)
	fmt.Println("All workers completed.")

	// Final statistics
	fmt.Printf("\n" + strings.Repeat("=", 60) + "\n")
	fmt.Printf("Thumbnail processing completed successfully\n")
	fmt.Printf(strings.Repeat("=", 60) + "\n")
	fmt.Printf("Total items to process: %d\n", len(workItems))
	fmt.Printf("Successfully processed: %d items\n", processedCount)
	fmt.Printf("Errors encountered: %d items\n", errorCount)
	if len(workItems) > 0 {
		successRate := float64(processedCount) / float64(len(workItems)) * 100
		fmt.Printf("Success rate: %.2f%%\n", successRate)
	}
	fmt.Printf(strings.Repeat("=", 60) + "\n")

	return nil
}

// processMediaItem processes a single media item and returns the result
func processMediaItem(ctx context.Context, db *database.DB, processor *services.Processor, work mediaItemWork) processResult {
	// Load image data from database
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

	// Process thumbnail and EXIF
	thumbData, exifData, err := processor.CreateThumbAndGetExif(imageData, true, true, 200)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("CreateThumbAndGetExif failed for media_item_id=%d blob_id=%d: %w",
			work.MediaItemID, work.BlobID, err)}
	}

	// Start transaction
	tx, err := db.Pool.Begin(ctx)
	if err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to begin transaction: %w", err)}
	}
	defer tx.Rollback(ctx)

	// Update thumbnail_data in media_blob
	if thumbData != nil {
		updateBlobQuery := `UPDATE media_blob SET thumbnail_data = $1 WHERE id = $2`
		_, err = tx.Exec(ctx, updateBlobQuery, thumbData, work.BlobID)
		if err != nil {
			return processResult{Success: false, Error: fmt.Errorf("failed to update thumbnail: %w", err)}
		}
	}

	// Update media_item with processed=true and EXIF data if available
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
		// Parse date_taken for year/month if available
		if exifData.DateTaken != "" {
			// Date format from EXIF is typically "YYYY:MM:DD HH:MM:SS"
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
		// Use parsed GPS coordinates (DMS converted to decimal, refs applied)
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

	// Commit transaction
	if err = tx.Commit(ctx); err != nil {
		return processResult{Success: false, Error: fmt.Errorf("failed to commit transaction: %w", err)}
	}

	return processResult{Success: true}
}

// listEntriesToProcess queries the database and reports the number of entries that would be processed
func listEntriesToProcess(ctx context.Context, db *database.DB, reprocess bool) error {
	if reprocess {
		fmt.Println("Querying database for media items (reprocess mode - including already processed)...")
	} else {
		fmt.Println("Querying database for media items that need processing...")
	}

	// Query media items - when reprocess=true, include all; otherwise only unprocessed or missing thumbnails
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
			fmt.Printf("Error scanning row %d: %v\n", totalCount, err)
			continue
		}

		// Count images vs non-images
		if mediaType == nil || !strings.HasPrefix(strings.ToLower(*mediaType), "image/") {
			nonImageCount++
		} else {
			imageCount++
		}
	}

	if err = rows.Err(); err != nil {
		return fmt.Errorf("error iterating rows: %w", err)
	}

	// Report results
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
