"""Filesystem image import functionality."""

import os
import mimetypes
import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from io import BytesIO

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Try to register HEIF/HEIC support if pillow-heif is available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

from ..database.connection import Database
from ..database.storage import ImageStorage


def get_image_extensions() -> List[str]:
    """Get list of image file extensions supported by Pillow."""
    # Pillow supports many formats
    return [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
        '.webp', '.ico', '.heic', '.heif', '.avif', '.jp2', '.j2k',
        '.jpf', '.jpx', '.j2c', '.jpc', '.pcx', '.dcx', '.psd',
        '.xbm', '.xpm', '.cur', '.svg', '.eps', '.pdf'
    ]


def extract_exif_data(image_path: Path) -> Dict[str, Any]:
    """Extract EXIF data from image file.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Dictionary with extracted EXIF data including:
        - year, month: Date taken
        - latitude, longitude, altitude: GPS coordinates
        - has_gps: Boolean indicating if GPS data exists
        - title, description, author: Image metadata
    """
    exif_data = {
        'year': None,
        'month': None,
        'latitude': None,
        'longitude': None,
        'altitude': None,
        'has_gps': False,
        'title': None,
        'description': None,
        'author': None
    }
    
    try:
        with Image.open(image_path) as img:
            # Try to get EXIF data
            exif = None
            if hasattr(img, '_getexif'):
                exif = img._getexif()
            elif hasattr(img, 'getexif'):
                exif = img.getexif()
            
            # Check if exif is valid and dictionary-like
            if not exif:
                return exif_data
            
            # Ensure exif is a dictionary-like object
            if not hasattr(exif, 'items'):
                # If exif is not dictionary-like, try to convert or skip
                return exif_data
            
            # Process EXIF tags
            try:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Extract date taken
                    if tag == 'DateTime' or tag == 'DateTimeOriginal':
                        try:
                            date_str = str(value)
                            # Format: "YYYY:MM:DD HH:MM:SS"
                            if ':' in date_str:
                                parts = date_str.split(' ')
                                if len(parts) > 0:
                                    date_parts = parts[0].split(':')
                                    if len(date_parts) >= 2:
                                        exif_data['year'] = int(date_parts[0])
                                        exif_data['month'] = int(date_parts[1])
                        except (ValueError, AttributeError):
                            pass
                    
                    # Extract title/description/author
                    if tag == 'ImageDescription':
                        exif_data['description'] = str(value) if value else None
                    elif tag == 'XPComment' or tag == 'UserComment':
                        if not exif_data['description']:
                            exif_data['description'] = str(value) if value else None
                    elif tag == 'Artist' or tag == 'Copyright':
                        exif_data['author'] = str(value) if value else None
                    elif tag == 'DocumentName':
                        exif_data['title'] = str(value) if value else None
            except (AttributeError, TypeError) as e:
                # If items() fails or exif structure is unexpected, skip EXIF processing
                pass
            
            # Extract GPS data
            try:
                if hasattr(exif, 'get'):
                    gps_info = exif.get(34853)  # GPSInfo tag
                else:
                    gps_info = None
                
                if gps_info and hasattr(gps_info, 'items'):
                    gps_data = {}
                    for key, value in gps_info.items():
                        tag = GPSTAGS.get(key, key)
                        gps_data[tag] = value
                    
                    # Convert GPS coordinates to decimal degrees
                    if 'GPSLatitude' in gps_data and 'GPSLatitudeRef' in gps_data:
                        lat = _convert_to_degrees(gps_data['GPSLatitude'])
                        if lat is not None:
                            if gps_data['GPSLatitudeRef'] == 'S':
                                lat = -lat
                            exif_data['latitude'] = lat
                    
                    if 'GPSLongitude' in gps_data and 'GPSLongitudeRef' in gps_data:
                        lon = _convert_to_degrees(gps_data['GPSLongitude'])
                        if lon is not None:
                            if gps_data['GPSLongitudeRef'] == 'W':
                                lon = -lon
                            exif_data['longitude'] = lon
                    
                    if 'GPSAltitude' in gps_data:
                        try:
                            exif_data['altitude'] = float(gps_data['GPSAltitude'])
                        except (ValueError, TypeError):
                            pass
                    
                    # Set has_gps if we have coordinates
                    if exif_data['latitude'] is not None and exif_data['longitude'] is not None:
                        exif_data['has_gps'] = True
            except (AttributeError, TypeError):
                # If GPS extraction fails, continue without GPS data
                pass
                    
    except Exception as e:
        print(f"Warning: Could not extract EXIF data from {image_path}: {e}")
    
    return exif_data


