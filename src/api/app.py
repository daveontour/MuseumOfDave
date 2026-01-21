"""FastAPI HTTP Server."""

import os
import threading
import json
import re
import asyncio
from pathlib import Path
from io import BytesIO
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks, Query, Request, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, and_, extract, Integer
from sqlalchemy.orm import joinedload
from PIL import Image

# Try to register HEIF/HEIC support if pillow-heif is available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

from ..database import Database,  Email, IMessage, FacebookAlbum, ReferenceDocument
from ..database.models import MediaMetadata, MediaBlob, MessageAttachment, Attachment, AlbumMedia
from ..database.storage import EmailStorage, ImageStorage
from ..services import ImageService, EmailService, ReferenceDocumentService, MessageService, ImportService
from ..services.gemini_service import ChatService, GeminiService
from ..services.chat_conversation_service import ChatConversationService
from ..services.subject_configuration_service import SubjectConfigurationService
from ..services.exceptions import ServiceException, ValidationError, NotFoundError, ConflictError
from ..services.dto import (
    ImageSearchFilters,
    MediaMetadataUpdate,
    FileData,
    DocumentMetadata,
    DocumentUpdate,
    ChatSessionInfo
)
from ..loader import EmailDatabaseLoader
from ..config import get_config
from ..messageimport.imessageimport import import_imessages_from_directory
from ..messageimport.whatsappimport import import_whatsapp_from_directory
from ..messageimport.facebookimport import import_facebook_from_directory
from ..messageimport.facebookalbumsimport import import_facebook_albums_from_directory
from ..messageimport.instagramimport import import_instagram_from_directory
from ..imageimport.filesystemimport import import_images_from_filesystem

# Create FastAPI app instance
app = FastAPI(
    title="Museum of Dave API",
    description="API server for email processing and retrieval",
    version="1.0.0"
)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Initialize Jinja2 templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Initialize database connection
db = Database(get_config())

# The Gemini Chat Service (global instance for maintaining conversation history)
chat_service = ChatService()
chat_service.set_database(db)

# Initialize loader (will be initialized per request)
loader = None

# Processing state management
processing_lock = threading.Lock()
processing_cancelled = threading.Event()
processing_in_progress = False

# Progress state for SSE streaming
processing_progress: Dict[str, Any] = {
    "current_label": None,
    "current_label_index": 0,
    "total_labels": 0,
    "emails_processed": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None,
    "labels": []
}

# SSE event queue for broadcasting progress updates
sse_clients: List[asyncio.Queue] = []
sse_clients_lock = threading.Lock()

# iMessage import state management
imessage_import_lock = threading.Lock()
imessage_import_cancelled = threading.Event()
imessage_import_in_progress = False

