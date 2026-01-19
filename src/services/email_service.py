"""Email service for business logic."""

from typing import List, Callable, Optional, Dict, Any
import threading

from ..loader import EmailDatabaseLoader
from ..database import Database
from ..database.models import Email
from sqlalchemy import or_
from .exceptions import ConflictError, ValidationError, NotFoundError


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

    def get_conversation_messages(self, participant_email: str, db: Optional[Database] = None) -> Dict[str, Any]:
        """Get formatted conversation messages for a participant email address.
        
        Args:
            participant_email: Email address to search for (in from_address or to_addresses)
            db: Optional Database instance. If not provided, creates a new one.
            
        Returns:
            Dictionary with chat_session, message_count, and messages list
            
        Raises:
            NotFoundError: If no emails found for the participant
        """
        if db is None:
            db = Database()
        
        session = db.get_session()
        try:
            emails = session.query(Email).filter(
                or_(
                    Email.from_address.like(f"%{participant_email}%"),
                    Email.to_addresses.like(f"%{participant_email}%")
                )
            ).order_by(
                Email.date.asc()
            ).all()
            
            if not emails:
                raise NotFoundError(f"No emails found for person: {participant_email}")
            
            # Format messages into structured JSON
            messages_data = {
                "chat_session": participant_email,
                "message_count": len(emails),
                "messages": []
            }
            
            for email in emails:
                messages_data["messages"].append({
                    "message_date": email.date.isoformat() if email.date else None,
                    "sender_name": email.from_address or "Unknown",
                    "type": "Incoming" if email.to_addresses and participant_email in (email.to_addresses or "") else "Outgoing",
                    "text": email.plain_text or email.snippet or "",
                    "has_attachment": email.has_attachments or False
                })
            
            return messages_data
        finally:
            session.close()
