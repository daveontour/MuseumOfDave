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


class AlbumMedia(Base):
    """Junction table linking Facebook albums to media items."""

    __tablename__ = "album_media"

    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("facebook_albums.id", ondelete="CASCADE"), nullable=False)
    media_item_id = Column(Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    album = relationship("FacebookAlbum", back_populates="media_items")
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

    media_items = relationship("AlbumMedia", back_populates="album", cascade="all, delete-orphan")


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
    
    # Relationship to albums via AlbumMedia junction table
    album_media = relationship("AlbumMedia", foreign_keys="AlbumMedia.media_item_id")

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

    __tablename__ = "places"

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
    is_subject = Column(Boolean, default=False, nullable=False)
    is_contact = Column(Boolean, default=False, nullable=False)
    is_group = Column(Boolean, default=False, nullable=False)
    is_organization = Column(Boolean, default=False, nullable=False)
    is_individual = Column(Boolean, default=False, nullable=False)
    is_company = Column(Boolean, default=False, nullable=False)
    is_government = Column(Boolean, default=False, nullable=False)
    is_non_profit = Column(Boolean, default=False, nullable=False)
    is_educational = Column(Boolean, default=False, nullable=False)
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
    linkedin = Column(Boolean, default=False, nullable=False)
    youtube = Column(Boolean, default=False, nullable=False)
    whatsapp = Column(Boolean, default=False, nullable=False)
    signal = Column(Boolean, default=False, nullable=False)


class Relationship(Base):
    """Relationship model - stores relationships between contacts."""

    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)  # e.g., "friend", "family", "colleague", "acquaintance"
    description = Column(Text, nullable=True)  # Manually entered description
    ai_description = Column(Text, nullable=True)  # AI generated description
    strength = Column(Integer, nullable=True)  # Relationship strength (e.g., 1-10)
    is_active = Column(Boolean, default=True, nullable=False)  # Active relationship
    is_personal = Column(Boolean, default=False, nullable=False)  # Personal relationship
    is_deleted = Column(Boolean, default=False, nullable=False)  # Deleted relationship
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    source = relationship("Contacts", foreign_keys=[source_id], backref="relationships_as_source")
    target = relationship("Contacts", foreign_keys=[target_id], backref="relationships_as_target")

    # Index for common queries
    __table_args__ = (
        Index('idx_relationship_source', 'source_id'),
        Index('idx_relationship_target', 'target_id'),
        Index('idx_relationship_type', 'type'),
    )


class GeminiFile(Base):
    """Gemini File mapping model - stores mapping between ReferenceDocument and Gemini uploaded files."""

    __tablename__ = "gemini_files"

    id = Column(Integer, primary_key=True)
    reference_document_id = Column(Integer, ForeignKey("reference_documents.id", ondelete="CASCADE"), nullable=False, unique=True)
    gemini_file_name = Column(String(500), nullable=False)  # Gemini file name/ID
    gemini_file_uri = Column(String(1000), nullable=True)  # Gemini file URI if available
    filename = Column(String(500), nullable=False)  # Original filename from ReferenceDocument
    state = Column(String(50), nullable=False, default="ACTIVE")  # ACTIVE, EXPIRED, etc.
    verified_at = Column(DateTime, default=utcnow)  # Last time file was verified with Gemini API
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    reference_document = relationship("ReferenceDocument", backref="gemini_file_mapping")

    __table_args__ = (
        Index('idx_gemini_file_reference_doc', 'reference_document_id'),
        Index('idx_gemini_file_name', 'gemini_file_name'),
    )


class ChatConversation(Base):
    """Chat Conversation model - stores conversation metadata."""

    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)  # User-provided conversation title
    voice = Column(String(100), nullable=False)  # Voice used for the conversation
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    last_message_at = Column(DateTime, nullable=True)  # Timestamp of last message for sorting

    turns = relationship("ChatTurn", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatTurn.turn_number")

    __table_args__ = (
        Index('idx_chat_conv_last_message', 'last_message_at'),
    )


class ChatTurn(Base):
    """Chat Turn model - stores individual conversation turns."""

    __tablename__ = "chat_turns"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False)
    user_input = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    voice = Column(String(100), nullable=True)  # Voice used for this turn (may differ from conversation default)
    temperature = Column(Float, nullable=True)  # Temperature used for this turn
    turn_number = Column(Integer, nullable=False)  # Sequential turn number within conversation
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("ChatConversation", back_populates="turns")

    __table_args__ = (
        Index('idx_chat_turn_conv_turn', 'conversation_id', 'turn_number'),
        Index('idx_chat_turn_conv_created', 'conversation_id', 'created_at'),
    )


class SubjectConfiguration(Base):
    """Subject Configuration model - stores subject name and system instructions (singleton)."""

    __tablename__ = "subject_configuration"

    id = Column(Integer, primary_key=True)
    subject_name = Column(String(500), nullable=False)
    gender = Column(String(20), nullable=False, default="Male")
    system_instructions = Column(Text, nullable=False)
    core_system_instructions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class Locations(Base):
    """Locations model."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    region=Column(String(255), nullable=True)
    altitude = Column(Float, nullable=True)
    source=Column(String(255), nullable=True)
    source_reference=Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