# Progress state for iMessage import SSE streaming
imessage_import_progress: Dict[str, Any] = {
    "current_conversation": None,
    "conversations_processed": 0,
    "total_conversations": 0,
    "messages_imported": 0,
    "messages_created": 0,
    "messages_updated": 0,
    "attachments_found": 0,
    "attachments_missing": 0,
    "missing_attachment_filenames": [],
    "errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

# SSE event queue for iMessage import progress updates
imessage_sse_clients: List[asyncio.Queue] = []
imessage_sse_clients_lock = threading.Lock()

# Conversation summary state management
conversation_summary_lock = threading.Lock()
conversation_summary_in_progress = False
conversation_summary_progress: Dict[str, Any] = {
    "status": "idle",  # idle, processing, completed, error
    "chat_session": None,
    "stage": None,
    "summary": None,
    "error": None
}

# SSE event queue for conversation summary progress updates
conversation_summary_sse_clients: List[asyncio.Queue] = []
conversation_summary_sse_clients_lock = threading.Lock()

# WhatsApp import state management
whatsapp_import_lock = threading.Lock()
whatsapp_import_cancelled = threading.Event()
whatsapp_import_in_progress = False

# Progress state for WhatsApp import SSE streaming
whatsapp_import_progress: Dict[str, Any] = {
    "current_conversation": None,
    "conversations_processed": 0,
    "total_conversations": 0,
    "messages_imported": 0,
    "messages_created": 0,
    "messages_updated": 0,
    "attachments_found": 0,
    "attachments_missing": 0,
    "missing_attachment_filenames": [],
    "errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

# SSE event queue for WhatsApp import progress updates
whatsapp_sse_clients: List[asyncio.Queue] = []
whatsapp_sse_clients_lock = threading.Lock()

# Facebook Messenger import state management
facebook_import_lock = threading.Lock()
facebook_import_cancelled = threading.Event()
facebook_import_in_progress = False

# Progress state for Facebook Messenger import SSE streaming
facebook_import_progress: Dict[str, Any] = {
    "current_conversation": None,
    "conversations_processed": 0,
    "total_conversations": 0,
    "messages_imported": 0,
    "messages_created": 0,
    "messages_updated": 0,
    "attachments_found": 0,
    "attachments_missing": 0,
    "missing_attachment_filenames": [],
    "errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

# SSE event queue for Facebook Messenger import progress updates
facebook_sse_clients: List[asyncio.Queue] = []
facebook_sse_clients_lock = threading.Lock()

# Instagram import state management
instagram_import_lock = threading.Lock()
instagram_import_cancelled = threading.Event()
instagram_import_in_progress = False

# Progress state for Instagram import SSE streaming
instagram_import_progress: Dict[str, Any] = {
    "current_conversation": None,
    "conversations_processed": 0,
    "total_conversations": 0,
    "messages_imported": 0,
    "messages_created": 0,
    "messages_updated": 0,
    "errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

# SSE event queue for Instagram import progress updates
instagram_sse_clients: List[asyncio.Queue] = []
instagram_sse_clients_lock = threading.Lock()

# Facebook Albums import state management
facebook_albums_import_lock = threading.Lock()
facebook_albums_import_cancelled = threading.Event()
facebook_albums_import_in_progress = False

# Progress state for Facebook Albums import SSE streaming
facebook_albums_import_progress: Dict[str, Any] = {
    "current_album": None,
    "albums_processed": 0,
    "total_albums": 0,
    "albums_imported": 0,
    "images_imported": 0,
    "images_found": 0,
    "images_missing": 0,
    "missing_image_filenames": [],
    "errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

# SSE event queue for Facebook Albums import progress updates
facebook_albums_sse_clients: List[asyncio.Queue] = []
facebook_albums_sse_clients_lock = threading.Lock()

# Filesystem import state management
filesystem_import_lock = threading.Lock()
filesystem_import_cancelled = threading.Event()
filesystem_import_in_progress = False

# Progress state for Filesystem import SSE streaming
filesystem_import_progress: Dict[str, Any] = {
    "status": "idle",
    "current_file": None,
    "files_processed": 0,
    "total_files": 0,
    "images_imported": 0,
    "images_updated": 0,
    "errors": 0,
    "error_messages": []
}

filesystem_import_sse_clients: List[asyncio.Queue] = []
filesystem_import_sse_clients_lock = threading.Lock()

# Thumbnail processing state management
thumbnail_processing_lock = threading.Lock()
thumbnail_processing_cancelled = threading.Event()
thumbnail_processing_in_progress = False

# Progress state for Thumbnail processing SSE streaming
thumbnail_processing_progress: Dict[str, Any] = {
    "phase": None,
    "phase1_scanned": 0,
    "phase1_updated": 0,
    "phase2_scanned": 0,
    "phase2_processed": 0,
    "phase2_errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None
}

thumbnail_processing_sse_clients: List[asyncio.Queue] = []
thumbnail_processing_sse_clients_lock = threading.Lock()


def update_imessage_progress_state(**kwargs):
    """Thread-safe function to update iMessage import progress state."""
    global imessage_import_progress
    with imessage_import_lock:
        for key, value in kwargs.items():
            if key in imessage_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
                    # Replace the list with the new one (which already contains all missing files)
                    imessage_import_progress[key] = value.copy()
                else:
                    imessage_import_progress[key] = value


def get_imessage_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current iMessage import progress state."""
    global imessage_import_progress
    with imessage_import_lock:
        return imessage_import_progress.copy()


def broadcast_imessage_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue iMessage import progress event for SSE clients."""
    global imessage_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with imessage_sse_clients_lock:
        disconnected_clients = []
        for client_queue in imessage_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in imessage_sse_clients:
                imessage_sse_clients.remove(client)


def update_conversation_summary_progress_state(**kwargs):
    """Thread-safe function to update conversation summary progress state."""
    global conversation_summary_progress
    with conversation_summary_lock:
        for key, value in kwargs.items():
            conversation_summary_progress[key] = value


def get_conversation_summary_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current conversation summary progress state."""
    global conversation_summary_progress
    with conversation_summary_lock:
        return conversation_summary_progress.copy()


def broadcast_conversation_summary_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue conversation summary event for SSE clients."""
    global conversation_summary_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with conversation_summary_sse_clients_lock:
        disconnected_clients = []
        for client_queue in conversation_summary_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in conversation_summary_sse_clients:
                conversation_summary_sse_clients.remove(client)


def update_whatsapp_progress_state(**kwargs):
    """Thread-safe function to update WhatsApp import progress state."""
    global whatsapp_import_progress
    with whatsapp_import_lock:
        for key, value in kwargs.items():
            if key in whatsapp_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
                    # Replace the list with the new one (which already contains all missing files)
                    whatsapp_import_progress[key] = value.copy()
                else:
                    whatsapp_import_progress[key] = value


def get_whatsapp_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current WhatsApp import progress state."""
    global whatsapp_import_progress
    with whatsapp_import_lock:
        return whatsapp_import_progress.copy()


def broadcast_whatsapp_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue WhatsApp import progress event for SSE clients."""
    global whatsapp_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with whatsapp_sse_clients_lock:
        disconnected_clients = []
        for client_queue in whatsapp_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in whatsapp_sse_clients:
                whatsapp_sse_clients.remove(client)


def update_facebook_progress_state(**kwargs):
    """Thread-safe function to update Facebook Messenger import progress state."""
    global facebook_import_progress
    with facebook_import_lock:
        for key, value in kwargs.items():
            if key in facebook_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
                    # Replace the list with the new one (which already contains all missing files)
                    facebook_import_progress[key] = value.copy()
                else:
                    facebook_import_progress[key] = value


def get_facebook_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current Facebook Messenger import progress state."""
    global facebook_import_progress
    with facebook_import_lock:
        return facebook_import_progress.copy()


def broadcast_facebook_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue Facebook Messenger import progress event for SSE clients."""
    global facebook_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with facebook_sse_clients_lock:
        disconnected_clients = []
        for client_queue in facebook_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in facebook_sse_clients:
                facebook_sse_clients.remove(client)


def update_facebook_albums_progress_state(**kwargs):
    """Thread-safe function to update Facebook Albums import progress state."""
    global facebook_albums_import_progress
    with facebook_albums_import_lock:
        for key, value in kwargs.items():
            if key in facebook_albums_import_progress:
                if key == "missing_image_filenames" and isinstance(value, list):
                    # Replace the list with the new one (which already contains all missing files)
                    facebook_albums_import_progress[key] = value.copy()
                else:
                    facebook_albums_import_progress[key] = value


def get_facebook_albums_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current Facebook Albums import progress state."""
    global facebook_albums_import_progress
    with facebook_albums_import_lock:
        return facebook_albums_import_progress.copy()


def broadcast_facebook_albums_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue Facebook Albums import progress event for SSE clients."""
    global facebook_albums_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with facebook_albums_sse_clients_lock:
        disconnected_clients = []
        for client_queue in facebook_albums_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in facebook_albums_sse_clients:
                facebook_albums_sse_clients.remove(client)


def update_filesystem_import_progress_state(**kwargs):
    """Thread-safe function to update Filesystem import progress state."""
    global filesystem_import_progress
    with filesystem_import_lock:
        for key, value in kwargs.items():
            if key in filesystem_import_progress:
                if key == "error_messages" and isinstance(value, list):
                    # Replace the list with the new one
                    filesystem_import_progress[key] = value.copy()
                else:
                    filesystem_import_progress[key] = value


def get_filesystem_import_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current Filesystem import progress state."""
    global filesystem_import_progress
    with filesystem_import_lock:
        return filesystem_import_progress.copy()


def broadcast_filesystem_import_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue Filesystem import progress event for SSE clients."""
    global filesystem_import_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with filesystem_import_sse_clients_lock:
        disconnected_clients = []
        for client_queue in filesystem_import_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in filesystem_import_sse_clients:
                filesystem_import_sse_clients.remove(client)


def update_thumbnail_processing_progress_state(**kwargs):
    """Thread-safe function to update thumbnail processing progress state."""
    global thumbnail_processing_progress
    with thumbnail_processing_lock:
        for key, value in kwargs.items():
            if key in thumbnail_processing_progress:
                thumbnail_processing_progress[key] = value


def get_thumbnail_processing_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current thumbnail processing progress state."""
    global thumbnail_processing_progress
    with thumbnail_processing_lock:
        return thumbnail_processing_progress.copy()


def broadcast_thumbnail_processing_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue thumbnail processing progress event for SSE clients."""
    global thumbnail_processing_sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with thumbnail_processing_sse_clients_lock:
        disconnected_clients = []
        for client_queue in thumbnail_processing_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in thumbnail_processing_sse_clients:
                thumbnail_processing_sse_clients.remove(client)


def update_instagram_progress_state(**kwargs):
    """Thread-safe function to update Instagram import progress state."""
    global instagram_import_progress
    with instagram_import_lock:
        for key, value in kwargs.items():
            if key in instagram_import_progress:
                if isinstance(value, (dict, list)):
                    instagram_import_progress[key] = value.copy()
                else:
                    instagram_import_progress[key] = value


def get_instagram_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current Instagram import progress state."""
    global instagram_import_progress
    with instagram_import_lock:
        return instagram_import_progress.copy()


def broadcast_instagram_progress_event_sync():
    """Thread-safe function to queue Instagram import progress event for SSE clients."""
    global instagram_sse_clients
    progress_state = get_instagram_progress_state()
    
    # Create SSE event data
    event_data = {
        "type": "progress",
        "data": progress_state
    }
    
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with instagram_sse_clients_lock:
        disconnected_clients = []
        for client_queue in instagram_sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in instagram_sse_clients:
                instagram_sse_clients.remove(client)


def update_progress_state(**kwargs):
    """Thread-safe function to update progress state."""
    global processing_progress
    with processing_lock:
        for key, value in kwargs.items():
            if key in processing_progress:
                processing_progress[key] = value


def get_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current progress state."""
    global processing_progress
    with processing_lock:
        return processing_progress.copy()


def broadcast_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue progress event for SSE clients."""
    global sse_clients
    event_data = {
        "type": event_type,
        "data": data
    }
    message = f"data: {json.dumps(event_data)}\n\n"
    
    # Queue message for all connected clients
    with sse_clients_lock:
        disconnected_clients = []
        for client_queue in sse_clients:
            try:
                # Use put_nowait to avoid blocking
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                # Queue is full, skip this client
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            if client in sse_clients:
                sse_clients.remove(client)


class ProcessLabelRequest(BaseModel):
    """Request model for processing emails by label."""
    labels: Optional[List[str]] = None
    new_only: bool = False
    all_folders: bool = False


class ProcessLabelResponse(BaseModel):
    """Response model for processing emails."""
    message: str
    labels: List[str]
    count: int
    timestamp: datetime


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    timestamp: datetime


class ImportIMessagesRequest(BaseModel):
    """Request model for importing iMessages from directory."""
    directory_path: str


class ImportIMessagesResponse(BaseModel):
    """Response model for iMessage import."""
    message: str
    directory_path: str
    conversations_processed: int
    messages_imported: int
    messages_created: int
    messages_updated: int
    attachments_found: int
    attachments_missing: int
    missing_attachment_filenames: List[str] = []
    errors: int
    timestamp: datetime


class ImportWhatsAppRequest(BaseModel):
    """Request model for WhatsApp import."""
    directory_path: str


class ImportWhatsAppResponse(BaseModel):
    """Response model for WhatsApp import."""
    message: str
    directory_path: str
    conversations_processed: int
    messages_imported: int
    messages_created: int
    messages_updated: int
    attachments_found: int
    attachments_missing: int
    missing_attachment_filenames: List[str] = []
    errors: int
    timestamp: datetime


class ImportFacebookRequest(BaseModel):
    """Request model for Facebook Messenger import."""
    directory_path: str
    user_name: Optional[str] = None


class ImportFacebookResponse(BaseModel):
    """Response model for Facebook Messenger import."""
    message: str
    directory_path: str
    conversations_processed: int
    messages_imported: int
    messages_created: int
    messages_updated: int
    attachments_found: int
    attachments_missing: int
    missing_attachment_filenames: List[str] = []
    errors: int
    timestamp: datetime


class ImportInstagramRequest(BaseModel):
    """Request model for Instagram import."""
    directory_path: str
    user_name: Optional[str] = None


class ImportInstagramResponse(BaseModel):
    """Response model for Instagram import."""
    message: str
    directory_path: str
    conversations_processed: int
    messages_imported: int
    messages_created: int
    messages_updated: int
    errors: int
    timestamp: datetime


class ImportFacebookAlbumsRequest(BaseModel):
    """Request model for Facebook Albums import."""
    directory_path: str


class ImportFacebookAlbumsResponse(BaseModel):
    """Response model for Facebook Albums import."""
    message: str
    directory_path: str
    albums_processed: int
    albums_imported: int
    images_imported: int
    images_found: int
    images_missing: int
    missing_image_filenames: List[str] = []
    errors: int
    timestamp: datetime


class ImportFilesystemImagesRequest(BaseModel):
    """Request model for Filesystem Images import."""
    root_directory: str
    max_images: Optional[int] = None
    create_thumbnail: bool = False


class ImportFilesystemImagesResponse(BaseModel):
    """Response model for Filesystem Images import."""
    message: str
    root_directory: str
    files_processed: int = 0
    total_files: int = 0
    images_imported: int = 0
    images_updated: int = 0
    errors: int = 0
    timestamp: datetime


class MediaMetadataResponse(BaseModel):
    """Response model for image metadata."""
    id: int
    media_blob_id: int
    description: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: bool = False
    media_type: Optional[str] = None
    processed: bool = False
    location_processed: bool = False
    image_processed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    year: Optional[int] = None
    month: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    rating: int = 5
    has_gps: bool = False
    google_maps_url: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None

    class Config:
        from_attributes = True


class EmailMetadataResponse(BaseModel):
    """Response model for email metadata."""
    id: int
    uid: str
    folder: str
    subject: Optional[str]
    from_address: Optional[str]
    to_addresses: Optional[str]
    cc_addresses: Optional[str]
    bcc_addresses: Optional[str]
    date: Optional[datetime]
    snippet: Optional[str]
    attachment_ids: List[int]
    created_at: datetime
    updated_at: datetime
    is_personal: bool = False
    is_business: bool = False
    is_important: bool = False
    use_by_ai: bool = True


class LabelResponse(BaseModel):
    """Response model for Gmail label."""
    id: str
    name: str
    type: Optional[str] = None
    message_list_visibility: Optional[str] = None
    label_list_visibility: Optional[str] = None


class AttachmentInfoResponse(BaseModel):
    """Response model for attachment with email metadata."""
    attachment_id: int
    filename: Optional[str]
    content_type: Optional[str]
    size: Optional[int]
    email_id: int
    email_subject: Optional[str]
    email_from: Optional[str]
    email_date: Optional[datetime]
    email_folder: str


class ImageGridResponse(BaseModel):
    """Response model for image grid pagination."""
    images: List[AttachmentInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ReferenceDocumentResponse(BaseModel):
    """Response model for reference document metadata."""
    id: int
    filename: str
    title: Optional[str]
    description: Optional[str]
    author: Optional[str]
    content_type: str
    size: int
    tags: Optional[str]
    categories: Optional[str]
    notes: Optional[str]
    available_for_task: bool
    created_at: datetime
    updated_at: datetime


class ReferenceDocumentUpdateRequest(BaseModel):
    """Request model for updating reference document metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: Optional[bool] = None


def get_loader() -> EmailDatabaseLoader:
    """Get or create email loader instance."""
    global loader
    if loader is None:
        loader = EmailDatabaseLoader()
        loader.init_client()
    return loader


def process_single_label_background(label: str, new_only: bool, result_dict: dict, lock: threading.Lock):
    """Background task to process emails for a single label."""
    try:
        print(f"[Thread] Starting processing for label: {label}")
        # Create a new loader instance for each thread to avoid sharing issues
        from ..loader import EmailDatabaseLoader
        from ..config import get_config
        loader_instance = EmailDatabaseLoader()
        loader_instance.init_client()
        
        count = loader_instance.load_emails(label, new_only=new_only)
        print(f"[Thread] Completed processing for label: {label}, processed {count} emails")
        
        # Thread-safe update of result dictionary
        with lock:
            result_dict["count"] += count
            result_dict["success"] = True  # Set to True if at least one succeeds
    except Exception as e:
        print(f"[Thread] Error processing label {label}: {str(e)}")
        import traceback
        traceback.print_exc()
        with lock:
            error_msg = result_dict.get("error", "")
            if error_msg:
                error_msg += " "
            result_dict["error"] = error_msg + f"Error processing {label}: {str(e)}; "
            result_dict["success"] = False


def process_emails_background(labels: List[str], new_only: bool, result_dict: dict):
    """Background task coordinator that processes labels sequentially."""
    global processing_in_progress
    
    # Filter out TRASH and SPAM folders
    filtered_labels = [label for label in labels if label.upper() not in ["TRASH", "SPAM"]]
    
    # Mark processing as started
    with processing_lock:
        processing_in_progress = True
        processing_cancelled.clear()
    
    # Initialize progress state
    update_progress_state(
        current_label=None,
        current_label_index=0,
        total_labels=len(filtered_labels),
        emails_processed=0,
        status="in_progress",
        error_message=None,
        labels=filtered_labels
    )
    
    # Broadcast initial progress event
    broadcast_progress_event_sync("progress", get_progress_state())
    
    try:
        # Initialize result dict
        result_dict["count"] = 0
        result_dict["success"] = False
        result_dict["error"] = ""
        
        # Process labels sequentially, one at a time
        for idx, label in enumerate(filtered_labels, start=1):
            # Check for cancellation before processing each label
            if processing_cancelled.is_set():
                print(f"[Background Task] Processing cancelled by user")
                result_dict["error"] = "Processing was cancelled by user"
                result_dict["success"] = False
                update_progress_state(status="cancelled", error_message="Processing was cancelled by user")
                broadcast_progress_event_sync("cancelled", get_progress_state())
                break
            
            try:
                print(f"[Background Task] Starting processing for label: {label}")
                
                # Update progress state - starting new label
                update_progress_state(
                    current_label=label,
                    current_label_index=idx
                )
                broadcast_progress_event_sync("progress", get_progress_state())
                
                loader_instance = get_loader()
                
                # Check for cancellation before loading emails
                if processing_cancelled.is_set():
                    print(f"[Background Task] Processing cancelled before loading emails for {label}")
                    result_dict["error"] = "Processing was cancelled by user"
                    result_dict["success"] = False
                    update_progress_state(status="cancelled", error_message="Processing was cancelled by user")
                    broadcast_progress_event_sync("cancelled", get_progress_state())
                    break
                
                count = loader_instance.load_emails(label, new_only=new_only)
                result_dict["count"] += count
                result_dict["success"] = True  # Set to True if at least one succeeds
                
                # Update progress state - label completed
                current_state = get_progress_state()
                update_progress_state(emails_processed=current_state["emails_processed"] + count)
                broadcast_progress_event_sync("progress", get_progress_state())
                
                print(f"[Background Task] Completed processing for label: {label}, processed {count} emails")
            except Exception as e:
                error_msg = result_dict.get("error", "")
                if error_msg:
                    error_msg += " "
                error_msg += f"Error processing {label}: {str(e)}; "
                result_dict["error"] = error_msg
                result_dict["success"] = False
                
                # Update progress state - error occurred
                current_state = get_progress_state()
                update_progress_state(
                    status="error",
                    error_message=error_msg
                )
                broadcast_progress_event_sync("error", get_progress_state())
                
                print(f"[Background Task] Error processing {label}: {str(e)}")
        
        # Mark as completed if not cancelled or errored
        current_state = get_progress_state()
        if current_state["status"] == "in_progress":
            update_progress_state(status="completed")
            broadcast_progress_event_sync("completed", get_progress_state())
            
    finally:
        # Mark processing as completed
        with processing_lock:
            processing_in_progress = False


@app.get("/")
async def root():
    """Root endpoint - returns a welcome message."""
    return {
        "message": "Welcome to the Museum of Dave API",
        "endpoints": {
            "GET /": "This endpoint",
            "GET /health": "Health check endpoint",
            "POST /emails/process": "Process emails from a list of labels",
            "POST /emails/process/cancel": "Cancel email processing if in progress",
            "GET /emails/process/status": "Get current email processing status",
            "POST /imessages/import": "Import iMessages from a directory structure",
            "GET /imessages/import/stream": "Stream iMessage import progress via SSE",
            "POST /imessages/import/cancel": "Cancel iMessage import if in progress",
            "GET /imessages/import/status": "Get current iMessage import status",
            "GET /imessages/chat-sessions": "Get list of unique chat session names",
            "GET /imessages/conversation/{chat_session}": "Get all messages for a specific chat session",
            "DELETE /imessages/conversation/{chat_session}": "Delete a conversation",
            "GET /imessages/{message_id}/attachment": "Get attachment content for a message",
            "POST /chat/generate": "Generate a chat response using ChatService with Gemini LLM",
            "POST /whatsapp/import": "Import WhatsApp messages from a directory structure",
            "GET /whatsapp/import/stream": "Stream WhatsApp import progress via SSE",
            "POST /whatsapp/import/cancel": "Cancel WhatsApp import if in progress",
            "GET /whatsapp/import/status": "Get current WhatsApp import status",
            "POST /facebook/import": "Import Facebook Messenger messages from a directory structure",
            "GET /facebook/import/stream": "Stream Facebook Messenger import progress via SSE",
            "POST /facebook/import/cancel": "Cancel Facebook Messenger import if in progress",
            "GET /facebook/import/status": "Get current Facebook Messenger import status",
            "POST /instagram/import": "Import Instagram messages from a directory structure",
            "GET /instagram/import/stream": "Stream Instagram import progress via SSE",
            "POST /instagram/import/cancel": "Cancel Instagram import if in progress",
            "GET /instagram/import/status": "Get current Instagram import status",
            "POST /facebook/albums/import": "Import Facebook Albums from a directory structure",
            "GET /facebook/albums/import/stream": "Stream Facebook Albums import progress via SSE",
            "POST /facebook/albums/import/cancel": "Cancel Facebook Albums import if in progress",
            "GET /facebook/albums/import/status": "Get current Facebook Albums import status",
            "GET /facebook/albums": "Get list of all Facebook albums",
            "GET /facebook/albums/{album_id}/images": "Get all images for a specific Facebook album",
            "GET /facebook/albums/images/{image_id}": "Get image data for a specific Facebook album image",
            "GET /emails/{email_id}/html": "Get email HTML content by ID",
            "GET /emails/{email_id}/text": "Get email plain text content by ID",
            "GET /emails/{email_id}/snippet": "Get email snippet by ID",
            "GET /emails/{email_id}/metadata": "Get email metadata by ID",
            "GET /emails/label": "Get metadata for all emails with given labels (query param: labels)",
            "GET /emails/folders": "Get list of available folders/labels from email server",
            "GET /emails/search": "Search emails by metadata criteria (from, to, month, year, subject, to_from, has_attachments)",
            "GET /attachments/{attachment_id}": "Get attachment content",
            "GET /attachments/random": "Get random attachment with email metadata",
            "GET /attachments/by-id": "Get attachment by ID order (query param: offset)",
            "GET /attachments/by-size": "Get attachment by size order (query params: order=asc|desc, offset)",
            "GET /attachments/count": "Get total count of attachments",
            "GET /attachments/{attachment_id}/info": "Get attachment info with email metadata",
            "DELETE /attachments/{attachment_id}": "Delete an attachment",
            "GET /attachments-viewer": "Attachment viewer web page",
            "GET /attachments/images": "Get images for grid display (query params: page, page_size, order, direction)",
            "GET /attachments-images-grid": "Image grid viewer web page"
        }
    }

@app.get("/new-page", response_class=HTMLResponse)
async def new_page(request: Request):
    """Serve the new page."""
    return templates.TemplateResponse(
        "new_page.html",
        {"request": request}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint - returns server status."""
    return MessageResponse(
        message="Server is running",
        timestamp=datetime.now()
    )


@app.get("/api/control-defaults")
async def get_control_defaults():
    """Get default values for control tab inputs from environment variables.
    
    Returns:
        Dictionary of default values for all control tab inputs
    """
    config = get_config()
    return config.get_control_defaults()


@app.post("/emails/process", response_model=ProcessLabelResponse)
async def process_emails(
    request: ProcessLabelRequest,
    background_tasks: BackgroundTasks
):
    """Process emails from Gmail labels asynchronously.
    
    Args:
        request: ProcessLabelRequest with list of labels, new_only flag, and optional all_folders flag
        background_tasks: FastAPI background tasks
        
    Returns:
        ProcessLabelResponse with processing status
    """
    global processing_in_progress
    
    # Create email service with state accessors
    def get_state():
        return processing_in_progress
    
    def set_state(value):
        global processing_in_progress
        processing_in_progress = value
    
    email_service = EmailService(
        get_processing_state=get_state,
        set_processing_state=set_state,
        cancellation_event=processing_cancelled,
        processing_lock=processing_lock
    )
    
    try:
        # Check if processing can start
        email_service.can_start_processing()
        
        # Determine which labels to process
        loader_instance = get_loader() if request.all_folders else None
        labels_to_process = email_service.determine_labels_to_process(
            labels=request.labels,
            all_folders=request.all_folders,
            loader=loader_instance
        )
        
        result_dict = {"count": 0, "success": False}
        
        # Start background processing
        background_tasks.add_task(
            process_emails_background,
            labels_to_process,
            request.new_only,
            result_dict
        )
        
        labels_str = ", ".join(labels_to_process)
        message = f"Processing emails from {len(labels_to_process)} label(s) started"
        if request.all_folders:
            message = f"Processing emails from all folders ({len(labels_to_process)} labels) started"
        
        return ProcessLabelResponse(
            message=message,
            labels=labels_to_process,
            count=0,  # Will be updated in background
            timestamp=datetime.now()
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing emails: {str(e)}"
        )


@app.post("/emails/process/cancel")
async def cancel_email_processing():
    """Cancel email processing if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global processing_in_progress
    
    # Create email service with state accessors
    def get_state():
        return processing_in_progress
    
    def set_state(value):
        global processing_in_progress
        processing_in_progress = value
    
    email_service = EmailService(
        get_processing_state=get_state,
        set_processing_state=set_state,
        cancellation_event=processing_cancelled,
        processing_lock=processing_lock
    )
    
    try:
        cancelled = email_service.cancel_processing()
        
        if cancelled:
            return {
                "message": "Email processing cancellation requested. Processing will stop after current label completes.",
                "cancelled": True
            }
        else:
            return {
                "message": "No email processing is currently in progress",
                "cancelled": False
            }
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.get("/emails/process/status")
async def get_processing_status():
    """Get the current status of email processing.
    
    Returns:
        Status information about email processing
    """
    global processing_in_progress
    
    progress_state = get_progress_state()
    
    with processing_lock:
        return {
            "in_progress": processing_in_progress,
            "cancelled": processing_cancelled.is_set(),
            **progress_state
        }


def import_imessages_background(directory_path: str, result_dict: dict):
    """Background function to import iMessages from directory."""
    global imessage_import_in_progress
    
    # Mark processing as started
    with imessage_import_lock:
        imessage_import_in_progress = True
        imessage_import_cancelled.clear()
    
    # Initialize progress state
    update_imessage_progress_state(
        current_conversation=None,
        conversations_processed=0,
        total_conversations=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_imessage_progress_event_sync("progress", get_imessage_progress_state())
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if imessage_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_imessage_progress_state(
                current_conversation=stats.get("current_conversation"),
                conversations_processed=stats.get("conversations_processed", 0),
                total_conversations=stats.get("total_conversations", 0),
                messages_imported=stats.get("messages_imported", 0),
                messages_created=stats.get("messages_created", 0),
                messages_updated=stats.get("messages_updated", 0),
                attachments_found=stats.get("attachments_found", 0),
                attachments_missing=stats.get("attachments_missing", 0),
                missing_attachment_filenames=stats.get("missing_attachment_filenames", []),
                errors=stats.get("errors", 0),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_imessage_progress_event_sync("progress", get_imessage_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return imessage_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_imessages_from_directory(
            directory_path,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_imessage_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in imessage_import_progress}
        )
        broadcast_imessage_progress_event_sync("completed", get_imessage_progress_state())
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_imessage_progress_state(
            status="error",
            error_message=error_msg
        )
        broadcast_imessage_progress_event_sync("error", get_imessage_progress_state())
        
        print(f"[Background Task] Error importing iMessages: {error_msg}")
    finally:
        # Mark processing as completed
        with imessage_import_lock:
            imessage_import_in_progress = False


@app.post("/imessages/import", response_model=ImportIMessagesResponse)
async def import_imessages(
    request: ImportIMessagesRequest,
    background_tasks: BackgroundTasks
):
    """Import iMessages from a directory structure asynchronously.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain a CSV file with the messages.
    
    Args:
        request: ImportIMessagesRequest with directory_path
        background_tasks: FastAPI background tasks
        
    Returns:
        ImportIMessagesResponse with initial status
        
    Raises:
        HTTPException: If directory doesn't exist or import already in progress
    """
    global imessage_import_in_progress
    
    # Create import service with state accessors
    def get_import_state(import_type: str) -> bool:
        if import_type == "imessage":
            return imessage_import_in_progress
        return False
    
    def set_import_state(import_type: str, value: bool):
        global imessage_import_in_progress
        if import_type == "imessage":
            imessage_import_in_progress = value
    
    def get_cancellation_event(import_type: str):
        if import_type == "imessage":
            return imessage_import_cancelled
        return None
    
    def get_import_lock(import_type: str):
        if import_type == "imessage":
            return imessage_import_lock
        return None
    
    import_service = ImportService(
        get_import_state=get_import_state,
        set_import_state=set_import_state,
        get_cancellation_event=get_cancellation_event,
        get_import_lock=get_import_lock
    )
    
    try:
        # Check if import can start
        import_service.can_start_import("imessage")
        
        # Validate directory
        import_service.validate_import_directory(request.directory_path)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    
    result_dict = {
        "conversations_processed": 0,
        "messages_imported": 0,
        "messages_created": 0,
        "messages_updated": 0,
        "attachments_found": 0,
        "attachments_missing": 0,
        "missing_attachment_filenames": [],
        "errors": 0,
        "success": False
    }
    
    # Start background processing
    background_tasks.add_task(
        import_imessages_background,
        request.directory_path,
        result_dict
    )
    
    return ImportIMessagesResponse(
        message="iMessage import started",
        directory_path=request.directory_path,
        conversations_processed=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        timestamp=datetime.now()
    )


@app.get("/imessages/import/stream")
async def stream_imessage_import_progress():
    """Stream iMessage import progress updates via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with imessage_sse_clients_lock:
            imessage_sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_imessage_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_imessage_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        # Send final state and close
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with imessage_sse_clients_lock:
                if client_queue in imessage_sse_clients:
                    imessage_sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/imessages/import/cancel")
async def cancel_imessage_import():
    """Cancel iMessage import if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global imessage_import_in_progress
    
    with imessage_import_lock:
        if not imessage_import_in_progress:
            return {
                "message": "No iMessage import is currently in progress",
                "cancelled": False
            }
        
        # Set cancellation flag
        imessage_import_cancelled.set()
        
        return {
            "message": "iMessage import cancellation requested. Processing will stop after current conversation completes.",
            "cancelled": True
        }


@app.get("/imessages/import/status")
async def get_imessage_import_status():
    """Get the current status of iMessage import.
    
    Returns:
        Status information about iMessage import
    """
    global imessage_import_in_progress
    
    progress_state = get_imessage_progress_state()
    
    with imessage_import_lock:
        return {
            "in_progress": imessage_import_in_progress,
            "cancelled": imessage_import_cancelled.is_set(),
            **progress_state
        }


@app.get("/imessages/chat-sessions")
async def get_chat_sessions():
    """Get list of unique chat session names from messages table.
    
    Returns:
        Dictionary with contacts_and_groups and other arrays
    """
    message_service = MessageService(db=db)
    try:
        result = message_service.get_chat_sessions()
        
        # Convert ChatSessionInfo objects to dictionaries
        def session_to_dict(session_info: ChatSessionInfo) -> dict:
            last_date = None
            if session_info.last_message_date:
                if hasattr(session_info.last_message_date, 'isoformat'):
                    last_date = session_info.last_message_date.isoformat()
                else:
                    last_date = str(session_info.last_message_date)
            
            return {
                "chat_session": session_info.chat_session,
                "message_count": session_info.message_count,
                "has_attachments": session_info.attachment_count > 0,
                "attachment_count": session_info.attachment_count,
                "message_type": session_info.message_type,
                "last_message_date": last_date
            }
        
        return {
            "contacts_and_groups": [session_to_dict(s) for s in result.contacts_and_groups],
            "other": [session_to_dict(s) for s in result.other]
        }
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_chat_sessions: {e}")
        traceback.print_exc()
        # Return empty arrays on error instead of crashing
        return {
            "contacts_and_groups": [],
            "other": []
        }


@app.get("/imessages/conversation/{chat_session}")
async def get_conversation_messages(chat_session: str):
    """Get all messages for a specific chat session.
    
    Args:
        chat_session: The chat session name (URL encoded)
        
    Returns:
        List of messages ordered chronologically
    """
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)
    
    session = db.get_session()
    try:
        messages = session.query(IMessage).filter(
            IMessage.chat_session == decoded_session
        ).order_by(
            IMessage.message_date.asc()
        ).all()
        
        from sqlalchemy.orm import joinedload
        messages_data = []
        for msg in messages:
            # Get attachment info from MessageAttachment junction table
            message_attachment = session.query(MessageAttachment).filter(
                MessageAttachment.message_id == msg.id
            ).first()
            
            attachment_filename = None
            attachment_type = None
            has_attachment = False
            
            if message_attachment:
                media_item = session.query(MediaMetadata).filter(
                    MediaMetadata.id == message_attachment.media_item_id
                ).first()
                if media_item:
                    attachment_filename = media_item.title
                    attachment_type = media_item.media_type
                    has_attachment = True
            
            messages_data.append({
                "id": msg.id,
                "chat_session": msg.chat_session,
                "message_date": msg.message_date.isoformat() if msg.message_date else None,
                "delivered_date": msg.delivered_date.isoformat() if msg.delivered_date else None,
                "read_date": msg.read_date.isoformat() if msg.read_date else None,
                "edited_date": msg.edited_date.isoformat() if msg.edited_date else None,
                "service": msg.service,
                "type": msg.type,
                "sender_id": msg.sender_id,
                "sender_name": msg.sender_name,
                "status": msg.status,
                "replying_to": msg.replying_to,
                "subject": msg.subject,
                "text": msg.text,
                "attachment_filename": attachment_filename,
                "attachment_type": attachment_type,
                "has_attachment": has_attachment
            })
        
        return {"messages": messages_data}
    finally:
        session.close()


@app.get("/imessages/{message_id}/metadata")
async def get_message_metadata(message_id: int):
    """Get message metadata by ID.
    
    Args:
        message_id: The ID of the message to retrieve metadata for
        
    Returns:
        Dictionary with message metadata including chat_session
        
    Raises:
        HTTPException: 404 if message not found
    """
    session = db.get_session()
    try:
        message = session.query(IMessage).filter(IMessage.id == message_id).first()
        
        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"Message with ID {message_id} not found"
            )
        
        return {
            "id": message.id,
            "chat_session": message.chat_session,
            "message_date": message.message_date.isoformat() if message.message_date else None,
            "service": message.service,
            "type": message.type,
            "sender_id": message.sender_id,
            "sender_name": message.sender_name,
            "text": message.text
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving message metadata: {str(e)}"
        )
    finally:
        session.close()


@app.post("/imessages/conversation/{chat_session}/summarize")
async def summarize_conversation(chat_session: str):
    """Summarize a conversation using Gemini LLM synchronously.
    
    Args:
        chat_session: The chat session name (URL encoded)
        
    Returns:
        Dictionary with status, summary, and chat_session
        
    Raises:
        HTTPException: 404 if chat session not found, 500 on error
    """
    from urllib.parse import unquote
    
    decoded_session = unquote(chat_session)
    
    # Get formatted conversation messages using MessageService
    try:
        message_service = MessageService(db=db)
        messages_data = message_service.get_formatted_conversation_messages(decoded_session)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    
    # Initialize Gemini service and get summary synchronously
    try:
        gemini_service = GeminiService()
    except ValueError as e:
        # Error during initialization (e.g., missing API key, invalid model)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
    try:
        summary = gemini_service.summarize_conversation(messages_data)
    except ValueError as e:
        # Missing API key or invalid data
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        # Other errors
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating summary: {error_msg}"
        )
    
    return {
        "status": "completed",
        "summary": summary,
        "chat_session": decoded_session
    }

@app.post("/emails/thread/{participant}/summarize")
async def summarize_conversation(participant: str):
    """Summarize email intercation  with a person using Gemini LLM synchronously.
    
    Args:
        participant: The person (URL encoded)
        
    Returns:
        Dictionary with status, summary, and chat_session
        
    Raises:
        HTTPException: 404 if chat session not found, 500 on error
    """
    from urllib.parse import unquote
    
    decoded_session = unquote(participant)
    
    # Get conversation messages using EmailService
    try:
        email_service = EmailService()
        messages_data = email_service.get_conversation_messages(decoded_session, db)
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    
    # Initialize Gemini service and get summary synchronously
    try:
        gemini_service = GeminiService()
    except ValueError as e:
        # Error during initialization (e.g., missing API key, invalid model)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
    try:
        summary = gemini_service.summarize_conversation(messages_data)
    except ValueError as e:
        # Missing API key or invalid data
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        # Other errors
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating summary: {error_msg}"
        )
    
    return {
        "status": "completed",
        "summary": summary,
        "chat_session": decoded_session
    }


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    prompt: str
    voice: Optional[str] = None
    temperature: Optional[float] = None
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str
    voice: Optional[str] = None
    embedded_json: Optional[Dict[str, Any]] = None


@app.post("/chat/generate", response_model=ChatResponse)
async def generate_chat_response(request: ChatRequest):
    """Generate a chat response using ChatService with Gemini LLM.
    
    This endpoint allows users to send a prompt and receive a response from the ChatService.
    The ChatService includes reference documents (with available_for_task=True) and 
    maintains conversation history (last 20 turns).
    
    Args:
        request: ChatRequest with prompt and optional voice selection
        
    Returns:
        ChatResponse with generated response text
        
    Raises:
        HTTPException: 500 on error
    """
    try:
        # Use global ChatService instance (maintains conversation history across requests)
        # Set voice if provided
        if request.voice:
            try:
                chat_service.set_voice(request.voice)
            except Exception as e:
                print(f"[generate_chat_response] Warning: Could not set voice '{request.voice}': {str(e)}")
        
        # Generate response using global chat_service instance
        temperature = request.temperature if request.temperature is not None else 0.0
        response_text, metadata_json_str = chat_service.generate_response(
            request.prompt, 
            temperature=temperature,
            conversation_id=request.conversation_id,
            db=db
        )

        # Parse response to extract embedded JSON from markdown code blocks
        text_content = response_text
        metadata_json = json.loads(metadata_json_str)
        embedded_json = None
        
        # Pattern to match JSON in markdown code blocks (```json ... ```)
        json_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        if matches:
            # Parse all JSON blocks and merge them
            merged_json = {}
            for json_str in matches:
                try:
                    parsed_json = json.loads(json_str.strip())



                    # Merge: if keys conflict, later blocks override earlier ones
                    # But preserve metadata keys (referenced_files, function_calls) separately
                    if isinstance(parsed_json, dict):
                        # If this block has metadata keys, merge them specially
                        if "referenced_files" in parsed_json or "function_calls" in parsed_json:
                            # This is metadata block - merge metadata keys
                            if "referenced_files" in parsed_json:
                                metadata_json["referenced_files"] = parsed_json["referenced_files"]
                            if "function_calls" in parsed_json:
                                metadata_json["function_calls"] = parsed_json["function_calls"]
                            # Also merge other keys
                            for key, value in parsed_json.items():
                                if key not in ["referenced_files", "function_calls"]:
                                    metadata_json[key] = value
                        else:
                            # Regular JSON block - merge normally
                            metadata_json.update(parsed_json)
                except json.JSONDecodeError as e:
                    print(f"[generate_chat_response] Warning: Could not parse embedded JSON block: {str(e)}")
                    continue
            
            if metadata_json:
                #embedded_json = merged_json
                # Remove all JSON code blocks from the text content
                text_content = re.sub(json_pattern, '', response_text, flags=re.DOTALL).strip()
                metadata_json["temperature"] = request.temperature
                metadata_json["prompt"] = request.prompt
                metadata_json["voice"] = chat_service.voice
                metadata_json["response_text"] = text_content
        
        return ChatResponse(
            response=text_content,
            voice=chat_service.voice,
            embedded_json=metadata_json
        )
        
    except ValueError as e:
        # Missing API key or invalid data
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    except Exception as e:
        # Other errors
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error generating chat response: {error_msg}"
        )


# Conversation Management Endpoints

class ConversationCreateRequest(BaseModel):
    """Request model for creating a conversation."""
    title: str
    voice: str


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation."""
    title: Optional[str] = None
    voice: Optional[str] = None


@app.post("/chat/conversations")
async def create_conversation(request: ConversationCreateRequest):
    """Create a new conversation.
    
    Args:
        request: ConversationCreateRequest with title and voice
        
    Returns:
        Dictionary with conversation details
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.create_conversation(request.title, request.voice)
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in create_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating conversation: {str(e)}")


@app.get("/chat/conversations")
async def list_conversations(limit: Optional[int] = Query(None)):
    """List all conversations, ordered by most recent activity.
    
    Args:
        limit: Optional limit on number of conversations to return
        
    Returns:
        List of conversation dictionaries
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversations = conversation_service.list_conversations(limit=limit)
        
        # Import here to avoid circular imports
        from ..database.models import ChatTurn
        
        result = []
        session = db.get_session()
        try:
            for conv in conversations:
                # Get turn count using a query (more reliable than lazy loading)
                # Use the conversation ID directly since we can't rely on the relationship
                # across different sessions
                turn_count = session.query(func.count(ChatTurn.id)).filter(
                    ChatTurn.conversation_id == conv.id
                ).scalar() or 0
                
                result.append({
                    "id": conv.id,
                    "title": conv.title,
                    "voice": conv.voice,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                    "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                    "turn_count": turn_count
                })
        finally:
            session.close()
        
        return result
    except Exception as e:
        import traceback
        print(f"Error in list_conversations: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing conversations: {str(e)}")


@app.get("/chat/conversations/{conversation_id}")
async def get_conversation(conversation_id: int):
    """Get conversation details including turns.
    
    Args:
        conversation_id: ID of the conversation
        
    Returns:
        Dictionary with conversation details and turns
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.get_conversation(conversation_id)
        
        # Get turns
        turns = conversation_service.get_conversation_turns(conversation_id, limit=30)
        
        turns_data = []
        for turn in turns:
            turns_data.append({
                "id": turn.id,
                "user_input": turn.user_input,
                "response_text": turn.response_text,
                "voice": turn.voice,
                "temperature": turn.temperature,
                "turn_number": turn.turn_number,
                "created_at": turn.created_at.isoformat() if turn.created_at else None
            })
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
            "turns": turns_data
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting conversation: {str(e)}")


@app.put("/chat/conversations/{conversation_id}")
async def update_conversation(conversation_id: int, request: ConversationUpdateRequest):
    """Update conversation metadata.
    
    Args:
        conversation_id: ID of the conversation
        request: ConversationUpdateRequest with optional title and voice
        
    Returns:
        Dictionary with updated conversation details
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation = conversation_service.update_conversation(
            conversation_id,
            title=request.title,
            voice=request.voice
        )
        
        return {
            "id": conversation.id,
            "title": conversation.title,
            "voice": conversation.voice,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in update_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating conversation: {str(e)}")


@app.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int):
    """Delete a conversation and all its turns.
    
    Args:
        conversation_id: ID of the conversation
        
    Returns:
        Dictionary with success status
    """
    try:
        conversation_service = ChatConversationService(db=db)
        conversation_service.delete_conversation(conversation_id)
        
        return {"success": True, "message": f"Conversation {conversation_id} deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in delete_conversation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error deleting conversation: {str(e)}")


# Subject Configuration Endpoints

class SubjectConfigurationRequest(BaseModel):
    """Request model for subject configuration."""
    subject_name: str
    system_instructions: str


@app.get("/api/subject-configuration")
async def get_subject_configuration():
    """Get current subject configuration.
    
    Returns:
        Dictionary with subject configuration or 404 if not set
    """
    try:
        config_service = SubjectConfigurationService(db=db)
        configuration = config_service.get_configuration()
        
        if not configuration:
            raise HTTPException(status_code=404, detail="Subject configuration not found")
        
        return {
            "id": configuration.id,
            "subject_name": configuration.subject_name,
            "system_instructions": configuration.system_instructions,
            "created_at": configuration.created_at.isoformat() if configuration.created_at else None,
            "updated_at": configuration.updated_at.isoformat() if configuration.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in get_subject_configuration: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting subject configuration: {str(e)}")


@app.post("/api/subject-configuration")
async def create_or_update_subject_configuration(request: SubjectConfigurationRequest):
    """Create or update subject configuration.
    
    Args:
        request: SubjectConfigurationRequest with subject_name and system_instructions
        
    Returns:
        Dictionary with created/updated configuration
    """
    try:
        config_service = SubjectConfigurationService(db=db)
        configuration = config_service.create_or_update_configuration(
            subject_name=request.subject_name,
            system_instructions=request.system_instructions
        )
        
        # Reload system prompt in chat service to use new configuration
        chat_service.reload_system_prompt(db=db)
        
        return {
            "id": configuration.id,
            "subject_name": configuration.subject_name,
            "system_instructions": configuration.system_instructions,
            "created_at": configuration.created_at.isoformat() if configuration.created_at else None,
            "updated_at": configuration.updated_at.isoformat() if configuration.updated_at else None
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in create_or_update_subject_configuration: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error saving subject configuration: {str(e)}")


@app.get("/chat/conversations/{conversation_id}/turns")
async def get_conversation_turns(conversation_id: int, limit: int = Query(30, ge=1, le=100)):
    """Get turns for a conversation.
    
    Args:
        conversation_id: ID of the conversation
        limit: Maximum number of turns to return (default 30, max 100)
        
    Returns:
        List of turn dictionaries
    """
    try:
        conversation_service = ChatConversationService(db=db)
        turns = conversation_service.get_conversation_turns(conversation_id, limit=limit)
        
        turns_data = []
        for turn in turns:
            turns_data.append({
                "id": turn.id,
                "user_input": turn.user_input,
                "response_text": turn.response_text,
                "voice": turn.voice,
                "temperature": turn.temperature,
                "turn_number": turn.turn_number,
                "created_at": turn.created_at.isoformat() if turn.created_at else None
            })
        
        return turns_data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_conversation_turns: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting conversation turns: {str(e)}")


def summarize_conversation_background(chat_session: str, messages_data: Dict[str, Any]):
    """Background task to summarize conversation using Gemini LLM.
    
    Args:
        chat_session: The chat session name
        messages_data: Dictionary containing formatted messages
    """
    global conversation_summary_in_progress
    
    try:
        # Update progress: processing started
        update_conversation_summary_progress_state(
            status="processing",
            stage="calling_llm"
        )
        broadcast_conversation_summary_event_sync("progress", {
            "status": "processing",
            "stage": "calling_llm",
            "chat_session": chat_session
        })
        
        # Initialize Gemini service and get summary
        try:
            gemini_service = GeminiService()
        except ValueError as e:
            # Error during initialization (e.g., missing API key, invalid model)
            error_msg = str(e)
            update_conversation_summary_progress_state(
                status="error",
                error=error_msg
            )
            broadcast_conversation_summary_event_sync("error", {
                "status": "error",
                "error": error_msg,
                "chat_session": chat_session
            })
            return
        
        summary = gemini_service.summarize_conversation(messages_data)
        
        # Update progress: completed
        update_conversation_summary_progress_state(
            status="completed",
            stage="completed",
            summary=summary
        )
        broadcast_conversation_summary_event_sync("completed", {
            "status": "completed",
            "summary": summary,
            "chat_session": chat_session
        })
        
    except ValueError as e:
        # Missing API key or invalid data
        error_msg = str(e)
        update_conversation_summary_progress_state(
            status="error",
            error=error_msg
        )
        broadcast_conversation_summary_event_sync("error", {
            "status": "error",
            "error": error_msg,
            "chat_session": chat_session
        })
    except Exception as e:
        # Other errors
        import traceback
        error_msg = str(e)
        # If it's already a user-friendly message, use it directly
        if not error_msg.startswith("Error generating summary:"):
            error_msg = f"Error generating summary: {error_msg}"
        traceback.print_exc()
        update_conversation_summary_progress_state(
            status="error",
            error=error_msg
        )
        broadcast_conversation_summary_event_sync("error", {
            "status": "error",
            "error": error_msg,
            "chat_session": chat_session
        })
    finally:
        # Reset in_progress flag
        with conversation_summary_lock:
            conversation_summary_in_progress = False


@app.get("/imessages/conversation/{chat_session}/summarize/stream")
async def stream_conversation_summary_progress(chat_session: str):
    """Stream conversation summary progress updates via Server-Sent Events (SSE).
    
    Args:
        chat_session: The chat session name (URL encoded)
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)
    
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with conversation_summary_sse_clients_lock:
            conversation_summary_sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_conversation_summary_progress_state()
            # Only send if it's for this chat session
            if initial_state.get("chat_session") == decoded_session:
                event_data = {
                    "type": "progress",
                    "data": initial_state
                }
                yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_conversation_summary_progress_state()
                    if progress_state.get("chat_session") == decoded_session:
                        if progress_state["status"] in ["completed", "error"]:
                            # Send final state and close
                            final_event = {
                                "type": progress_state["status"],
                                "data": progress_state
                            }
                            yield f"data: {json.dumps(final_event)}\n\n"
                            break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with conversation_summary_sse_clients_lock:
                if client_queue in conversation_summary_sse_clients:
                    conversation_summary_sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.delete("/imessages/conversation/{chat_session}")
async def delete_conversation(chat_session: str):
    """Delete all messages for a specific chat session.
    
    Args:
        chat_session: The chat session name (URL encoded)
        
    Returns:
        Success message with count of deleted messages
        
    Raises:
        HTTPException: 404 if chat session not found
    """
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)
    
    session = db.get_session()
    try:
        # Count messages before deletion
        message_count = session.query(IMessage).filter(
            IMessage.chat_session == decoded_session
        ).count()
        
        if message_count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Chat session '{decoded_session}' not found"
            )
        
        # Delete all messages for this chat session
        deleted_count = session.query(IMessage).filter(
            IMessage.chat_session == decoded_session
        ).delete()
        
        session.commit()
        
        return {
            "message": f"Successfully deleted {deleted_count} message(s) from chat session",
            "deleted_count": deleted_count,
            "chat_session": decoded_session
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting chat session: {str(e)}"
        )
    finally:
        session.close()


