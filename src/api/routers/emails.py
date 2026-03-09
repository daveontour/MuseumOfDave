"""Email routes."""
import threading
import json
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, BackgroundTasks, Query, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import or_, func, and_, extract

from ...database import Database, Email
from ...database.models import MediaMetadata, MediaBlob
from ...services import EmailService
from ...services.gemini_service import GeminiService
from ...services.exceptions import ServiceException, ValidationError, NotFoundError, ConflictError
from ...loader import EmailDatabaseLoader
from ..deps import db
from ..state import (
    processing_lock,
    processing_cancelled,
    processing_in_progress,
    update_progress_state,
    get_progress_state,
    broadcast_progress_event_sync,
    sse_clients,
    sse_clients_lock,
    _record_import_control_last_run,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Loader (global, initialized per-request)
# ---------------------------------------------------------------------------

loader = None


def get_loader() -> EmailDatabaseLoader:
    """Get or create email loader instance."""
    global loader
    if loader is None:
        loader = EmailDatabaseLoader()
        loader.init_client()
    return loader


# ---------------------------------------------------------------------------
# Background task helpers
# ---------------------------------------------------------------------------

def process_single_label_background(label: str, new_only: bool, result_dict: dict, lock: threading.Lock):
    """Background task to process emails for a single label."""
    try:
        print(f"[Thread] Starting processing for label: {label}")
        from ...loader import EmailDatabaseLoader
        loader_instance = EmailDatabaseLoader()
        loader_instance.init_client()

        count = loader_instance.load_emails(label, new_only=new_only)
        print(f"[Thread] Completed processing for label: {label}, processed {count} emails")

        with lock:
            result_dict["count"] += count
            result_dict["success"] = True
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
        result_dict["count"] = 0
        result_dict["success"] = False
        result_dict["error"] = ""

        for idx, label in enumerate(filtered_labels, start=1):
            if processing_cancelled.is_set():
                print(f"[Background Task] Processing cancelled by user")
                result_dict["error"] = "Processing was cancelled by user"
                result_dict["success"] = False
                update_progress_state(status="cancelled", error_message="Processing was cancelled by user")
                broadcast_progress_event_sync("cancelled", get_progress_state())
                break

            try:
                print(f"[Background Task] Starting processing for label: {label}")

                update_progress_state(
                    current_label=label,
                    current_label_index=idx
                )
                broadcast_progress_event_sync("progress", get_progress_state())

                loader_instance = get_loader()

                if processing_cancelled.is_set():
                    print(f"[Background Task] Processing cancelled before loading emails for {label}")
                    result_dict["error"] = "Processing was cancelled by user"
                    result_dict["success"] = False
                    update_progress_state(status="cancelled", error_message="Processing was cancelled by user")
                    broadcast_progress_event_sync("cancelled", get_progress_state())
                    break

                count = loader_instance.load_emails(label, new_only=new_only)
                result_dict["count"] += count
                result_dict["success"] = True

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

                current_state = get_progress_state()
                update_progress_state(
                    status="error",
                    error_message=error_msg
                )
                broadcast_progress_event_sync("error", get_progress_state())

                print(f"[Background Task] Error processing {label}: {str(e)}")

        current_state = get_progress_state()
        if current_state["status"] == "in_progress":
            update_progress_state(status="completed")
            broadcast_progress_event_sync("completed", get_progress_state())

    finally:
        state = get_progress_state()
        result = "cancelled" if processing_cancelled.is_set() else (state.get("status") or "error")
        msg = state.get("error_message") if result == "error" else None
        _record_import_control_last_run("email_processing", result, msg)
        with processing_lock:
            processing_in_progress = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/emails/process", response_model=ProcessLabelResponse)
async def process_emails(
    request: ProcessLabelRequest,
    background_tasks: BackgroundTasks
):
    """Process emails from Gmail labels asynchronously."""
    global processing_in_progress

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
        email_service.can_start_processing()

        loader_instance = get_loader() if request.all_folders else None
        labels_to_process = email_service.determine_labels_to_process(
            labels=request.labels,
            all_folders=request.all_folders,
            loader=loader_instance
        )

        result_dict = {"count": 0, "success": False}

        background_tasks.add_task(
            process_emails_background,
            labels_to_process,
            request.new_only,
            result_dict
        )

        message = f"Processing emails from {len(labels_to_process)} label(s) started"
        if request.all_folders:
            message = f"Processing emails from all folders ({len(labels_to_process)} labels) started"

        return ProcessLabelResponse(
            message=message,
            labels=labels_to_process,
            count=0,
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


@router.post("/emails/process/cancel")
async def cancel_email_processing():
    """Cancel email processing if it is in progress."""
    global processing_in_progress

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


@router.get("/emails/process/status")
async def get_processing_status():
    """Get the current status of email processing."""
    global processing_in_progress

    progress_state = get_progress_state()

    with processing_lock:
        return {
            "in_progress": processing_in_progress,
            "cancelled": processing_cancelled.is_set(),
            **progress_state
        }


@router.get("/emails/process/stream")
async def stream_processing_progress():
    """Stream processing progress updates via Server-Sent Events (SSE)."""
    async def event_generator():
        client_queue = asyncio.Queue(maxsize=100)

        with sse_clients_lock:
            sse_clients.append(client_queue)

        try:
            initial_state = get_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            heartbeat_interval = 30
            last_heartbeat = asyncio.get_event_loop().time()

            while True:
                try:
                    timeout = max(1, heartbeat_interval - (asyncio.get_event_loop().time() - last_heartbeat))
                    try:
                        message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                        yield message
                    except asyncio.TimeoutError:
                        heartbeat_data = {
                            "type": "heartbeat",
                            "data": {"timestamp": datetime.now().isoformat()}
                        }
                        yield f"data: {json.dumps(heartbeat_data)}\n\n"
                        last_heartbeat = asyncio.get_event_loop().time()

                    progress_state = get_progress_state()
                    if progress_state["status"] in ["completed", "cancelled", "error"]:
                        final_event = {
                            "type": progress_state["status"],
                            "data": progress_state
                        }
                        yield f"data: {json.dumps(final_event)}\n\n"
                        break

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    error_event = {
                        "type": "error",
                        "data": {"error": str(e)}
                    }
                    yield f"data: {json.dumps(error_event)}\n\n"
                    break
        finally:
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


@router.post("/emails/thread/{participant}/summarize")
async def summarize_email_thread(participant: str):
    """Summarize email interaction with a person using Gemini LLM synchronously."""
    from urllib.parse import unquote

    decoded_session = unquote(participant)

    try:
        email_service = EmailService()
        messages_data = email_service.get_conversation_messages(decoded_session, db)
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


@router.get("/emails/{email_id}/html")
async def get_email_html(email_id: int):
    """Get email HTML content by ID."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()

    if not email:
        raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

    if not email.raw_message:
        if email.plain_text:
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
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
            return Response(content=html_content, media_type="text/html")
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Email with ID {email_id} has no HTML or text content"
            )

    return Response(content=email.raw_message, media_type="text/html")


@router.get("/emails/{email_id}/text")
async def get_email_text(email_id: int):
    """Get email plain text content by ID."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()

    if not email:
        raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

    if not email.plain_text:
        raise HTTPException(status_code=404, detail=f"Email with ID {email_id} has no text content")

    return Response(content=email.plain_text, media_type="text/plain")


@router.get("/emails/{email_id}/snippet")
async def get_email_snippet(email_id: int):
    """Get email snippet by ID."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()
    finally:
        session.close()

    if not email:
        raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

    if not email.snippet:
        raise HTTPException(status_code=404, detail=f"Email with ID {email_id} has no snippet")

    return Response(content=email.snippet, media_type="text/plain")


@router.get("/emails/{email_id}/metadata", response_model=EmailMetadataResponse)
async def get_email_metadata(email_id: int):
    """Get email metadata by ID."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()

        if not email:
            raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

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
    finally:
        session.close()


@router.put("/emails/{email_id}")
async def update_email(email_id: int, updates: Dict[str, Any]):
    """Update email fields."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).filter(Email.user_deleted == False).first()

        if not email:
            raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

        if 'is_personal' in updates:
            email.is_personal = bool(updates['is_personal'])
        if 'is_business' in updates:
            email.is_business = bool(updates['is_business'])
        if 'is_important' in updates:
            email.is_important = bool(updates['is_important'])
        if 'use_by_ai' in updates:
            email.use_by_ai = bool(updates['use_by_ai'])

        session.commit()

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
        raise HTTPException(status_code=500, detail=f"Error updating email: {str(e)}")
    finally:
        session.close()


@router.delete("/emails/bulk-delete")
async def bulk_delete_emails(delete_data: Dict[str, Any] = Body(...)):
    """Bulk delete multiple emails by their IDs."""
    session = db.get_session()
    try:
        email_ids = delete_data.get("email_ids", [])

        if not email_ids:
            raise HTTPException(status_code=400, detail="No email IDs provided")

        deleted_count = 0
        errors = []

        for email_id in email_ids:
            try:
                email = session.query(Email).filter(Email.id == email_id).first()

                if not email:
                    errors.append(f"Email {email_id} not found")
                    continue

                media_items = session.query(MediaMetadata).filter(
                    MediaMetadata.source == "email_attachment",
                    MediaMetadata.source_reference == str(email_id)
                ).all()

                for media_item in media_items:
                    media_blob = session.query(MediaBlob).filter(
                        MediaBlob.id == media_item.media_blob_id
                    ).first()

                    session.delete(media_item)

                    if media_blob:
                        other_items_count = session.query(MediaMetadata).filter(
                            MediaMetadata.media_blob_id == media_blob.id
                        ).count()

                        if other_items_count == 0:
                            session.delete(media_blob)

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
        raise HTTPException(status_code=500, detail=f"Error bulk deleting emails: {str(e)}")
    finally:
        session.close()


@router.delete("/emails/{email_id}")
async def delete_email(email_id: int):
    """Delete an email by ID (soft delete)."""
    session = db.get_session()
    try:
        email = session.query(Email).filter(Email.id == email_id).first()

        if not email:
            raise HTTPException(status_code=404, detail=f"Email with ID {email_id} not found")

        media_items = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment",
            MediaMetadata.source_reference == str(email_id)
        ).all()

        for media_item in media_items:
            media_blob = session.query(MediaBlob).filter(
                MediaBlob.id == media_item.media_blob_id
            ).first()

            session.delete(media_item)

            if media_blob:
                other_items_count = session.query(MediaMetadata).filter(
                    MediaMetadata.media_blob_id == media_blob.id
                ).count()

                if other_items_count == 0:
                    session.delete(media_blob)

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
        raise HTTPException(status_code=500, detail=f"Error deleting email: {str(e)}")
    finally:
        session.close()


@router.get("/emails/folders", response_model=List[LabelResponse])
async def get_folders():
    """Get list of available folders/labels from the email server."""
    try:
        loader_instance = get_loader()
        labels = loader_instance.client.get_labels()

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


@router.get("/emails/label", response_model=List[EmailMetadataResponse])
async def get_emails_by_label(labels: List[str] = Query(..., description="List of labels to filter by")):
    """Get metadata for all emails with given labels."""
    if not labels:
        raise HTTPException(
            status_code=400,
            detail="At least one label must be provided as query parameter (e.g., ?labels=INBOX&labels=IMPORTANT)"
        )

    session = db.get_session()
    try:
        label_filters = []
        for label in labels:
            label_filters.extend([
                Email.folder == label,
                Email.folder.like(f"{label},%"),
                Email.folder.like(f"%,{label},%"),
                Email.folder.like(f"%,{label}")
            ])

        emails = session.query(Email).filter(
            and_(
                or_(*label_filters),
                Email.user_deleted == False
            )
        ).all()

        result = []
        for email in emails:
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


@router.get("/emails/search", response_model=List[EmailMetadataResponse])
async def search_emails(
    from_address: Optional[str] = Query(None, description="Filter by sender (partial match)"),
    to_address: Optional[str] = Query(None, description="Filter by recipient (partial match)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    subject: Optional[str] = Query(None, description="Filter by subject (partial match)"),
    to_from: Optional[str] = Query(None, description="Filter by email being either to or from this address (partial match)"),
    has_attachments: Optional[bool] = Query(None, description="Filter by whether email has attachments")
):
    """Search emails by metadata criteria."""
    session = db.get_session()
    try:
        query = session.query(Email)
        filters = []

        if from_address:
            filters.append(Email.from_address.ilike(f"%{from_address}%"))

        if to_address:
            filters.append(Email.to_addresses.ilike(f"%{to_address}%"))

        if month is not None:
            filters.append(extract('month', Email.date) == month)

        if year is not None:
            filters.append(extract('year', Email.date) == year)

        if subject:
            filters.append(Email.subject.ilike(f"%{subject}%"))

        if to_from:
            to_from_addresses = [a.strip() for a in to_from.split(',') if a.strip()]
            address_filters = [
                or_(
                    Email.to_addresses.ilike(f"%{address}%"),
                    Email.from_address.ilike(f"%{address}%")
                )
                for address in to_from_addresses
            ]
            if address_filters:
                filters.append(or_(*address_filters))

        if has_attachments is not None:
            filters.append(Email.has_attachments == has_attachments)

        filters.append(Email.user_deleted == False)

        if filters:
            query = query.filter(and_(*filters))

        query = query.order_by(Email.date.desc())

        emails = query.all()

        result = []
        for email in emails:
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
