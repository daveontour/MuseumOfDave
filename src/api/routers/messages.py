"""Messages routes: iMessage, WhatsApp, Facebook Messenger, Instagram imports, and writing style."""
import os
import re
import json
import asyncio
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Response, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ...database.models import (
    IMessage, MediaMetadata, MediaBlob, MessageAttachment
)
from ...services import MessageService
from ...services.gemini_service import GeminiService
from ...services.message_service import ChatSessionInfo
from ...services.exceptions import ServiceException, NotFoundError
from ...services.subject_configuration_service import SubjectConfigurationService
from ...utils.docker_utils import translate_path_to_container
from ..deps import db
from ..state import (
    # iMessage
    imessage_import_lock, imessage_import_cancelled, imessage_import_in_progress,
    update_imessage_progress_state, get_imessage_progress_state,
    broadcast_imessage_progress_event_sync, imessage_sse_clients, imessage_sse_clients_lock,
    # WhatsApp
    whatsapp_import_lock, whatsapp_import_cancelled, whatsapp_import_in_progress,
    update_whatsapp_progress_state, get_whatsapp_progress_state,
    broadcast_whatsapp_progress_event_sync, whatsapp_sse_clients, whatsapp_sse_clients_lock,
    # Facebook Messenger
    facebook_import_lock, facebook_import_cancelled, facebook_import_in_progress,
    update_facebook_progress_state, get_facebook_progress_state,
    broadcast_facebook_progress_event_sync, facebook_sse_clients, facebook_sse_clients_lock,
    # Instagram
    instagram_import_lock, instagram_import_cancelled, instagram_import_in_progress,
    update_instagram_progress_state, get_instagram_progress_state,
    broadcast_instagram_progress_event_sync, instagram_sse_clients, instagram_sse_clients_lock,
    # Conversation summary
    conversation_summary_lock, conversation_summary_in_progress,
    update_conversation_summary_progress_state, get_conversation_summary_progress_state,
    broadcast_conversation_summary_event_sync,
    conversation_summary_sse_clients, conversation_summary_sse_clients_lock,
    _record_import_control_last_run,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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
    export_root: Optional[str] = None


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
    export_root: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Shared helpers (import-processor path + stdout parsers)
# ---------------------------------------------------------------------------

def _get_import_processor_path() -> Path:
    """Resolve path to import-processor binary. Uses IMPORT_PROCESSOR_PATH env if set."""
    import os as _os
    env_path = _os.environ.get("IMPORT_PROCESSOR_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    import_processor_dir = project_root / "import-processor"
    if _os.name == "nt":
        binary = import_processor_dir / "import-processor.exe"
    else:
        binary = import_processor_dir / "import-processor"
    if not binary.exists():
        raise FileNotFoundError(
            f"import-processor not found at {binary}. "
            "Build it with: cd import-processor && go build -o import-processor ./cmd/import-processor"
        )
    return binary


def _parse_message_stdout(stdout: str) -> tuple:
    """Generic parser for message import stdout. Returns 9-tuple."""
    conversations_processed = 0
    messages_imported = 0
    messages_created = 0
    messages_updated = 0
    attachments_found = 0
    attachments_missing = 0
    errors = 0
    missing_filenames: list = []
    status_parts: list = []
    m1 = re.search(r"Processed (\d+) conversation\(s\)", stdout)
    if m1:
        conversations_processed = int(m1.group(1))
    m2 = re.search(r"Imported (\d+) message\(s\) \((\d+) created, (\d+) updated\)", stdout)
    if m2:
        messages_imported = int(m2.group(1))
        messages_created = int(m2.group(2))
        messages_updated = int(m2.group(3))
    m3 = re.search(r"Found (\d+) attachment\(s\), (\d+) missing", stdout)
    if m3:
        attachments_found = int(m3.group(1))
        attachments_missing = int(m3.group(2))
    m4 = re.search(r"Skipped invalid messages.*: (\d+)", stdout)
    if m4:
        errors = int(m4.group(1))
    in_missing = False
    for line in stdout.splitlines():
        line = line.rstrip()
        if line == "Missing attachment files:":
            in_missing = True
            continue
        if in_missing and line.startswith("  - "):
            missing_filenames.append(line[4:].strip())
    if conversations_processed > 0:
        status_parts.append(f"Processed {conversations_processed} conversation(s)")
    if messages_imported > 0:
        status_parts.append(f"Imported {messages_imported} message(s) ({messages_created} created, {messages_updated} updated)")
    if attachments_found > 0 or attachments_missing > 0:
        status_parts.append(f"Found {attachments_found}, {attachments_missing} missing")
    if errors > 0:
        status_parts.append(f"{errors} error(s)")
    status_message = "Import completed successfully. " + "; ".join(status_parts) if status_parts else "Import completed."
    return (conversations_processed, messages_imported, messages_created, messages_updated,
            attachments_found, attachments_missing, errors, missing_filenames, status_message)


def _run_subprocess_with_sse(
    args: list,
    cancelled_event,
    update_fn,
    get_state_fn,
    broadcast_fn,
    get_in_progress,
    set_in_progress,
    import_lock,
    import_type: str,
    parse_fn,
    update_completed_fn,
):
    """Generic subprocess runner for import-processor commands with SSE streaming."""
    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        full_args = [str(binary)] + args
        proc = subprocess.Popen(
            full_args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_parts: list = []

        def read_stderr():
            try:
                for line in iter(proc.stderr.readline, ""):
                    if cancelled_event.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        update_fn(status_line=line)
                        broadcast_fn("status", {"status_line": line})
            except Exception:
                pass

        def read_stdout():
            try:
                while True:
                    chunk = proc.stdout.read(8192)
                    if not chunk:
                        break
                    stdout_parts.append(chunk)
            except Exception:
                pass

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread.start()
        stdout_thread.start()
        stderr_thread.join()
        stdout_thread.join()
        stdout = "".join(stdout_parts)

        if cancelled_event.is_set():
            proc.terminate()
            proc.wait(timeout=10)
            update_fn(status="cancelled", status_line="Import cancelled.")
            broadcast_fn("cancelled", get_state_fn())
        else:
            proc.wait(timeout=60)
            if proc.returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
                update_fn(status="error", error_message=err_msg, status_line=err_msg)
                broadcast_fn("error", get_state_fn())
            else:
                parsed = parse_fn(stdout or "")
                update_completed_fn(parsed)
                broadcast_fn("completed", get_state_fn())
    except FileNotFoundError as e:
        update_fn(status="error", error_message=str(e), status_line=str(e))
        broadcast_fn("error", get_state_fn())
    except Exception as e:
        err_msg = str(e)
        update_fn(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_fn("error", get_state_fn())
    finally:
        state = get_state_fn()
        _record_import_control_last_run(import_type, state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        with import_lock:
            set_in_progress(False)


async def _sse_stream(get_state_fn, client_list, client_lock):
    """Generic SSE streaming generator."""
    client_queue = asyncio.Queue()
    with client_lock:
        client_list.append(client_queue)
    try:
        initial_state = get_state_fn()
        status = initial_state.get("status", "idle")
        if status in ("completed", "cancelled", "error"):
            event_data = {"type": status, "data": initial_state}
        else:
            event_data = {"type": "progress", "data": initial_state}
        yield f"data: {json.dumps(event_data)}\n\n"
        if status in ("completed", "cancelled", "error"):
            return

        heartbeat_interval = 30
        last_heartbeat = asyncio.get_event_loop().time()
        while True:
            try:
                timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                    yield message
                except asyncio.TimeoutError:
                    heartbeat_data = {"type": "heartbeat", "data": {"timestamp": datetime.now().isoformat()}}
                    yield f"data: {json.dumps(heartbeat_data)}\n\n"
                    last_heartbeat = asyncio.get_event_loop().time()

                progress_state = get_state_fn()
                if progress_state["status"] in ["completed", "cancelled", "error"]:
                    final_event = {"type": progress_state["status"], "data": progress_state}
                    yield f"data: {json.dumps(final_event)}\n\n"
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"
                break
    finally:
        with client_lock:
            if client_queue in client_list:
                client_list.remove(client_queue)


# ---------------------------------------------------------------------------
# iMessage background task
# ---------------------------------------------------------------------------

def import_imessage_background_subprocess(directory_path: str):
    """Background task: run import-processor imessage, stream stderr via SSE, broadcast completion."""
    global imessage_import_in_progress

    with imessage_import_lock:
        imessage_import_in_progress = True
        imessage_import_cancelled.clear()

    update_imessage_progress_state(
        status="in_progress",
        status_line="Starting import-processor...",
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
    )
    broadcast_imessage_progress_event_sync("status", {"status_line": "Starting import-processor..."})

    def update_completed(parsed):
        conv, msg_imp, msg_cre, msg_upd, att_found, att_miss, errs, missing_filenames, status_message = parsed
        update_imessage_progress_state(
            status="completed",
            status_line=status_message,
            conversations_processed=conv,
            total_conversations=conv,
            messages_imported=msg_imp,
            messages_created=msg_cre,
            messages_updated=msg_upd,
            attachments_found=att_found,
            attachments_missing=att_miss,
            missing_attachment_filenames=missing_filenames,
            errors=errs,
        )

    _run_subprocess_with_sse(
        args=["imessage", "--path", str(Path(translate_path_to_container(directory_path)).resolve())],
        cancelled_event=imessage_import_cancelled,
        update_fn=update_imessage_progress_state,
        get_state_fn=get_imessage_progress_state,
        broadcast_fn=broadcast_imessage_progress_event_sync,
        get_in_progress=lambda: imessage_import_in_progress,
        set_in_progress=lambda v: globals().__setitem__("imessage_import_in_progress", v),
        import_lock=imessage_import_lock,
        import_type="imessage",
        parse_fn=_parse_message_stdout,
        update_completed_fn=update_completed,
    )


# ---------------------------------------------------------------------------
# WhatsApp background task
# ---------------------------------------------------------------------------

def import_whatsapp_background_subprocess(directory_path: str):
    """Background task: run import-processor whatsapp, stream stderr via SSE, broadcast completion."""
    global whatsapp_import_in_progress

    with whatsapp_import_lock:
        whatsapp_import_in_progress = True
        whatsapp_import_cancelled.clear()

    update_whatsapp_progress_state(
        status="in_progress",
        status_line="Starting import-processor...",
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
    )
    broadcast_whatsapp_progress_event_sync("status", {"status_line": "Starting import-processor..."})

    def update_completed(parsed):
        conv, msg_imp, msg_cre, msg_upd, att_found, att_miss, errs, missing_filenames, status_message = parsed
        update_whatsapp_progress_state(
            status="completed",
            status_line=status_message,
            conversations_processed=conv,
            total_conversations=conv,
            messages_imported=msg_imp,
            messages_created=msg_cre,
            messages_updated=msg_upd,
            attachments_found=att_found,
            attachments_missing=att_miss,
            missing_attachment_filenames=missing_filenames,
            errors=errs,
        )

    _run_subprocess_with_sse(
        args=["whatsapp", "--path", str(Path(translate_path_to_container(directory_path)).resolve())],
        cancelled_event=whatsapp_import_cancelled,
        update_fn=update_whatsapp_progress_state,
        get_state_fn=get_whatsapp_progress_state,
        broadcast_fn=broadcast_whatsapp_progress_event_sync,
        get_in_progress=lambda: whatsapp_import_in_progress,
        set_in_progress=lambda v: globals().__setitem__("whatsapp_import_in_progress", v),
        import_lock=whatsapp_import_lock,
        import_type="whatsapp",
        parse_fn=_parse_message_stdout,
        update_completed_fn=update_completed,
    )


# ---------------------------------------------------------------------------
# Facebook Messenger background task
# ---------------------------------------------------------------------------

def import_facebook_background_subprocess(directory_path: str, user_name: Optional[str], export_root: Optional[str]):
    """Background task: run import-processor facebook, stream stderr via SSE, broadcast completion."""
    global facebook_import_in_progress

    with facebook_import_lock:
        facebook_import_in_progress = True
        facebook_import_cancelled.clear()

    update_facebook_progress_state(
        status="in_progress",
        status_line="Starting import-processor...",
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
    )
    broadcast_facebook_progress_event_sync("status", {"status_line": "Starting import-processor..."})

    # path_str = str(Path(translate_path_to_container(directory_path)).resolve())
    # print(f"[import_facebook_background_subprocess] path_str: {path_str}")
    # print(f"[import_facebook_background_subprocess] export_root: {export_root}")
    # print(f"[import_facebook_background_subprocess] translate_path_to_container(export_root): {translate_path_to_container(export_root)}")
    # print(f"[import_facebook_background_subprocess] str(Path(translate_path_to_container(export_root)).resolve()): {str(Path(translate_path_to_container(export_root)).resolve())}")
    args = ["facebook", "--path", directory_path]
    if export_root:
        args.extend(["--export-root", str(Path(translate_path_to_container(export_root)).resolve())])

    def update_completed(parsed):
        conv, msg_imp, msg_cre, msg_upd, att_found, att_miss, errs, missing_filenames, status_message = parsed
        update_facebook_progress_state(
            status="completed",
            status_line=status_message,
            conversations_processed=conv,
            total_conversations=conv,
            messages_imported=msg_imp,
            messages_created=msg_cre,
            messages_updated=msg_upd,
            attachments_found=att_found,
            attachments_missing=att_miss,
            missing_attachment_filenames=missing_filenames,
            errors=errs,
        )

    _run_subprocess_with_sse(
        args=args,
        cancelled_event=facebook_import_cancelled,
        update_fn=update_facebook_progress_state,
        get_state_fn=get_facebook_progress_state,
        broadcast_fn=broadcast_facebook_progress_event_sync,
        get_in_progress=lambda: facebook_import_in_progress,
        set_in_progress=lambda v: globals().__setitem__("facebook_import_in_progress", v),
        import_lock=facebook_import_lock,
        import_type="facebook",
        parse_fn=_parse_message_stdout,
        update_completed_fn=update_completed,
    )


# ---------------------------------------------------------------------------
# Instagram background task
# ---------------------------------------------------------------------------

def import_instagram_background_subprocess(directory_path: str, user_name: Optional[str], export_root: Optional[str]):
    """Background task: run import-processor instagram, stream stderr via SSE, broadcast completion."""
    global instagram_import_in_progress

    with instagram_import_lock:
        instagram_import_in_progress = True
        instagram_import_cancelled.clear()

    update_instagram_progress_state(
        status="in_progress",
        status_line="Starting import-processor...",
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
    )
    broadcast_instagram_progress_event_sync("status", {"status_line": "Starting import-processor..."})

    path_str = str(Path(translate_path_to_container(directory_path)).resolve())
    args = ["instagram", "--path", path_str]
    if export_root:
        args.extend(["--export-root", str(Path(translate_path_to_container(export_root)).resolve())])

    def update_completed(parsed):
        conv, msg_imp, msg_cre, msg_upd, att_found, att_miss, errs, missing_filenames, status_message = parsed
        update_instagram_progress_state(
            status="completed",
            status_line=status_message,
            conversations_processed=conv,
            total_conversations=conv,
            messages_imported=msg_imp,
            messages_created=msg_cre,
            messages_updated=msg_upd,
            attachments_found=att_found,
            attachments_missing=att_miss,
            missing_attachment_filenames=missing_filenames,
            errors=errs,
        )

    _run_subprocess_with_sse(
        args=args,
        cancelled_event=instagram_import_cancelled,
        update_fn=update_instagram_progress_state,
        get_state_fn=get_instagram_progress_state,
        broadcast_fn=broadcast_instagram_progress_event_sync,
        get_in_progress=lambda: instagram_import_in_progress,
        set_in_progress=lambda v: globals().__setitem__("instagram_import_in_progress", v),
        import_lock=instagram_import_lock,
        import_type="instagram",
        parse_fn=_parse_message_stdout,
        update_completed_fn=update_completed,
    )


# ---------------------------------------------------------------------------
# Conversation summary background task
# ---------------------------------------------------------------------------

def summarize_conversation_background(chat_session: str, messages_data: Dict[str, Any]):
    """Background task to summarize conversation using Gemini LLM."""
    global conversation_summary_in_progress

    try:
        update_conversation_summary_progress_state(
            status="processing",
            stage="calling_llm"
        )
        broadcast_conversation_summary_event_sync("progress", {
            "status": "processing",
            "stage": "calling_llm",
            "chat_session": chat_session
        })

        try:
            gemini_service = GeminiService()
        except ValueError as e:
            error_msg = str(e)
            update_conversation_summary_progress_state(status="error", error=error_msg)
            broadcast_conversation_summary_event_sync("error", {
                "status": "error",
                "error": error_msg,
                "chat_session": chat_session
            })
            return

        summary = gemini_service.summarize_conversation(messages_data)

        update_conversation_summary_progress_state(status="completed", stage="completed", summary=summary)
        broadcast_conversation_summary_event_sync("completed", {
            "status": "completed",
            "summary": summary,
            "chat_session": chat_session
        })

    except ValueError as e:
        error_msg = str(e)
        update_conversation_summary_progress_state(status="error", error=error_msg)
        broadcast_conversation_summary_event_sync("error", {"status": "error", "error": error_msg, "chat_session": chat_session})
    except Exception as e:
        import traceback
        error_msg = str(e)
        if not error_msg.startswith("Error generating summary:"):
            error_msg = f"Error generating summary: {error_msg}"
        traceback.print_exc()
        update_conversation_summary_progress_state(status="error", error=error_msg)
        broadcast_conversation_summary_event_sync("error", {"status": "error", "error": error_msg, "chat_session": chat_session})
    finally:
        with conversation_summary_lock:
            conversation_summary_in_progress = False


# ---------------------------------------------------------------------------
# iMessage routes
# ---------------------------------------------------------------------------

@router.post("/imessages/import", response_model=ImportIMessagesResponse)
async def import_imessages(
    request: ImportIMessagesRequest,
    background_tasks: BackgroundTasks
):
    """Import iMessages from a directory structure asynchronously."""
    global imessage_import_in_progress

    with imessage_import_lock:
        if imessage_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="iMessage import is already in progress. Please cancel it first or wait for it to complete."
            )

    directory_path = Path(translate_path_to_container(request.directory_path)).resolve()
    print(f"Facebook Messenger Import directory_path: {directory_path} (Dockerized: {directory_path.exists()})")
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )

    background_tasks.add_task(import_imessage_background_subprocess, directory_path)

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


@router.get("/imessages/import/stream")
async def stream_imessage_import_progress():
    """Stream iMessage import progress updates via Server-Sent Events (SSE)."""
    return StreamingResponse(
        _sse_stream(get_imessage_progress_state, imessage_sse_clients, imessage_sse_clients_lock),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/imessages/import/cancel")
async def cancel_imessage_import():
    """Cancel iMessage import if it is in progress."""
    global imessage_import_in_progress

    with imessage_import_lock:
        if not imessage_import_in_progress:
            return {"message": "No iMessage import is currently in progress", "cancelled": False}
        imessage_import_cancelled.set()
        return {"message": "iMessage import cancellation requested.", "cancelled": True}


@router.get("/imessages/import/status")
async def get_imessage_import_status():
    """Get the current status of iMessage import."""
    global imessage_import_in_progress

    progress_state = get_imessage_progress_state()
    with imessage_import_lock:
        return {
            "in_progress": imessage_import_in_progress,
            "cancelled": imessage_import_cancelled.is_set(),
            **progress_state
        }


@router.get("/imessages/chat-sessions")
async def get_chat_sessions():
    """Get list of unique chat session names from messages table."""
    message_service = MessageService(db=db)
    try:
        result = message_service.get_chat_sessions()

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
            "contacts": [session_to_dict(s) for s in result.contacts],
            "groups": [session_to_dict(s) for s in result.groups],
            "other": [session_to_dict(s) for s in result.other]
        }
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in get_chat_sessions: {e}")
        traceback.print_exc()
        return {"contacts_and_groups": [], "other": []}


@router.get("/imessages/conversation/{chat_session}")
async def get_conversation_messages(chat_session: str):
    """Get all messages for a specific chat session."""
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)

    session = db.get_session()
    try:
        messages = session.query(IMessage).options(
            joinedload(IMessage.media_attachments).joinedload(MessageAttachment.media_item)
        ).filter(
            IMessage.chat_session == decoded_session
        ).order_by(
            IMessage.message_date.asc()
        ).all()

        messages_data = []
        for msg in messages:
            attachment_filename = None
            attachment_type = None
            has_attachment = False

            if msg.media_attachments:
                media_item = msg.media_attachments[0].media_item
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


@router.get("/imessages/{message_id}/metadata")
async def get_message_metadata(message_id: int):
    """Get message metadata by ID."""
    session = db.get_session()
    try:
        message = session.query(IMessage).filter(IMessage.id == message_id).first()

        if not message:
            raise HTTPException(status_code=404, detail=f"Message with ID {message_id} not found")

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
        raise HTTPException(status_code=500, detail=f"Error retrieving message metadata: {str(e)}")
    finally:
        session.close()


@router.post("/imessages/conversation/{chat_session}/summarize")
async def summarize_conversation(chat_session: str):
    """Summarize a conversation using Gemini LLM synchronously."""
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)

    try:
        message_service = MessageService(db=db)
        messages_data = message_service.get_formatted_conversation_messages(decoded_session)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        gemini_service = GeminiService()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        summary = gemini_service.summarize_conversation(messages_data)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

    return {"status": "completed", "summary": summary, "chat_session": decoded_session}


@router.get("/imessages/conversation/{chat_session}/summarize/stream")
async def stream_conversation_summary_progress(chat_session: str):
    """Stream conversation summary progress updates via Server-Sent Events (SSE)."""
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)

    async def event_generator():
        client_queue = asyncio.Queue(maxsize=100)
        with conversation_summary_sse_clients_lock:
            conversation_summary_sse_clients.append(client_queue)
        try:
            initial_state = get_conversation_summary_progress_state()
            if initial_state.get("chat_session") == decoded_session:
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

                    progress_state = get_conversation_summary_progress_state()
                    if progress_state.get("chat_session") == decoded_session:
                        if progress_state["status"] in ["completed", "error"]:
                            yield f"data: {json.dumps({'type': progress_state['status'], 'data': progress_state})}\n\n"
                            break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'data': {'error': str(e)}})}\n\n"
                    break
        finally:
            with conversation_summary_sse_clients_lock:
                if client_queue in conversation_summary_sse_clients:
                    conversation_summary_sse_clients.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.delete("/imessages/conversation/{chat_session}")
