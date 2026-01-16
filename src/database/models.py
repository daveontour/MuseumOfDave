"""Database models and schema management."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    LargeBinary,
    Boolean,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


def utcnow():
    """Get current UTC datetime (replacement for deprecated datetime.utcnow())."""
    return datetime.now(timezone.utc)

Base = declarative_base()


class Email(Base):
    """Email model."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    uid = Column(String(255), nullable=False)
    folder = Column(String(255), nullable=False)
    subject = Column(String(1000))
    from_address = Column(String(500))
    to_addresses = Column(Text)
    cc_addresses = Column(Text)
    bcc_addresses = Column(Text)
    date = Column(DateTime)
    raw_message = Column(Text)
    plain_text = Column(Text)
    snippet = Column(Text)
    embedding = Column(Text, nullable=True)  # Will store vector as text/json, can be converted to pgvector later
    has_attachments = Column(Boolean, default=False, nullable=False)
    user_deleted = Column(Boolean, default=False, nullable=False)
    is_personal = Column(Boolean, default=False, nullable=False)
    is_business = Column(Boolean, default=False, nullable=False)
    is_social = Column(Boolean, default=False, nullable=False)
    is_promotional = Column(Boolean, default=False, nullable=False)
    is_spam = Column(Boolean, default=False, nullable=False)
    is_important = Column(Boolean, default=False, nullable=False)
    use_by_ai = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    attachments = relationship("Attachment", back_populates="email", cascade="all, delete-orphan")

    # Note: GIN index will be created manually after checking for pg_trgm extension
    # This avoids errors when the extension is not available
    __table_args__ = (
        UniqueConstraint('uid', 'folder', name='uq_email_uid_folder'),
        Index('idx_email_uid_folder', 'uid', 'folder'),
    )


class Attachment(Base):
    """Attachment model."""

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500))
    content_type = Column(String(255))
    size = Column(Integer)
    data = Column(LargeBinary)
    image_thumbnail = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    email = relationship("Email", back_populates="attachments")


class MessageAttachment(Base):
    """Junction table linking messages to media items."""

    __tablename__ = "message_attachments"

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    media_item_id = Column(Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    message = relationship("IMessage", back_populates="media_attachments")
    media_item = relationship("MediaMetadata", foreign_keys=[media_item_id])


class IMessage(Base):
    """Message model (supports iMessage, SMS, and WhatsApp)."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chat_session = Column(String(500))
    message_date = Column(DateTime)
    delivered_date = Column(DateTime, nullable=True)
    read_date = Column(DateTime, nullable=True)
    edited_date = Column(DateTime, nullable=True)
    service = Column(String(100))
    type = Column(String(50))  # Incoming or Outgoing
    sender_id = Column(String(255), nullable=True)
    sender_name = Column(String(500), nullable=True)
    status = Column(String(100))
    replying_to = Column(String(500), nullable=True)
    subject = Column(String(1000), nullable=True)
    text = Column(Text, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    location_processed = Column(Boolean, default=False, nullable=False)
    image_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    media_attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")


class FacebookAlbum(Base):
    """Facebook Album model."""

    __tablename__ = "facebook_albums"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    cover_photo_uri = Column(String(500), nullable=True)
    last_modified_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    images = relationship("FacebookAlbumImage", back_populates="album", cascade="all, delete-orphan")


class FacebookAlbumImage(Base):
    """Facebook Album Image model."""

    __tablename__ = "facebook_album_images"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("facebook_albums.id", ondelete="CASCADE"), nullable=False)
    uri = Column(String(500), nullable=False)
    filename = Column(String(500), nullable=True)
    creation_timestamp = Column(DateTime, nullable=True)
    title = Column(String(1000), nullable=True)
    description = Column(Text, nullable=True)
    image_data = Column(LargeBinary, nullable=True)
    media_type = Column(String(255), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    location_processed = Column(Boolean, default=False, nullable=False)
    image_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    album = relationship("FacebookAlbum", back_populates="images")


class ReferenceDocument(Base):
    """Reference Document model."""

    __tablename__ = "reference_documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String(500), nullable=False)
    title = Column(String(1000), nullable=True)
    description = Column(Text, nullable=True)
    author = Column(String(500), nullable=True)
    content_type = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=False)
    tags = Column(Text, nullable=True)
    categories = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    ai_detailed_summary = Column(Text, nullable=True)
    ai_quick_summary = Column(Text, nullable=True)
    available_for_task = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class MediaMetadata(Base):
    """Media metadata model."""

    __tablename__ = "media_items"

    id = Column(Integer, primary_key=True)
    media_blob_id = Column(Integer, ForeignKey("media_blob.id", ondelete="RESTRICT"), nullable=False)
    description = Column(Text, nullable=True)
    title = Column(String(1000), nullable=True)
    author = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    categories = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    available_for_task = Column(Boolean, default=False, nullable=False)
    media_type = Column(String(255), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    location_processed = Column(Boolean, default=False, nullable=False)
    image_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow) 
    embedding = Column(Text, nullable=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    rating = Column(Integer, nullable=False, default=5)
    has_gps = Column(Boolean, default=False, nullable=False)
    google_maps_url = Column(String(500), nullable=True)
    region=Column(String(255), nullable=True)
    is_personal = Column(Boolean, default=False, nullable=False)
    is_business = Column(Boolean, default=False, nullable=False)
    is_social = Column(Boolean, default=False, nullable=False)
    is_promotional = Column(Boolean, default=False, nullable=False)
    is_spam = Column(Boolean, default=False, nullable=False)
    is_important = Column(Boolean, default=False, nullable=False)
    use_by_ai = Column(Boolean, default=False, nullable=True)
    source=Column(String(255), nullable=True)
    source_reference=Column(String(500), nullable=True)
    media_blob = relationship("MediaBlob", back_populates="media_metadata", uselist=False, cascade="all, delete")
    
    # Relationship to messages via MessageAttachment junction table
    message_attachments = relationship("MessageAttachment", foreign_keys="MessageAttachment.media_item_id", back_populates="media_item")

class MediaBlob(Base):
    """Media Blob model."""

    __tablename__ = "media_blob"

    id = Column(Integer, primary_key=True)
    image_data = Column(LargeBinary, nullable=True)
    thumbnail_data = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    # Relationship back to MediaMetadata (no foreign key needed - MediaMetadata has media_blob_id)
    media_metadata = relationship("MediaMetadata", back_populates="media_blob", uselist=False)

class Places(Base):
    """Places model."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    has_gps = Column(Boolean, default=False, nullable=False)
    google_maps_url = Column(String(500), nullable=True)
    region=Column(String(255), nullable=True)
    source=Column(String(255), nullable=True)
    source_reference=Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class Contacts(Base):
    """Contacts model."""

    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    email = Column(String(500), nullable=True)
    phone = Column(String(500), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(255), nullable=True)
    state = Column(String(255), nullable=True)
    zip = Column(String(255), nullable=True)
    country = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    facebook = Column(Boolean, default=False, nullable=False)
    instagram = Column(Boolean, default=False, nullable=False)
    twitter = Column(Boolean, default=False, nullable=False)
    linkedin = Column(Boolean, default=False, nullable=False)
    youtube = Column(Boolean, default=False, nullable=False)
    tiktok = Column(Boolean, default=False, nullable=False)
    pinterest = Column(Boolean, default=False, nullable=False)
    reddit = Column(Boolean, default=False, nullable=False)
    telegram = Column(Boolean, default=False, nullable=False)
    whatsapp = Column(Boolean, default=False, nullable=False)
    signal = Column(Boolean, default=False, nullable=False)
