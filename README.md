# Museum of Dave

Unified email processing and API server for managing Gmail emails in a PostgreSQL database.

## Project Structure

```
MuseumOfDave/
├── src/
│   ├── __init__.py
│   ├── config.py              # Shared configuration
│   ├── loader.py              # Email processing logic
│   ├── email_client/          # Gmail client package
│   │   ├── __init__.py
│   │   └── client.py
│   ├── database/              # Database package
│   │   ├── __init__.py
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── connection.py      # Database connection
│   │   └── storage.py         # Storage operations
│   └── api/                   # FastAPI package
│       ├── __init__.py
│       └── app.py             # API endpoints
├── main.py                    # Entry point
├── requirements.txt           # Python dependencies
└── .env                       # Environment configuration
```

## Setup

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows Git Bash
   # or
   venv\Scripts\activate.bat     # Windows CMD
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables in `.env`:
   ```env
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=your_database
   DB_USER=your_user
   DB_PASSWORD=your_password
   ATTACHMENT_ALLOWED_TYPES=doc,docx,image/png,image/jpeg
   ATTACHMENT_MIN_SIZE=1024
   ```

4. Place Gmail credentials:
   - `credentials.json` - Gmail API OAuth credentials
   - `token.json` - Will be created automatically after first authentication

## Running the Application

Start the server:
```bash
python main.py
```

The server will:
1. Initialize the database connection
2. Create/verify database tables
3. Start the API server on `http://localhost:8000`

## Web Pages

The application includes two web-based viewers for managing attachments:

### Attachment Viewer (`/attachments-viewer`)

A single-attachment viewer that allows you to review and manage email attachments one at a time.

**Features:**
- **Navigation**: Previous/Next buttons to browse attachments sequentially
- **Order Options**: 
  - Random order
  - ID order (ascending)
  - Size: Smallest to Biggest
  - Size: Biggest to Smallest
- **Filtering**:
  - Toggle to show/hide PDF, MS Word, and Octet Stream attachments
  - Minimum file size filter (No limit, 1 KB, 10 KB, 100 KB, 1 MB, 10 MB, 100 MB)
- **Actions**:
  - **Keep**: Move to next attachment without deleting
  - **Delete**: Delete current attachment and move to next (can be disabled for PDF/MS Word/Octet Stream)
  - Optional confirmation dialog before deletion
- **Display**:
  - Shows full-size images (not thumbnails)
  - Shows thumbnails for PDF, MS Word, and other file types
  - Displays attachment metadata (ID, filename, content type, size)
  - Displays email metadata (subject, from, date, folder)

**Usage**: Navigate to `http://your-server:port/attachments-viewer` in your web browser.

### Image Grid Viewer (`/attachments-images-grid`)

A grid-based viewer for browsing and managing multiple images at once (50 images per page).

**Features:**
- **Grid Display**: Shows 50 images per page in a responsive grid layout
- **Sorting Options**:
  - Sort by: ID, Size, or Date
  - Direction: Ascending or Descending
- **Image Information**: Each image displays:
  - Thumbnail preview
  - Attachment ID
  - File size
- **Selection**:
  - Checkbox on each image for selection
  - Click image card to toggle selection
  - Visual feedback (red border) for selected images
- **Actions**:
  - **View Full Size**: Button on each image to open full-size version in a modal
  - **Delete Selected**: Bulk delete selected images
- **Pagination**: Previous/Next buttons to navigate between pages

**Usage**: Navigate to `http://your-server:port/attachments-images-grid` in your web browser.

## API Endpoints

### GET /
Root endpoint with API information.

### GET /health
Health check endpoint.

### POST /emails/process
Process emails from a Gmail label asynchronously.

**Request Body:**
```json
{
  "label": "INBOX",
  "new_only": true
}
```

**Response:**
```json
{
  "message": "Processing emails from label 'INBOX' started",
  "label": "INBOX",
  "count": 0,
  "timestamp": "2024-01-01T12:00:00"
}
```

### GET /attachments/{attachment_id}
Get attachment content by ID with appropriate MIME type.

## Interactive API Documentation

Once the server is running:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Features

- **Email Processing**: Fetch and process emails from Gmail labels
- **Attachment Filtering**: Configurable attachment filtering by type and size
- **Database Storage**: PostgreSQL storage with full-text search support
- **RESTful API**: FastAPI-based API with automatic documentation
- **Asynchronous Processing**: Background processing of email labels

## Configuration

The application uses environment variables for configuration. See `.env` file for required settings.

### Database Configuration
- `DB_HOST`: PostgreSQL host
- `DB_PORT`: PostgreSQL port (default: 5432)
- `DB_NAME`: Database name
- `DB_USER`: Database user
- `DB_PASSWORD`: Database password

### Attachment Filtering
- `ATTACHMENT_ALLOWED_TYPES`: Comma-separated list of allowed file extensions or MIME types
- `ATTACHMENT_MIN_SIZE`: Minimum attachment size in bytes (default: 0)