def _convert_to_degrees(value):
    """Convert GPS coordinate to decimal degrees.
    
    Args:
        value: Tuple of (degrees, minutes, seconds) or (degrees, minutes)
        
    Returns:
        Decimal degrees
    """
    try:
        d, m, s = value[0], value[1], value[2] if len(value) > 2 else 0
        return float(d) + float(m) / 60.0 + float(s) / 3600.0
    except (ValueError, TypeError, IndexError):
        return None


def generate_directory_tags(file_path: Path, root_directory: Path) -> str:
    """Generate comma-separated tags from directory structure.
    
    Args:
        file_path: Full path to the image file
        root_directory: Root directory for import
        
    Returns:
        Comma-separated string of directory names from root to file
    """
    try:
        # Get relative path from root
        relative_path = file_path.relative_to(root_directory)
        # Get parent directory
        parent_dir = relative_path.parent
        
        if parent_dir == Path('.'):
            return ''
        
        # Split into parts and filter out empty strings
        parts = [part for part in parent_dir.parts if part]
        return ','.join(parts)
    except (ValueError, AttributeError):
        return ''


def create_thumbnail(image_data: bytes, max_size: int = 100) -> Optional[bytes]:
    """Create a thumbnail from image data.
    
    Args:
        image_data: Binary image data
        max_size: Maximum width/height for thumbnail (default: 100)
        
    Returns:
        Binary thumbnail data as JPEG, or None if creation fails
    """
    try:
        # Open image from bytes
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if necessary
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        
        # Calculate thumbnail size maintaining aspect ratio
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # Save to bytes as JPEG
        thumbnail_bytes = BytesIO()
        img.save(thumbnail_bytes, format="JPEG", quality=85)
        thumbnail_bytes.seek(0)
        
        return thumbnail_bytes.getvalue()
    except Exception as e:
        print(f"Warning: Could not create thumbnail: {e}")
        return None


def _should_exclude_directory(directory_path: Path, exclude_patterns: List[str]) -> bool:
    """Check if a directory should be excluded based on patterns.
    
    Args:
        directory_path: Path to the directory to check
        exclude_patterns: List of patterns to match against (supports wildcards * and ?)
        
    Returns:
        True if directory should be excluded, False otherwise
    """
    if not exclude_patterns:
        return False
    
    directory_str = str(directory_path)
    directory_name = directory_path.name
    
    for pattern in exclude_patterns:
        # Check if pattern matches directory name or any part of the path
        if fnmatch.fnmatch(directory_name, pattern) or fnmatch.fnmatch(directory_str, pattern):
            return True
        # Also check if pattern appears anywhere in the path
        if pattern in directory_str:
            return True
    
    return False


