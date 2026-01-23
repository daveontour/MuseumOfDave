"""
Main entry point for Museum of Dave application.
Creates database tables and starts the API server.
"""

from sys import platform
from googleapiclient.discovery import os
import uvicorn
from src.database import Database
from src.config import get_config
from src.api import app

import shutil
import subprocess


def main():
    """Main function - initialize database and start API server."""
    print("Initializing Museum of Dave application...")
    
    # Initialize database and create tables
    config = get_config()
    db = Database(config)
    db.create_tables()
    print("Database tables created/verified.")
    
    # Initialize subject configuration from files
    from src.services.subject_configuration_service import SubjectConfigurationService
    config_service = SubjectConfigurationService(db=db)
    config_service.initialize_from_files()
    print("Subject configuration initialized from files.")
    
    # Start the API server
    print("Starting API server on http://0.0.0.0:8000")
    print("API documentation available at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)

def _find_imagemagick_command():
        """Find ImageMagick executable in system PATH.
        
        Returns:
            Path to ImageMagick executable or None if not found
        """
        # Try common ImageMagick command names
        commands = ["magick", "magick.exe", "convert"]
        
        # for cmd in commands:
        #     path = shutil.which(cmd)
        #     if path:
        #         return path
        
        # On Windows, also try common installation paths

        common_paths = [
            r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe",
            r"C:\Program Files\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
            r"C:\Program Files\ImageMagick-7.0.11-Q16-HDRI\magick.exe",
            r"C:\Program Files (x86)\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
            r"C:\Program Files (x86)\ImageMagick-7.1.0-Q16-HDRI\magick.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        return None

def test_imagemagick():
    # 1. Ask Python where it thinks 'magick' is
    path = _find_imagemagick_command()
    print(f"Python sees 'magick' at: {path}")

    # 2. Ask Python where it thinks 'convert' is
    path_convert = shutil.which("convert")
    print(f"Python sees 'convert' at: {path_convert}")

    # 3. Try to run the version check
    try:
        # If this prints the Windows File System tool help text, you have the wrong one.
        result = subprocess.run(["magick", "-version"], capture_output=True, text=True)
        print("\n--- Command Output ---")
        print(result.stdout)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    #test_imagemagick()
    main()
