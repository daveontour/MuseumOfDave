# import-processor

Museum of Dave import processor - a CLI tool for importing WhatsApp messages, iMessage conversations, Facebook Messenger messages, Facebook albums, Facebook places, Instagram messages, and processing media thumbnails/EXIF data.

## Commands

### whatsapp

Import WhatsApp messages from a CSV directory structure.

```bash
# Run import (uses WHATSAPP_DIRECTORY_PATH from .env, or --path)
import-processor whatsapp

# Specify directory on command line (overrides config)
import-processor whatsapp --path /path/to/whatsapp/export

# List CSV files that would be processed without importing
import-processor whatsapp --list
```

**Requirements:**
- Directory: set `WHATSAPP_DIRECTORY_PATH` in .env, or use `--path` (command line overrides config)

### imessage

Import iMessage conversations from a CSV directory (iMazing export format).

```bash
# Run import (uses IMESSAGE_DIRECTORY_PATH from .env, or --path)
import-processor imessage

# Specify directory on command line (overrides config)
import-processor imessage --path /path/to/imessage/export

# List CSV files that would be processed without importing
import-processor imessage --list
```

**Requirements:**
- Directory: set `IMESSAGE_DIRECTORY_PATH` in .env, or use `--path` (command line overrides config)
- Same directory structure as WhatsApp: top-level conversation subdirectories with CSV files inside.

### facebook

Import Facebook Messenger messages from a JSON directory structure (Facebook data export format).

```bash
# Run import (uses FACEBOOK_DIRECTORY_PATH from .env, or --path)
import-processor facebook

# Specify directory on command line (overrides config)
import-processor facebook --path /path/to/facebook/messages

# Optional: specify export root for resolving attachment URIs
import-processor facebook --path /path/to/messages --export-root /path/to/facebook/export

# List JSON files that would be processed without importing
import-processor facebook --list
```

**Requirements:**
- Directory: set `FACEBOOK_DIRECTORY_PATH` in .env, or use `--path` (command line overrides config)
- Structure: top-level conversation subdirectories, each containing `message_1.json`, `message_2.json`, etc.
- Optional: `--export-root` if attachment URIs are relative to a parent export directory

### facebook-albums

Import Facebook albums from a JSON directory structure (Facebook data export format).

```bash
# Run import (uses FACEBOOK_ALBUMS_DIRECTORY_PATH from .env, or --path)
import-processor facebook-albums

# Specify directory on command line (overrides config)
import-processor facebook-albums --path /path/to/your_facebook_activity/posts

# Optional: specify export root for resolving image URIs
import-processor facebook-albums --path /path/to/posts --export-root /path/to/facebook/export

# List album JSON files that would be processed without importing
import-processor facebook-albums --list
```

**Requirements:**
- Directory: set `FACEBOOK_ALBUMS_DIRECTORY_PATH` in .env, or use `--path` (command line overrides config)
- Structure: directory containing `album` subdirectory with `*.json` files, or the album directory directly
- Each JSON file: album with name, description, cover_photo, photos (each with uri, creation_timestamp, title, description)
- Optional: `--export-root` if image URIs are relative to a parent export directory
- Database tables: `facebook_albums`, `album_media` (created by main app migrations)

### facebook-places

Import Facebook places from a posts JSON file. Extracts all `place` elements from nested structures and stores them in the `locations` table.

```bash
# Run import (uses FACEBOOK_PLACES_PATH from .env, or --path)
import-processor facebook-places

# Single file
import-processor facebook-places --path /path/to/your_posts_1.json

# Directory - processes all JSON files
import-processor facebook-places --path /path/to/posts_directory
```

**Requirements:**
- Path: set `FACEBOOK_PLACES_PATH` in .env, or use `--path` (file or directory)
- JSON: Facebook posts export format with nested `place` elements (name, coordinate, address, url)
- Database: `locations` table; optional `update_location_regions()` function for region updates

### instagram

Import Instagram messages from a JSON directory structure (Instagram/Meta data export format).

```bash
# Run import (uses INSTAGRAM_DIRECTORY_PATH from .env, or --path)
import-processor instagram

# Specify directory on command line (overrides config)
import-processor instagram --path /path/to/instagram/messages/inbox

# Optional: specify export root for resolving photo URIs
import-processor instagram --path /path/to/inbox --export-root /path/to/your_instagram_activity

# List JSON files that would be processed without importing
import-processor instagram --list
```

**Requirements:**
- Directory: set `INSTAGRAM_DIRECTORY_PATH` in .env, or use `--path` (command line overrides config)
- Structure: top-level conversation subdirectories, each containing `message_1.json`, `message_2.json`, etc.
- Optional: `--export-root` if photo URIs are relative to a parent export directory (e.g. `your_instagram_activity`)

### filesystem

Import images from filesystem directories (no thumbnail or EXIF processing).

```bash
# Run import (uses FILESYSTEM_IMPORT_DIRECTORIES from .env, or --path)
import-processor filesystem

# Specify paths on command line
import-processor filesystem --path /path/to/images1 --path /path/to/images2

# List files that would be processed
import-processor filesystem --list

# Limit number of images (for testing)
import-processor filesystem --max 100

# Exclude patterns
import-processor filesystem --exclude "*.photostructure" --exclude "Thumbs.db"
```

**Requirements:**
- At least one directory: set `FILESYSTEM_IMPORT_DIRECTORIES` (comma-separated) in .env, or use `--path` (repeatable)
- Optional: `FILESYSTEM_EXCLUDE_PATTERNS` (comma-separated)

### thumbnails

Process thumbnails and EXIF data for media items in the database.

```bash
# Run processing (only unprocessed items)
import-processor thumbnails

# List count of entries that would be processed
import-processor thumbnails --list

# Include already-processed items (re-extract EXIF data)
import-processor thumbnails --reprocess
```

## Configuration

Copy `.env.example` to `.env` and configure:

- **DB_HOST**, **DB_PORT**, **DB_NAME**, **DB_USER**, **DB_PASSWORD** - PostgreSQL connection (required for both commands)
- **WHATSAPP_DIRECTORY_PATH** - Path to WhatsApp export directory (optional if using `--path`)
- **IMESSAGE_DIRECTORY_PATH** - Path to iMessage export directory (optional if using `--path`)
- **FACEBOOK_DIRECTORY_PATH** - Path to Facebook Messenger export directory (optional if using `--path`)
- **FACEBOOK_ALBUMS_DIRECTORY_PATH** - Path to Facebook albums (e.g. `your_facebook_activity/posts`) (optional if using `--path`)
- **FACEBOOK_PLACES_PATH** - Path to Facebook posts JSON file or directory (optional if using `--path`)
- **INSTAGRAM_DIRECTORY_PATH** - Path to Instagram messages directory (optional if using `--path`)
- **FILESYSTEM_IMPORT_DIRECTORIES** - Comma-separated paths for filesystem import (optional if using `--path`)
- **FILESYSTEM_EXCLUDE_PATTERNS** - Comma-separated exclude patterns (optional)

## Build

```bash
go build -o import-processor ./cmd/import-processor
```

## Dependencies

- PostgreSQL (pgx driver)
- ImageMagick (`magick` command) - required for thumbnail processing