async def delete_conversation_messages(chat_session: str):
    """Delete all messages for a specific chat session."""
    from urllib.parse import unquote
    decoded_session = unquote(chat_session)

    session = db.get_session()
    try:
        message_count = session.query(IMessage).filter(IMessage.chat_session == decoded_session).count()

        if message_count == 0:
            raise HTTPException(status_code=404, detail=f"Chat session '{decoded_session}' not found")

        deleted_count = session.query(IMessage).filter(IMessage.chat_session == decoded_session).delete()
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
        raise HTTPException(status_code=500, detail=f"Error deleting chat session: {str(e)}")
    finally:
        session.close()


@router.get("/imessages/{message_id}/attachment")
async def get_imessage_attachment(message_id: int, preview: bool = False):
    """Get attachment content for a message."""
    session = db.get_session()
    try:
        message = session.query(IMessage).filter(IMessage.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail=f"Message with ID {message_id} not found")

        message_attachment = session.query(MessageAttachment).filter(
            MessageAttachment.message_id == message_id
        ).first()

        if not message_attachment:
            raise HTTPException(status_code=404, detail=f"Message with ID {message_id} has no attachment")

        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == message_attachment.media_item_id
        ).first()

        if not media_item:
            raise HTTPException(status_code=404, detail="Media item for attachment not found")

        media_blob = session.query(MediaBlob).filter(MediaBlob.id == media_item.media_blob_id).first()
        if not media_blob:
            raise HTTPException(status_code=404, detail="Media blob for attachment not found")

        if preview:
            content = media_blob.thumbnail_data
            if content is None:
                raise HTTPException(status_code=404, detail="Message attachment has no thumbnail available")
            content_type = "image/jpeg"
            filename = media_item.title or "attachment"
            base_name, ext = os.path.splitext(filename)
            safe_filename = f"{base_name}_thumb.jpg".replace('"', '\\"')
        else:
            content = media_blob.image_data
            if content is None:
                raise HTTPException(status_code=404, detail="Message attachment has no content")
            content_type = media_item.media_type or "application/octet-stream"
            filename = media_item.title or "attachment"
            safe_filename = filename.replace('"', '\\"')

        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{safe_filename}"'}
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# WhatsApp routes
# ---------------------------------------------------------------------------

