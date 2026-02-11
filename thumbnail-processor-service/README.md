# Thumbnail Processor Service

A Go console application that processes thumbnails and extracts EXIF data for media items stored in PostgreSQL.

## Features

- Processes thumbnails for images using ImageMagick
- Extracts EXIF data (GPS coordinates, date taken, description, etc.)
- Parallel processing using worker pool (scales with CPU cores)
- Updates database with thumbnail data and EXIF metadata
- Progress tracking and detailed status reporting

## Prerequisites

- Go 1.21 or later
- PostgreSQL database
- ImageMagick installed and available in PATH (`magick` command)

## Installation

1. Navigate to the service directory:
```bash
cd thumbnail-processor-service
```

2. Install dependencies:
```bash
go mod download
```

3. Set up environment variables (see `.env.example`):
```bash
cp .env.example .env
# Edit .env with your database credentials
```

## Configuration

Create a `.env` file in the root directory with the following variables:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

## Usage

Run the service:
```bash
go run cmd/server/main.go
```

Or build and run:
```bash
go build -o thumbnail-processor-service cmd/server/main.go
./thumbnail-processor-service
```

## How It Works

1. Queries the database for media items that need processing:
   - Items where `processed = false`
   - Items where `thumbnail_data IS NULL` or empty

2. Filters to only process image types (MIME type starts with `image/`)

3. Uses a worker pool (number of CPU cores) to process items in parallel:
   - Each worker loads image data from the database
   - Processes thumbnail using ImageMagick
   - Extracts EXIF data
   - Updates database with thumbnail and metadata

4. Provides detailed progress reporting and statistics

## Database Schema

The service expects the following PostgreSQL tables:
- `media_blob` - Stores image binary data and thumbnails
- `media_items` - Stores media metadata

## Performance

- Uses worker pool based on CPU cores for optimal parallelization
- Database connection pool configured for concurrent access
- Processes images on-demand (doesn't load all images into memory)
- Provides progress updates every 25 items processed

## License

This service is part of the Museum of Dave project.
