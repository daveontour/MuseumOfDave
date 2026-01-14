"""FastAPI HTTP Server."""

import os
import threading
import json
import asyncio
from pathlib import Path
from io import BytesIO
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks, Query, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import or_, func, and_, extract
from sqlalchemy.orm import joinedload
from PIL import Image

# Try to register HEIF/HEIC support if pillow-heif is available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

from ..database import Database, Attachment, Email, IMessage, FacebookAlbum, FacebookAlbumImage, ReferenceDocument
from ..database.models import ImageMetadata, ImageBlob
from ..database.storage import EmailStorage, ImageStorage
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
    export_root: Optional[str] = None
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
    export_root: Optional[str] = None
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
    export_root: Optional[str] = None


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


class ImageMetadataResponse(BaseModel):
    """Response model for image metadata."""
    id: int
    image_blob_id: int
    description: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: bool = False
    image_type: Optional[str] = None
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
    
    # Check if processing is already in progress
    with processing_lock:
        if processing_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Email processing is already in progress. Please cancel it first or wait for it to complete."
            )
    
    # Determine which labels to process
    labels_to_process = []
    
    if request.all_folders:
        # Fetch all folders from the email server
        try:
            loader_instance = get_loader()
            all_labels = loader_instance.client.get_labels()
            # Extract label names, excluding system labels that shouldn't be processed
            # (like CHAT, SENT, DRAFT, etc. - but we'll include all user labels)
            labels_to_process = [label.get("name") for label in all_labels if label.get("name")]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve folders from email server: {str(e)}"
            )
    elif request.labels:
        labels_to_process = request.labels
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'labels' must be provided or 'all_folders' must be set to true"
        )
    
    if not labels_to_process:
        raise HTTPException(
            status_code=400,
            detail="No labels found to process"
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


@app.post("/emails/process/cancel")
async def cancel_email_processing():
    """Cancel email processing if it is in progress.
    
    Returns:
        Success message indicating cancellation status
    """
    global processing_in_progress
    
    with processing_lock:
        if not processing_in_progress:
            return {
                "message": "No email processing is currently in progress",
                "cancelled": False
            }
        
        # Set cancellation flag
        processing_cancelled.set()
        
        return {
            "message": "Email processing cancellation requested. Processing will stop after current label completes.",
            "cancelled": True
        }


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
    
    # Check if import is already in progress
    with imessage_import_lock:
        if imessage_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="iMessage import is already in progress. Please cancel it first or wait for it to complete."
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
    session = db.get_session()
    try:
        # Query distinct chat_session values with message counts, attachment counts, and service types
        from sqlalchemy import func, case, text
        try:
            results = session.query(
                IMessage.chat_session,
                func.count(IMessage.id).label('message_count'),
                func.sum(
                    case((IMessage.attachment_data.isnot(None), 1), else_=0)
                ).label('attachment_count'),
                func.max(IMessage.service).label('primary_service'),
                func.max(IMessage.message_date).label('last_message_date'),
                func.count(case((IMessage.service.ilike('%iMessage%'), 1), else_=None)).label('imessage_count'),
                func.count(case((IMessage.service.ilike('%SMS%'), 1), else_=None)).label('sms_count'),
                func.count(case((IMessage.service == 'WhatsApp', 1), else_=None)).label('whatsapp_count'),
                func.count(case((IMessage.service == 'Facebook Messenger', 1), else_=None)).label('facebook_count'),
                func.count(case((IMessage.service == 'Instagram', 1), else_=None)).label('instagram_count')
            ).filter(
                IMessage.chat_session.isnot(None)
            ).group_by(
                IMessage.chat_session
            ).order_by(
                func.max(IMessage.message_date).desc()
            ).all()
        except Exception as table_error:
            # If table doesn't exist or has wrong name, try querying the old table name directly
            error_msg = str(table_error).lower()
            if 'does not exist' in error_msg or 'relation' in error_msg or 'table' in error_msg:
                # Try querying the old 'imessages' table name
                try:
                    results = session.execute(text("""
                        SELECT 
                            chat_session,
                            COUNT(id) as message_count,
                            SUM(CASE WHEN attachment_data IS NOT NULL THEN 1 ELSE 0 END) as attachment_count,
                            MAX(service) as primary_service,
                            MAX(message_date) as last_message_date,
                            COUNT(CASE WHEN service ILIKE '%iMessage%' THEN 1 END) as imessage_count,
                            COUNT(CASE WHEN service ILIKE '%SMS%' THEN 1 END) as sms_count,
                            COUNT(CASE WHEN service = 'WhatsApp' THEN 1 END) as whatsapp_count,
                            COUNT(CASE WHEN service = 'Facebook Messenger' THEN 1 END) as facebook_count,
                            COUNT(CASE WHEN service = 'Instagram' THEN 1 END) as instagram_count
                        FROM imessages
                        WHERE chat_session IS NOT NULL
                        GROUP BY chat_session
                        ORDER BY MAX(message_date) DESC
                    """)).fetchall()
                except Exception:
                    # If that also fails, return empty results
                    results = []
            else:
                raise
        
        import re
        
        def is_phone_number(chat_session: str) -> bool:
            """Check if chat_session is primarily a phone number."""
            if not chat_session:
                return False
            # Remove common separators and check if it's mostly digits
            cleaned = re.sub(r'[\s\-\(\)]', '', chat_session)
            # Check if it starts with + followed by digits, or is mostly digits
            if cleaned.startswith('+'):
                # Remove + and check if rest is digits
                return cleaned[1:].isdigit() and len(cleaned[1:]) >= 7
            # Check if it's mostly digits (at least 7 digits)
            digit_count = sum(1 for c in cleaned if c.isdigit())
            return digit_count >= 7 and len(cleaned) <= 20
        
        contacts_and_groups = []
        other_sessions = []
        
        for result in results:
            imessage_count = result[5] or 0
            sms_count = result[6] or 0
            whatsapp_count = result[7] or 0
            facebook_count = result[8] if len(result) > 8 else 0
            instagram_count = result[9] if len(result) > 9 else 0
            total_count = result[1] or 0
            last_message_date = result[4]
            
            # Determine message type: 'imessage', 'sms', 'whatsapp', 'facebook', 'instagram', or 'mixed'
            non_zero_counts = sum([
                1 if imessage_count > 0 else 0,
                1 if sms_count > 0 else 0,
                1 if whatsapp_count > 0 else 0,
                1 if facebook_count > 0 else 0,
                1 if instagram_count > 0 else 0
            ])
            
            if non_zero_counts == 1:
                # Only one service type
                if imessage_count > 0:
                    message_type = 'imessage'
                elif sms_count > 0:
                    message_type = 'sms'
                elif whatsapp_count > 0:
                    message_type = 'whatsapp'
                elif facebook_count > 0:
                    message_type = 'facebook'
                elif instagram_count > 0:
                    message_type = 'instagram'
                else:
                    message_type = 'sms'  # Default fallback
            elif non_zero_counts > 1:
                # Multiple service types
                message_type = 'mixed'
            else:
                # Fallback to primary_service if available
                primary_service = result[3] or ''
                if 'iMessage' in primary_service:
                    message_type = 'imessage'
                elif 'WhatsApp' in primary_service:
                    message_type = 'whatsapp'
                elif 'Facebook Messenger' in primary_service:
                    message_type = 'facebook'
                elif 'Instagram' in primary_service:
                    message_type = 'instagram'
                elif 'SMS' in primary_service:
                    message_type = 'sms'
                else:
                    message_type = 'sms'  # Default to SMS
            
            # Format last_message_date
            last_message_date_str = None
            if last_message_date:
                if hasattr(last_message_date, 'isoformat'):
                    # datetime object
                    last_message_date_str = last_message_date.isoformat()
                else:
                    # Already a string or other format
                    last_message_date_str = str(last_message_date)
            
            session_data = {
                "chat_session": result[0],
                "message_count": result[1],
                "has_attachments": (result[2] or 0) > 0,
                "attachment_count": result[2] or 0,
                "message_type": message_type,
                "last_message_date": last_message_date_str
            }
            
            # Categorize based on whether it's a phone number
            if is_phone_number(result[0]):
                other_sessions.append(session_data)
            else:
                contacts_and_groups.append(session_data)
        
        return {
            "contacts_and_groups": contacts_and_groups,
            "other": other_sessions
        }
    except Exception as e:
        import traceback
        print(f"Error in get_chat_sessions: {e}")
        traceback.print_exc()
        # Return empty arrays on error instead of crashing
        return {
            "contacts_and_groups": [],
            "other": []
        }
    finally:
        session.close()


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
        
        messages_data = []
        for msg in messages:
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
                "attachment_filename": msg.attachment_filename,
                "attachment_type": msg.attachment_type,
                "has_attachment": msg.attachment_data is not None
            })
        
        return {"messages": messages_data}
    finally:
        session.close()


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