@router.post("/whatsapp/import", response_model=ImportWhatsAppResponse)
async def import_whatsapp(request: ImportWhatsAppRequest, background_tasks: BackgroundTasks):
    """Import WhatsApp messages from a directory structure asynchronously."""
    global whatsapp_import_in_progress

    with whatsapp_import_lock:
        if whatsapp_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="WhatsApp import is already in progress. Please cancel it first or wait for it to complete."
            )

    #directory = Path(request.directory_path)
    directory_path = Path(translate_path_to_container(request.directory_path))
    print(f"WhatsApp Import directory_path: {directory_path} (Dockerized: {directory_path.exists()})")
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {directory_path}"
        )

    background_tasks.add_task(import_whatsapp_background_subprocess, directory_path)

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


@router.get("/whatsapp/import/stream")
async def stream_whatsapp_import_progress():
    """Stream WhatsApp import progress updates via SSE."""
    return StreamingResponse(
        _sse_stream(get_whatsapp_progress_state, whatsapp_sse_clients, whatsapp_sse_clients_lock),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/whatsapp/import/cancel")
async def cancel_whatsapp_import():
    """Cancel WhatsApp import if it is in progress."""
    global whatsapp_import_in_progress

    with whatsapp_import_lock:
        if not whatsapp_import_in_progress:
            return {"message": "No WhatsApp import is currently in progress", "cancelled": False}
        whatsapp_import_cancelled.set()
        return {"message": "WhatsApp import cancellation requested.", "cancelled": True}


@router.get("/whatsapp/import/status")
async def get_whatsapp_import_status():
    """Get the current status of WhatsApp import."""
    global whatsapp_import_in_progress

    progress_state = get_whatsapp_progress_state()
    with whatsapp_import_lock:
        return {
            "in_progress": whatsapp_import_in_progress,
            "cancelled": whatsapp_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Facebook Messenger routes
# ---------------------------------------------------------------------------

@router.post("/facebook/import", response_model=ImportFacebookResponse)
async def import_facebook(request: ImportFacebookRequest, background_tasks: BackgroundTasks):
    """Import Facebook Messenger messages from a directory structure asynchronously."""
    global facebook_import_in_progress

    with facebook_import_lock:
        if facebook_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Facebook Messenger import is already in progress. Please cancel it first or wait for it to complete."
            )

    directory_path = Path(translate_path_to_container(request.directory_path)).resolve()
    print(f"Facebook Messenger Import directory_path: {directory_path} (Dockerized: {directory_path.exists()})")
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )

    background_tasks.add_task(import_facebook_background_subprocess, directory_path, request.user_name, request.export_root)

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


