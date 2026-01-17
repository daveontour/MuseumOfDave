"""Export root detection utility for import functions."""

from pathlib import Path
from typing import Optional


def detect_export_root_by_marker(directory_path: Path, marker: str, uri: Optional[str] = None) -> Optional[Path]:
    """Detect export root by searching for marker directory.
    
    Searches upward from directory_path to find a directory containing the marker.
    If URI is provided, validates the detected root by checking if the URI path exists.
    
    Args:
        directory_path: Starting directory to search from
        marker: Directory name to search for (e.g., 'your_facebook_activity')
        uri: Optional URI to validate the found root
        
    Returns:
        Path to export root if found, None otherwise
    """
    if not directory_path or not marker:
        return None
    
    current = directory_path.resolve()
    max_levels = 10  # Prevent infinite loops
    
    # Strategy 1: Search upward for marker directory
    for _ in range(max_levels):
        marker_path = current / marker
        if marker_path.exists() and marker_path.is_dir():
            # Validate if URI provided
            if uri:
                test_path = current / uri
                if test_path.exists() and test_path.is_file():
                    return current
                # Also check if URI path exists as directory (for nested structures)
                test_path_dir = current / uri
                if test_path_dir.exists() and test_path_dir.is_dir():
                    return current
            else:
                # No URI to validate, return first match
                return current
        
        # Check if we've reached filesystem root
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent
    
    # Strategy 2: If URI provided, try to infer from URI structure
    if uri and marker in uri:
        # Split URI at marker to find potential root
        parts = uri.split(marker, 1)
        if len(parts) > 0 and parts[0]:
            # Try to find the directory that contains the marker
            # The part before marker might be relative path segments
            uri_prefix = parts[0].rstrip('/')
            if uri_prefix:
                # Search upward looking for a directory that, when combined with URI prefix, contains marker
                current = directory_path.resolve()
                for _ in range(max_levels):
                    # Try different combinations
                    test_root = current
                    if uri_prefix.startswith('/'):
                        # Absolute path segment
                        test_marker = Path(uri_prefix.lstrip('/')) / marker
                    else:
                        # Relative path segment
                        test_marker = current / uri_prefix / marker
                    
                    if test_marker.exists() and test_marker.is_dir():
                        # Found marker, now find the root
                        # The root should be the directory that contains the marker
                        marker_parent = test_marker.parent
                        # Work backwards to find where marker_prefix ends
                        if uri_prefix:
                            prefix_parts = uri_prefix.strip('/').split('/')
                            for part in reversed(prefix_parts):
                                if marker_parent.name == part:
                                    marker_parent = marker_parent.parent
                            return marker_parent
                        return marker_parent
                    
                    parent = current.parent
                    if parent == current:
                        break
                    current = parent
    
    return None


def detect_facebook_export_root(directory_path: Path, uri: Optional[str] = None) -> Optional[Path]:
    """Detect Facebook export root by searching upward from directory_path.
    
    Strategy:
    1. Search upward for directory containing 'your_facebook_activity'
    2. Validate by checking if URI path exists relative to found root
    3. Try common parent directories if direct search fails
    
    Args:
        directory_path: Starting directory to search from
        uri: Optional URI to validate the found root
        
    Returns:
        Path to export root if found, None otherwise
    """
    return detect_export_root_by_marker(directory_path, 'your_facebook_activity', uri)


def detect_instagram_export_root(directory_path: Path, uri: Optional[str] = None) -> Optional[Path]:
    """Detect Instagram export root by searching upward from directory_path.
    
    Strategy:
    1. Search upward for directory containing 'your_instagram_activity'
    2. Validate by checking if URI path exists relative to found root
    3. Handle both 'inbox' and 'inboxtest' variations
    
    Args:
        directory_path: Starting directory to search from
        uri: Optional URI to validate the found root
        
    Returns:
        Path to export root if found, None otherwise
    """
    # First try standard detection
    root = detect_export_root_by_marker(directory_path, 'your_instagram_activity', uri)
    
    if root:
        return root
    
    # If URI provided and detection failed, try with inbox/inboxtest variations
    if uri:
        # Try replacing inbox with inboxtest or vice versa
        uri_variations = [uri]
        if '/inbox/' in uri:
            uri_variations.append(uri.replace('/inbox/', '/inboxtest/'))
        elif '/inboxtest/' in uri:
            uri_variations.append(uri.replace('/inboxtest/', '/inbox/'))
        
        for uri_var in uri_variations:
            root = detect_export_root_by_marker(directory_path, 'your_instagram_activity', uri_var)
            if root:
                return root
    
    return None
