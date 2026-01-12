"""Email storage operations."""

from typing import List, Set, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from .connection import Database
from .models import Email, Attachment, IMessage


class EmailStorage:
    """Handle email storage operations."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize storage with database connection."""
        if db is None:
            db = Database()
        self.db = db

    def email_exists(self, uid: str, folder: str) -> bool:
        """Check if email with given uid and folder already exists."""
        session = self.db.get_session()
        try:
            count = session.query(Email).filter(
                Email.uid == uid,
                Email.folder == folder
            ).count()
            return count > 0
        finally:
            session.close()

    def get_existing_uids(self, folder: str) -> Set[str]:
        """Get set of all UIDs already in database for a specific folder."""
        session = self.db.get_session()
        try:
            uids = session.query(Email.uid).filter(Email.folder == folder).all()
            return {uid[0] for uid in uids if uid[0] is not None}
        finally:
            session.close()

    def save_email(
        self,
        uid: str,
        folder: str,
        subject: Optional[str],
        snippet: Optional[str],
        from_address: Optional[str],
        to_addresses: Optional[str],
        cc_addresses: Optional[str],
        bcc_addresses: Optional[str],
        date: Optional[Any],
        raw_message: str,
        plain_text: Optional[str],
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Email:
        """Save email and attachments to database."""
        session = self.db.get_session()
        try:
            # Check if email already exists
            existing = session.query(Email).filter(
                Email.uid == uid,
                Email.folder == folder
            ).first()
            if existing:
                # Update existing email
                existing.subject = subject
                existing.snippet = snippet
                existing.from_address = from_address
                existing.to_addresses = to_addresses
                existing.cc_addresses = cc_addresses
                existing.bcc_addresses = bcc_addresses
                existing.date = date
                existing.raw_message = raw_message
                existing.plain_text = plain_text
                email = existing
            else:
                # Create new email
                email = Email(
                    uid=uid,
                    folder=folder,
                    subject=subject,
                    snippet=snippet,
                    from_address=from_address,
                    to_addresses=to_addresses,
                    cc_addresses=cc_addresses,
                    bcc_addresses=bcc_addresses,
                    date=date,
                    raw_message=raw_message,
                    plain_text=plain_text,
                )
                session.add(email)
                session.flush()  # Get the email ID

            # Save attachments
            has_saved_attachments = False
            if attachments:
                # Delete existing attachments if updating
                if existing:
                    session.query(Attachment).filter(Attachment.email_id == email.id).delete()

                for att_data in attachments:
                    attachment = Attachment(
                        email_id=email.id,
                        filename=att_data.get("filename"),
                        content_type=att_data.get("mimeType") or att_data.get("content_type"),
                        size=att_data.get("size"),
                        data=att_data.get("data"),  # Should already be bytes from loader
                        image_thumbnail=att_data.get("thumbnail"),  # Thumbnail if image
                    )
                    session.add(attachment)
                    has_saved_attachments = True

            # Set has_attachments flag - True only if attachments passed filter and were saved
            email.has_attachments = has_saved_attachments

            session.commit()
            return email
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_email(self, email_id: int) -> Optional[Email]:
        """Get email by ID."""
        session = self.db.get_session()
        try:
            return session.query(Email).filter(Email.id == email_id).first()
        finally:
            session.close()


class IMessageStorage:
    """Handle iMessage storage operations."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize storage with database connection."""
        if db is None:
            db = Database()
        self.db = db

    def save_imessage(
        self,
        message_data: Dict[str, Any],
        attachment_data: Optional[bytes] = None,
    ) -> Tuple[IMessage, bool]:
        """Save iMessage to database. Updates existing message if found, otherwise creates new one.
        
        A message is considered duplicate if it has the same:
        - chat_session
        - message_date
        - sender_id
        - type (Incoming/Outgoing)
        
        Returns:
            tuple: (IMessage instance, is_update: bool) where is_update is True if message was updated, False if created
        """
        session = self.db.get_session()
        try:
            # Check if message already exists
            existing = session.query(IMessage).filter(
                IMessage.chat_session == message_data.get("chat_session"),
                IMessage.message_date == message_data.get("message_date"),
                IMessage.sender_id == message_data.get("sender_id"),
                IMessage.type == message_data.get("type")
            ).first()
            
            if existing:
                # Update existing message
                existing.delivered_date = message_data.get("delivered_date")
                existing.read_date = message_data.get("read_date")
                existing.edited_date = message_data.get("edited_date")
                existing.service = message_data.get("service")
                existing.sender_name = message_data.get("sender_name")
                existing.status = message_data.get("status")
                existing.replying_to = message_data.get("replying_to")
                existing.subject = message_data.get("subject")
                existing.text = message_data.get("text")
                existing.attachment_filename = message_data.get("attachment_filename")
                existing.attachment_type = message_data.get("attachment_type")
                if attachment_data is not None:
                    existing.attachment_data = attachment_data
                imessage = existing
                is_update = True
            else:
                # Create new message
                imessage = IMessage(
                    chat_session=message_data.get("chat_session"),
                    message_date=message_data.get("message_date"),
                    delivered_date=message_data.get("delivered_date"),
                    read_date=message_data.get("read_date"),
                    edited_date=message_data.get("edited_date"),
                    service=message_data.get("service"),
                    type=message_data.get("type"),
                    sender_id=message_data.get("sender_id"),
                    sender_name=message_data.get("sender_name"),
                    status=message_data.get("status"),
                    replying_to=message_data.get("replying_to"),
                    subject=message_data.get("subject"),
                    text=message_data.get("text"),
                    attachment_filename=message_data.get("attachment_filename"),
                    attachment_type=message_data.get("attachment_type"),
                    attachment_data=attachment_data,
                )
                session.add(imessage)
                is_update = False
            
            session.commit()
            return (imessage, is_update)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
