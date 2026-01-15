"""Data Transfer Objects for service layer."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class ImageSearchFilters:
    """Filters for image search."""
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None
    image_type: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    has_gps: Optional[bool] = None
    rating: Optional[int] = None
    rating_min: Optional[int] = None
    rating_max: Optional[int] = None
    available_for_task: Optional[bool] = None
    processed: Optional[bool] = None
    location_processed: Optional[bool] = None
    image_processed: Optional[bool] = None
    region: Optional[str] = None


@dataclass
class ImageMetadataUpdate:
    """Update parameters for image metadata."""
    description: Optional[str] = None
    tags: Optional[str] = None
    rating: Optional[int] = None


@dataclass
class BulkUpdateResult:
    """Result of bulk update operation."""
    updated_count: int
    errors: Optional[List[str]] = None


@dataclass
class BulkDeleteResult:
    """Result of bulk delete operation."""
    deleted_count: int
    errors: Optional[List[str]] = None


@dataclass
class ImageContent:
    """Image content with metadata."""
    content: bytes
    content_type: str
    filename: str


@dataclass
class FileValidationResult:
    """Result of file validation."""
    is_valid: bool
    content_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class FileData:
    """File data for document creation."""
    filename: str
    content: bytes
    content_type: str
    size: int


@dataclass
class DocumentMetadata:
    """Metadata for document creation."""
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: bool = False


@dataclass
class DocumentUpdate:
    """Update parameters for documents."""
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: Optional[bool] = None


@dataclass
class ChatSessionInfo:
    """Information about a chat session."""
    chat_session: str
    message_count: int
    attachment_count: int
    primary_service: Optional[str]
    last_message_date: Optional[Any]
    imessage_count: int
    sms_count: int
    whatsapp_count: int
    facebook_count: int
    instagram_count: int
    message_type: str  # 'imessage', 'sms', 'whatsapp', 'facebook', 'instagram', or 'mixed'


@dataclass
class ChatSessionsResult:
    """Result of chat session query."""
    contacts_and_groups: List[ChatSessionInfo]
    other: List[ChatSessionInfo]