def import_whatsapp_background(directory_path: str, result_dict: dict):
    """Background function to import WhatsApp messages from directory."""
    global whatsapp_import_in_progress
    
    # Mark processing as started
    with whatsapp_import_lock:
        whatsapp_import_in_progress = True
        whatsapp_import_cancelled.clear()
    
    # Initialize progress state
    update_whatsapp_progress_state(
        current_conversation=None,
        conversations_processed=0,
        total_conversations=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_whatsapp_progress_event_sync("progress", get_whatsapp_progress_state())
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if whatsapp_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_whatsapp_progress_state(
                current_conversation=stats.get("current_conversation"),
                conversations_processed=stats.get("conversations_processed", 0),
                total_conversations=stats.get("total_conversations", 0),
                messages_imported=stats.get("messages_imported", 0),
                messages_created=stats.get("messages_created", 0),
                messages_updated=stats.get("messages_updated", 0),
                attachments_found=stats.get("attachments_found", 0),
                attachments_missing=stats.get("attachments_missing", 0),
                missing_attachment_filenames=stats.get("missing_attachment_filenames", []),
                errors=stats.get("errors", 0),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_whatsapp_progress_event_sync("progress", get_whatsapp_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return whatsapp_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_whatsapp_from_directory(
            directory_path,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_whatsapp_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in whatsapp_import_progress}
        )
        broadcast_whatsapp_progress_event_sync("completed", get_whatsapp_progress_state())
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_whatsapp_progress_state(
            status="error",
            error_message=error_msg
        )
        broadcast_whatsapp_progress_event_sync("error", get_whatsapp_progress_state())
        
        print(f"[Background Task] Error importing WhatsApp messages: {error_msg}")
    finally:
        # Mark processing as completed
        with whatsapp_import_lock:
            whatsapp_import_in_progress = False


@app.post("/whatsapp/import", response_model=ImportWhatsAppResponse)
async def import_whatsapp(
    request: ImportWhatsAppRequest,
    background_tasks: BackgroundTasks
):
    """Import WhatsApp messages from a directory structure asynchronously.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain a CSV file with the messages.
    
    Args:
        request: ImportWhatsAppRequest with directory_path
        background_tasks: FastAPI background tasks
        
    Returns:
        ImportWhatsAppResponse with initial status
        
    Raises:
        HTTPException: If directory doesn't exist or import already in progress
    """
    global whatsapp_import_in_progress
    
    # Check if import is already in progress
    with whatsapp_import_lock:
        if whatsapp_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="WhatsApp import is already in progress. Please cancel it first or wait for it to complete."
            )
    
    # Validate directory exists
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )
    
    result_dict = {
        "conversations_processed": 0,
        "messages_imported": 0,
        "messages_created": 0,
        "messages_updated": 0,
        "attachments_found": 0,
        "attachments_missing": 0,
        "missing_attachment_filenames": [],
        "errors": 0,
        "success": False
    }
    
    # Start background processing
    background_tasks.add_task(
        import_whatsapp_background,
        request.directory_path,
        result_dict
    )
    
    return ImportWhatsAppResponse(
        message="WhatsApp import started",
        directory_path=request.directory_path,
        conversations_processed=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        timestamp=datetime.now()
    )


