"""Shared import state management - global variables and thread-safe accessors."""
import json
import asyncio
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..database.models import ImportControlLastRun
from .deps import db

# ---------------------------------------------------------------------------
# Email processing state
# ---------------------------------------------------------------------------

processing_lock = threading.Lock()
processing_cancelled = threading.Event()
processing_in_progress = False

processing_progress: Dict[str, Any] = {
    "current_label": None,
    "current_label_index": 0,
    "total_labels": 0,
    "emails_processed": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None,
    "labels": []
}

sse_clients: List[asyncio.Queue] = []
sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# iMessage import state
# ---------------------------------------------------------------------------

imessage_import_lock = threading.Lock()
imessage_import_cancelled = threading.Event()
imessage_import_in_progress = False

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
    "error_message": None,
    "status_line": None,
}

imessage_sse_clients: List[asyncio.Queue] = []
imessage_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Conversation summary state
# ---------------------------------------------------------------------------

conversation_summary_lock = threading.Lock()
conversation_summary_in_progress = False
conversation_summary_progress: Dict[str, Any] = {
    "status": "idle",  # idle, processing, completed, error
    "chat_session": None,
    "stage": None,
    "summary": None,
    "error": None
}

conversation_summary_sse_clients: List[asyncio.Queue] = []
conversation_summary_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# WhatsApp import state
# ---------------------------------------------------------------------------

whatsapp_import_lock = threading.Lock()
whatsapp_import_cancelled = threading.Event()
whatsapp_import_in_progress = False

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
    "error_message": None,
    "status_line": None,
}

whatsapp_sse_clients: List[asyncio.Queue] = []
whatsapp_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Facebook Messenger import state
# ---------------------------------------------------------------------------

facebook_import_lock = threading.Lock()
facebook_import_cancelled = threading.Event()
facebook_import_in_progress = False

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
    "error_message": None,
    "status_line": None,
}

facebook_sse_clients: List[asyncio.Queue] = []
facebook_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Instagram import state
# ---------------------------------------------------------------------------

instagram_import_lock = threading.Lock()
instagram_import_cancelled = threading.Event()
instagram_import_in_progress = False

instagram_import_progress: Dict[str, Any] = {
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
    "error_message": None,
    "status_line": None,
}

instagram_sse_clients: List[asyncio.Queue] = []
instagram_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Facebook Albums import state
# ---------------------------------------------------------------------------

facebook_albums_import_lock = threading.Lock()
facebook_albums_import_cancelled = threading.Event()
facebook_albums_import_in_progress = False

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
    "error_message": None,
    "status_line": None,
}

facebook_albums_sse_clients: List[asyncio.Queue] = []
facebook_albums_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Facebook Places import state
# ---------------------------------------------------------------------------

facebook_places_import_lock = threading.Lock()
facebook_places_import_cancelled = threading.Event()
facebook_places_import_in_progress = False
facebook_places_import_progress: Dict[str, Any] = {
    "status": "idle",
    "status_line": None,
    "places_imported": 0,
    "places_created": 0,
    "places_updated": 0,
    "errors": [],
    "error_message": None,
}
facebook_places_sse_clients: List[asyncio.Queue] = []
facebook_places_sse_clients_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Filesystem import state
# ---------------------------------------------------------------------------

filesystem_import_lock = threading.Lock()
filesystem_import_cancelled = threading.Event()
filesystem_import_in_progress = False

