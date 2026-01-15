"""Email service for business logic."""

from typing import List, Callable, Optional
import threading

from ..loader import EmailDatabaseLoader
from .exceptions import ConflictError, ValidationError


class EmailService:
    """Service for email-related business logic."""

    def __init__(
        self,
        get_processing_state: Optional[Callable[[], bool]] = None,
        set_processing_state: Optional[Callable[[bool], None]] = None,
        cancellation_event: Optional[threading.Event] = None,
        processing_lock: Optional[threading.Lock] = None
    ):
        """Initialize email service.
        
        Args:
            get_processing_state: Function that returns current processing_in_progress state
            set_processing_state: Function that sets processing_in_progress state
            cancellation_event: threading.Event for cancellation flag
            processing_lock: threading.Lock for thread-safe state access
        """
        self._get_processing_state = get_processing_state
        self._set_processing_state = set_processing_state
        self._cancellation_event = cancellation_event
        self._processing_lock = processing_lock

    def can_start_processing(self) -> bool:
        """Check if email processing can start.
        
        Returns:
            True if processing can start, False otherwise
            
        Raises:
            ConflictError: If processing is already in progress
        """
        if self._processing_lock:
            with self._processing_lock:
                if self._get_processing_state and self._get_processing_state():
                    raise ConflictError(
                        "Email processing is already in progress. Please cancel it first or wait for it to complete."
                    )
        elif self._get_processing_state and self._get_processing_state():
            raise ConflictError(
                "Email processing is already in progress. Please cancel it first or wait for it to complete."
            )
        return True

    def determine_labels_to_process(
        self,
        labels: List[str] = None,
        all_folders: bool = False,
        loader: EmailDatabaseLoader = None
    ) -> List[str]:
        """Determine which labels to process.
        
        Args:
            labels: Optional list of specific labels to process
            all_folders: If True, fetch all folders from email server
            loader: EmailDatabaseLoader instance for fetching labels
            
        Returns:
            List of label names to process
            
        Raises:
            ValidationError: If neither labels nor all_folders is provided, or no labels found
        """
        labels_to_process = []
        
        if all_folders:
            if not loader:
                raise ValidationError("Loader is required when all_folders is True")
            
            # Fetch all folders from the email server
            try:
                all_labels = loader.client.get_labels()
                # Extract label names, excluding system labels that shouldn't be processed
                # (like CHAT, SENT, DRAFT, etc. - but we'll include all user labels)
                labels_to_process = [label.get("name") for label in all_labels if label.get("name")]
            except Exception as e:
                raise ValidationError(f"Failed to retrieve folders from email server: {str(e)}")
        elif labels:
            labels_to_process = labels
        else:
            raise ValidationError("Either 'labels' must be provided or 'all_folders' must be set to true")
        
        if not labels_to_process:
            raise ValidationError("No labels found to process")
        
        return labels_to_process

    def cancel_processing(self) -> bool:
        """Cancel email processing if it is in progress.
        
        Returns:
            True if cancellation was requested, False if no processing was in progress
        """
        if self._processing_lock:
            with self._processing_lock:
                if self._get_processing_state and not self._get_processing_state():
                    return False
                
                # Set cancellation flag
                if self._cancellation_event:
                    self._cancellation_event.set()
                return True
        else:
            if self._get_processing_state and not self._get_processing_state():
                return False
            
            # Set cancellation flag
            if self._cancellation_event:
                self._cancellation_event.set()
            return True
