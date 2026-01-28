"""Email storage operations."""

from typing import List, Set, Optional, Dict, Any, Tuple
from datetime import datetime
from io import BytesIO
from sqlalchemy.orm import Session

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from .connection import Database
from .models import Email, IMessage, FacebookAlbum, MediaMetadata, MediaBlob, MessageAttachment, AlbumMedia, utcnow


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
                # Delete existing media items for this email if updating
                if existing:
                    session.query(MediaMetadata).filter(
                        MediaMetadata.source == "email_attachment",
                        MediaMetadata.source_reference == str(email.id)
                    ).delete()

                for att_data in attachments:
                    attachment_data = att_data.get("data")
                    thumbnail_data = att_data.get("thumbnail")
                    content_type = att_data.get("mimeType") or att_data.get("content_type")
                    
                    # Create MediaBlob and MediaItem entries for unified media system
                    if attachment_data is not None:
                        try:
                            # Extract EXIF data if it's an image
                            exif_data = {}
                            if content_type and content_type.startswith('image/'):
                                try:
                                    exif_data = extract_exif_data_from_bytes(attachment_data)
                                except Exception as e:
                                    print(f"Warning: Could not extract EXIF data from email attachment: {e}")
                                    exif_data = {}
                            
                            # Create MediaBlob
                            media_blob = MediaBlob(
                                image_data=attachment_data,
                                thumbnail_data=thumbnail_data
                            )
                            session.add(media_blob)
                            session.flush()  # Get blob ID
                            
                            # Extract year and month - prefer EXIF data, fallback to email date
                            year = exif_data.get('year')
                            month = exif_data.get('month')
                            if year is None or month is None:
                                if email.date:
                                    if isinstance(email.date, datetime):
                                        year = email.date.year
                                        month = email.date.month
                            
                            # Create MediaItem with source="email_attachment" and source_reference=email.id
                            media_item = MediaMetadata(
                                media_blob_id=media_blob.id,
                                source="email_attachment",
                                source_reference=str(email.id),  # Email ID as string in source_reference
                                title=exif_data.get('title') or att_data.get("filename"),  # Use EXIF title if available, otherwise filename
                                description=exif_data.get('description') or email.snippet,  # Use EXIF description if available, otherwise email snippet
                                tags=email.subject,  # Use email subject as tags
                                media_type=content_type,  # Store all content types (images, PDFs, etc.)
                                year=year,
                                month=month,
                                latitude=exif_data.get('latitude'),
                                longitude=exif_data.get('longitude'),
                                altitude=exif_data.get('altitude'),
                                has_gps=exif_data.get('has_gps', False)
                            )
                            session.add(media_item)
                            has_saved_attachments = True
                        except Exception as e:
                            # Log error but don't fail the attachment save
                            print(f"Warning: Could not create unified media entry for email attachment: {e}")

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