@app.get("/whatsapp/import/stream")
async def stream_whatsapp_import_progress():
    """Stream WhatsApp import progress updates via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with whatsapp_sse_clients_lock:
            whatsapp_sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_whatsapp_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_whatsapp_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        # Send final state and close
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with whatsapp_sse_clients_lock:
                if client_queue in whatsapp_sse_clients:
                    whatsapp_sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/whatsapp/import/cancel")
async def cancel_whatsapp_import():
    """Cancel WhatsApp import if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global whatsapp_import_in_progress
    
    with whatsapp_import_lock:
        if not whatsapp_import_in_progress:
            return {
                "message": "No WhatsApp import is currently in progress",
                "cancelled": False
            }
        
        # Set cancellation flag
        whatsapp_import_cancelled.set()
        
        return {
            "message": "WhatsApp import cancellation requested. Processing will stop after current conversation completes.",
            "cancelled": True
        }


@app.get("/whatsapp/import/status")
async def get_whatsapp_import_status():
    """Get the current status of WhatsApp import.
    
    Returns:
        Status information about WhatsApp import
    """
    global whatsapp_import_in_progress
    
    progress_state = get_whatsapp_progress_state()
    
    with whatsapp_import_lock:
        return {
            "in_progress": whatsapp_import_in_progress,
            "cancelled": whatsapp_import_cancelled.is_set(),
            **progress_state
        }


def import_facebook_background(directory_path: str, user_name: Optional[str], result_dict: dict):
    """Background function to import Facebook Messenger messages from directory."""
    global facebook_import_in_progress
    
    # Mark processing as started
    with facebook_import_lock:
        facebook_import_in_progress = True
        facebook_import_cancelled.clear()
    
    # Initialize progress state
    update_facebook_progress_state(
        current_conversation=None,
        conversations_processed=0,
        total_conversations=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_facebook_progress_event_sync("progress", get_facebook_progress_state())
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if facebook_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_facebook_progress_state(
                current_conversation=stats.get("current_conversation"),
                conversations_processed=stats.get("conversations_processed", 0),
                total_conversations=stats.get("total_conversations", 0),
                messages_imported=stats.get("messages_imported", 0),
                messages_created=stats.get("messages_created", 0),
                messages_updated=stats.get("messages_updated", 0),
                attachments_found=stats.get("attachments_found", 0),
                attachments_missing=stats.get("attachments_missing", 0),
                missing_attachment_filenames=stats.get("missing_attachment_filenames", []),
                errors=stats.get("errors", 0),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_facebook_progress_event_sync("progress", get_facebook_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return facebook_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_facebook_from_directory(
            directory_path,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check,
            user_name=user_name
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_facebook_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in facebook_import_progress}
        )
        broadcast_facebook_progress_event_sync("completed", get_facebook_progress_state())
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_facebook_progress_state(
            status="error",
            error_message=error_msg
        )
        broadcast_facebook_progress_event_sync("error", get_facebook_progress_state())
        
        print(f"[Background Task] Error importing Facebook Messenger messages: {error_msg}")
    finally:
        # Mark processing as completed
        with facebook_import_lock:
            facebook_import_in_progress = False


@app.post("/facebook/import", response_model=ImportFacebookResponse)
async def import_facebook(
    request: ImportFacebookRequest,
    background_tasks: BackgroundTasks
):
    """Import Facebook Messenger messages from a directory structure asynchronously.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain JSON files (message_1.json, message_2.json, etc.) with the messages.
    
    The export_root parameter is optional. If not provided, the system will attempt to auto-detect
    the export root directory by searching upward from the directory_path for 'your_facebook_activity'.
    
    Args:
        request: ImportFacebookRequest with directory_path, optional export_root and user_name
        background_tasks: FastAPI background tasks
        
    Returns:
        ImportFacebookResponse with initial status
        
    Raises:
        HTTPException: If directory doesn't exist or import already in progress
    """
    global facebook_import_in_progress
    
    # Check if import is already in progress
    with facebook_import_lock:
        if facebook_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Facebook Messenger import is already in progress. Please cancel it first or wait for it to complete."
            )
    
    # Validate directory exists
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )
    
    result_dict = {
        "conversations_processed": 0,
        "messages_imported": 0,
        "messages_created": 0,
        "messages_updated": 0,
        "attachments_found": 0,
        "attachments_missing": 0,
        "missing_attachment_filenames": [],
        "errors": 0,
        "success": False
    }
    
    # Start background processing
    background_tasks.add_task(
        import_facebook_background,
        request.directory_path,
        request.user_name,
        result_dict
    )
    
    return ImportFacebookResponse(
        message="Facebook Messenger import started",
        directory_path=request.directory_path,
        conversations_processed=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        attachments_found=0,
        attachments_missing=0,
        missing_attachment_filenames=[],
        errors=0,
        timestamp=datetime.now()
    )


@app.get("/facebook/import/stream")
async def stream_facebook_import_progress():
    """Stream Facebook Messenger import progress updates via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with facebook_sse_clients_lock:
            facebook_sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_facebook_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_facebook_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        # Send final state and close
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with facebook_sse_clients_lock:
                if client_queue in facebook_sse_clients:
                    facebook_sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/facebook/import/cancel")
async def cancel_facebook_import():
    """Cancel Facebook Messenger import if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global facebook_import_in_progress
    
    with facebook_import_lock:
        if not facebook_import_in_progress:
            return {
                "message": "No Facebook Messenger import is currently in progress",
                "cancelled": False
            }
        
        # Set cancellation flag
        facebook_import_cancelled.set()
        
        return {
            "message": "Facebook Messenger import cancellation requested. Processing will stop after current conversation completes.",
            "cancelled": True
        }


@app.get("/facebook/import/status")
async def get_facebook_import_status():
    """Get the current status of Facebook Messenger import.
    
    Returns:
        Status information about Facebook Messenger import
    """
    global facebook_import_in_progress
    
    progress_state = get_facebook_progress_state()
    
    with facebook_import_lock:
        return {
            "in_progress": facebook_import_in_progress,
            "cancelled": facebook_import_cancelled.is_set(),
            **progress_state
        }


def import_instagram_background(
    directory_path: str,
    user_name: Optional[str],
    result_dict: Dict[str, Any]
):
    """Background function to import Instagram messages from directory."""
    global instagram_import_in_progress
    
    # Mark import as in progress
    with instagram_import_lock:
        instagram_import_in_progress = True
        instagram_import_cancelled.clear()
    
    # Initialize progress state
    update_instagram_progress_state(
        current_conversation=None,
        conversations_processed=0,
        total_conversations=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_instagram_progress_event_sync()
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if instagram_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_instagram_progress_state(
                current_conversation=stats.get("current_conversation"),
                conversations_processed=stats.get("conversations_processed", 0),
                total_conversations=stats.get("total_conversations", 0),
                messages_imported=stats.get("messages_imported", 0),
                messages_created=stats.get("messages_created", 0),
                messages_updated=stats.get("messages_updated", 0),
                errors=stats.get("errors", 0),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_instagram_progress_event_sync()
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return instagram_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_instagram_from_directory(
            directory_path,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check,
            user_name=user_name
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_instagram_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in instagram_import_progress}
        )
        broadcast_instagram_progress_event_sync()
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_instagram_progress_state(
            status="error",
            error_message=error_msg
        )
        broadcast_instagram_progress_event_sync()
        
        print(f"[Background Task] Error importing Instagram messages: {error_msg}")
    finally:
        # Mark processing as completed
        with instagram_import_lock:
            instagram_import_in_progress = False


@app.post("/instagram/import", response_model=ImportInstagramResponse)
async def import_instagram(
    request: ImportInstagramRequest,
    background_tasks: BackgroundTasks
):
    """Import Instagram messages from a directory structure asynchronously.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain JSON files (message_1.json, message_2.json, etc.) with the messages.
    
    The system will automatically detect the export root directory by searching upward
    from the directory_path for 'your_instagram_activity'.
    
    Args:
        request: ImportInstagramRequest with directory_path and optional user_name
        background_tasks: FastAPI background tasks
        
    Returns:
        ImportInstagramResponse with initial status
        
    Raises:
        HTTPException: If directory doesn't exist or import already in progress
    """
    global instagram_import_in_progress
    
    # Check if import is already in progress
    with instagram_import_lock:
        if instagram_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Instagram import is already in progress. Please cancel it first or wait for it to complete."
            )
    
    # Validate directory exists
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )
    
    result_dict = {
        "conversations_processed": 0,
        "messages_imported": 0,
        "messages_created": 0,
        "messages_updated": 0,
        "errors": 0,
        "success": False
    }
    
    # Start background processing
    background_tasks.add_task(
        import_instagram_background,
        request.directory_path,
        request.user_name,
        result_dict
    )
    
    return ImportInstagramResponse(
        message="Instagram import started",
        directory_path=request.directory_path,
        conversations_processed=0,
        messages_imported=0,
        messages_created=0,
        messages_updated=0,
        errors=0,
        timestamp=datetime.now()
    )


@app.get("/instagram/import/stream")
async def stream_instagram_import_progress():
    """Stream Instagram import progress updates via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with instagram_sse_clients_lock:
            instagram_sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_instagram_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_instagram_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        # Send final state and close
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with instagram_sse_clients_lock:
                if client_queue in instagram_sse_clients:
                    instagram_sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/instagram/import/cancel")
async def cancel_instagram_import():
    """Cancel Instagram import if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global instagram_import_in_progress
    
    with instagram_import_lock:
        if not instagram_import_in_progress:
            return {
                "message": "No Instagram import is currently in progress",
                "cancelled": False
            }
        
        instagram_import_cancelled.set()
        
        return {
            "message": "Instagram import cancellation requested. Processing will stop after current conversation completes.",
            "cancelled": True
        }


@app.get("/instagram/import/status")
async def get_instagram_import_status():
    """Get the current status of Instagram import.
    
    Returns:
        Status information about Instagram import
    """
    global instagram_import_in_progress
    
    progress_state = get_instagram_progress_state()
    
    with instagram_import_lock:
        return {
            "in_progress": instagram_import_in_progress,
            "cancelled": instagram_import_cancelled.is_set(),
            **progress_state
        }


