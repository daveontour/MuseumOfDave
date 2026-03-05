"""IMAP email import routes."""
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

from ...loader import EmailDatabaseLoader
from ..state import (
    imap_processing_lock,
    imap_processing_cancelled,
    imap_processing_in_progress,
    imap_sse_clients,
    imap_sse_clients_lock,
    update_imap_progress_state,
    get_imap_progress_state,
    broadcast_imap_progress_event_sync,
    _record_import_control_last_run,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IMAPProcessRequest(BaseModel):
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True
    folders: Optional[List[str]] = None
    all_folders: bool = False
    new_only: bool = False


class IMAPFoldersRequest(BaseModel):
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def process_imap_background(request_params: dict, folders: List[str], result_dict: dict):
    """Background task that imports emails from IMAP folders sequentially."""
    global imap_processing_in_progress

    with imap_processing_lock:
        imap_processing_in_progress = True
        imap_processing_cancelled.clear()

    update_imap_progress_state(
        current_folder=None,
        current_folder_index=0,
        total_folders=len(folders),
        emails_processed=0,
        status="in_progress",
        error_message=None,
        folders=folders
    )
    broadcast_imap_progress_event_sync("progress", get_imap_progress_state())

    loader_instance = EmailDatabaseLoader()
    try:
        loader_instance.init_imap_client(
            host=request_params["host"],
            port=request_params["port"],
            username=request_params["username"],
            password=request_params["password"],
            use_ssl=request_params["use_ssl"],
        )

        result_dict["count"] = 0
        total_emails_processed = 0

        for idx, folder in enumerate(folders, start=1):
            if imap_processing_cancelled.is_set():
                update_imap_progress_state(status="cancelled", error_message="Cancelled by user")
                broadcast_imap_progress_event_sync("cancelled", get_imap_progress_state())
                break

            update_imap_progress_state(current_folder=folder, current_folder_index=idx)
            broadcast_imap_progress_event_sync("progress", get_imap_progress_state())

            try:
                base = total_emails_processed

                def per_email(count_in_folder, _base=base):
                    update_imap_progress_state(emails_processed=_base + count_in_folder)
                    broadcast_imap_progress_event_sync("progress", get_imap_progress_state())

                count = loader_instance.load_emails(
                    folder,
                    new_only=request_params["new_only"],
                    progress_callback=per_email,
                )
                result_dict["count"] += count
                total_emails_processed += count
                update_imap_progress_state(emails_processed=total_emails_processed)
                broadcast_imap_progress_event_sync("progress", get_imap_progress_state())
                print(f"[IMAP] Folder {folder}: {count} emails processed")
            except Exception as e:
                error_msg = f"Error processing folder {folder}: {str(e)}"
                print(f"[IMAP] {error_msg}")
                import traceback
                traceback.print_exc()
                update_imap_progress_state(status="error", error_message=error_msg)
                broadcast_imap_progress_event_sync("error", get_imap_progress_state())

        current = get_imap_progress_state()
        if current["status"] == "in_progress":
            update_imap_progress_state(status="completed")
            broadcast_imap_progress_event_sync("completed", get_imap_progress_state())

    finally:
        try:
            if hasattr(loader_instance, 'client') and loader_instance.client:
                loader_instance.client.disconnect()
        except Exception:
            pass

        state = get_imap_progress_state()
        result = "cancelled" if imap_processing_cancelled.is_set() else (state.get("status") or "error")
        msg = state.get("error_message") if result == "error" else None
        _record_import_control_last_run("imap_processing", result, msg)

        with imap_processing_lock:
            imap_processing_in_progress = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/imap/process")
async def process_imap(request: IMAPProcessRequest, background_tasks: BackgroundTasks):
    """Start importing emails from an IMAP server."""
    global imap_processing_in_progress

    with imap_processing_lock:
        if imap_processing_in_progress:
            raise HTTPException(status_code=409, detail="IMAP processing already in progress")

    # Resolve folder list by connecting briefly
    from ...email_client.imap_client import IMAPClient
    client = IMAPClient(request.host, request.port, request.username, request.password, request.use_ssl)
    try:
        client.connect()
        if request.all_folders:
            folders = client.get_folders()
        elif request.folders:
            folders = request.folders
        else:
            folders = ["INBOX"]
        client.disconnect()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IMAP connection failed: {str(e)}")

    if not folders:
        raise HTTPException(status_code=400, detail="No folders found or specified")

    result_dict = {"count": 0}
    params = request.model_dump()
    background_tasks.add_task(process_imap_background, params, folders, result_dict)

    return {"message": f"IMAP processing started for {len(folders)} folder(s)", "folders": folders}


@router.post("/imap/process/cancel")
async def cancel_imap_processing():
    """Cancel in-progress IMAP import."""
    global imap_processing_in_progress

    with imap_processing_lock:
        if not imap_processing_in_progress:
            return {"message": "No IMAP processing in progress", "cancelled": False}

    imap_processing_cancelled.set()
    return {"message": "IMAP processing cancellation requested", "cancelled": True}


@router.get("/imap/process/status")
async def get_imap_status():
    """Get the current status of IMAP processing."""
    global imap_processing_in_progress

    progress_state = get_imap_progress_state()

    with imap_processing_lock:
        return {
            "in_progress": imap_processing_in_progress,
            "cancelled": imap_processing_cancelled.is_set(),
            **progress_state
        }


@router.get("/imap/process/stream")
async def stream_imap_progress():
    """Stream IMAP processing progress via Server-Sent Events."""
    async def event_generator():
        client_queue = asyncio.Queue(maxsize=100)

        with imap_sse_clients_lock:
            imap_sse_clients.append(client_queue)

        try:
            initial_state = get_imap_progress_state()
            yield f"data: {json.dumps({'type': 'progress', 'data': initial_state})}\n\n"

            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()

            while True:
                try:
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        yield f"data: {json.dumps({'type': 'heartbeat', 'data': {'timestamp': datetime.now().isoformat()}})}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()

                    progress_state = get_imap_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        yield f"data: {json.dumps({'type': progress_state['status'], 'data': progress_state})}\n\n"
                        break

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"
                    break
        finally:
            with imap_sse_clients_lock:
                if client_queue in imap_sse_clients:
                    imap_sse_clients.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/imap/folders")
async def get_imap_folders(request: IMAPFoldersRequest):
    """List available folders for an IMAP server."""
    from ...email_client.imap_client import IMAPClient
    client = IMAPClient(request.host, request.port, request.username, request.password, request.use_ssl)
    try:
        client.connect()
        folders = client.get_folders()
        client.disconnect()
        return {"folders": folders}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect: {str(e)}")
