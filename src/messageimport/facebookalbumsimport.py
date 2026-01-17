"""Facebook Albums import functionality."""

import json
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from ..database.connection import Database
from ..database.storage import FacebookAlbumStorage
from .export_root_detector import detect_facebook_export_root


def parse_timestamp_ms(timestamp_ms: Optional[int]) -> Optional[datetime]:
    """Parse Unix timestamp in milliseconds to datetime object."""
    if not timestamp_ms:
        return None
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0)
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not parse timestamp '{timestamp_ms}': {e}")
        return None


def find_image_file(base_dir: Path, uri: str, export_root: Optional[Path] = None, auto_detect_root: bool = True) -> Optional[Path]:
    """Find image file by URI. URIs are relative to export root.
    
    Args:
        base_dir: Base directory (album directory)
        uri: URI from Facebook export (relative path)
        export_root: Optional export root directory for absolute URIs
        auto_detect_root: If True and export_root is None, attempt to auto-detect export root
        
    Returns:
        Path to image file if found, None otherwise
    """
    # Auto-detect export root if not provided
    detected_root = export_root
    if not detected_root and auto_detect_root:
        detected_root = detect_facebook_export_root(base_dir, uri)
        if detected_root:
            print(f"Auto-detected Facebook export root: {detected_root}")
    
    # Try relative to export root if provided or detected
    if detected_root:
        export_path = detected_root / uri
        if export_path.exists() and export_path.is_file():
            return export_path
    
    # Try relative to base directory
    relative_path = base_dir / uri
    if relative_path.exists() and relative_path.is_file():
        return relative_path
    
    # Try with just filename
    filename = Path(uri).name
    filename_path = base_dir / filename
    if filename_path.exists() and filename_path.is_file():
        return filename_path
    
    # Search for files ending with the filename
    for file_path in base_dir.rglob(filename):
        if file_path.is_file():
            return file_path
    
    return None