def import_facebook_background(directory_path: str, export_root: Optional[str], user_name: Optional[str], result_dict: dict):
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
            export_root=export_root,
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
        request.export_root,
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
    export_root: Optional[str],
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
            export_root=export_root,
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
    
    Args:
        request: ImportInstagramRequest with directory_path, optional export_root and user_name
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
        request.export_root,
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


def import_facebook_albums_background(directory_path: str, export_root: Optional[str], result_dict: dict):
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
            cancelled_check=cancelled_check,
            export_root=export_root
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
    directory_path: str,
    max_images: Optional[int],
    create_thumbnail: bool,
    result_dict: dict
):
    """Background function to import images from filesystem."""
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
    
    try:
        def progress_callback(stats: Dict[str, Any]):
            """Callback function to update progress state."""
            # Check for cancellation
            if filesystem_import_cancelled.is_set():
                return
            
            # Update progress state with current stats
            update_filesystem_import_progress_state(
                current_file=stats.get("current_file"),
                files_processed=stats.get("files_processed", 0),
                total_files=stats.get("total_files", 0),
                images_imported=stats.get("images_imported", 0),
                images_updated=stats.get("images_updated", 0),
                errors=stats.get("errors", 0),
                error_messages=stats.get("error_messages", []),
                status="in_progress"
            )
            
            # Broadcast progress event
            broadcast_filesystem_import_progress_event_sync("progress", get_filesystem_import_progress_state())
        
        def cancelled_check() -> bool:
            """Check if import should be cancelled."""
            return filesystem_import_cancelled.is_set()
        
        # Run import with progress callback
        stats = import_images_from_filesystem(
            root_directory=directory_path,
            max_images=max_images,
            should_create_thumbnail=create_thumbnail,
            progress_callback=progress_callback,
            cancelled_check=cancelled_check
        )
        
        result_dict.update(stats)
        result_dict["success"] = True
        
        # Update final progress state
        update_filesystem_import_progress_state(
            status="completed",
            **{k: v for k, v in stats.items() if k in filesystem_import_progress and k != "status"}
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
    
    Args:
        request: Import request containing directory_path and optional export_root
        
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
        request.export_root,
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
    """Import images from filesystem directory.
    
    Args:
        request: Import request containing root_directory, optional max_images, and create_thumbnail flag
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
    
    # Validate directory path
    directory_path = Path(request.root_directory)
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.root_directory}"
        )
    
    # Prepare result dictionary for background task
    result_dict = {}
    
    # Start background import task
    background_tasks.add_task(
        import_filesystem_images_background,
        str(directory_path),
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
            func.count(FacebookAlbumImage.id).label('image_count')
        ).outerjoin(
            FacebookAlbumImage, FacebookAlbum.id == FacebookAlbumImage.album_id
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
        List of images with id, uri, filename, title, description, creation_timestamp, image_type
    """
    session = db.get_session()
    try:
        images = session.query(FacebookAlbumImage).filter(
            FacebookAlbumImage.album_id == album_id
        ).order_by(
            FacebookAlbumImage.creation_timestamp.asc()
        ).all()
        
        result = []
        for image in images:
            result.append({
                "id": image.id,
                "uri": image.uri,
                "filename": image.filename,
                "title": image.title,
                "description": image.description,
                "creation_timestamp": image.creation_timestamp.isoformat() if image.creation_timestamp else None,
                "image_type": image.image_type
            })
        
        return result
    finally:
        session.close()


@app.get("/facebook/albums/images/{image_id}")
async def get_facebook_album_image(image_id: int):
    """Get image data for a specific Facebook album image.
    
    Args:
        image_id: The ID of the image
        
    Returns:
        Image file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if image not found
    """
    session = db.get_session()
    try:
        image = session.query(FacebookAlbumImage).filter(
            FacebookAlbumImage.id == image_id
        ).first()
    finally:
        session.close()
    
    if not image:
        raise HTTPException(
            status_code=404,
            detail=f"Image with ID {image_id} not found"
        )
    
    if not image.image_data:
        raise HTTPException(
            status_code=404,
            detail=f"Image with ID {image_id} has no image data"
        )
    
    # Determine content type from image_type or filename
    content_type = image.image_type or "image/jpeg"
    if image.filename:
        import mimetypes
        guessed_type, _ = mimetypes.guess_type(image.filename)
        if guessed_type:
            content_type = guessed_type
    
    return Response(
        content=image.image_data,
        media_type=content_type
    )


@app.get("/imessages/{message_id}/attachment")
async def get_imessage_attachment(message_id: int, preview: bool = False):
    """Get attachment content for an iMessage.
    
    Args:
        message_id: The ID of the message
        preview: If True, return thumbnail/preview (not implemented yet, returns full)
        
    Returns:
        Attachment file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if message not found or has no attachment
    """
    session = db.get_session()
    try:
        message = session.query(IMessage).filter(IMessage.id == message_id).first()
    finally:
        session.close()
    
    if not message:
        raise HTTPException(
            status_code=404,
            detail=f"Message with ID {message_id} not found"
        )
    
    if not message.attachment_data:
        raise HTTPException(
            status_code=404,
            detail=f"Message with ID {message_id} has no attachment"
        )
    
    # Determine content type from attachment_type or filename
    content_type = message.attachment_type or "application/octet-stream"
    if message.attachment_filename:
        import mimetypes
        guessed_type, _ = mimetypes.guess_type(message.attachment_filename)
        if guessed_type:
            content_type = guessed_type
    
    filename = message.attachment_filename or "attachment"
    safe_filename = filename.replace('"', '\\"')
    
    return Response(
        content=message.attachment_data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }
    )


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
        email = session.query(Email).filter(Email.id == email_id).first()
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
        email = session.query(Email).filter(Email.id == email_id).first()
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
        email = session.query(Email).filter(Email.id == email_id).first()
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
        # Eagerly load attachments to avoid lazy loading issues
        email = session.query(Email).options(joinedload(Email.attachments)).filter(Email.id == email_id).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} not found"
            )
        
        # Get attachment IDs and create response while session is open
        attachment_ids = [att.id for att in email.attachments]
        
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
            updated_at=email.updated_at
        )
    finally:
        session.close()


