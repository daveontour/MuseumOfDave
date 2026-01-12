"""Email storage operations."""

from typing import List, Set, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from .connection import Database
from .models import Email, Attachment, IMessage, FacebookAlbum, FacebookAlbumImage


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


class FacebookAlbumStorage:
    """Handle Facebook Album storage operations."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize storage with database connection."""
        if db is None:
            db = Database()
        self.db = db

    def save_album(
        self,
        name: str,
        description: Optional[str] = None,
        cover_photo_uri: Optional[str] = None,
        last_modified_timestamp: Optional[Any] = None,
    ) -> Tuple[int, bool]:
        """Save Facebook album to database. Always creates new entry (no deduplication).
        
        Returns:
            tuple: (album_id: int, is_update: bool) where is_update is always False
        """
        session = self.db.get_session()
        try:
            # Always create new album (no deduplication)
            album = FacebookAlbum(
                name=name,
                description=description,
                cover_photo_uri=cover_photo_uri,
                last_modified_timestamp=last_modified_timestamp,
            )
            session.add(album)
            session.flush()  # Get the album ID
            
            # Get the ID as a value while session is still open
            album_id = album.id
            
            session.commit()
            
            return (album_id, False)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_album_image(
        self,
        album_id: int,
        uri: str,
        filename: Optional[str] = None,
        creation_timestamp: Optional[Any] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        image_data: Optional[bytes] = None,
        image_type: Optional[str] = None,
    ) -> Tuple[FacebookAlbumImage, bool]:
        """Save Facebook album image to database. Always creates new entry (no deduplication).
        
        Returns:
            tuple: (FacebookAlbumImage instance, is_update: bool) where is_update is always False
        """
        session = self.db.get_session()
        try:
            # Ensure image_data is bytes if provided
            if image_data is not None and not isinstance(image_data, bytes):
                print(f"Warning: image_data is not bytes (type: {type(image_data)}), converting...")
                if isinstance(image_data, str):
                    image_data = image_data.encode('utf-8')
                else:
                    image_data = bytes(image_data)
            
            # Always create new image (no deduplication)
            image = FacebookAlbumImage(
                album_id=album_id,
                uri=uri,
                filename=filename,
                creation_timestamp=creation_timestamp,
                title=title,
                description=description,
                image_data=image_data,
                image_type=image_type,
            )
            session.add(image)
            session.flush()  # Flush to ensure data is written
            
            # Debug: Log what we're trying to save
            if image_data is not None:
                print(f"Debug: Saving image with data length {len(image_data)} bytes, type: {image_type}, URI: {uri}")
                # Verify the data is set on the object
                if image.image_data is None:
                    print(f"ERROR: image.image_data is None after flush! Expected {len(image_data)} bytes")
            else:
                print(f"Debug: Saving image WITHOUT data (image_data is None), URI: {uri}")
            
            session.commit()
            
            return (image, False)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