def import_facebook_albums_background(directory_path: str, result_dict: dict):
    """Background function to import Facebook Albums from directory."""
    global facebook_albums_import_in_progress
    
    # Mark processing as started
    with facebook_albums_import_lock:
        facebook_albums_import_in_progress = True
        facebook_albums_import_cancelled.clear()
    
    # Initialize progress state
    update_facebook_albums_progress_state(
        current_album=None,
        albums_processed=0,
        total_albums=0,
        albums_imported=0,
        images_imported=0,
        images_found=0,
        images_missing=0,
        missing_image_filenames=[],
        errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_facebook_albums_progress_event_sync("progress", get_facebook_albums_progress_state())
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if facebook_albums_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_facebook_albums_progress_state(
                current_album=stats.get("current_album"),
                albums_processed=stats.get("albums_processed", 0),
                total_albums=stats.get("total_albums", 0),
                albums_imported=stats.get("albums_imported", 0),
                images_imported=stats.get("images_imported", 0),
                images_found=stats.get("images_found", 0),
                images_missing=stats.get("images_missing", 0),
                missing_image_filenames=stats.get("missing_image_filenames", []),
                errors=stats.get("errors", 0),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_facebook_albums_progress_event_sync("progress", get_facebook_albums_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return facebook_albums_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_facebook_albums_from_directory(
            directory_path,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_facebook_albums_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in facebook_albums_import_progress}
        )
        broadcast_facebook_albums_progress_event_sync("completed", get_facebook_albums_progress_state())
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_facebook_albums_progress_state(
            status="error",
            error_message=error_msg
        )
        broadcast_facebook_albums_progress_event_sync("error", get_facebook_albums_progress_state())
        
        print(f"[Background Task] Error importing Facebook Albums: {error_msg}")
    finally:
        # Mark processing as completed
        with facebook_albums_import_lock:
            facebook_albums_import_in_progress = False


def import_filesystem_images_background(
    directory_paths: List[str],
    max_images: Optional[int],
    create_thumbnail: bool,
    result_dict: dict
):
    """Background function to import images from filesystem.
    
    Args:
        directory_paths: List of directory paths to import from
        max_images: Maximum total number of images to import across all directories (None for all)
        create_thumbnail: Whether to create thumbnails
        result_dict: Dictionary to store results
    """
    global filesystem_import_in_progress
    
    # Mark processing as started
    with filesystem_import_lock:
        filesystem_import_in_progress = True
        filesystem_import_cancelled.clear()
    
    # Initialize progress state
    update_filesystem_import_progress_state(
        status="in_progress",
        current_file=None,
        files_processed=0,
        total_files=0,
        images_imported=0,
        images_updated=0,
        errors=0,
        error_messages=[]
    )
    
    # Broadcast initial progress event
    broadcast_filesystem_import_progress_event_sync("progress", get_filesystem_import_progress_state())
    
    # Accumulated stats across all directories
    accumulated_stats = {
        'total_files': 0,
        'files_processed': 0,
        'images_imported': 0,
        'images_updated': 0,
        'errors': 0,
        'error_messages': [],
        'current_file': None
    }
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if filesystem_import_cancelled.is_set():
                return
            
            # Calculate totals: accumulated stats from previous directories + current directory progress
            # Note: stats from import_images_from_filesystem are cumulative for the current directory
            # So we add accumulated stats (from previous directories) to current directory stats
            update_filesystem_import_progress_state(
                current_file=stats.get("current_file"),
                files_processed=accumulated_stats['files_processed'] + stats.get("files_processed", 0),
                total_files=accumulated_stats['total_files'] + stats.get("total_files", 0),
                images_imported=accumulated_stats['images_imported'] + stats.get("images_imported", 0),
                images_updated=accumulated_stats['images_updated'] + stats.get("images_updated", 0),
                errors=accumulated_stats['errors'] + stats.get("errors", 0),
                error_messages=accumulated_stats['error_messages'] + stats.get("error_messages", []),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_filesystem_import_progress_event_sync("progress", get_filesystem_import_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return filesystem_import_cancelled.is_set()
        
        # Get exclude patterns from config
        config = get_config()
        exclude_patterns = config.get_filesystem_exclude_patterns()
        
        # Process each directory sequentially
        remaining_images = max_images  # Track remaining images if max_images is set
        for idx, directory_path in enumerate(directory_paths):
            # Check for cancellation before processing each directory
            if filesystem_import_cancelled.is_set():
                break
            
            # Calculate max_images for this directory
            directory_max_images = None
            if remaining_images is not None:
                # If we've already imported enough, skip remaining directories
                if remaining_images <= 0:
                    break
                directory_max_images = remaining_images
            
            # Run import with progress callback for this directory
            stats = import_images_from_filesystem(
                root_directory=directory_path,
                max_images=directory_max_images,
                should_create_thumbnail=create_thumbnail,
                progress_callback=progress_callback,
                cancelled_check=cancelled_check,
                exclude_patterns=exclude_patterns
            )
            
            # Accumulate stats (stats from import_images_from_filesystem are totals for that directory)
            accumulated_stats['total_files'] += stats.get('total_files', 0)
            accumulated_stats['files_processed'] += stats.get('files_processed', 0)
            accumulated_stats['images_imported'] += stats.get('images_imported', 0)
            accumulated_stats['images_updated'] += stats.get('images_updated', 0)
            accumulated_stats['errors'] += stats.get('errors', 0)
            accumulated_stats['error_messages'].extend(stats.get('error_messages', []))
            
            # Update remaining images count
            if remaining_images is not None:
                images_added = stats.get('images_imported', 0) + stats.get('images_updated', 0)
                remaining_images -= images_added
        
        result_dict.update(accumulated_stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_filesystem_import_progress_state(
            status="completed",
            **{k: v for k, v in accumulated_stats.items() if k in filesystem_import_progress and k != "status"}
        )
        broadcast_filesystem_import_progress_event_sync("completed", get_filesystem_import_progress_state())
        
    except Exception as e:
        error_msg = str(e)
        result_dict["success"] = False
        result_dict["error"] = error_msg
        
        update_filesystem_import_progress_state(
            status="error",
            error_messages=[error_msg]
        )
        broadcast_filesystem_import_progress_event_sync("error", get_filesystem_import_progress_state())
        
        print(f"[Background Task] Error importing filesystem images: {error_msg}")
    finally:
        # Mark processing as completed
        with filesystem_import_lock:
            filesystem_import_in_progress = False


@app.post("/facebook/albums/import", response_model=ImportFacebookAlbumsResponse)
async def import_facebook_albums(
    request: ImportFacebookAlbumsRequest,
    background_tasks: BackgroundTasks
):
    """Import Facebook Albums from a directory structure.
    
    The system will automatically detect the export root directory by searching upward
    from the directory_path for 'your_facebook_activity'.
    
    Args:
        request: Import request containing directory_path
        
    Returns:
        Response indicating import has started
        
    Raises:
        HTTPException: 400 if import is already in progress
    """
    global facebook_albums_import_in_progress
    
    with facebook_albums_import_lock:
        if facebook_albums_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Facebook Albums import is already in progress"
            )
    
    # Validate directory path
    directory_path = Path(request.directory_path)
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )
    
    # Prepare result dictionary for background task
    result_dict = {}
    
    # Start background import task
    background_tasks.add_task(
        import_facebook_albums_background,
        str(directory_path),
        result_dict
    )
    
    return ImportFacebookAlbumsResponse(
        message="Facebook Albums import started",
        directory_path=request.directory_path,
        albums_processed=0,
        albums_imported=0,
        images_imported=0,
        images_found=0,
        images_missing=0,
        missing_image_filenames=[],
        errors=0,
        timestamp=datetime.utcnow()
    )


@app.get("/facebook/albums/import/stream")
async def stream_facebook_albums_import_progress(request: Request):
    """Stream Facebook Albums import progress via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()
        
        # Add client queue to list
        with facebook_albums_sse_clients_lock:
            facebook_albums_sse_clients.append(client_queue)
        
        try:
            # Send initial state
            initial_state = get_facebook_albums_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with facebook_albums_sse_clients_lock:
                if client_queue in facebook_albums_sse_clients:
                    facebook_albums_sse_clients.remove(client_queue)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/facebook/albums/import/cancel")
async def cancel_facebook_albums_import():
    """Cancel Facebook Albums import if in progress.
    
    Returns:
        Status message indicating cancellation request
    """
    global facebook_albums_import_in_progress
    
    with facebook_albums_import_lock:
        if not facebook_albums_import_in_progress:
            return {"message": "No Facebook Albums import in progress"}
        
        facebook_albums_import_cancelled.set()
        return {"message": "Facebook Albums import cancellation requested"}


@app.get("/facebook/albums/import/status")
async def get_facebook_albums_import_status():
    """Get current status of Facebook Albums import.
    
    Returns:
        Status information about Facebook Albums import
    """
    global facebook_albums_import_in_progress
    
    progress_state = get_facebook_albums_progress_state()
    
    with facebook_albums_import_lock:
        return {
            "in_progress": facebook_albums_import_in_progress,
            "cancelled": facebook_albums_import_cancelled.is_set(),
            **progress_state
        }


@app.post("/images/import", response_model=ImportFilesystemImagesResponse)
async def import_filesystem_images(
    request: ImportFilesystemImagesRequest,
    background_tasks: BackgroundTasks
):
    """Import images from filesystem directory(ies).
    
    Args:
        request: Import request containing root_directory (semicolon-separated paths), optional max_images, and create_thumbnail flag
        background_tasks: FastAPI background tasks
        
    Returns:
        Response indicating import has started
        
    Raises:
        HTTPException: 400 if import is already in progress or directory invalid
    """
    global filesystem_import_in_progress
    
    with filesystem_import_lock:
        if filesystem_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Filesystem images import is already in progress"
            )
    
    # Parse semicolon-separated directory paths
    directory_paths_str = request.root_directory
    directory_paths = [path.strip() for path in directory_paths_str.split(';') if path.strip()]
    
    if not directory_paths:
        raise HTTPException(
            status_code=400,
            detail="At least one directory path is required"
        )
    
    # Validate all directory paths
    invalid_paths = []
    validated_paths = []
    for path_str in directory_paths:
        directory_path = Path(path_str)
        if not directory_path.exists() or not directory_path.is_dir():
            invalid_paths.append(path_str)
        else:
            validated_paths.append(str(directory_path))
    
    if invalid_paths:
        raise HTTPException(
            status_code=400,
            detail=f"One or more directories do not exist or are not directories: {', '.join(invalid_paths)}"
        )
    
    # Prepare result dictionary for background task
    result_dict = {}
    
    # Start background import task with multiple directories
    background_tasks.add_task(
        import_filesystem_images_background,
        validated_paths,
        request.max_images,
        request.create_thumbnail,
        result_dict
    )
    
    return ImportFilesystemImagesResponse(
        message="Filesystem images import started",
        root_directory=request.root_directory,
        files_processed=0,
        total_files=0,
        images_imported=0,
        images_updated=0,
        errors=0,
        timestamp=datetime.utcnow()
    )


@app.get("/images/import/stream")
async def stream_filesystem_import_progress(request: Request):
    """Stream Filesystem import progress via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()
        
        # Add client queue to list
        with filesystem_import_sse_clients_lock:
            filesystem_import_sse_clients.append(client_queue)
        
        try:
            # Send initial state
            initial_state = get_filesystem_import_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with filesystem_import_sse_clients_lock:
                if client_queue in filesystem_import_sse_clients:
                    filesystem_import_sse_clients.remove(client_queue)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/images/import/cancel")
async def cancel_filesystem_import():
    """Cancel Filesystem import if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global filesystem_import_in_progress
    
    with filesystem_import_lock:
        if not filesystem_import_in_progress:
            return {
                "message": "No Filesystem import is currently in progress",
                "cancelled": False
            }
        
        filesystem_import_cancelled.set()
        
        return {
            "message": "Filesystem import cancellation requested. Processing will stop after current image completes.",
            "cancelled": True
        }


@app.get("/images/import/status")
async def get_filesystem_import_status():
    """Get the current status of Filesystem import.
    
    Returns:
        Status information about Filesystem import
    """
    global filesystem_import_in_progress
    
    progress_state = get_filesystem_import_progress_state()
    
    with filesystem_import_lock:
        return {
            "in_progress": filesystem_import_in_progress,
            "cancelled": filesystem_import_cancelled.is_set(),
            **progress_state
        }


def process_thumbnails_background(result_dict: dict):
    """Background function to process image thumbnails.
    
    Phase 1: Scan media_blob table - if thumbnail_data is not null, 
             set image_processed=true in corresponding media_items table.
    Phase 2: Scan media_items table - for items with image_processed=false 
             and media_type starting with "image/", create thumbnails and 
             set image_processed=true.
    """
    global thumbnail_processing_in_progress
    
    # Mark processing as started
    with thumbnail_processing_lock:
        thumbnail_processing_in_progress = True
        thumbnail_processing_cancelled.clear()
    
    # Initialize progress state
    update_thumbnail_processing_progress_state(
        phase=None,
        phase1_scanned=0,
        phase1_updated=0,
        phase2_scanned=0,
        phase2_processed=0,
        phase2_errors=0,
        status="in_progress",
        error_message=None
    )
    
    # Broadcast initial progress event
    broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
    
    try:
        session = db.get_session()
        
        try:
            # Phase 1: Update image_processed for items that already have thumbnails
            update_thumbnail_processing_progress_state(phase="1")
            broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
            
            # Query MediaBlob where thumbnail_data is not null
            blobs_with_thumbnails = session.query(MediaBlob).filter(
                MediaBlob.thumbnail_data.isnot(None)
            ).all()
            
            phase1_scanned = 0
            phase1_updated = 0
            
            for blob in blobs_with_thumbnails:
                # Check for cancellation
                if thumbnail_processing_cancelled.is_set():
                    update_thumbnail_processing_progress_state(status="cancelled")
                    broadcast_thumbnail_processing_event_sync("cancelled", get_thumbnail_processing_progress_state())
                    return
                
                phase1_scanned += 1
                
                # Find corresponding MediaMetadata
                metadata = session.query(MediaMetadata).filter(
                    MediaMetadata.media_blob_id == blob.id,
                    MediaMetadata.image_processed == False
                ).first()
                
                if metadata:
                    metadata.image_processed = True
                    phase1_updated += 1
                    
                    # Commit periodically (every 100 items)
                    if phase1_scanned % 100 == 0:
                        session.commit()
                        update_thumbnail_processing_progress_state(
                            phase1_scanned=phase1_scanned,
                            phase1_updated=phase1_updated
                        )
                        broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
            
            # Final commit for phase 1
            session.commit()
            update_thumbnail_processing_progress_state(
                phase1_scanned=phase1_scanned,
                phase1_updated=phase1_updated
            )
            broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
            
            # Phase 2: Create thumbnails for images without them
            update_thumbnail_processing_progress_state(phase="2")
            broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
            
            # Import create_thumbnail function
            from ..imageimport.filesystemimport import create_thumbnail
            
            # Query MediaMetadata where image_processed=False and media_type starts with "image/"
            items_needing_thumbnails = session.query(MediaMetadata).filter(
                MediaMetadata.image_processed == False,
                MediaMetadata.media_type.like('image/%')
            ).all()
            
            phase2_scanned = 0
            phase2_processed = 0
            phase2_errors = 0
            
            for metadata_item in items_needing_thumbnails:
                # Check for cancellation
                if thumbnail_processing_cancelled.is_set():
                    session.commit()
                    update_thumbnail_processing_progress_state(status="cancelled")
                    broadcast_thumbnail_processing_event_sync("cancelled", get_thumbnail_processing_progress_state())
                    return
                
                phase2_scanned += 1
                
                try:
                    # Get MediaBlob
                    blob = session.query(MediaBlob).filter(
                        MediaBlob.id == metadata_item.media_blob_id
                    ).first()
                    
                    if blob and blob.image_data:
                        # Create thumbnail
                        thumbnail_data = create_thumbnail(blob.image_data)
                        
                        if thumbnail_data:
                            # Update blob with thumbnail
                            blob.thumbnail_data = thumbnail_data
                            # Mark as processed
                            metadata_item.image_processed = True
                            phase2_processed += 1
                        else:
                            # Thumbnail creation failed, but don't count as error
                            # Just mark as processed to avoid retrying
                            metadata_item.image_processed = True
                            phase2_errors += 1
                    else:
                        # No image data, mark as processed to avoid retrying
                        metadata_item.image_processed = True
                        phase2_errors += 1
                    
                    # Commit periodically (every 50 items)
                    if phase2_scanned % 50 == 0:
                        session.commit()
                        update_thumbnail_processing_progress_state(
                            phase2_scanned=phase2_scanned,
                            phase2_processed=phase2_processed,
                            phase2_errors=phase2_errors
                        )
                        broadcast_thumbnail_processing_event_sync("progress", get_thumbnail_processing_progress_state())
                
                except Exception as e:
                    # Handle errors gracefully - continue processing
                    print(f"Error processing thumbnail for media_item {metadata_item.id}: {e}")
                    phase2_errors += 1
                    # Mark as processed to avoid retrying
                    metadata_item.image_processed = True
                    continue
            
            # Final commit for phase 2
            session.commit()
            update_thumbnail_processing_progress_state(
                phase2_scanned=phase2_scanned,
                phase2_processed=phase2_processed,
                phase2_errors=phase2_errors,
                status="completed"
            )
            broadcast_thumbnail_processing_event_sync("completed", get_thumbnail_processing_progress_state())
            
            result_dict.update({
                "success": True,
                "phase1_scanned": phase1_scanned,
                "phase1_updated": phase1_updated,
                "phase2_scanned": phase2_scanned,
                "phase2_processed": phase2_processed,
                "phase2_errors": phase2_errors
            })
        
        except Exception as e:
            error_msg = str(e)
            print(f"Error in thumbnail processing: {error_msg}")
            update_thumbnail_processing_progress_state(
                status="error",
                error_message=error_msg
            )
            broadcast_thumbnail_processing_event_sync("error", get_thumbnail_processing_progress_state())
            result_dict.update({
                "success": False,
                "error": error_msg
            })
        
        finally:
            session.close()
    
    finally:
        # Mark processing as complete
        with thumbnail_processing_lock:
            thumbnail_processing_in_progress = False


@app.post("/images/process-thumbnails")
async def start_thumbnail_processing(background_tasks: BackgroundTasks):
    """Start thumbnail processing.
    
    Returns:
        Response indicating processing has started
        
    Raises:
        HTTPException: 400 if processing is already in progress
    """
    global thumbnail_processing_in_progress
    
    with thumbnail_processing_lock:
        if thumbnail_processing_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Thumbnail processing is already in progress"
            )
    
    result_dict = {}
    
    # Start background processing task
    background_tasks.add_task(
        process_thumbnails_background,
        result_dict
    )
    
    return {
        "message": "Thumbnail processing started",
        "status": "started"
    }


@app.get("/images/process-thumbnails/stream")
async def stream_thumbnail_processing_progress(request: Request):
    """Stream thumbnail processing progress via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()
        
        # Add client queue to list
        with thumbnail_processing_sse_clients_lock:
            thumbnail_processing_sse_clients.append(client_queue)
        
        try:
            # Send initial state
            initial_state = get_thumbnail_processing_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in thumbnail processing SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with thumbnail_processing_sse_clients_lock:
                if client_queue in thumbnail_processing_sse_clients:
                    thumbnail_processing_sse_clients.remove(client_queue)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/images/process-thumbnails/cancel")
async def cancel_thumbnail_processing():
    """Cancel thumbnail processing if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global thumbnail_processing_in_progress
    
    with thumbnail_processing_lock:
        if not thumbnail_processing_in_progress:
            return {
                "message": "No thumbnail processing is currently in progress",
                "cancelled": False
            }
        
        thumbnail_processing_cancelled.set()
        
        return {
            "message": "Thumbnail processing cancellation requested. Processing will stop after current item completes.",
            "cancelled": True
        }


@app.get("/images/process-thumbnails/status")
async def get_thumbnail_processing_status():
    """Get the current status of thumbnail processing.
    
    Returns:
        Status information about thumbnail processing
    """
    global thumbnail_processing_in_progress
    
    progress_state = get_thumbnail_processing_progress_state()
    
    with thumbnail_processing_lock:
        return {
            "in_progress": thumbnail_processing_in_progress,
            "cancelled": thumbnail_processing_cancelled.is_set(),
            **progress_state
        }


@app.get("/facebook/albums")
async def get_facebook_albums():
    """Get list of all Facebook albums.
    
    Returns:
        List of albums with id, name, description, cover_photo_uri, image_count
    """
    session = db.get_session()
    try:
        from sqlalchemy import func
        albums = session.query(
            FacebookAlbum.id,
            FacebookAlbum.name,
            FacebookAlbum.description,
            FacebookAlbum.cover_photo_uri,
            func.count(func.distinct(AlbumMedia.id)).label('image_count')
        ).outerjoin(
            AlbumMedia, FacebookAlbum.id == AlbumMedia.album_id
        ).group_by(
            FacebookAlbum.id
        ).order_by(
            FacebookAlbum.name
        ).all()
        
        result = []
        for album in albums:
            result.append({
                "id": album.id,
                "name": album.name,
                "description": album.description,
                "cover_photo_uri": album.cover_photo_uri,
                "image_count": album.image_count or 0
            })
        
        return result
    finally:
        session.close()


@app.get("/facebook/albums/{album_id}/images")
async def get_facebook_album_images(album_id: int):
    """Get all images for a specific Facebook album.
    
    Args:
        album_id: The ID of the album
        
    Returns:
        List of images with id, title, description, media_type, created_at
    """
    session = db.get_session()
    try:
        # Query MediaMetadata via AlbumMedia junction table
        media_items = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            AlbumMedia.album_id == album_id
        ).order_by(
            MediaMetadata.created_at.asc()
        ).all()
        
        result = []
        for media_item in media_items:
            result.append({
                "id": media_item.id,
                "title": media_item.title,
                "description": media_item.description,
                "media_type": media_item.media_type,
                "created_at": media_item.created_at.isoformat() if media_item.created_at else None
            })
        
        return result
    finally:
        session.close()


@app.get("/facebook/albums/images/{image_id}")
async def get_facebook_album_image(image_id: int):
    """Get image data for a specific Facebook album image.
    
    Args:
        image_id: The ID of the media item
        
    Returns:
        Image file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if image not found or not linked to an album
    """
    session = db.get_session()
    try:
        # Query MediaMetadata and verify it's linked to an album via AlbumMedia
        media_item = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            MediaMetadata.id == image_id
        ).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found or not linked to an album"
            )
        
        # Get MediaBlob
        if not media_item.media_blob or not media_item.media_blob.image_data:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} has no image data"
            )
        
        # Determine content type from media_type
        content_type = media_item.media_type or "image/jpeg"
        if media_item.title:
            import mimetypes
            guessed_type, _ = mimetypes.guess_type(media_item.title)
            if guessed_type:
                content_type = guessed_type
        
        return Response(
            content=media_item.media_blob.image_data,
            media_type=content_type
        )
    finally:
        session.close()


@app.get("/imessages/{message_id}/attachment")
async def get_imessage_attachment(message_id: int, preview: bool = False):
    """Get attachment content for a message.
    
    Uses unified media system via MessageAttachment junction table.
    
    Args:
        message_id: The ID of the message
        preview: If True, return thumbnail/preview instead of full attachment
        
    Returns:
        Attachment file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if message not found or has no attachment
    """
    session = db.get_session()
    try:
        message = session.query(IMessage).filter(IMessage.id == message_id).first()
        
        if not message:
            raise HTTPException(
                status_code=404,
                detail=f"Message with ID {message_id} not found"
            )
        
        # Get first attachment via MessageAttachment junction table
        message_attachment = session.query(MessageAttachment).filter(
            MessageAttachment.message_id == message_id
        ).first()
        
        if not message_attachment:
            raise HTTPException(
                status_code=404,
                detail=f"Message with ID {message_id} has no attachment"
            )
        
        # Get media item and blob
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == message_attachment.media_item_id
        ).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Media item for attachment not found"
            )
        
        media_blob = session.query(MediaBlob).filter(
            MediaBlob.id == media_item.media_blob_id
        ).first()
        
        if not media_blob:
            raise HTTPException(
                status_code=404,
                detail=f"Media blob for attachment not found"
            )
        
        # Get content
        if preview:
            content = media_blob.thumbnail_data
            if content is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Message attachment has no thumbnail available"
                )
            content_type = "image/jpeg"  # Thumbnails are always JPEG
            filename = media_item.title or "attachment"
            base_name, ext = os.path.splitext(filename)
            safe_filename = f"{base_name}_thumb.jpg".replace('"', '\\"')
        else:
            content = media_blob.image_data
            if content is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Message attachment has no content"
                )
            content_type = media_item.media_type or "application/octet-stream"
            filename = media_item.title or "attachment"
            safe_filename = filename.replace('"', '\\"')
        
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{safe_filename}"'
            }
        )
    finally:
        session.close()


@app.get("/emails/process/stream")
async def stream_processing_progress():
    """Stream processing progress updates via Server-Sent Events (SSE).
    
    Returns:
        StreamingResponse with text/event-stream content type
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue(maxsize=100)
        
        # Add client to the list
        with sse_clients_lock:
            sse_clients.append(client_queue)
        
        try:
            # Send initial progress state
            initial_state = get_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
            # Send heartbeat every 30 seconds to keep connection alive
            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()
            
            while True:
                try:
                    # Wait for message with timeout for heartbeat
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()
                    
                    # Check if processing is complete
                    progress_state = get_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        # Send final state and close
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break
                        
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    # Send error and break
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
            # Remove client from the list
            with sse_clients_lock:
                if client_queue in sse_clients:
                    sse_clients.remove(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/emails/{email_id}/html")
async def get_email_html(email_id: int):
    """Get email HTML content by ID.
    
    Args:
        email_id: The ID of the email to retrieve HTML for
        
    Returns:
        HTML content with text/html content type
        
    Raises:
        HTTPException: 404 if email not found or has no HTML content
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()
    
    if not email:
        raise HTTPException(
            status_code=404,
            detail=f"Email with ID {email_id} not found"
        )
    
    # If HTML is not available, fall back to plain text wrapped in HTML
    if not email.raw_message:
        if email.plain_text:
            # Wrap plain text in basic HTML for display
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
{email.plain_text}
</body>
</html>"""
            return Response(
                content=html_content,
                media_type="text/html"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} has no HTML or text content"
            )
    
    # Return the HTML content with proper content type
    return Response(
        content=email.raw_message,
        media_type="text/html"
    )


@app.get("/emails/{email_id}/text")
async def get_email_text(email_id: int):
    """Get email plain text content by ID.
    
    Args:
        email_id: The ID of the email to retrieve plain text for
        
    Returns:
        Plain text content with text/plain content type
        
    Raises:
        HTTPException: 404 if email not found or has no text content
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()
    
    if not email:
        raise HTTPException(
            status_code=404,
            detail=f"Email with ID {email_id} not found"
        )
    
    if not email.plain_text:
        raise HTTPException(
            status_code=404,
            detail=f"Email with ID {email_id} has no text content"
        )
    
    # Return the plain text content with proper content type
    return Response(
        content=email.plain_text,
        media_type="text/plain"
    )


@app.get("/emails/{email_id}/snippet")
async def get_email_snippet(email_id: int):
    """Get email snippet by ID.
    
    Args:
        email_id: The ID of the email to retrieve snippet for
        
    Returns:
        Snippet text with text/plain content type
        
    Raises:
        HTTPException: 404 if email not found or has no snippet
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()
    
    if not email:
        raise HTTPException(
            status_code=404,
            detail=f"Email with ID {email_id} not found"
        )
    
    if not email.snippet:
        raise HTTPException(
            status_code=404,
            detail=f"Email with ID {email_id} has no snippet"
        )
    
    # Return the snippet with proper content type
    return Response(
        content=email.snippet,
        media_type="text/plain"
    )


@app.get("/emails/{email_id}/metadata", response_model=EmailMetadataResponse)
async def get_email_metadata(email_id: int):
    """Get email metadata by ID.
    
    Args:
        email_id: The ID of the email to retrieve metadata for
        
    Returns:
        EmailMetadataResponse with email metadata including attachment IDs
        
    Raises:
        HTTPException: 404 if email not found
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} not found"
            )
        
        # Get media item IDs (attachment IDs) for this email
        media_items = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment",
            MediaMetadata.source_reference == str(email_id)
        ).all()
        attachment_ids = [item.id for item in media_items]
        
        # Return the metadata as JSON
        return EmailMetadataResponse(
            id=email.id,
            uid=email.uid,
            folder=email.folder,
            subject=email.subject,
            from_address=email.from_address,
            to_addresses=email.to_addresses,
            cc_addresses=email.cc_addresses,
            bcc_addresses=email.bcc_addresses,
            date=email.date,
            snippet=email.snippet,
            attachment_ids=attachment_ids,
            created_at=email.created_at,
            updated_at=email.updated_at,
            is_personal=email.is_personal,
            is_business=email.is_business,
            is_important=email.is_important,
            use_by_ai=email.use_by_ai
        )
    finally:
        session.close()


@app.put("/emails/{email_id}")
async def update_email(email_id: int, updates: Dict[str, Any]):
    """Update email fields.
    
    Args:
        email_id: The ID of the email to update
        updates: Dictionary with fields to update (is_personal, is_business, is_important, use_by_ai)
        
    Returns:
        Updated EmailMetadataResponse
        
    Raises:
        HTTPException: 404 if email not found
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} not found"
            )
        
        # Update allowed fields
        if 'is_personal' in updates:
            email.is_personal = bool(updates['is_personal'])
        if 'is_business' in updates:
            email.is_business = bool(updates['is_business'])
        if 'is_important' in updates:
            email.is_important = bool(updates['is_important'])
        if 'use_by_ai' in updates:
            email.use_by_ai = bool(updates['use_by_ai'])
        
        session.commit()
        
        # Get media item IDs (attachment IDs) for this email
        media_items = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment",
            MediaMetadata.source_reference == str(email_id)
        ).all()
        attachment_ids = [item.id for item in media_items]
        
        return EmailMetadataResponse(
            id=email.id,
            uid=email.uid,
            folder=email.folder,
            subject=email.subject,
            from_address=email.from_address,
            to_addresses=email.to_addresses,
            cc_addresses=email.cc_addresses,
            bcc_addresses=email.bcc_addresses,
            date=email.date,
            snippet=email.snippet,
            attachment_ids=attachment_ids,
            created_at=email.created_at,
            updated_at=email.updated_at,
            is_personal=email.is_personal,
            is_business=email.is_business,
            is_important=email.is_important,
            use_by_ai=email.use_by_ai
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating email: {str(e)}"
        )
    finally:
        session.close()