def extract_exif_data_from_bytes(image_data: bytes) -> Dict[str, Any]:
    """Extract EXIF data from image bytes.
    
    Args:
        image_data: Image file bytes
        
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
        with Image.open(BytesIO(image_data)) as img:
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
        print(f"Warning: Could not extract EXIF data from image bytes: {e}")
    
    return exif_data


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
        attachment_filename: Optional[str] = None,
        attachment_type: Optional[str] = None,
        source: Optional[str] = None
    ) -> Tuple[IMessage, bool]:
        """Save iMessage to database. Updates existing message if found, otherwise creates new one.
        
        If attachment_data is provided, it will be saved to media_blob/media_items tables
        and linked via MessageAttachment junction table.
        
        A message is considered duplicate if it has the same:
        - chat_session
        - message_date
        - sender_id
        - type (Incoming/Outgoing)
        
        Returns:
            tuple: (IMessage instance, is_update: bool) where is_update is True if message was updated, False if created
        """
        session = self.db.get_session()

        if not message_data.get("is_group_chat"):
            message_data["is_group_chat"] = False
        else:
            message_data["is_group_chat"] = True
            
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
                existing.is_group_chat = message_data.get("is_group_chat")
                
                # Delete existing message attachments if updating
                session.query(MessageAttachment).filter(MessageAttachment.message_id == existing.id).delete()
                
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
                    is_group_chat=message_data.get("is_group_chat"),
                )
                session.add(imessage)
                session.flush()  # Get message ID
                is_update = False
            
            # Handle attachment if provided
            if attachment_data is not None:
                try:
                    # Create thumbnail if it's an image
                    thumbnail_data = None
                    exif_data = {}

                    
                    if attachment_type and attachment_type.startswith('image/'):
                        # Import here to avoid circular import
                        from src.services.process_images_service import ProcessImagesService
                        process_images_service = ProcessImagesService()
                        thumbnail_data, exif_data = process_images_service.create_thumb_and_get_exif(attachment_data, process_thunbnail=True, process_exif=True, width=200)
                        # try:
                        #     from ..imageimport.filesystemimport import create_thumbnail
                        #     thumbnail_data = create_thumbnail(attachment_data)
                        # except Exception as e:
                        #     print(f"Warning: Could not create thumbnail for message attachment: {e}")
                        
                        # # Extract EXIF data including GPS location
                        # try:
                        #     exif_data = extract_exif_data_from_bytes(attachment_data)
                        # except Exception as e:
                        #     print(f"Warning: Could not extract EXIF data from message attachment: {e}")
                        #     exif_data = {}
                    
                    # Create MediaBlob
                    media_blob = MediaBlob(
                        image_data=attachment_data,
                        thumbnail_data=thumbnail_data
                    )
                    session.add(media_blob)
                    session.flush()  # Get blob ID
                    
                    # Extract year and month - prefer EXIF data, fallback to message date
                    year = exif_data.get('year')
                    month = exif_data.get('month')
                    if year is None or month is None:
                        message_date = message_data.get("message_date")
                        if message_date:
                            if isinstance(message_date, datetime):
                                year = message_date.year
                                month = message_date.month
                    
                    if source == None:
                        source = "message_attachment"
                    # Create MediaMetadata entry with GPS data if available
                    media_item = MediaMetadata(
                        media_blob_id=media_blob.id,
                        tags=message_data.get("chat_session"),
                        source=source,
                        source_reference=str(imessage.id),
                        title=exif_data.get('title') or attachment_filename,
                        description=exif_data.get('description') if exif_data else None,
                        media_type=attachment_type,
                        year=year,
                        month=month,
                        latitude=exif_data.get('latitude')if exif_data else None,
                        longitude=exif_data.get('longitude')if exif_data else None,
                        altitude=exif_data.get('altitude')if exif_data else None,
                        has_gps=exif_data.get('has_gps', False)if exif_data else None,
                    )
                    session.add(media_item)
                    session.flush()  # Get media_item ID
                    
                    # Create MessageAttachment junction entry
                    message_attachment = MessageAttachment(
                        message_id=imessage.id,
                        media_item_id=media_item.id
                    )
                    session.add(message_attachment)
                except Exception as e:
                    print(f"Warning: Could not create unified media entry for message attachment: {e}")
            
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
    ) -> Tuple[MediaMetadata, bool]:
        """Save Facebook album image to database using unified media system.
        
        Creates MediaBlob, MediaMetadata, and AlbumMedia entries.
        
        Returns:
            tuple: (MediaMetadata instance, is_update: bool) where is_update is always False
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
            
            # Create thumbnail if it's an image
            thumbnail_data = None
            if image_data is not None and image_type and image_type.startswith('image/'):
                try:
                    from ..imageimport.filesystemimport import create_thumbnail
                    thumbnail_data = create_thumbnail(image_data)
                except Exception as e:
                    print(f"Warning: Could not create thumbnail for album image: {e}")
            
            # Create MediaBlob
            media_blob = MediaBlob(
                image_data=image_data,
                thumbnail_data=thumbnail_data
            )
            session.add(media_blob)
            session.flush()  # Get blob ID
            
            # Extract year and month from creation_timestamp if available
            year = None
            month = None
            if creation_timestamp:
                if isinstance(creation_timestamp, datetime):
                    year = creation_timestamp.year
                    month = creation_timestamp.month
            
            # Get album name for tags
            album = session.query(FacebookAlbum).filter(FacebookAlbum.id == album_id).first()
            album_name = album.name if album else None
            
            # Create MediaMetadata entry
            media_item = MediaMetadata(
                media_blob_id=media_blob.id,
                source="facebook_album",
                source_reference=str(album_id),
                title=title or filename,
                description=description,
                tags=album_name,  # Include album name in tags
                media_type=image_type,
                year=year,
                month=month
            )
            session.add(media_item)
            session.flush()  # Get media_item ID
            
            # Create AlbumMedia junction entry
            album_media = AlbumMedia(
                album_id=album_id,
                media_item_id=media_item.id
            )
            session.add(album_media)
            
            session.commit()
            
            return (media_item, False)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class ImageStorage:
    """Handle image storage operations."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize storage with database connection."""
        if db is None:
            db = Database()
        self.db = db

    def save_image(
        self,
        source_reference: str,
        image_data: bytes,
        thumbnail_data: Optional[bytes] = None,
        media_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        altitude: Optional[float] = None,
        has_gps: bool = False,
        source: str = "Filesystem",
        processed: bool = False,
        **kwargs
    ) -> Tuple[MediaMetadata, bool]:
        """Save or update image with metadata.
        
        Args:
            source_reference: Full file path (used for duplicate detection)
            image_data: Binary image data
            thumbnail_data: Optional thumbnail binary data
            media_type: MIME type of media (image, PDF, etc.)
            title: Image title
            description: Image description
            tags: Comma-separated tags
            year: Year from EXIF
            month: Month from EXIF
            latitude: GPS latitude
            longitude: GPS longitude
            altitude: GPS altitude
            has_gps: Whether GPS data exists
            source: Source of image (default "Filesystem")
            **kwargs: Additional metadata fields
            
        Returns:
            Tuple of (MediaMetadata instance, is_update: bool)
        """
        session = self.db.get_session()
        try:
            # Check for existing image by source_reference
            existing_metadata = session.query(MediaMetadata).filter(
                MediaMetadata.source == source).filter(
                MediaMetadata.source_reference == source_reference
            ).first()
            
            if existing_metadata:
                # Update existing image
                is_update = True
                # Update MediaBlob
                existing_blob = session.query(MediaBlob).filter(
                    MediaBlob.id == existing_metadata.media_blob_id
                ).first()
                
                if existing_blob:
                    existing_blob.image_data = image_data
                    if thumbnail_data is not None:
                        existing_blob.thumbnail_data = thumbnail_data
                    existing_blob.updated_at = utcnow()
                
                # Update MediaMetadata
                existing_metadata.title = title
                existing_metadata.description = description
                existing_metadata.tags = tags
                existing_metadata.media_type = media_type
                existing_metadata.year = year
                existing_metadata.month = month
                existing_metadata.latitude = latitude
                existing_metadata.longitude = longitude
                existing_metadata.altitude = altitude
                existing_metadata.has_gps = has_gps
                existing_metadata.source = source
                existing_metadata.source_reference = source_reference
                existing_metadata.updated_at = utcnow()
                
                # Update any additional fields from kwargs
                for key, value in kwargs.items():
                    if hasattr(existing_metadata, key):
                        setattr(existing_metadata, key, value)
                
                session.commit()
                return (existing_metadata, is_update)
            else:
                # Create new image
                is_update = False
                # Create MediaBlob first
                media_blob = MediaBlob(
                    image_data=image_data,
                    thumbnail_data=thumbnail_data
                )
                session.add(media_blob)
                session.flush()  # Get the blob ID
                
                # Create MediaMetadata
                media_metadata = MediaMetadata(
                    media_blob_id=media_blob.id,
                    title=title,
                    description=description,
                    tags=tags,
                    media_type=media_type,
                    year=year,
                    month=month,
                    latitude=latitude,
                    longitude=longitude,
                    altitude=altitude,
                    has_gps=has_gps,
                    source=source,
                    source_reference=source_reference,
                    processed=processed,
                    **kwargs
                )
                session.add(media_metadata)
                session.commit()
                
                return (media_metadata, is_update)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_image_by_blob_id(self, blob_id: int) -> Optional[MediaBlob]:
        """Retrieve image by blob ID.
        
        Args:
            blob_id: The ID of the MediaBlob
            
        Returns:
            MediaBlob instance or None if not found
        """
        session = self.db.get_session()
        try:
            media_blob = session.query(MediaBlob).filter(MediaBlob.id == blob_id).first()
            if media_blob:
                # Detach the object from the session to avoid session management issues
                session.expunge(media_blob)
            return media_blob
        finally:
            session.close()

    def get_image_by_metadata_id(self, metadata_id: int) -> Optional[MediaBlob]:
        """Retrieve image by metadata ID.
        
        Args:
            metadata_id: The ID of the MediaMetadata
            
        Returns:
            MediaBlob instance or None if not found
        """
        session = self.db.get_session()
        try:
            metadata = session.query(MediaMetadata).filter(MediaMetadata.id == metadata_id).first()
            if metadata:
                media_blob = session.query(MediaBlob).filter(MediaBlob.id == metadata.media_blob_id).first()
                if media_blob:
                    # Detach the object from the session to avoid session management issues
                    session.expunge(media_blob)
                return media_blob
            return None
        finally:
            session.close()
    
    def update_media_metadata(
        self,
        metadata_id: int,
        description: Optional[str] = None,
        tags: Optional[str] = None,
        rating: Optional[int] = None,
        **kwargs
    ) -> Optional[MediaMetadata]:
        """Update image metadata fields.
        
        Args:
            metadata_id: The ID of the MediaMetadata to update
            description: Optional description to update
            tags: Optional tags to update
            rating: Optional rating to update (1-5)
            **kwargs: Additional metadata fields to update
            
        Returns:
            Updated MediaMetadata instance or None if not found
        """
        session = self.db.get_session()
        try:
            metadata = session.query(MediaMetadata).filter(MediaMetadata.id == metadata_id).first()
            if not metadata:
                return None
            
            # Update fields if provided
            if description is not None:
                metadata.description = description
            if tags is not None:
                metadata.tags = tags
            if rating is not None:
                # Validate rating is between 1 and 5
                if rating < 1 or rating > 5:
                    raise ValueError("Rating must be between 1 and 5")
                metadata.rating = rating
            
            # Update any additional fields from kwargs
            for key, value in kwargs.items():
                if hasattr(metadata, key):
                    setattr(metadata, key, value)
            
            metadata.updated_at = utcnow()
            session.commit()
            
            # Detach object from session
            session.expunge(metadata)
            return metadata
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def delete_image_by_metadata_id(self, metadata_id: int) -> bool:
        """Delete an image by metadata ID, ensuring cascade deletion of MediaBlob.
        
        Args:
            metadata_id: The ID of the MediaMetadata to delete
            
        Returns:
            True if deleted, False if not found
        """
        session = self.db.get_session()
        try:
            # Load the metadata with the relationship to ensure cascade works
            metadata = session.query(MediaMetadata).filter(MediaMetadata.id == metadata_id).first()
            if not metadata:
                return False
            
            # Delete the metadata - this should cascade delete the MediaBlob
            # We need to explicitly load the relationship for cascade to work
            _ = metadata.media_blob  # Load the relationship
            session.delete(metadata)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_image_thumbnail(self, image_id: int, thumbnail_data: bytes) -> bool:
        """Update image thumbnail.
        
        Args:
            image_id: The metadata ID of the image to update
            thumbnail_data: The thumbnail data to update
            
        Returns:
            True if update was successful, False if image not found
        """
        session = self.db.get_session()
        try:
            # Get MediaMetadata
            media_metadata = session.query(MediaMetadata).filter(MediaMetadata.id == image_id).first()
            if not media_metadata:
                return False
            
            # Get the associated MediaBlob
            media_blob = session.query(MediaBlob).filter(MediaBlob.id == media_metadata.media_blob_id).first()
            if not media_blob:
                return False
            
            # Update thumbnail_data in MediaBlob
            media_blob.thumbnail_data = thumbnail_data
            media_blob.updated_at = utcnow()
            media_metadata.processed = True
            session.commit()

            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()