def import_images_from_filesystem(
    root_directory: str,
    max_images: Optional[int] = None,
    should_create_thumbnail: bool = False,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
    exclude_patterns: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Import images from filesystem directory.
    
    Args:
        root_directory: Root directory to search for images
        max_images: Maximum number of images to import (None for all)
        should_create_thumbnail: Whether to generate thumbnails
        progress_callback: Optional callback function called after each image is processed
        cancelled_check: Optional function to check if import should be cancelled
        exclude_patterns: Optional list of directory patterns to exclude (supports wildcards * and ?)
        
    Returns:
        Dictionary with import statistics
    """
    root_path = Path(root_directory)
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Directory does not exist or is not a directory: {root_directory}")
    
    storage = ImageStorage()
    image_extensions = get_image_extensions()
    
    # Default exclude_patterns to empty list if not provided
    if exclude_patterns is None:
        exclude_patterns = []
    
    stats = {
        'total_files': 0,
        'files_processed': 0,
        'images_imported': 0,
        'images_updated': 0,
        'errors': 0,
        'error_messages': [],
        'current_file': None
    }
    
    # Track files per directory
    files_per_directory = {}
    
    # First pass: count total files
    for file_path in root_path.rglob('*'):
        #ignore any directory path which have a . in the path name

        if ".photostructure" in file_path.parent.name:
            continue
        if "._" in file_path.name:
            continue
        if "Thumbs.db" in file_path.name:
            continue
        if "desktop.ini" in file_path.name:
            continue
        if "ehthumbs.db" in file_path.name:
            continue
        if "ehthumbs.db-shm" in file_path.name:
            continue
        
        # Check if directory should be excluded
        if exclude_patterns and _should_exclude_directory(file_path.parent, exclude_patterns):
            continue

        if file_path.is_file() and file_path.suffix.lower() in image_extensions:
            stats['total_files'] += 1
            # Track per directory
            directory = str(file_path.parent)
            files_per_directory[directory] = files_per_directory.get(directory, 0) + 1
    
    # Print files per directory
    print("\nFiles per directory:")
    print("-" * 80)
    for directory, count in sorted(files_per_directory.items(), key=lambda item: item[1], reverse=True):
        print(f"{directory}: {count} file(s)")
    print("-" * 80)
    print(f"Total files: {stats['total_files']}\n")
    
    # Second pass: process images
    images_processed = 0
    for file_path in root_path.rglob('*'):
        # Check for cancellation
        if cancelled_check and cancelled_check():
            stats['status'] = 'cancelled'
            break

        if ".photostructure" in file_path.parent.name:
            continue
        if "._" in file_path.parent.name:
            continue
        if "Thumbs.db" in file_path.parent.name:
            continue
        if "desktop.ini" in file_path.parent.name:
            continue
        if "ehthumbs.db" in file_path.parent.name:
            continue
        if "ehthumbs.db-shm" in file_path.parent.name:
            continue
        
        # Check if directory should be excluded
        if exclude_patterns and _should_exclude_directory(file_path.parent, exclude_patterns):
            continue
        
        # Check max_images limit
        if max_images and images_processed >= max_images:
            break
        
        if not file_path.is_file():
            continue
        
        if file_path.suffix.lower() not in image_extensions:
            continue
        
        stats['current_file'] = str(file_path)
        stats['files_processed'] += 1
        
        try:
            # Read image data
            with open(file_path, 'rb') as f:
                image_data = f.read()
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = f"image/{file_path.suffix[1:].lower()}"
            
            # Extract EXIF data
            exif_data = extract_exif_data(file_path)
            
            # Generate thumbnail if requested
            thumbnail_data = None
            if should_create_thumbnail:
                try:
                    thumbnail_data = create_thumbnail(image_data)
                except Exception as thumb_error:
                    # If thumbnail creation fails, log but continue without thumbnail
                    print(f"Warning: Could not create thumbnail for {file_path}: {thumb_error}")
                    thumbnail_data = None
            
            # Generate directory tags
            tags = generate_directory_tags(file_path, root_path)
            
            # Save or update image
            metadata, is_update = storage.save_image(
                source_reference=str(file_path.absolute()),
                image_data=image_data,
                thumbnail_data=thumbnail_data,
                media_type=mime_type,
                title=file_path.stem,
                description=exif_data.get('description'),
                tags=tags,
                year=exif_data.get('year'),
                month=exif_data.get('month'),
                latitude=exif_data.get('latitude'),
                longitude=exif_data.get('longitude'),
                altitude=exif_data.get('altitude'),
                has_gps=exif_data.get('has_gps', False),
                source="Filesystem"
            )
            
            if is_update:
                stats['images_updated'] += 1
            else:
                stats['images_imported'] += 1
            
            images_processed += 1
            
            # Call progress callback
            if progress_callback:
                progress_callback(stats.copy())
                
        except Exception as e:
            error_msg = f"Error processing {file_path}: {str(e)}"
            print(error_msg)
            stats['errors'] += 1
            stats['error_messages'].append(error_msg)
            
            # Call progress callback even on error
            if progress_callback:
                progress_callback(stats.copy())
    
    stats['status'] = 'completed'
    return stats