@app.delete("/emails/bulk-delete")
async def bulk_delete_emails(delete_data: Dict[str, Any] = Body(...)):
    """Bulk delete multiple emails by their IDs.
    
    Args:
        delete_data: Dictionary containing:
            - email_ids: List of email IDs to delete
        
    Returns:
        Success message with count of deleted emails
        
    Raises:
        HTTPException: 400 if validation fails, 500 on error
    """
    session = db.get_session()
    try:
        email_ids = delete_data.get("email_ids", [])
        
        if not email_ids:
            raise HTTPException(
                status_code=400,
                detail="No email IDs provided"
            )
        
        deleted_count = 0
        errors = []
        
        for email_id in email_ids:
            try:
                email = session.query(Email).filter(Email.id == email_id).first()
                
                if not email:
                    errors.append(f"Email {email_id} not found")
                    continue
                
                # Delete all media items associated with the email
                media_items = session.query(MediaMetadata).filter(
                    MediaMetadata.source == "email_attachment",
                    MediaMetadata.source_reference == str(email_id)
                ).all()
                
                for media_item in media_items:
                    # Get the media blob
                    media_blob = session.query(MediaBlob).filter(
                        MediaBlob.id == media_item.media_blob_id
                    ).first()
                    
                    # Delete media item
                    session.delete(media_item)
                    
                    # Check if any other media items reference this blob
                    if media_blob:
                        other_items_count = session.query(MediaMetadata).filter(
                            MediaMetadata.media_blob_id == media_blob.id
                        ).count()
                        
                        # If no other items reference this blob, delete it
                        if other_items_count == 0:
                            session.delete(media_blob)
                
                # Set user_deleted flag to True (soft delete) and clear other fields
                email.raw_message = None
                email.plain_text = None
                email.snippet = None
                email.embedding = None
                email.has_attachments = False
                email.user_deleted = True
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting email {email_id}: {str(e)}")
        
        session.commit()
        
        return {
            "message": f"Deleted {deleted_count} email(s)",
            "deleted_count": deleted_count,
            "errors": errors
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk deleting emails: {str(e)}"
        )
    finally:
        session.close()


@app.delete("/emails/{email_id}")
async def delete_email(email_id: int):
    """Delete an email by ID.
    
    Deletes all attachments associated with the email and sets the user_deleted
    field to True (soft delete) instead of actually deleting the email record.
    
    Args:
        email_id: The ID of the email to delete
        
    Returns:
        Success message with email ID
        
    Raises:
        HTTPException: 404 if email not found
    """
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} not found"
            )
        
        # Delete all media items associated with the email
        media_items = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment",
            MediaMetadata.source_reference == str(email_id)
        ).all()
        
        for media_item in media_items:
            # Get the media blob
            media_blob = session.query(MediaBlob).filter(
                MediaBlob.id == media_item.media_blob_id
            ).first()
            
            # Delete media item
            session.delete(media_item)
            
            # Check if any other media items reference this blob
            if media_blob:
                other_items_count = session.query(MediaMetadata).filter(
                    MediaMetadata.media_blob_id == media_blob.id
                ).count()
                
                # If no other items reference this blob, delete it
                if other_items_count == 0:
                    session.delete(media_blob)
        
        # Set user_deleted flag to True (soft delete) and clear other fields
        # This is a soft delete, so we don't actually delete the email record,
        # but we clear the fields so that the email is not returned in search results.
        # This is to stop the email being re-processed by the background job which would otherwise
        # cause the email to be re-processed and re-indexed.
        email.raw_message = None
        email.plain_text = None
        email.snippet = None
        email.embedding = None
        email.has_attachments = False
        email.user_deleted = True
        session.commit()
        
        return {"message": f"Email {email_id} deleted successfully", "email_id": email_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting email: {str(e)}"
        )
    finally:
        session.close()


@app.get("/emails/folders", response_model=List[LabelResponse])
async def get_folders():
    """Get list of available folders/labels from the email server.
    
    Returns:
        List of LabelResponse objects containing all available Gmail labels
        
    Raises:
        HTTPException: 500 if unable to connect to email server or authentication fails
    """
    try:
        loader_instance = get_loader()
        labels = loader_instance.client.get_labels()
        
        # Convert Gmail label objects to response models
        return [
            LabelResponse(
                id=label.get("id", ""),
                name=label.get("name", ""),
                type=label.get("type"),
                message_list_visibility=label.get("messageListVisibility"),
                label_list_visibility=label.get("labelListVisibility")
            )
            for label in labels
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve folders from email server: {str(e)}"
        )


@app.get("/emails/label", response_model=List[EmailMetadataResponse])
async def get_emails_by_label(labels: List[str] = Query(..., description="List of labels to filter by")):
    """Get metadata for all emails with given labels.
    
    Args:
        labels: List of labels to filter emails by (e.g., ["INBOX", "IMPORTANT"])
                Provided as query parameter: ?labels=INBOX&labels=IMPORTANT
        
    Returns:
        List of EmailMetadataResponse objects for all emails matching any of the given labels
        
    Note:
        Labels are stored as comma-separated strings in the folder field.
        This endpoint matches emails where any of the provided labels appears anywhere in the folder field.
    """
    if not labels:
        raise HTTPException(
            status_code=400,
            detail="At least one label must be provided as query parameter (e.g., ?labels=INBOX&labels=IMPORTANT)"
        )
    
    session = db.get_session()
    try:
        # Build filter conditions for each label
        label_filters = []
        for label in labels:
            label_filters.extend([
                Email.folder == label,  # Exact match
                Email.folder.like(f"{label},%"),  # Label at start
                Email.folder.like(f"%,{label},%"),  # Label in middle
                Email.folder.like(f"%,{label}")  # Label at end
            ])
        
        # Query emails where the folder field contains any of the labels
        # Exclude emails where user_deleted is True
        emails = session.query(Email).filter(
            and_(
                or_(*label_filters),
                Email.user_deleted == False
            )
        ).all()
        
        # Convert to response models (get attachment IDs from media items)
        result = []
        for email in emails:
            # Get media item IDs (attachment IDs) for this email
            media_items = session.query(MediaMetadata).filter(
                MediaMetadata.source == "email_attachment",
                MediaMetadata.source_reference == str(email.id)
            ).all()
            attachment_ids = [item.id for item in media_items]
            
            result.append(EmailMetadataResponse(
                id=email.id,
                uid=email.uid,
                folder=email.folder,
                subject=email.subject,
                from_address=email.from_address,
                to_addresses=email.to_addresses,
                cc_addresses=email.cc_addresses,
                bcc_addresses=email.bcc_addresses,
                date=email.date,
                snippet=email.snippet,
                attachment_ids=attachment_ids,
                created_at=email.created_at,
                updated_at=email.updated_at
            ))
    finally:
        session.close()
    
    return result


