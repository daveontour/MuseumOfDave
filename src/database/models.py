"""Database models and schema management."""

from datetime import datetime
from sqlalchemy import (
    Column,
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    email = relationship("Email", back_populates="attachments")


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
    attachment_filename = Column(String(500), nullable=True)
    attachment_type = Column(String(255), nullable=True)
    attachment_data = Column(LargeBinary, nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    location_processed = Column(Boolean, default=False, nullable=False)
    image_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FacebookAlbum(Base):
    """Facebook Album model."""

    __tablename__ = "facebook_albums"

    id = Column(Integer, primary_key=True)
    name = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    cover_photo_uri = Column(String(500), nullable=True)
    last_modified_timestamp = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    image_type = Column(String(255), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    location_processed = Column(Boolean, default=False, nullable=False)
    image_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    available_for_task = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)