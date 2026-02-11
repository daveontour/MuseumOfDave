# WhatsApp Import Service

A Go microservice using Gin framework that imports WhatsApp messages from CSV files in a directory structure, handles attachments, and stores data in PostgreSQL.

## Features

- Import WhatsApp messages from CSV files organized in conversation directories
- Handle message attachments with fallback support (.heic → .jpg, .opus → .mp3)
- Automatic MIME type detection
- Group chat detection
- Progress tracking and cancellation support
- REST API endpoints for import management

## Prerequisites

- Go 1.21 or later
- PostgreSQL database
- Access to WhatsApp export directory structure

## Installation

1. Clone or navigate to the service directory:
```bash
cd whatsapp-import-service
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
PORT=8080
```

## Running the Service

```bash
go run cmd/server/main.go
```

Or build and run:

```bash
go build -o whatsapp-import-service cmd/server/main.go
./whatsapp-import-service
```

The service will start on port 8080 by default (or the port specified in `PORT` environment variable).

## API Endpoints

### POST /whatsapp/import
Start importing WhatsApp messages from a directory.

**Request Body:**
```json
{
  "directory_path": "/path/to/whatsapp/export"
}
```

**Response:**
```json
{
  "message": "WhatsApp import has been initiated.",
  "status": "started"
}
```

### GET /whatsapp/import/status
Get the current status of the import process.

**Response:**
```json
{
  "status": "in_progress",
  "conversations_processed": 5,
  "total_conversations": 10,
  "messages_imported": 150,
  "messages_created": 140,
  "messages_updated": 10,
  "attachments_found": 45,
  "attachments_missing": 2,
  "missing_attachment_filenames": ["conversation1/file.jpg"],
  "errors": 0,
  "current_conversation": "John Doe"
}
```

### POST /whatsapp/import/cancel
Cancel the currently running import.

**Response:**
```json
{
  "message": "Import cancellation requested.",
  "status": "cancelled"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "time": "2026-02-07T12:00:00Z"
}
```

## Directory Structure

The service expects a directory structure like:

```
whatsapp-export/
├── Conversation1/
│   ├── messages.csv
│   ├── attachment1.jpg
│   └── attachment2.mp4
├── Conversation2/
│   ├── messages.csv
│   └── attachment1.png
└── ...
```

Each subdirectory represents a conversation and should contain:
- At least one CSV file with the messages
- Attachment files referenced in the CSV

## CSV Format

The CSV file should have the following columns:
- Message Date
- Sent Date
- Chat Session
- Type
- Sender ID
- Sender Name
- Status
- Replying to
- Text
- Attachment
- Attachment type

## Database Schema

The service expects the following PostgreSQL tables:
- `messages` - Stores message data
- `media_blob` - Stores attachment binary data
- `media_metadata` - Stores attachment metadata
- `message_attachments` - Junction table linking messages to attachments
- `subject_configuration` - Stores subject configuration (optional)

## Development

### Project Structure

```
whatsapp-import-service/
├── cmd/
│   └── server/
│       └── main.go              # Application entry point
├── internal/
│   ├── config/
│   │   └── config.go            # Configuration management
│   ├── database/
│   │   ├── connection.go        # PostgreSQL connection
│   │   ├── models.go            # Database models
│   │   └── storage.go           # Storage operations
│   ├── import/
│   │   ├── whatsapp.go          # Main import logic
│   │   └── parser.go            # CSV parsing utilities
│   ├── services/
│   │   └── subject_config.go    # Subject configuration service
│   └── handlers/
│       └── import.go            # HTTP handlers
├── pkg/
│   └── utils/
│       ├── file.go              # File utilities
│       └── mime.go              # MIME type detection
├── go.mod
├── go.sum
├── .env.example
└── README.md
```

## Dependencies

- `github.com/gin-gonic/gin` - Web framework
- `github.com/jackc/pgx/v5` - PostgreSQL driver
- `github.com/jackc/pgxpool/v5` - Connection pooling
- `github.com/joho/godotenv` - Environment variable loading

## Notes

- The service processes imports asynchronously in the background
- Progress can be tracked via the status endpoint
- Imports can be cancelled at any time
- The service automatically detects group chats based on notification patterns and sender counts
- Attachment fallback logic handles common format conversions (.heic → .jpg, .opus → .mp3)

## License

This service is part of the Museum of Dave project.
