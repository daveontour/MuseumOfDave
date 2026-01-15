"""Configuration management."""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    from dotenv import load_dotenv, find_dotenv
    
    # Try to find .env file using multiple strategies
    env_path = None
    
    # Method 1: Use find_dotenv() which searches from current directory up to root
    try:
        env_path = find_dotenv(raise_error_if_not_found=False)
    except Exception:
        pass
    
    # Method 2: Try project root (go up from this file)
    if not env_path or not Path(env_path).exists():
        try:
            project_root = Path(__file__).resolve().parent.parent
            candidate = project_root / ".env"
            if candidate.exists():
                env_path = str(candidate)
        except Exception:
            pass
    
    # Method 3: Try workspace folder from environment (set by VS Code)
    if not env_path or not Path(env_path).exists():
        workspace_folder = os.getenv("VSCODE_WORKSPACE_FOLDER") or os.getenv("WORKSPACE_FOLDER")
        if workspace_folder:
            candidate = Path(workspace_folder) / ".env"
            if candidate.exists():
                env_path = str(candidate)
    
    # Method 4: Try current working directory
    if not env_path or not Path(env_path).exists():
        candidate = Path.cwd() / ".env"
        if candidate.exists():
            env_path = str(candidate)
    
    # Load the .env file if found
    if env_path and Path(env_path).exists():
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        # Final fallback: try default behavior (searches from current directory)
        result = load_dotenv(override=True)
        # If still not found, try one more time with explicit path from cwd
        if not result:
            cwd_env = Path.cwd() / ".env"
            if cwd_env.exists():
                load_dotenv(dotenv_path=str(cwd_env), override=True)
except ImportError:
    pass


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def connection_string(self) -> str:
        """Get SQLAlchemy connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

@dataclass
class AttachmentConfig:
    """Attachment filtering configuration."""
    allowed_types: Optional[list] = None  # List of allowed file extensions or MIME types
    min_size: int = 0  # Minimum size in bytes (0 = no minimum)


class Config:
    """Main configuration class."""

    def __init__(self):
        """Load configuration from environment variables."""
        self.db = self._load_database_config()
        self.attachments = self._load_attachment_config()

    def _load_database_config(self) -> DatabaseConfig:
        """Load database configuration from environment."""
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")

        if not all([host, name, user, password]):
            raise ValueError(
                "Missing required database configuration. "
                "Set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD environment variables."
            )

        try:
            port_int = int(port)
        except ValueError:
            raise ValueError(f"DB_PORT must be an integer, got: {port}")

        return DatabaseConfig(
            host=host,
            port=port_int,
            name=name,
            user=user,
            password=password,
        )

    def _load_attachment_config(self) -> AttachmentConfig:
        """Load attachment filtering configuration from environment."""
        # Parse allowed types (comma-separated list)
        allowed_types_str = os.getenv("ATTACHMENT_ALLOWED_TYPES", "").strip()
        allowed_types = None
        if allowed_types_str:
            # Split by comma and strip whitespace
            allowed_types = [t.strip().lower() for t in allowed_types_str.split(",") if t.strip()]
            if not allowed_types:  # Empty list after filtering
                allowed_types = None

        # Parse minimum size (in bytes)
        min_size_str = os.getenv("ATTACHMENT_MIN_SIZE", "0").strip()
        try:
            min_size = int(min_size_str)
            if min_size < 0:
                raise ValueError("ATTACHMENT_MIN_SIZE must be non-negative")
        except ValueError:
            raise ValueError(f"ATTACHMENT_MIN_SIZE must be an integer, got: {min_size_str}")

        return AttachmentConfig(
            allowed_types=allowed_types,
            min_size=min_size,
        )

    def get_control_defaults(self) -> dict:
        """Get default values for control tab inputs from environment variables."""
        return {
            # Email Controls
            "process_all_folders": os.getenv("DEFAULT_PROCESS_ALL_FOLDERS", "false").lower() == "true",
            "new_only_option": os.getenv("DEFAULT_NEW_ONLY_OPTION", "true").lower() == "true",
            
            # WhatsApp Import
            "whatsapp_import_directory": os.getenv("DEFAULT_WHATSAPP_IMPORT_DIRECTORY", ""),
            
            # Facebook Messenger Import
            "facebook_import_directory": os.getenv("DEFAULT_FACEBOOK_IMPORT_DIRECTORY", ""),
            "facebook_export_root": os.getenv("DEFAULT_FACEBOOK_EXPORT_ROOT", ""),
            "facebook_user_name": os.getenv("DEFAULT_FACEBOOK_USER_NAME", ""),
            
            # Instagram Import
            "instagram_import_directory": os.getenv("DEFAULT_INSTAGRAM_IMPORT_DIRECTORY", ""),
            "instagram_export_root": os.getenv("DEFAULT_INSTAGRAM_EXPORT_ROOT", ""),
            "instagram_user_name": os.getenv("DEFAULT_INSTAGRAM_USER_NAME", ""),
            
            # iMessage Import
            "imessage_directory_path": os.getenv("DEFAULT_IMESSAGE_DIRECTORY_PATH", ""),
            
            # Facebook Albums Import
            "facebook_albums_import_directory": os.getenv("DEFAULT_FACEBOOK_ALBUMS_IMPORT_DIRECTORY", ""),
            "facebook_albums_export_root": os.getenv("DEFAULT_FACEBOOK_ALBUMS_EXPORT_ROOT", ""),
            
            # Filesystem Image Import
            "filesystem_import_directory": os.getenv("DEFAULT_FILESYSTEM_IMPORT_DIRECTORY", ""),
            "filesystem_import_max_images": os.getenv("DEFAULT_FILESYSTEM_IMPORT_MAX_IMAGES", ""),
            "filesystem_import_create_thumbnail": os.getenv("DEFAULT_FILESYSTEM_IMPORT_CREATE_THUMBNAIL", "false").lower() == "true",
        }
    
    def get_filesystem_exclude_patterns(self) -> list:
        """Get directory exclude patterns for filesystem image import from environment variables.
        
        Returns:
            List of patterns (strings) to exclude. Patterns can contain wildcards (*, ?).
            Empty list if not configured.
        """
        exclude_patterns_str = os.getenv("FILESYSTEM_IMPORT_EXCLUDE_PATTERNS", "").strip()
        if not exclude_patterns_str:
            return []
        
        # Split by comma and strip whitespace
        patterns = [p.strip() for p in exclude_patterns_str.split(",") if p.strip()]
        return patterns


def get_config() -> Config:
    """Get configuration instance."""
    return Config()
