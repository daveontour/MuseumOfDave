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
    """iMessage model."""

    __tablename__ = "imessages"

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)