@app.delete("/emails/{email_id}")
async def delete_email(email_id: int):
    """Delete an email by ID.
    
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
        
        # Delete the email - attachments will be cascade deleted via SQLAlchemy relationship
        session.delete(email)
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
        # Eagerly load attachments to avoid lazy loading issues
        emails = session.query(Email).options(joinedload(Email.attachments)).filter(
            or_(*label_filters)
        ).all()
        
        # Convert to response models (access attachments while session is open)
        result = [
            EmailMetadataResponse(
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
                attachment_ids=[att.id for att in email.attachments],
                created_at=email.created_at,
                updated_at=email.updated_at
            )
            for email in emails
        ]
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
        query = session.query(Email).options(joinedload(Email.attachments))
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
        
        # Apply all filters with AND logic
        if filters:
            query = query.filter(and_(*filters))
        
        # Sort by descending date (newest first)
        query = query.order_by(Email.date.desc())
        
        # Execute query
        emails = query.all()
        
        # Convert to response models (access attachments while session is open)
        result = [
            EmailMetadataResponse(
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
                attachment_ids=[att.id for att in email.attachments],
                created_at=email.created_at,
                updated_at=email.updated_at
            )
            for email in emails
        ]
        
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
        # Get a random attachment
        attachment = session.query(Attachment).order_by(func.random()).first()
        
        if not attachment:
            return None
        
        # Get the email for this attachment
        email = session.query(Email).filter(Email.id == attachment.email_id).first()
        
        if not email:
            return None
        
        return AttachmentInfoResponse(
            attachment_id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
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
        attachment = session.query(Attachment).order_by(Attachment.id.asc()).offset(offset).first()
        
        if not attachment:
            return None
        
        # Get the email for this attachment
        email = session.query(Email).filter(Email.id == attachment.email_id).first()
        
        if not email:
            return None
        
        return AttachmentInfoResponse(
            attachment_id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
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
    
    Args:
        order: Order direction - 'asc' for smallest to biggest, 'desc' for biggest to smallest
        offset: Offset for pagination (0-based)
        
    Returns:
        AttachmentInfoResponse with attachment and email metadata, or None if no attachment at offset
    """
    session = db.get_session()
    try:
        if order == "asc":
            attachment = session.query(Attachment).order_by(Attachment.size.asc().nullslast()).offset(offset).first()
        else:
            attachment = session.query(Attachment).order_by(Attachment.size.desc().nullslast()).offset(offset).first()
        
        if not attachment:
            return None
        
        # Get the email for this attachment
        email = session.query(Email).filter(Email.id == attachment.email_id).first()
        
        if not email:
            return None
        
        return AttachmentInfoResponse(
            attachment_id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
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
        count = session.query(Attachment).count()
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
        
        # Query attachments - filter by type if not showing all types
        if all_types:
            attachments_query = session.query(Attachment).join(Email)
        else:
            attachments_query = session.query(Attachment).join(Email).filter(
                Attachment.content_type.like('image/%')
            )
        
        # Apply sorting
        if order == "id":
            if direction == "asc":
                attachments_query = attachments_query.order_by(Attachment.id.asc())
            else:
                attachments_query = attachments_query.order_by(Attachment.id.desc())
        elif order == "size":
            if direction == "asc":
                attachments_query = attachments_query.order_by(Attachment.size.asc().nullslast())
            else:
                attachments_query = attachments_query.order_by(Attachment.size.desc().nullslast())
        elif order == "date":
            if direction == "asc":
                attachments_query = attachments_query.order_by(Email.date.asc().nullslast())
            else:
                attachments_query = attachments_query.order_by(Email.date.desc().nullslast())
        
        # Get total count
        total = attachments_query.count()
        
        # Get paginated results
        attachments = attachments_query.offset(offset).limit(page_size).all()
        
        # Build response
        image_list = []
        for att in attachments:
            email = att.email
            image_list.append(AttachmentInfoResponse(
                attachment_id=att.id,
                filename=att.filename,
                content_type=att.content_type,
                size=att.size,
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
        attachment_id: The ID of the attachment
        
    Returns:
        AttachmentInfoResponse with attachment and email metadata
        
    Raises:
        HTTPException: 404 if attachment not found
    """
    session = db.get_session()
    try:
        attachment = session.query(Attachment).filter(Attachment.id == attachment_id).first()
        
        if not attachment:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )
        
        # Get the email for this attachment
        email = session.query(Email).filter(Email.id == attachment.email_id).first()
        
        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email for attachment {attachment_id} not found"
            )
        
        return AttachmentInfoResponse(
            attachment_id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size=attachment.size,
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
    """Delete an attachment by ID.
    
    Args:
        attachment_id: The ID of the attachment to delete
        
    Returns:
        Success message
        
    Raises:
        HTTPException: 404 if attachment not found
    """
    session = db.get_session()
    try:
        attachment = session.query(Attachment).filter(Attachment.id == attachment_id).first()
        
        if not attachment:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )
        
        session.delete(attachment)
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
    """Get attachment content by ID.
    
    Args:
        attachment_id: The ID of the attachment to retrieve
        preview: If True and attachment is an image, return thumbnail instead of full image
        
    Returns:
        Attachment file content with appropriate MIME type
        
    Raises:
        HTTPException: 404 if attachment not found or has no content
    """
    session = db.get_session()
    try:
        attachment = session.query(Attachment).filter(Attachment.id == attachment_id).first()
    finally:
        session.close()
    
    if not attachment:
        raise HTTPException(
            status_code=404,
            detail=f"Attachment with ID {attachment_id} not found"
        )
    
    # Check if preview is requested
    content_type = attachment.content_type or "application/octet-stream"
    
    if preview:
        # Return thumbnail if available (for all file types)
        content = attachment.image_thumbnail
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} has no thumbnail available"
            )
        # Thumbnails are always JPEG
        content_type = "image/jpeg"
        filename = attachment.filename or "attachment"
        # Add _thumb suffix to filename
        base_name, ext = os.path.splitext(filename)
        safe_filename = f"{base_name}_thumb.jpg".replace('"', '\\"')
    else:
        # Return full attachment
        content = attachment.data
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} has no content"
            )
        filename = attachment.filename or "attachment"
        safe_filename = filename.replace('"', '\\"')
    
    # Set Content-Disposition header for filename
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"'
    }
    
    # Return the binary content with proper headers
    return Response(
        content=content,
        media_type=content_type,
        headers=headers
    )


@app.get("/images/search", response_model=List[ImageMetadataResponse])
async def search_images(
    title: Optional[str] = Query(None, description="Filter by title (partial match, case-insensitive)"),
    description: Optional[str] = Query(None, description="Filter by description (partial match, case-insensitive)"),
    author: Optional[str] = Query(None, description="Filter by author (partial match, case-insensitive)"),
    tags: Optional[str] = Query(None, description="Filter by tags (partial match, case-insensitive)"),
    categories: Optional[str] = Query(None, description="Filter by categories (partial match, case-insensitive)"),
    source: Optional[str] = Query(None, description="Filter by source (exact match, case-insensitive)"),
    source_reference: Optional[str] = Query(None, description="Filter by source_reference (partial match, case-insensitive)"),
    image_type: Optional[str] = Query(None, description="Filter by image type/MIME type (partial match, case-insensitive)"),
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
        image_type: Partial match on image type/MIME type
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
        List of ImageMetadataResponse objects matching all specified criteria
    """
    session = db.get_session()
    try:
        # Start building query
        query = session.query(ImageMetadata)
        filters = []
        
        # Text field filters (partial match, case-insensitive)
        if title:
            filters.append(ImageMetadata.title.ilike(f"%{title}%"))
        
        if description:
            filters.append(ImageMetadata.description.ilike(f"%{description}%"))
        
        if author:
            filters.append(ImageMetadata.author.ilike(f"%{author}%"))
        
        if tags:
            filters.append(ImageMetadata.tags.ilike(f"%{tags}%"))
        
        if categories:
            filters.append(ImageMetadata.categories.ilike(f"%{categories}%"))
        
        if source:
            filters.append(ImageMetadata.source.ilike(source))
        
        if source_reference:
            filters.append(ImageMetadata.source_reference.ilike(f"%{source_reference}%"))
        
        if image_type:
            filters.append(ImageMetadata.image_type.ilike(f"%{image_type}%"))
        
        if region:
            filters.append(ImageMetadata.region.ilike(f"%{region}%"))
        
        # Numeric filters
        if year is not None:
            filters.append(ImageMetadata.year == year)
        
        if month is not None:
            filters.append(ImageMetadata.month == month)
        
        # Rating filters
        if rating is not None:
            filters.append(ImageMetadata.rating == rating)
        else:
            if rating_min is not None:
                filters.append(ImageMetadata.rating >= rating_min)
            if rating_max is not None:
                filters.append(ImageMetadata.rating <= rating_max)
        
        # Boolean filters
        if has_gps is not None:
            filters.append(ImageMetadata.has_gps == has_gps)
        
        if available_for_task is not None:
            filters.append(ImageMetadata.available_for_task == available_for_task)
        
        if processed is not None:
            filters.append(ImageMetadata.processed == processed)
        
        if location_processed is not None:
            filters.append(ImageMetadata.location_processed == location_processed)
        
        if image_processed is not None:
            filters.append(ImageMetadata.image_processed == image_processed)
        
        # Apply all filters with AND logic
        if filters:
            query = query.filter(and_(*filters))
        
        # Sort by created_at descending (newest first)
        query = query.order_by(ImageMetadata.created_at.desc())
        
        # Execute query
        images = query.all()
        
        # Convert to response models
        result = []
        for img in images:
            result.append(ImageMetadataResponse(
                id=img.id,
                image_blob_id=img.image_blob_id,
                description=img.description,
                title=img.title,
                author=img.author,
                tags=img.tags,
                categories=img.categories,
                notes=img.notes,
                available_for_task=img.available_for_task,
                image_type=img.image_type,
                processed=img.processed,
                location_processed=img.location_processed,
                image_processed=img.image_processed,
                created_at=img.created_at,
                updated_at=img.updated_at,
                year=img.year,
                month=img.month,
                latitude=img.latitude,
                longitude=img.longitude,
                altitude=img.altitude,
                rating=img.rating,
                has_gps=img.has_gps,
                google_maps_url=img.google_maps_url,
                region=img.region,
                source=img.source,
                source_reference=img.source_reference
            ))
        
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching images: {str(e)}"
        )
    finally:
        session.close()


@app.get("/images/{image_id}")
async def get_image_content(
    image_id: int,
    type: str = Query("blob", regex="^(blob|metadata)$", description="Type of ID: 'blob' for image_blob.id or 'metadata' for image_information.id"),
    preview: bool = Query(False, description="If True, return thumbnail instead of full image"),
    convert_heic_to_jpg: bool = Query(True, description="If True, convert HEIC images to JPG format before returning")
):
    """Get image content by ID.
    
    Args:
        image_id: The ID of the image (blob ID or metadata ID depending on type parameter)
        type: Type of ID - 'blob' for image_blob.id or 'metadata' for image_information.id (default: 'blob')
        preview: If True, return thumbnail instead of full image
        convert_heic_to_jpg: If True, convert HEIC images to JPG format before returning (default: True)
        
    Returns:
        Image binary data with appropriate content-type
        
    Raises:
        HTTPException: 404 if image not found or has no content
    """
    # Use shared database instance to avoid creating new connections
    storage = ImageStorage(db=db)
    
    # Get image blob based on type
    if type == "metadata":
        image_blob = storage.get_image_by_metadata_id(image_id)
    else:
        image_blob = storage.get_image_by_blob_id(image_id)
    
    if not image_blob:
        raise HTTPException(
            status_code=404,
            detail=f"Image with ID {image_id} (type: {type}) not found"
        )
    
    # Determine content
    if preview:
        content = image_blob.thumbnail_data
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} has no thumbnail available"
            )
        content_type = "image/jpeg"  # Thumbnails are always JPEG
        filename = "image_thumb.jpg"
    else:
        content = image_blob.image_data
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} has no image data"
            )
        # Get content type from metadata using a single optimized query
        session = db.get_session()
        try:
            if type == "metadata":
                # We already know the metadata ID, so query directly
                metadata = session.query(ImageMetadata).filter(
                    ImageMetadata.id == image_id
                ).first()
            else:
                # Query metadata by blob_id
                metadata = session.query(ImageMetadata).filter(
                    ImageMetadata.image_blob_id == image_blob.id
                ).first()
            
            if metadata and metadata.image_type:
                content_type = metadata.image_type
            else:
                content_type = "image/jpeg"  # Default
            filename = metadata.source_reference.split(os.sep)[-1] if metadata and metadata.source_reference else "image"
        finally:
            session.close()
        
        # Convert HEIC to JPG if requested
        if convert_heic_to_jpg and content_type and content_type.lower() in ('image/heic', 'image/heif'):
            try:
                # Open the HEIC image
                img = Image.open(BytesIO(content))
                
                # Convert to RGB if necessary
                if img.mode in ("RGBA", "LA", "P"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")
                
                # Convert to JPEG bytes
                jpg_bytes = BytesIO()
                img.save(jpg_bytes, format="JPEG", quality=95)
                jpg_bytes.seek(0)
                content = jpg_bytes.getvalue()
                
                # Update content type and filename
                content_type = "image/jpeg"
                if filename and filename.lower().endswith(('.heic', '.heif')):
                    filename = os.path.splitext(filename)[0] + '.jpg'
                else:
                    filename = "image.jpg"
            except Exception as e:
                # If conversion fails, return original image with a warning
                # In production, you might want to log this error
                pass  # Fall through to return original content
    
    # Set Content-Disposition header
    safe_filename = filename.replace('"', '\\"')
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"'
    }
    
    return Response(
        content=content,
        media_type=content_type,
        headers=headers
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
        query = session.query(ImageMetadata)
        
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
                        ImageMetadata.id >= start_id,
                        ImageMetadata.id <= end_id
                    )
                )
            elif start_id is not None:
                query = query.filter(ImageMetadata.id >= start_id)
            elif end_id is not None:
                query = query.filter(ImageMetadata.id <= end_id)
            
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
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Read file content
    file_content = await file.read()
    if not file_content:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Get content type
    content_type = file.content_type or "application/octet-stream"
    
    # Validate file type (documents and images)
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "application/json",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/webp"
    ]
    
    if content_type not in allowed_types:
        # Try to guess from filename
        import mimetypes
        guessed_type, _ = mimetypes.guess_type(file.filename)
        if guessed_type and guessed_type in allowed_types:
            content_type = guessed_type
        else:
            raise HTTPException(
                status_code=400,
                detail=f"File type {content_type} not allowed. Allowed types: documents and images."
            )
    
    session = db.get_session()
    try:
        document = ReferenceDocument(
            filename=file.filename,
            title=title,
            description=description,
            author=author,
            content_type=content_type,
            size=len(file_content),
            data=file_content,
            tags=tags,
            categories=categories,
            notes=notes,
            available_for_task=available_for_task
        )
        
        session.add(document)
        session.commit()
        session.refresh(document)
        
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
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")
    finally:
        session.close()


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
    session = db.get_session()
    try:
        document = session.query(ReferenceDocument).filter(ReferenceDocument.id == document_id).first()
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"Reference document with ID {document_id} not found"
            )
        
        # Update fields if provided
        if update_data.title is not None:
            document.title = update_data.title
        if update_data.description is not None:
            document.description = update_data.description
        if update_data.author is not None:
            document.author = update_data.author
        if update_data.tags is not None:
            document.tags = update_data.tags
        if update_data.categories is not None:
            document.categories = update_data.categories
        if update_data.notes is not None:
            document.notes = update_data.notes
        if update_data.available_for_task is not None:
            document.available_for_task = update_data.available_for_task
        
        document.updated_at = datetime.utcnow()
        
        session.commit()
        session.refresh(document)
        
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
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")
    finally:
        session.close()


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
