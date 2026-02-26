import platform
import os
from pathlib import Path

def translate_path_to_container(path) -> str:
    r"""
    Translates a Windows host path (e.g., C:\Users\Fred\Photos) into
    a Linux container path (e.g., /mnt/c/Users/Fred/Photos).
    
    This only applies translation if the app is running on Linux
    but receives a path that looks like a Windows path (has a drive letter).
    Accepts str or pathlib.Path.
    """
    if path is None:
        return path
    path = str(path) if not isinstance(path, str) else path
    if not path:
        return path

    # Check if we are running on Linux (container)
    if platform.system() != 'Linux':
        return path

    # Check if input looks like a Windows path (e.g. "C:\...")
    if ':' not in path:
        return path


    clean_path = path.replace('\\', '/')
    parts = clean_path.split(':', 1)
    
    if len(parts) < 2:
        return path
        
    drive_letter = parts[0].lower()
    rest_of_path = parts[1]
    
    # Construct new path using the /mnt/ convention

    translated_path = f"/mnt/{drive_letter}{rest_of_path}"
    
    # Optional: Log the translation for debugging
    print(f"[DockerUtils] Translated path '{path}' -> '{translated_path}'")
    
    return translated_path