@router.get("/facebook/import/stream")
async def stream_facebook_import_progress():
    """Stream Facebook Messenger import progress updates via SSE."""
    return StreamingResponse(
        _sse_stream(get_facebook_progress_state, facebook_sse_clients, facebook_sse_clients_lock),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/facebook/import/cancel")
async def cancel_facebook_import():
    """Cancel Facebook Messenger import if it is in progress."""
    global facebook_import_in_progress

    with facebook_import_lock:
        if not facebook_import_in_progress:
            return {"message": "No Facebook Messenger import is currently in progress", "cancelled": False}
        facebook_import_cancelled.set()
        return {"message": "Facebook Messenger import cancellation requested.", "cancelled": True}


@router.get("/facebook/import/status")
async def get_facebook_import_status():
    """Get the current status of Facebook Messenger import."""
    global facebook_import_in_progress

    progress_state = get_facebook_progress_state()
    with facebook_import_lock:
        return {
            "in_progress": facebook_import_in_progress,
            "cancelled": facebook_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Instagram routes
# ---------------------------------------------------------------------------

@router.post("/instagram/import", response_model=ImportInstagramResponse)
async def import_instagram(request: ImportInstagramRequest, background_tasks: BackgroundTasks):
    """Import Instagram messages from a directory structure asynchronously."""
    global instagram_import_in_progress

    with instagram_import_lock:
        if instagram_import_in_progress:
            raise HTTPException(
                status_code=409,
                detail="Instagram import is already in progress. Please cancel it first or wait for it to complete."
            )

    # directory = Path(request.directory_path)
    directory = Path(translate_path_to_container(request.directory_path))
    print(f"Instagram Import directory_path: {directory} (Dockerized: {directory.exists()})")
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )

    background_tasks.add_task(import_instagram_background_subprocess, directory, request.user_name, request.export_root)

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


@router.get("/instagram/import/stream")
async def stream_instagram_import_progress():
    """Stream Instagram import progress updates via SSE."""
    return StreamingResponse(
        _sse_stream(get_instagram_progress_state, instagram_sse_clients, instagram_sse_clients_lock),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@router.post("/instagram/import/cancel")
async def cancel_instagram_import():
    """Cancel Instagram import if it is in progress."""
    global instagram_import_in_progress

    with instagram_import_lock:
        if not instagram_import_in_progress:
            return {"message": "No Instagram import is currently in progress", "cancelled": False}
        instagram_import_cancelled.set()
        return {"message": "Instagram import cancellation requested.", "cancelled": True}


@router.get("/instagram/import/status")
async def get_instagram_import_status():
    """Get the current status of Instagram import."""
    global instagram_import_in_progress

    progress_state = get_instagram_progress_state()
    with instagram_import_lock:
        return {
            "in_progress": instagram_import_in_progress,
            "cancelled": instagram_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Writing style route
# ---------------------------------------------------------------------------

@router.post("/writing-style/summarize")
async def summarize_writing_style_endpoint():

    session = db.get_session()
    try:
        total_available = session.query(IMessage).filter(IMessage.sender_name == "Dave Burton").count()

        if total_available == 0:
            raise HTTPException(status_code=404, detail="No messages found for sender 'Dave Burton'")

        selected_messages = session.query(IMessage).options(
            joinedload(IMessage.media_attachments)
        ).filter(
            IMessage.sender_name == "Dave Burton"
        ).order_by(func.random()).limit(5000).all()

        sample_size = len(selected_messages)

        messages_data_list = []
        for msg in selected_messages:
            has_attachment = bool(msg.media_attachments)
            messages_data_list.append({
                "message_date": msg.message_date.isoformat() if msg.message_date else None,
                "sender_name": msg.sender_name or "Unknown",
                "type": msg.type or "",
                "text": msg.text or "",
                "has_attachment": has_attachment
            })

        messages_data = {
            "chat_session": "Dave Burton (writing style sample)",
            "message_count": len(messages_data_list),
            "messages": messages_data_list
        }
    finally:
        session.close()

    try:
        gemini_service = GeminiService()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        summary = gemini_service.summarize_writing_style(messages_data)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating writing style summary: {str(e)}")

    config_service = SubjectConfigurationService(db=db)
    config_service.update_writing_style_ai(summary)

    return {
        "status": "completed",
        "summary": summary,
        "message_count": sample_size,
        "total_available": total_available
    }


# ---------------------------------------------------------------------------
# Psychological profile route
# ---------------------------------------------------------------------------

@router.post("/psychological-profile/summarize")
async def summarize_psychological_profile_endpoint():
    """Generate a psychological profile of Dave Burton using a random sample of 5000 messages."""
    session = db.get_session()
    try:
        total_available = session.query(IMessage).filter(IMessage.sender_name == "Dave Burton").count()

        if total_available == 0:
            raise HTTPException(status_code=404, detail="No messages found for sender 'Dave Burton'")

        selected_messages = session.query(IMessage).options(
            joinedload(IMessage.media_attachments)
        ).filter(
            IMessage.sender_name == "Dave Burton"
        ).order_by(func.random()).limit(5000).all()

        sample_size = len(selected_messages)

        messages_data_list = []
        for msg in selected_messages:
            has_attachment = bool(msg.media_attachments)
            messages_data_list.append({
                "message_date": msg.message_date.isoformat() if msg.message_date else None,
                "sender_name": msg.sender_name or "Unknown",
                "type": msg.type or "",
                "text": msg.text or "",
                "has_attachment": has_attachment
            })

        messages_data = {
            "chat_session": "Dave Burton (psychological profile sample)",
            "message_count": len(messages_data_list),
            "messages": messages_data_list
        }
    finally:
        session.close()

    try:
        gemini_service = GeminiService()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        profile = gemini_service.summarize_psychological_profile(messages_data)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating psychological profile: {str(e)}")

    config_service = SubjectConfigurationService(db=db)
    config_service.update_psychological_profile_ai(profile)

    return {
        "status": "completed",
        "profile": profile,
        "message_count": sample_size,
        "total_available": total_available
    }