@app.get("/emails/search", response_model=List[EmailMetadataResponse])
async def search_emails(
    from_address: Optional[str] = Query(None, description="Filter by sender (partial match)"),
    to_address: Optional[str] = Query(None, description="Filter by recipient (partial match)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    subject: Optional[str] = Query(None, description="Filter by subject (partial match)"),
    to_from: Optional[str] = Query(None, description="Filter by email being either to or from this address (partial match)"),
    has_attachments: Optional[bool] = Query(None, description="Filter by whether email has attachments")
):
    """Search emails by metadata criteria.
    
    All parameters are optional. When multiple parameters are provided, they are combined with AND logic.
    Text fields (from_address, to_address, subject, to_from) support partial matching (case-insensitive).
    
    Args:
        from_address: Partial match on sender email address
        to_address: Partial match on recipient email address
        month: Month number (1-12) extracted from email date
        year: Year extracted from email date
        subject: Partial match on email subject
        to_from: Partial match on email being either to or from this address
        has_attachments: Filter by attachment presence (true/false)
        
    Returns:
        List of EmailMetadataResponse objects matching all specified criteria
    """
    session = db.get_session()
    try:
        # Start building query with base filter
        query = session.query(Email)
        filters = []
        
        # Filter by from_address (partial match, case-insensitive)
        if from_address:
            filters.append(Email.from_address.ilike(f"%{from_address}%"))
        
        # Filter by to_address (partial match, case-insensitive)
        if to_address:
            filters.append(Email.to_addresses.ilike(f"%{to_address}%"))
        
        # Filter by month (extract month from date)
        if month is not None:
            filters.append(extract('month', Email.date) == month)
        
        # Filter by year (extract year from date)
        if year is not None:
            filters.append(extract('year', Email.date) == year)
        
        # Filter by subject (partial match, case-insensitive)
        if subject:
            filters.append(Email.subject.ilike(f"%{subject}%"))
        
        # Filter by to_from (check both to_addresses and from_address)
        if to_from:
            filters.append(
                or_(
                    Email.to_addresses.ilike(f"%{to_from}%"),
                    Email.from_address.ilike(f"%{to_from}%")
                )
            )
        
        # Filter by has_attachments
        if has_attachments is not None:
            filters.append(Email.has_attachments == has_attachments)
        
        # Always exclude emails where user_deleted is True
        filters.append(Email.user_deleted == False)
        
        # Apply all filters with AND logic
        if filters:
            query = query.filter(and_(*filters))
        
        # Sort by descending date (newest first)
        query = query.order_by(Email.date.desc())
        
        # Execute query
        emails = query.all()
        
        # Convert to response models (get attachment IDs from media items)
        result = []
        for email in emails:
            # Get media item IDs (attachment IDs) for this email
            media_items = session.query(MediaMetadata).filter(
                MediaMetadata.source == "email_attachment",
                MediaMetadata.source_reference == str(email.id)
            ).all()
            attachment_ids = [item.id for item in media_items]
            
            result.append(EmailMetadataResponse(
                id=email.id,
                uid=email.uid,
                folder=email.folder,
                subject=email.subject,
                from_address=email.from_address,
                to_addresses=email.to_addresses,
                cc_addresses=email.cc_addresses,
                bcc_addresses=email.bcc_addresses,
                date=email.date,
                snippet=email.snippet,
                attachment_ids=attachment_ids,
                created_at=email.created_at,
                updated_at=email.updated_at
            ))
        
        return result
    finally:
        session.close()


@app.get("/attachments/random", response_model=Optional[AttachmentInfoResponse])
async def get_random_attachment():
    """Get a random attachment with its email metadata.
    
    Returns:
        AttachmentInfoResponse with attachment and email metadata, or None if no attachments exist
    """
    session = db.get_session()
    try:
        # Get a random media item with source="email_attachment"
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).order_by(func.random()).first()
        
        if not media_item:
            return None
        
        # Get the email for this attachment (from source_reference)
        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            return None
        
        # Get content type from media_type or default
        content_type = media_item.media_type or "application/octet-stream"
        
        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,  # Size not stored in MediaMetadata
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@app.get("/attachments/by-id", response_model=Optional[AttachmentInfoResponse])
async def get_attachment_by_id_order(offset: int = Query(0, ge=0, description="Offset for pagination")):
    """Get attachment by ID order with offset.
    
    Args:
        offset: Offset for pagination (0-based)
        
    Returns:
        AttachmentInfoResponse with attachment and email metadata, or None if no attachment at offset
    """
    session = db.get_session()
    try:
        # Get media item by ID order with source="email_attachment"
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).order_by(MediaMetadata.id.asc()).offset(offset).first()
        
        if not media_item:
            return None
        
        # Get the email for this attachment (from source_reference)
        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            return None
        
        # Get content type from media_type or default
        content_type = media_item.media_type or "application/octet-stream"
        
        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,  # Size not stored in MediaMetadata
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@app.get("/attachments/by-size", response_model=Optional[AttachmentInfoResponse])
async def get_attachment_by_size_order(
    order: str = Query("asc", regex="^(asc|desc)$", description="Order: 'asc' for smallest to biggest, 'desc' for biggest to smallest"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get attachment by size order with offset.
    
    Note: Size ordering is based on media blob data length since MediaMetadata doesn't store size.
    
    Args:
        order: Order direction - 'asc' for smallest to biggest, 'desc' for biggest to smallest
        offset: Offset for pagination (0-based)
        
    Returns:
        AttachmentInfoResponse with attachment and email metadata, or None if no attachment at offset
    """
    session = db.get_session()
    try:
        # Query media items with their blobs, ordered by blob data length
        query = session.query(MediaMetadata).join(MediaBlob).filter(
            MediaMetadata.source == "email_attachment"
        )
        
        # Order by blob data length (using func.length for binary data)
        from sqlalchemy import func
        if order == "asc":
            query = query.order_by(func.length(MediaBlob.image_data).asc().nullslast())
        else:
            query = query.order_by(func.length(MediaBlob.image_data).desc().nullslast())
        
        media_item = query.offset(offset).first()
        
        if not media_item:
            return None
        
        # Get the email for this attachment (from source_reference)
        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            return None
        
        # Get content type from media_type or default
        content_type = media_item.media_type or "application/octet-stream"
        
        # Calculate size from blob data length
        media_blob = session.query(MediaBlob).filter(MediaBlob.id == media_item.media_blob_id).first()
        size = len(media_blob.image_data) if media_blob and media_blob.image_data else None
        
        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=size,
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@app.get("/attachments/count")
async def get_attachment_count():
    """Get total count of attachments in the database.
    
    Returns:
        Dictionary with total count
    """
    session = db.get_session()
    try:
        count = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).count()
        return {"count": count}
    finally:
        session.close()


@app.get("/attachments/images", response_model=ImageGridResponse)
async def get_images_grid(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of images per page"),
    order: str = Query("id", regex="^(id|size|date)$", description="Sort order: 'id', 'size', or 'date'"),
    direction: str = Query("asc", regex="^(asc|desc)$", description="Sort direction: 'asc' or 'desc'"),
    all_types: bool = Query(False, description="If True, show all file types, not just images")
):
    """Get images for grid display with pagination and sorting.
    
    Args:
        page: Page number (1-based)
        page_size: Number of images per page (max 100)
        order: Sort order - 'id', 'size', or 'date'
        direction: Sort direction - 'asc' or 'desc'
        all_types: If True, return all file types, otherwise only images
        
    Returns:
        ImageGridResponse with paginated image list
    """
    session = db.get_session()
    try:
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Query media items with source="email_attachment" - filter by type if not showing all types
        if all_types:
            media_query = session.query(MediaMetadata).join(MediaBlob).join(
                Email, Email.id == func.cast(MediaMetadata.source_reference, Integer)
            ).filter(MediaMetadata.source == "email_attachment")
        else:
            media_query = session.query(MediaMetadata).join(MediaBlob).join(
                Email, Email.id == func.cast(MediaMetadata.source_reference, Integer)
            ).filter(
                MediaMetadata.source == "email_attachment",
                MediaMetadata.media_type.like('image/%')
            )
        
        # Apply sorting
        if order == "id":
            if direction == "asc":
                media_query = media_query.order_by(MediaMetadata.id.asc())
            else:
                media_query = media_query.order_by(MediaMetadata.id.desc())
        elif order == "size":
            # Order by blob data length
            if direction == "asc":
                media_query = media_query.order_by(func.length(MediaBlob.image_data).asc().nullslast())
            else:
                media_query = media_query.order_by(func.length(MediaBlob.image_data).desc().nullslast())
        elif order == "date":
            if direction == "asc":
                media_query = media_query.order_by(Email.date.asc().nullslast())
            else:
                media_query = media_query.order_by(Email.date.desc().nullslast())
        
        # Get total count
        total = media_query.count()
        
        # Get paginated results
        media_items = media_query.offset(offset).limit(page_size).all()
        
        # Build response
        image_list = []
        for media_item in media_items:
            # Get email from source_reference
            email_id = int(media_item.source_reference)
            email = session.query(Email).filter(Email.id == email_id).first()
            
            if email:
                # Get content type and size
                content_type = media_item.image_type or "application/octet-stream"
                media_blob = session.query(MediaBlob).filter(MediaBlob.id == media_item.media_blob_id).first()
                size = len(media_blob.image_data) if media_blob and media_blob.image_data else None
                
                image_list.append(AttachmentInfoResponse(
                    attachment_id=media_item.id,
                    filename=media_item.title or "attachment",
                    content_type=content_type,
                    size=size,
                    email_id=email.id,
                    email_subject=email.subject,
                    email_from=email.from_address,
                    email_date=email.date,
                    email_folder=email.folder
                ))
        
        total_pages = (total + page_size - 1) // page_size  # Ceiling division
        
        return ImageGridResponse(
            images=image_list,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    finally:
        session.close()


@app.get("/attachments/{attachment_id}/info", response_model=AttachmentInfoResponse)
async def get_attachment_info(attachment_id: int):
    """Get attachment information with email metadata.
    
    Args:
        attachment_id: The media_item ID of the attachment
        
    Returns:
        AttachmentInfoResponse with attachment and email metadata
        
    Raises:
        HTTPException: 404 if attachment not found
    """
    session = db.get_session()
    try:
        # Get media item (attachment_id is now media_item_id)
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )
        
        # Get the email for this attachment (from source_reference)
        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email for attachment {attachment_id} not found"
            )
        
        # Get content type from media_type or default
        content_type = media_item.media_type or "application/octet-stream"
        
        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,  # Size not stored in MediaMetadata
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@app.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: int):
    """Delete an attachment by ID (media_item_id).
    
    Deletes from unified MediaMetadata/MediaBlob tables.
    
    Args:
        attachment_id: The media_item ID of the attachment to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: 404 if attachment not found
    """
    session = db.get_session()
    try:
        # Get media item (attachment_id is now media_item_id)
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )
        
        # Get the media blob
        media_blob = session.query(MediaBlob).filter(
            MediaBlob.id == media_item.media_blob_id
        ).first()
        
        if media_blob:
            # Check if any other media items reference this blob (before deleting)
            other_items_count = session.query(MediaMetadata).filter(
                MediaMetadata.media_blob_id == media_blob.id
            ).count()
            
            # Delete media item
            session.delete(media_item)
            
            # If this was the only item referencing this blob, delete the blob too
            if other_items_count == 1:
                session.delete(media_blob)
        
        session.commit()
        
        return {"message": f"Attachment {attachment_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting attachment: {str(e)}"
        )
    finally:
        session.close()


@app.get("/attachments/{attachment_id}")
async def get_attachment_content(attachment_id: int, preview: bool = False):
    """Get attachment content by ID (media_item_id).
    
    Uses unified MediaMetadata/MediaBlob tables.
    
    Args:
        attachment_id: The media_item ID of the attachment to retrieve
        preview: If True and attachment is an image, return thumbnail instead of full image
        
    Returns:
        Attachment file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if attachment not found or has no content
    """
    session = db.get_session()
    try:
        # Get media item (attachment_id is now media_item_id)
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )
        
        # Get the media blob
        media_blob = session.query(MediaBlob).filter(
            MediaBlob.id == media_item.media_blob_id
        ).first()
        
        if not media_blob:
            raise HTTPException(
                status_code=404,
                detail=f"Media blob for attachment {attachment_id} not found"
            )
        
        # Determine content type from media_type or default
        content_type = media_item.media_type or "application/octet-stream"
        
        if preview:
            content = media_blob.thumbnail_data
            if content is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Attachment with ID {attachment_id} has no thumbnail available"
                )
            content_type = "image/jpeg"
            filename = media_item.title or "attachment"
            base_name, ext = os.path.splitext(filename)
            safe_filename = f"{base_name}_thumb.jpg".replace('"', '\\"')
        else:
            content = media_blob.image_data
            if content is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Attachment with ID {attachment_id} has no content"
                )
            filename = media_item.title or "attachment"
            safe_filename = filename.replace('"', '\\"')
        
        headers = {
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }
        
        return Response(
            content=content,
            media_type=content_type,
            headers=headers
        )
    finally:
        session.close()


@app.get("/images/search", response_model=List[MediaMetadataResponse])
async def search_images(
    title: Optional[str] = Query(None, description="Filter by title (partial match, case-insensitive)"),
    description: Optional[str] = Query(None, description="Filter by description (partial match, case-insensitive)"),
    author: Optional[str] = Query(None, description="Filter by author (partial match, case-insensitive)"),
    tags: Optional[str] = Query(None, description="Filter by tags (partial match, case-insensitive)"),
    categories: Optional[str] = Query(None, description="Filter by categories (partial match, case-insensitive)"),
    source: Optional[str] = Query(None, description="Filter by source (exact match, case-insensitive)"),
    source_reference: Optional[str] = Query(None, description="Filter by source_reference (partial match, case-insensitive)"),
    media_type: Optional[str] = Query(None, description="Filter by media type/MIME type (partial match, case-insensitive)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    has_gps: Optional[bool] = Query(None, description="Filter by whether image has GPS data"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating (1-5)"),
    rating_min: Optional[int] = Query(None, ge=1, le=5, description="Filter by minimum rating (1-5)"),
    rating_max: Optional[int] = Query(None, ge=1, le=5, description="Filter by maximum rating (1-5)"),
    available_for_task: Optional[bool] = Query(None, description="Filter by available_for_task flag"),
    processed: Optional[bool] = Query(None, description="Filter by processed flag"),
    location_processed: Optional[bool] = Query(None, description="Filter by location_processed flag"),
    image_processed: Optional[bool] = Query(None, description="Filter by image_processed flag"),
    region: Optional[str] = Query(None, description="Filter by region (partial match, case-insensitive)")
):
    """Search images by metadata criteria.
    
    All parameters are optional. When multiple parameters are provided, they are combined with AND logic.
    Text fields support partial matching (case-insensitive) unless otherwise specified.
    
    Args:
        title: Partial match on image title
        description: Partial match on image description
        author: Partial match on image author
        tags: Partial match on tags (comma-separated)
        categories: Partial match on categories (comma-separated)
        source: Exact match on source (case-insensitive)
        source_reference: Partial match on source_reference (file path)
        media_type: Partial match on media type/MIME type
        year: Filter by year
        month: Filter by month (1-12)
        has_gps: Filter by GPS data presence
        rating: Exact match on rating (1-5)
        rating_min: Minimum rating (1-5)
        rating_max: Maximum rating (1-5)
        available_for_task: Filter by available_for_task flag
        processed: Filter by processed flag
        location_processed: Filter by location_processed flag
        image_processed: Filter by image_processed flag
        region: Partial match on region
        
    Returns:
        List of MediaMetadataResponse objects matching all specified criteria
    """
    image_service = ImageService(db=db)
    try:
        # Build filters from query parameters
        filters = ImageSearchFilters(
            title=title,
            description=description,
            author=author,
            tags=tags,
            categories=categories,
            source=source,
            source_reference=source_reference,
            media_type=media_type,
            year=year,
            month=month,
            has_gps=has_gps,
            rating=rating,
            rating_min=rating_min,
            rating_max=rating_max,
            available_for_task=available_for_task,
            processed=processed,
            location_processed=location_processed,
            image_processed=image_processed,
            region=region
        )
        
        # Search images using service
        images = image_service.search_images(filters)
        
        # Convert to response models
        return [MediaMetadataResponse(**image_service.to_response_model(img)) for img in images]
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching images: {str(e)}"
        )


@app.get("/images/years")
async def get_distinct_years():
    """Get list of distinct years from media_items table.
    
    Returns:
        List of distinct years (integers) sorted in descending order
    """
    session = db.get_session()
    try:
        # Query distinct years from MediaMetadata where year is not null
        years = session.query(func.distinct(MediaMetadata.year)).filter(
            MediaMetadata.year.isnot(None)
        ).order_by(
            MediaMetadata.year.desc()
        ).all()
        
        # Extract year values from tuples and return as list
        year_list = [year[0] for year in years]
        
        return {"years": year_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct years: {str(e)}"
        )
    finally:
        session.close()


@app.get("/images/tags")
async def get_distinct_tags():
    """Get list of distinct tags from media_items table.
    
    Tags are stored as comma-separated strings, so this endpoint extracts
    all unique individual tags from all tag fields.
    
    Returns:
        List of distinct tags (strings) sorted alphabetically
    """
    session = db.get_session()
    try:
        # Query all tags from MediaMetadata where tags is not null
        tag_records = session.query(MediaMetadata.tags).filter(
            MediaMetadata.tags.isnot(None),
            MediaMetadata.tags != ''
        ).all()
        
        # Extract and split comma-separated tags
        all_tags = set()
        for record in tag_records:
            if record[0]:
                # Split by comma and clean up whitespace
                tags = [tag.strip() for tag in record[0].split(',') if tag.strip()]
                all_tags.update(tags)
        
        # Convert to sorted list
        tag_list = sorted(list(all_tags))
        
        return {"tags": tag_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct tags: {str(e)}"
        )
    finally:
        session.close()


@app.get("/getLocations")
async def get_locations():
    """Get metadata of media items that have GPS data set.
    
    Returns:
        List of media items with GPS coordinates, including:
        - id: Media item ID
        - latitude: Latitude coordinate
        - longitude: Longitude coordinate
        - altitude: Altitude (if available)
        - title: Media title
        - description: Media description
        - year: Year the media was taken
        - month: Month the media was taken
        - tags: Tags associated with the media
        - google_maps_url: Google Maps URL (if available)
        - region: Region name (if available)
        - created_at: Creation timestamp
        - source: Source of the media item (if available)
        - source_reference: Source reference (if available)
    """
    session = db.get_session()
    try:
        # Query media items with GPS data
        # Filter by has_gps=True OR (latitude is not None AND longitude is not None)
        media_items = session.query(MediaMetadata).filter(
            or_(
                MediaMetadata.has_gps == True,
                and_(
                    MediaMetadata.latitude.isnot(None),
                    MediaMetadata.longitude.isnot(None)
                )
            )
        ).all()
        
        # Build response list
        locations = []
        for item in media_items:
            location_data = {
                "id": item.id,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "altitude": item.altitude,
                "title": item.title,
                "description": item.description,
                "year": item.year,
                "month": item.month,
                "tags": item.tags,
                "google_maps_url": item.google_maps_url,
                "region": item.region,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "media_type": item.media_type,
                "source": item.source,
                "source_reference": item.source_reference
            }
            locations.append(location_data)
        
        return {"locations": locations}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving locations: {str(e)}"
        )
    finally:
        session.close()


@app.get("/images/{image_id}")
async def get_image_content(
    image_id: int,
    type: str = Query("blob", regex="^(blob|metadata)$", description="Type of ID: 'blob' for media_blob.id or 'metadata' for media_items.id"),
    preview: bool = Query(False, description="If True, return thumbnail instead of full image"),
    convert_heic_to_jpg: bool = Query(True, description="If True, convert HEIC images to JPG format before returning")
):
    """Get image content by ID.
    
    Args:
        image_id: The ID of the image (blob ID or metadata ID depending on type parameter)
        type: Type of ID - 'blob' for media_blob.id or 'metadata' for media_items.id (default: 'blob')
        preview: If True, return thumbnail instead of full image
        convert_heic_to_jpg: If True, convert HEIC images to JPG format before returning (default: True)
        
    Returns:
        Image binary data with appropriate content-type
        
    Raises:
        HTTPException: 404 if image not found or has no content
    """
    image_service = ImageService(db=db)
    try:
        # Get image content using service
        image_content = image_service.get_image_content(
            image_id=image_id,
            id_type=type,
            preview=preview,
            convert_heic=convert_heic_to_jpg
        )
        
        # Set Content-Disposition header
        safe_filename = image_content.filename.replace('"', '\\"')
        headers = {
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }
        
        return Response(
            content=image_content.content,
            media_type=image_content.content_type,
            headers=headers
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image: {str(e)}"
        )


@app.put("/images/bulk-update")
async def bulk_update_images(update_data: Dict[str, Any]):
    """Bulk update multiple images with tags.
    
    Args:
        update_data: Dictionary containing:
            - image_ids: List of image metadata IDs to update
            - tags: Tags to apply (will be appended to existing tags)
        
    Returns:
        Success message with count of updated images
        
    Raises:
        HTTPException: 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        image_ids = update_data.get("image_ids", [])
        tags = update_data.get("tags")
        
        # Bulk update using service
        result = image_service.bulk_update_tags(image_ids, tags)
        
        return {
            "message": f"Updated {result.updated_count} image(s)",
            "updated_count": result.updated_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk updating images: {str(e)}"
        )


@app.get("/images/{image_id}/metadata", response_model=MediaMetadataResponse)
async def get_image_metadata(image_id: int):
    """Get image metadata by ID.
    
    Args:
        image_id: The metadata ID of the image
        
    Returns:
        MediaMetadataResponse with full image metadata
        
    Raises:
        HTTPException: 404 if image not found
    """
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(MediaMetadata.id == image_id).first()
        
        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found"
            )
        
        # Convert to response model
        return MediaMetadataResponse(
            id=media_item.id,
            media_blob_id=media_item.media_blob_id,
            description=media_item.description,
            title=media_item.title,
            author=media_item.author,
            tags=media_item.tags,
            categories=media_item.categories,
            notes=media_item.notes,
            available_for_task=media_item.available_for_task,
            media_type=media_item.media_type,
            processed=media_item.processed,
            location_processed=media_item.location_processed,
            image_processed=media_item.image_processed,
            created_at=media_item.created_at,
            updated_at=media_item.updated_at,
            year=media_item.year,
            month=media_item.month,
            latitude=media_item.latitude,
            longitude=media_item.longitude,
            altitude=media_item.altitude,
            rating=media_item.rating or 5,
            has_gps=media_item.has_gps,
            google_maps_url=media_item.google_maps_url,
            region=media_item.region,
            source=media_item.source,
            source_reference=media_item.source_reference
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image metadata: {str(e)}"
        )
    finally:
        session.close()


@app.put("/images/{image_id}")
async def update_image_metadata(image_id: int, update_data: Dict[str, Any]):
    """Update image metadata fields.
    
    Args:
        image_id: The metadata ID of the image to update
        update_data: Dictionary containing fields to update (description, tags, rating)
        
    Returns:
        Success message with updated image ID
        
    Raises:
        HTTPException: 404 if image not found, 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        # Extract allowed fields
        updates = MediaMetadataUpdate(
            description=update_data.get("description"),
            tags=update_data.get("tags"),
            rating=update_data.get("rating")
        )
        
        # Update metadata using service
        updated_metadata = image_service.update_image_metadata(image_id, updates)
        
        return {
            "message": f"Image {image_id} updated successfully",
            "image_id": image_id,
            "updated_fields": {
                "description": updates.description is not None,
                "tags": updates.tags is not None,
                "rating": updates.rating is not None
            }
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating image: {str(e)}"
        )


@app.delete("/images/bulk-delete")
async def bulk_delete_images(delete_data: Dict[str, Any]):
    """Bulk delete multiple images by their metadata IDs.
    
    Args:
        delete_data: Dictionary containing:
            - image_ids: List of image metadata IDs to delete
        
    Returns:
        Success message with count of deleted images
        
    Raises:
        HTTPException: 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        image_ids = delete_data.get("image_ids", [])
        
        # Bulk delete using service
        result = image_service.bulk_delete_images(image_ids)
        
        return {
            "message": f"Deleted {result.deleted_count} image(s)",
            "deleted_count": result.deleted_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk deleting images: {str(e)}"
        )


@app.delete("/images/{image_id}")
async def delete_image(image_id: int):
    """Delete an image by metadata ID.
    
    Args:
        image_id: The metadata ID of the image to delete
        
    Returns:
        Success message with image ID
        
    Raises:
        HTTPException: 404 if image not found
    """
    storage = ImageStorage(db=db)
    try:
        deleted = storage.delete_image_by_metadata_id(image_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Image with metadata ID {image_id} not found"
            )
        return {"message": f"Image {image_id} deleted successfully", "image_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting image: {str(e)}"
        )


@app.delete("/images")
async def delete_images(
    all: bool = Query(False, description="If True, delete all images"),
    start_id: Optional[int] = Query(None, description="Start of ID range (inclusive)"),
    end_id: Optional[int] = Query(None, description="End of ID range (inclusive)")
):
    """Delete images with options to delete all or by ID range.
    
    Args:
        all: If True, delete all images (requires explicit confirmation)
        start_id: Start of ID range for deletion (inclusive)
        end_id: End of ID range for deletion (inclusive)
        
    Returns:
        Success message with count of deleted images
        
    Raises:
        HTTPException: 400 if parameters are invalid, 404 if no images found
    """
    session = db.get_session()
    try:
        # Validate parameters
        if all and (start_id is not None or end_id is not None):
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both 'all=true' and ID range parameters"
            )
        
        if not all and start_id is None and end_id is None:
            raise HTTPException(
                status_code=400,
                detail="Must specify either 'all=true' or at least one of 'start_id' or 'end_id'"
            )
        
        # Build query
        query = session.query(MediaMetadata)
        
        if all:
            # Delete all images
            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found to delete"
                )
            
            # Delete all metadata records (cascade will delete blobs)
            deleted_count = query.delete(synchronize_session=False)
            session.commit()
            
            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count
            }
        else:
            # Delete by ID range
            if start_id is not None and end_id is not None:
                if start_id > end_id:
                    raise HTTPException(
                        status_code=400,
                        detail="start_id must be less than or equal to end_id"
                    )
                query = query.filter(
                    and_(
                        MediaMetadata.id >= start_id,
                        MediaMetadata.id <= end_id
                    )
                )
            elif start_id is not None:
                query = query.filter(MediaMetadata.id >= start_id)
            elif end_id is not None:
                query = query.filter(MediaMetadata.id <= end_id)
            
            # Count before deletion
            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found in the specified range"
                )
            
            # Delete metadata records (cascade will delete blobs)
            # Need to load relationships for cascade to work properly
            metadata_records = query.all()
            deleted_count = 0
            for metadata in metadata_records:
                # Load the relationship to ensure cascade works
                _ = metadata.image_blob
                session.delete(metadata)
                deleted_count += 1
            
            session.commit()
            
            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count,
                "start_id": start_id,
                "end_id": end_id
            }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting images: {str(e)}"
        )
    finally:
        session.close()