def guess_mime_type(filename: str) -> Optional[str]:
    """Guess MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def read_image_file(image_path: Path, uri: str) -> tuple[Optional[str], Optional[str], Optional[bytes]]:
    """Read image file and return filename, MIME type, and binary data.
    
    Returns:
        tuple: (filename, mime_type, data)
    """
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        filename = Path(uri).name
        mime_type = guess_mime_type(filename) or "image/jpeg"
        return filename, mime_type, image_data
    except Exception as e:
        print(f"Warning: Could not read image file {image_path}: {e}")
        return None, None, None


def import_facebook_albums_from_directory(
    directory_path: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
    export_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import Facebook albums from a directory structure.
    
    The directory should contain JSON files in an 'album' subdirectory.
    Each JSON file represents an album with photos.
    
    Args:
        directory_path: Path to the directory containing album JSON files (or the album subdirectory)
        progress_callback: Optional callback function called after each album is processed.
                          Receives a dict with current stats including missing_attachment_filenames.
        cancelled_check: Optional function to check if import should be cancelled.
                        Should return True if cancelled.
        export_root: Optional path to Facebook export root directory (for resolving image URIs)
        
    Returns:
        dict: Statistics about the import process
    """
    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory does not exist or is not a directory: {directory_path}")
    
    # Auto-detect export root if not provided
    export_root_path = None
    if export_root:
        export_root_path = Path(export_root)
    else:
        # Try to auto-detect export root from directory structure
        export_root_path = detect_facebook_export_root(directory)
        if export_root_path:
            print(f"Auto-detected Facebook export root: {export_root_path}")
    
    # Check if directory_path is the album subdirectory or contains it
    album_dir = directory
    if (directory / "album").exists() and (directory / "album").is_dir():
        album_dir = directory / "album"
    
    storage = FacebookAlbumStorage()
    
    # Count total albums first
    json_files = list(album_dir.glob("*.json"))
    total_albums = len(json_files)
    
    stats = {
        "albums_processed": 0,
        "total_albums": total_albums,
        "albums_imported": 0,
        "images_imported": 0,
        "images_found": 0,
        "images_missing": 0,
        "missing_image_filenames": [],
        "errors": 0,
    }
    
    # Iterate through JSON files
    for json_file in json_files:
        # Check for cancellation
        if cancelled_check and cancelled_check():
            print("Facebook Albums import cancelled by user")
            break
        
        stats["albums_processed"] += 1
        stats["current_album"] = json_file.name
        
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                
                # Extract album data
                album_name = data.get('name', json_file.stem)
                album_description = data.get('description')
                
                # Extract cover photo URI
                cover_photo = data.get('cover_photo', {})
                cover_photo_uri = cover_photo.get('uri') if cover_photo else None
                
                # Extract last modified timestamp
                last_modified_timestamp_ms = data.get('last_modified_timestamp')
                last_modified_timestamp = parse_timestamp_ms(last_modified_timestamp_ms)
                
                # Save album to database
                album_id, _ = storage.save_album(
                    name=album_name,
                    description=album_description,
                    cover_photo_uri=cover_photo_uri,
                    last_modified_timestamp=last_modified_timestamp
                )
                
                stats["albums_imported"] += 1
                
                # Process photos
                photos = data.get('photos', [])
                
                for photo in photos:
                    try:
                        uri = photo.get('uri', '')
                        if not uri:
                            continue
                        
                        # Find image file
                        image_path = find_image_file(album_dir, uri, export_root_path)
                        
                        # Try .heic -> .jpg fallback
                        if not image_path and uri.lower().endswith('.heic'):
                            jpg_uri = uri[:-5] + '.jpg'
                            image_path = find_image_file(album_dir, jpg_uri, export_root_path)
                            if image_path:
                                uri = jpg_uri
                        
                        # Try .opus -> .mp3 fallback (though unlikely for images)
                        if not image_path and uri.lower().endswith('.opus'):
                            mp3_uri = uri[:-5] + '.mp3'
                            image_path = find_image_file(album_dir, mp3_uri, export_root_path)
                            if image_path:
                                uri = mp3_uri
                        
                        # Read image file if found
                        filename = None
                        image_type = None
                        image_data = None
                        
                        if image_path and image_path.exists():
                            filename, image_type, image_data = read_image_file(image_path, uri)
                            
                            if image_data:
                                stats["images_found"] += 1
                            else:
                                missing_filename = f"{album_name}/{Path(uri).name}"
                                stats["images_missing"] += 1
                                if missing_filename not in stats["missing_image_filenames"]:
                                    stats["missing_image_filenames"].append(missing_filename)
                        else:
                            missing_filename = f"{album_name}/{Path(uri).name}"
                            stats["images_missing"] += 1
                            if missing_filename not in stats["missing_image_filenames"]:
                                stats["missing_image_filenames"].append(missing_filename)
                        
                        # Extract photo metadata
                        creation_timestamp_ms = photo.get('creation_timestamp')
                        creation_timestamp = parse_timestamp_ms(creation_timestamp_ms)
                        title = photo.get('title')
                        description = photo.get('description')
                        
                        # Save image to database (only if we have at least a URI)
                        # Note: image_data and image_type may be None if file wasn't found
                        storage.save_album_image(
                            album_id=album_id,
                            uri=uri,
                            filename=filename,
                            creation_timestamp=creation_timestamp,
                            title=title,
                            description=description,
                            image_data=image_data,  # May be None if file not found
                            image_type=image_type   # May be None if file not found
                        )
                        
                        stats["images_imported"] += 1
                        
                    except Exception as e:
                        print(f"Error processing photo: {e}")
                        import traceback
                        traceback.print_exc()
                        stats["errors"] += 1
                        continue
                        
        except Exception as e:
            print(f"Error reading JSON file {json_file}: {e}")
            import traceback
            traceback.print_exc()
            stats["errors"] += 1
            continue
        
        # Call progress callback after each album is processed
        if progress_callback:
            progress_callback(stats.copy())
    
    return stats


def main():
    """Main function for testing the import."""
    # Initialize database connection and create tables
    db = Database()
    db.create_tables()
    
    # Test directory path - update this to your actual directory
    test_directory = r"G:\My Drive\meta-2026-Jan-11-23-20-25\facebook-daveontour-2026-01-11-MnAtpBDv\your_facebook_activity\posts"
    export_root = r"G:\My Drive\meta-2026-Jan-11-23-20-25\facebook-daveontour-2026-01-11-MnAtpBDv"
    
    print(f"Starting Facebook Albums import from: {test_directory}")
    print("-" * 60)
    
    try:
        stats = import_facebook_albums_from_directory(
            test_directory,
            export_root=export_root
        )
        
        print("-" * 60)
        print("Import completed!")
        print(f"Albums processed: {stats['albums_processed']}")
        print(f"Albums imported: {stats['albums_imported']}")
        print(f"Images imported: {stats['images_imported']}")
        print(f"Images found: {stats['images_found']}")
        print(f"Images missing: {stats['images_missing']}")
        print(f"Errors: {stats['errors']}")
        
    except Exception as e:
        print(f"Import failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