filesystem_import_progress: Dict[str, Any] = {
    "status": "idle",
    "status_line": None,
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

# ---------------------------------------------------------------------------
# Thumbnail processing state
# ---------------------------------------------------------------------------

thumbnail_processing_lock = threading.Lock()
thumbnail_processing_cancelled = threading.Event()
thumbnail_processing_in_progress = False

thumbnail_processing_progress: Dict[str, Any] = {
    "phase": None,
    "phase1_scanned": 0,
    "phase1_updated": 0,
    "phase2_scanned": 0,
    "phase2_total": 0,
    "phase2_processed": 0,
    "phase2_errors": 0,
    "status": "idle",  # idle, in_progress, completed, cancelled, error
    "error_message": None,
    "status_line": None,
}

thumbnail_processing_sse_clients: List[asyncio.Queue] = []
thumbnail_processing_sse_clients_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helper: record import run results
# ---------------------------------------------------------------------------

def _record_import_control_last_run(import_type: str, result: str, result_message: Optional[str] = None):
    """Record the last run time and result of an import control. Result: success, error, cancelled."""
    try:
        session = db.get_session()
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            existing = session.query(ImportControlLastRun).filter(
                ImportControlLastRun.import_type == import_type
            ).first()
            if existing:
                existing.last_run_at = now
                existing.result = result
                existing.result_message = result_message[:500] if result_message else None
            else:
                session.add(ImportControlLastRun(
                    import_type=import_type,
                    last_run_at=now,
                    result=result,
                    result_message=result_message[:500] if result_message else None
                ))
            session.commit()
        finally:
            session.close()
    except Exception as e:
        print(f"[ImportControlLastRun] Failed to record: {e}")


# ---------------------------------------------------------------------------
# Email processing state functions
# ---------------------------------------------------------------------------

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

    with sse_clients_lock:
        disconnected_clients = []
        for client_queue in sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in sse_clients:
                sse_clients.remove(client)


# ---------------------------------------------------------------------------
# iMessage import state functions
# ---------------------------------------------------------------------------

def update_imessage_progress_state(**kwargs):
    """Thread-safe function to update iMessage import progress state."""
    global imessage_import_progress
    with imessage_import_lock:
        for key, value in kwargs.items():
            if key in imessage_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
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

    with imessage_sse_clients_lock:
        disconnected_clients = []
        for client_queue in imessage_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in imessage_sse_clients:
                imessage_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Conversation summary state functions
# ---------------------------------------------------------------------------

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

    with conversation_summary_sse_clients_lock:
        disconnected_clients = []
        for client_queue in conversation_summary_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in conversation_summary_sse_clients:
                conversation_summary_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# WhatsApp import state functions
# ---------------------------------------------------------------------------

def update_whatsapp_progress_state(**kwargs):
    """Thread-safe function to update WhatsApp import progress state."""
    global whatsapp_import_progress
    with whatsapp_import_lock:
        for key, value in kwargs.items():
            if key in whatsapp_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
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

    with whatsapp_sse_clients_lock:
        disconnected_clients = []
        for client_queue in whatsapp_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in whatsapp_sse_clients:
                whatsapp_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Facebook Messenger import state functions
# ---------------------------------------------------------------------------

def update_facebook_progress_state(**kwargs):
    """Thread-safe function to update Facebook Messenger import progress state."""
    global facebook_import_progress
    with facebook_import_lock:
        for key, value in kwargs.items():
            if key in facebook_import_progress:
                if key == "missing_attachment_filenames" and isinstance(value, list):
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

    with facebook_sse_clients_lock:
        disconnected_clients = []
        for client_queue in facebook_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in facebook_sse_clients:
                facebook_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Facebook Albums import state functions
# ---------------------------------------------------------------------------

def update_facebook_albums_progress_state(**kwargs):
    """Thread-safe function to update Facebook Albums import progress state."""
    global facebook_albums_import_progress
    with facebook_albums_import_lock:
        for key, value in kwargs.items():
            if key in facebook_albums_import_progress:
                if key == "missing_image_filenames" and isinstance(value, list):
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

    with facebook_albums_sse_clients_lock:
        disconnected_clients = []
        for client_queue in facebook_albums_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in facebook_albums_sse_clients:
                facebook_albums_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Facebook Places import state functions
# ---------------------------------------------------------------------------

def update_facebook_places_progress_state(**kwargs):
    """Thread-safe function to update Facebook Places import progress state."""
    global facebook_places_import_progress
    with facebook_places_import_lock:
        for key, value in kwargs.items():
            if key in facebook_places_import_progress:
                if key == "errors" and isinstance(value, list):
                    facebook_places_import_progress[key] = value.copy()
                else:
                    facebook_places_import_progress[key] = value


def get_facebook_places_progress_state() -> Dict[str, Any]:
    """Thread-safe function to get current Facebook Places import progress state."""
    global facebook_places_import_progress
    with facebook_places_import_lock:
        return facebook_places_import_progress.copy()


def broadcast_facebook_places_progress_event_sync(event_type: str, data: Dict[str, Any]):
    """Thread-safe function to queue Facebook Places import progress event for SSE clients."""
    global facebook_places_sse_clients
    event_data = {"type": event_type, "data": data}
    message = f"data: {json.dumps(event_data)}\n\n"
    with facebook_places_sse_clients_lock:
        disconnected_clients = []
        for client_queue in facebook_places_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)
        for client in disconnected_clients:
            if client in facebook_places_sse_clients:
                facebook_places_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Filesystem import state functions
# ---------------------------------------------------------------------------

def update_filesystem_import_progress_state(**kwargs):
    """Thread-safe function to update Filesystem import progress state."""
    global filesystem_import_progress
    with filesystem_import_lock:
        for key, value in kwargs.items():
            if key in filesystem_import_progress:
                if key == "error_messages" and isinstance(value, list):
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

    with filesystem_import_sse_clients_lock:
        disconnected_clients = []
        for client_queue in filesystem_import_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in filesystem_import_sse_clients:
                filesystem_import_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Thumbnail processing state functions
# ---------------------------------------------------------------------------

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

    with thumbnail_processing_sse_clients_lock:
        disconnected_clients = []
        for client_queue in thumbnail_processing_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in thumbnail_processing_sse_clients:
                thumbnail_processing_sse_clients.remove(client)


# ---------------------------------------------------------------------------
# Instagram import state functions
# ---------------------------------------------------------------------------

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


def broadcast_instagram_progress_event_sync(event_type: str = "progress", data: Optional[Dict[str, Any]] = None):
    """Thread-safe function to queue Instagram import progress event for SSE clients."""
    global instagram_sse_clients
    if data is None:
        data = get_instagram_progress_state()

    event_data = {
        "type": event_type,
        "data": data
    }

    message = f"data: {json.dumps(event_data)}\n\n"

    with instagram_sse_clients_lock:
        disconnected_clients = []
        for client_queue in instagram_sse_clients:
            try:
                client_queue.put_nowait(message)
            except asyncio.QueueFull:
                pass
            except Exception:
                disconnected_clients.append(client_queue)

        for client in disconnected_clients:
            if client in instagram_sse_clients:
                instagram_sse_clients.remove(client)
