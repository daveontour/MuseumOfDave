"""Import service for coordination logic."""

from pathlib import Path
from typing import Callable, Optional
import threading

from .exceptions import ValidationError, ConflictError


class ImportService:
    """Service for import coordination logic."""

    def __init__(
        self,
        get_import_state: Optional[Callable[[str], bool]] = None,
        set_import_state: Optional[Callable[[str, bool], None]] = None,
        get_cancellation_event: Optional[Callable[[str], threading.Event]] = None,
        get_import_lock: Optional[Callable[[str], threading.Lock]] = None
    ):
        """Initialize import service.
        
        Args:
            get_import_state: Function that returns current import_in_progress state for a given import type
            set_import_state: Function that sets import_in_progress state for a given import type
            get_cancellation_event: Function that returns cancellation event for a given import type
            get_import_lock: Function that returns lock for a given import type
        """
        self._get_import_state = get_import_state
        self._set_import_state = set_import_state
        self._get_cancellation_event = get_cancellation_event
        self._get_import_lock = get_import_lock

    def validate_import_directory(self, directory_path: str) -> None:
        """Validate that import directory exists and is a directory.
        
        Args:
            directory_path: Path to directory to validate
            
        Raises:
            ValidationError: If directory doesn't exist or is not a directory
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise ValidationError(f"Directory does not exist: {directory_path}")
        if not directory.is_dir():
            raise ValidationError(f"Path is not a directory: {directory_path}")

    def can_start_import(self, import_type: str) -> bool:
        """Check if import can start.
        
        Args:
            import_type: Type of import ('imessage', 'whatsapp', 'facebook', 'instagram', 'facebook_albums', 'filesystem')
            
        Returns:
            True if import can start
            
        Raises:
            ConflictError: If import is already in progress
        """
        if not self._get_import_state:
            return True
        
        if self._get_import_state(import_type):
            raise ConflictError(
                f"{import_type} import is already in progress. Please cancel it first or wait for it to complete."
            )
        return True

    def cancel_import(self, import_type: str) -> bool:
        """Cancel import if it is in progress.
        
        Args:
            import_type: Type of import to cancel
            
        Returns:
            True if cancellation was requested, False if no import was in progress
        """
        if not self._get_import_state or not self._get_import_state(import_type):
            return False
        
        # Set cancellation flag
        if self._get_cancellation_event:
            event = self._get_cancellation_event(import_type)
            if event:
                event.set()
        return True