@app.get("/attachments-viewer", response_class=HTMLResponse)
async def attachments_viewer(request: Request):
    """Serve the attachment viewer web page."""
    return templates.TemplateResponse(
        "attachments_viewer.html",
        {"request": request}
    )


@app.get("/attachments-images-grid", response_class=HTMLResponse)
async def images_grid_viewer(request: Request):
    """Serve the image grid viewer web page."""
    return templates.TemplateResponse(
        "images_grid.html",
        {"request": request}
    )


# Reference Documents API Endpoints

@app.get("/reference-documents", response_model=List[ReferenceDocumentResponse])
async def get_reference_documents(
    search: Optional[str] = Query(None, description="Search in filename, title, description, author"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    available_for_task: Optional[bool] = Query(None, description="Filter by available_for_task flag"),
    content_type: Optional[str] = Query(None, description="Filter by content type")
):
    """Get all reference documents with optional filters.
    
    Args:
        search: Search term for filename, title, description, or author (partial match, case-insensitive)
        category: Filter by category (exact match)
        tag: Filter by tag (exact match)
        available_for_task: Filter by available_for_task flag
        content_type: Filter by content type (partial match)
        
    Returns:
        List of ReferenceDocumentResponse objects matching filters
    """
    session = db.get_session()
    try:
        query = session.query(ReferenceDocument)
        filters = []
        
        # Search filter
        if search:
            search_term = f"%{search}%"
            filters.append(
                or_(
                    ReferenceDocument.filename.ilike(search_term),
                    ReferenceDocument.title.ilike(search_term),
                    ReferenceDocument.description.ilike(search_term),
                    ReferenceDocument.author.ilike(search_term)
                )
            )
        
        # Category filter
        if category:
            filters.append(ReferenceDocument.categories.ilike(f"%{category}%"))
        
        # Tag filter
        if tag:
            filters.append(ReferenceDocument.tags.ilike(f"%{tag}%"))
        
        # Available for task filter
        if available_for_task is not None:
            filters.append(ReferenceDocument.available_for_task == available_for_task)
        
        # Content type filter
        if content_type:
            filters.append(ReferenceDocument.content_type.ilike(f"%{content_type}%"))
        
        # Apply filters
        if filters:
            query = query.filter(and_(*filters))
        
        # Order by created_at descending
        query = query.order_by(ReferenceDocument.created_at.desc())
        
        documents = query.all()
        
        # Convert to response models
        result = []
        for doc in documents:
            result.append(ReferenceDocumentResponse(
                id=doc.id,
                filename=doc.filename,
                title=doc.title,
                description=doc.description,
                author=doc.author,
                content_type=doc.content_type,
                size=doc.size,
                tags=doc.tags,
                categories=doc.categories,
                notes=doc.notes,
                available_for_task=doc.available_for_task,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            ))
        
        return result
    finally:
        session.close()


@app.get("/reference-documents/{document_id}", response_model=ReferenceDocumentResponse)
async def get_reference_document(document_id: int):
    """Get reference document metadata by ID.
    
    Args:
        document_id: The ID of the document
        
    Returns:
        ReferenceDocumentResponse with document metadata
        
    Raises:
        HTTPException: 404 if document not found
    """
    session = db.get_session()
    try:
        document = session.query(ReferenceDocument).filter(ReferenceDocument.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Reference document with ID {document_id} not found"
            )
        
        return ReferenceDocumentResponse(
            id=document.id,
            filename=document.filename,
            title=document.title,
            description=document.description,
            author=document.author,
            content_type=document.content_type,
            size=document.size,
            tags=document.tags,
            categories=document.categories,
            notes=document.notes,
            available_for_task=document.available_for_task,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
    finally:
        session.close()


@app.get("/reference-documents/{document_id}/download")
async def download_reference_document(document_id: int):
    """Download/view reference document file.
    
    Args:
        document_id: The ID of the document to download
        
    Returns:
        Binary file content with appropriate Content-Type
        
    Raises:
        HTTPException: 404 if document not found or has no data
    """
    session = db.get_session()
    try:
        document = session.query(ReferenceDocument).filter(ReferenceDocument.id == document_id).first()
    finally:
        session.close()
    
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Reference document with ID {document_id} not found"
        )
    
    if not document.data:
        raise HTTPException(
            status_code=404,
            detail=f"Reference document with ID {document_id} has no file data"
        )
    
    filename = document.filename or "document"
    safe_filename = filename.replace('"', '\\"')
    
    return Response(
        content=document.data,
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }
    )


@app.post("/reference-documents", response_model=ReferenceDocumentResponse)
async def create_reference_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    author: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    categories: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    available_for_task: bool = Form(False)
):
    """Upload a new reference document.
    
    Args:
        file: The file to upload
        title: Optional title for the document
        description: Optional description
        author: Optional author name
        tags: Optional comma-separated tags
        categories: Optional comma-separated categories
        notes: Optional notes
        available_for_task: Whether document is available for tasks
        
    Returns:
        ReferenceDocumentResponse with created document metadata
        
    Raises:
        HTTPException: 400 if file is invalid or empty
    """
    doc_service = ReferenceDocumentService(db=db)
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Validate file
        validation_result = doc_service.validate_file(file, file_content)
        
        # Prepare file data and metadata
        file_data = FileData(
            filename=file.filename,
            content=file_content,
            content_type=validation_result.content_type,
            size=len(file_content)
        )
        
        metadata = DocumentMetadata(
            title=title,
            description=description,
            author=author,
            tags=tags,
            categories=categories,
            notes=notes,
            available_for_task=available_for_task
        )
        
        # Create document
        document = doc_service.create_document(file_data, metadata)
        
        # Convert to response model
        return ReferenceDocumentResponse(**doc_service.to_response_model(document))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")


@app.put("/reference-documents/{document_id}", response_model=ReferenceDocumentResponse)
async def update_reference_document(
    document_id: int,
    update_data: ReferenceDocumentUpdateRequest
):
    """Update reference document metadata.
    
    Args:
        document_id: The ID of the document to update
        update_data: Update request with fields to update
        
    Returns:
        ReferenceDocumentResponse with updated document metadata
        
    Raises:
        HTTPException: 404 if document not found
    """
    doc_service = ReferenceDocumentService(db=db)
    
    try:
        # Convert request to DTO
        updates = DocumentUpdate(
            title=update_data.title,
            description=update_data.description,
            author=update_data.author,
            tags=update_data.tags,
            categories=update_data.categories,
            notes=update_data.notes,
            available_for_task=update_data.available_for_task
        )
        
        # Update document using service
        document = doc_service.update_document(document_id, updates)
        
        # Convert to response model
        return ReferenceDocumentResponse(**doc_service.to_response_model(document))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")


@app.delete("/reference-documents/{document_id}")
async def delete_reference_document(document_id: int):
    """Delete a reference document.
    
    Args:
        document_id: The ID of the document to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: 404 if document not found
    """
    session = db.get_session()
    try:
        document = session.query(ReferenceDocument).filter(ReferenceDocument.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Reference document with ID {document_id} not found"
            )
        
        session.delete(document)
        session.commit()
        
        return {"message": f"Reference document {document_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")
    finally:
        session.close()


@app.delete("/admin/empty-media-tables")
async def empty_media_tables():
    """Empty the attachments, media_blob, media_items, messages, and message_attachments tables.
    
    WARNING: This permanently deletes all data from these tables.
    
    Returns:
        Dictionary with deletion counts for each table
    """
    session = db.get_session()
    try:
        # Delete in order to respect foreign key constraints
        # 1. Delete message_attachments first (references messages and media_items)
        message_attachment_count = session.query(MessageAttachment).count()
        session.query(MessageAttachment).delete()
        
        # 2. Delete messages
        message_count = session.query(IMessage).count()
        session.query(IMessage).delete()
        
        # 3. Delete media_items (references media_blob)
        media_item_count = session.query(MediaMetadata).count()
        session.query(MediaMetadata).delete()
        
        # 4. Delete media_blob
        media_blob_count = session.query(MediaBlob).count()
        session.query(MediaBlob).delete()
        
        # 5. Delete attachments (old table, may not exist)
        attachment_count = 0
        try:
            attachment_count = session.query(Attachment).count()
            session.query(Attachment).delete()
        except Exception:
            # Table might not exist, ignore
            pass

        #6. Delete album_media (Facebook album images are now in unified media system)
        album_media_count = session.query(AlbumMedia).count()
        session.query(AlbumMedia).delete()

        #7. Delete facebook_albums
        facebook_album_count = session.query(FacebookAlbum).count()
        session.query(FacebookAlbum).delete()
        
        session.commit()
        
        return {
            "message": "Tables emptied successfully",
            "deleted_counts": {
                "message_attachments": message_attachment_count,
                "messages": message_count,
                "media_items": media_item_count,
                "media_blob": media_blob_count,
                "attachments": attachment_count,
                "album_media": album_media_count,
                "facebook_albums": facebook_album_count
            }
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error emptying tables: {str(e)}")
    finally:
        session.close()
