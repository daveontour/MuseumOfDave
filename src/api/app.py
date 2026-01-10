"""FastAPI HTTP Server."""

import os
import threading
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload

from ..database import Database, Attachment, Email
from ..database.storage import EmailStorage
from ..loader import EmailDatabaseLoader
from ..config import get_config

# Create FastAPI app instance
app = FastAPI(
    title="Museum of Dave API",
    description="API server for email processing and retrieval",
    version="1.0.0"
)

# Initialize database connection
db = Database(get_config())

# Initialize loader (will be initialized per request)
loader = None

# Processing state management
processing_lock = threading.Lock()
processing_cancelled = threading.Event()
processing_in_progress = False


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
    
    # Mark processing as started
    with processing_lock:
        processing_in_progress = True
        processing_cancelled.clear()
    
    try:
        # Initialize result dict
        result_dict["count"] = 0
        result_dict["success"] = False
        result_dict["error"] = ""
        
        # Process labels sequentially, one at a time
        for label in labels:
            # Check for cancellation before processing each label
            if processing_cancelled.is_set():
                print(f"[Background Task] Processing cancelled by user")
                result_dict["error"] = "Processing was cancelled by user"
                result_dict["success"] = False
                break
            
            # Skip TRASH and SPAM folders
            if label.upper() in ["TRASH", "SPAM"]:
                print(f"Skipping folder: {label}")
                continue
            
            try:
                print(f"[Background Task] Starting processing for label: {label}")
                loader_instance = get_loader()
                
                # Check for cancellation before loading emails
                if processing_cancelled.is_set():
                    print(f"[Background Task] Processing cancelled before loading emails for {label}")
                    result_dict["error"] = "Processing was cancelled by user"
                    result_dict["success"] = False
                    break
                
                count = loader_instance.load_emails(label, new_only=new_only)
                result_dict["count"] += count
                result_dict["success"] = True  # Set to True if at least one succeeds
                print(f"[Background Task] Completed processing for label: {label}, processed {count} emails")
            except Exception as e:
                error_msg = result_dict.get("error", "")
                if error_msg:
                    error_msg += " "
                result_dict["error"] = error_msg + f"Error processing {label}: {str(e)}; "
                result_dict["success"] = False
                print(f"[Background Task] Error processing {label}: {str(e)}")
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
            "GET /emails/{email_id}/html": "Get email HTML content by ID",
            "GET /emails/{email_id}/text": "Get email plain text content by ID",
            "GET /emails/{email_id}/snippet": "Get email snippet by ID",
            "GET /emails/{email_id}/metadata": "Get email metadata by ID",
            "GET /emails/label": "Get metadata for all emails with given labels (query param: labels)",
            "GET /emails/folders": "Get list of available folders/labels from email server",
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
    
    with processing_lock:
        return {
            "in_progress": processing_in_progress,
            "cancelled": processing_cancelled.is_set()
        }


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


@app.get("/attachments-viewer", response_class=HTMLResponse)
async def attachments_viewer():
    """Serve the attachment viewer web page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Attachment Viewer - Museum of Dave</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 20px;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            font-size: 1.1em;
            color: #666;
        }
        
        .no-attachments {
            text-align: center;
            padding: 40px;
            font-size: 1.1em;
            color: #666;
        }
        
        .button-group {
            display: flex;
            gap: 15px;
            justify-content: center;
            margin-bottom: 20px;
        }
        
        .attachment-section {
            margin-bottom: 20px;
        }
        
        .attachment-preview {
            text-align: center;
            background: #f8f9fa;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 15px;
            min-height: 300px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .attachment-preview img {
            max-width: 100%;
            max-height: 500px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .metadata-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }
        
        .attachment-info {
            background: #f8f9fa;
            border-radius: 6px;
            padding: 12px;
        }
        
        .attachment-info h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.2em;
        }
        
        .info-row {
            display: grid;
            grid-template-columns: 120px 1fr;
            gap: 8px;
            padding: 6px 0;
            border-bottom: 1px solid #e0e0e0;
            font-size: 0.9em;
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            font-weight: 600;
            color: #555;
        }
        
        .info-value {
            color: #333;
        }
        
        .email-metadata {
            background: #e8f4f8;
            border-radius: 6px;
            padding: 12px;
        }
        
        .email-metadata h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 1.2em;
        }
        
        @media (max-width: 768px) {
            .metadata-container {
                grid-template-columns: 1fr;
            }
        }
        
        button {
            padding: 12px 30px;
            font-size: 1em;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }
        
        .btn-keep {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-keep:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-delete {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
        }
        
        .btn-delete:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(245, 87, 108, 0.4);
        }
        
        .btn-nav {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
        }
        
        .btn-nav:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(79, 172, 254, 0.4);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📎 Attachment Viewer</h1>
            <p>Review and manage your email attachments</p>
        </div>
        <div class="content">
            <div id="loading" class="loading">Loading attachment...</div>
            <div id="no-attachments" class="no-attachments" style="display: none;">
                No attachments found in the database.
            </div>
            <div id="attachment-view" style="display: none;">
                <div class="button-group">
                    <button class="btn-nav" id="prev-btn" onclick="previousAttachment()">Previous</button>
                    <button class="btn-keep" id="keep-btn" onclick="keepAttachment()">Keep</button>
                    <button class="btn-delete" id="delete-btn" onclick="deleteAttachment()">Delete</button>
                    <button class="btn-nav" id="next-btn" onclick="nextAttachment()">Next</button>
                </div>
                <div style="text-align: center; margin-bottom: 15px; display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; align-items: center;">
                    <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9em; color: #555;">
                        <input type="checkbox" id="confirm-delete-checkbox" checked style="cursor: pointer;">
                        <span>Confirm before deleting</span>
                    </label>
                    <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9em; color: #555;">
                        <input type="checkbox" id="show-pdf-checkbox" checked style="cursor: pointer;">
                        <span>Show PDF/MS Word/Octet Stream</span>
                    </label>
                    <label style="display: inline-flex; align-items: center; gap: 8px; font-size: 0.9em; color: #555;">
                        <span>Order:</span>
                        <select id="order-select" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 0.9em; cursor: pointer;">
                            <option value="random">Random</option>
                            <option value="id">ID Order</option>
                            <option value="size-asc">Size: Smallest to Biggest</option>
                            <option value="size-desc">Size: Biggest to Smallest</option>
                        </select>
                    </label>
                    <label style="display: inline-flex; align-items: center; gap: 8px; font-size: 0.9em; color: #555;">
                        <span>Min Size:</span>
                        <select id="min-size-select" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #ccc; font-size: 0.9em; cursor: pointer;">
                            <option value="0">No limit</option>
                            <option value="1024">1 KB</option>
                            <option value="10240">10 KB</option>
                            <option value="102400">100 KB</option>
                            <option value="1048576">1 MB</option>
                            <option value="10485760">10 MB</option>
                            <option value="104857600">100 MB</option>
                        </select>
                    </label>
                </div>
                
                <div class="metadata-container">
                    <div class="attachment-info">
                        <h3>Attachment Information</h3>
                        <div class="info-row">
                            <span class="info-label">ID:</span>
                            <span class="info-value" id="attachment-id">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Filename:</span>
                            <span class="info-value" id="filename">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Content Type:</span>
                            <span class="info-value" id="content-type">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Size:</span>
                            <span class="info-value" id="size">-</span>
                        </div>
                    </div>
                    
                    <div class="email-metadata">
                       
                        <div class="info-row">
                            <span class="info-label">Subject:</span>
                            <span class="info-value" id="email-subject">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">From:</span>
                            <span class="info-value" id="email-from">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Date:</span>
                            <span class="info-value" id="email-date">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Folder:</span>
                            <span class="info-value" id="email-folder">-</span>
                        </div>
                    </div>
                </div>
                
                <div class="attachment-section">
                    <div class="attachment-preview" id="preview-container">
                        <!-- Attachment preview will be displayed here -->
                    </div>
                </div>
            </div>
            <div id="error" class="error" style="display: none;"></div>
        </div>
    </div>
    
    <script>
        let currentAttachmentId = null;
        let currentOffset = 0;
        let currentOrder = 'random';
        const API_BASE = window.location.origin;
        
        async function loadAttachment(maxAttempts = 50) {
            try {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('attachment-view').style.display = 'none';
                document.getElementById('no-attachments').style.display = 'none';
                document.getElementById('error').style.display = 'none';
                
                const showPdf = document.getElementById('show-pdf-checkbox').checked;
                const order = document.getElementById('order-select').value;
                const minSize = parseInt(document.getElementById('min-size-select').value) || 0;
                currentOrder = order;
                
                let attempts = 0;
                let offset = currentOffset;
                
                while (attempts < maxAttempts) {
                    attempts++;
                    
                    let response;
                    if (order === 'random') {
                        response = await fetch(`${API_BASE}/attachments/random`);
                        offset = 0; // Reset offset for random
                    } else if (order === 'id') {
                        response = await fetch(`${API_BASE}/attachments/by-id?offset=${offset}`);
                    } else if (order === 'size-asc') {
                        response = await fetch(`${API_BASE}/attachments/by-size?order=asc&offset=${offset}`);
                    } else if (order === 'size-desc') {
                        response = await fetch(`${API_BASE}/attachments/by-size?order=desc&offset=${offset}`);
                    }
                    
                    if (response.status === 404 || !response.ok) {
                        // If not random and we've reached the end, try wrapping around
                        if (order !== 'random' && offset > 0) {
                            offset = 0;
                            continue;
                        }
                        // If offset is very large (from previous wrap), reset to 0
                        if (order !== 'random' && offset > 1000000) {
                            offset = 0;
                            continue;
                        }
                        document.getElementById('loading').style.display = 'none';
                        document.getElementById('no-attachments').style.display = 'block';
                        return;
                    }
                    
                    const data = await response.json();
                    
                    if (!data || !data.attachment_id) {
                        // If not random and we've reached the end, try wrapping around
                        if (order !== 'random' && offset > 0) {
                            offset = 0;
                            continue;
                        }
                        // If offset is very large (from previous wrap), reset to 0
                        if (order !== 'random' && offset > 1000000) {
                            offset = 0;
                            continue;
                        }
                        document.getElementById('loading').style.display = 'none';
                        document.getElementById('no-attachments').style.display = 'block';
                        return;
                    }
                    
                    // Check file size filter first
                    const fileSize = data.size || 0;
                    if (minSize > 0 && fileSize < minSize) {
                        // Skip this attachment if it's below the minimum size
                        if (order !== 'random') {
                            offset++;
                        }
                        continue;
                    }
                    
                    // Check if it's a PDF, MS Word, or octet stream and if they should be shown
                    const contentType = data.content_type ? data.content_type.toLowerCase() : '';
                    const isPdf = contentType === 'application/pdf';
                    const isMsWord = contentType === 'application/msword' || 
                                     contentType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
                                     contentType === 'application/vnd.ms-word.document.macroenabled.12';
                    const isOctetStream = contentType === 'application/octet-stream';
                    
                    if (!showPdf && (isPdf || isMsWord || isOctetStream)) {
                        // Skip this attachment and try again
                        if (order !== 'random') {
                            offset++;
                        }
                        continue;
                    }
                    
                    currentOffset = offset;
                    
                    currentAttachmentId = data.attachment_id;
                    
                    // Display attachment info
                    document.getElementById('attachment-id').textContent = data.attachment_id || 'Unknown';
                    document.getElementById('filename').textContent = data.filename || 'Unknown';
                    document.getElementById('content-type').textContent = data.content_type || 'Unknown';
                    document.getElementById('size').textContent = data.size ? formatBytes(data.size) : 'Unknown';
                    
                    // Display email metadata
                    document.getElementById('email-subject').textContent = data.email_subject || 'No subject';
                    document.getElementById('email-from').textContent = data.email_from || 'Unknown';
                    document.getElementById('email-date').textContent = data.email_date ? new Date(data.email_date).toLocaleString() : 'Unknown';
                    document.getElementById('email-folder').textContent = data.email_folder || 'Unknown';
                    
                    // Enable/disable Delete button based on PDF/MS Word/Octet Stream status
                    const deleteBtn = document.getElementById('delete-btn');
                    if (isPdf || isMsWord || isOctetStream) {
                        deleteBtn.disabled = true;
                        deleteBtn.title = 'Delete is disabled for PDF, MS Word, and Octet Stream attachments';
                    } else {
                        deleteBtn.disabled = false;
                        deleteBtn.title = '';
                    }
                    
                    // Load attachment preview (full version, not thumbnail)
                    const previewContainer = document.getElementById('preview-container');
                    previewContainer.innerHTML = '';
                    
                    // Check if it's an image
                    const isImage = data.content_type && data.content_type.startsWith('image/');
                    
                    if (isImage) {
                        const img = document.createElement('img');
                        img.src = `${API_BASE}/attachments/${data.attachment_id}`;
                        img.alt = data.filename || 'Attachment preview';
                        img.onerror = function() {
                            previewContainer.innerHTML = '<p style="color: #666;">Image not available</p>';
                        };
                        previewContainer.appendChild(img);
                    } else if (isPdf || isMsWord || isOctetStream) {
                        // For PDFs, MS Word, and Octet Streams, show thumbnail
                        const img = document.createElement('img');
                        img.src = `${API_BASE}/attachments/${data.attachment_id}?preview=true`;
                        img.alt = data.filename || 'File preview';
                        img.onerror = function() {
                            const fileType = isPdf ? 'PDF' : (isMsWord ? 'MS Word' : 'File');
                            previewContainer.innerHTML = `<p style="color: #666;">${fileType}: ${data.filename || 'Unknown'}</p><p style="color: #999; font-size: 0.9em;">Preview not available</p>`;
                        };
                        previewContainer.appendChild(img);
                    } else {
                        // For other non-image files, show thumbnail if available, otherwise show file info
                        const img = document.createElement('img');
                        img.src = `${API_BASE}/attachments/${data.attachment_id}?preview=true`;
                        img.alt = data.filename || 'Attachment preview';
                        img.onerror = function() {
                            previewContainer.innerHTML = `<p style="color: #666;">File: ${data.filename || 'Unknown'}</p><p style="color: #999; font-size: 0.9em;">${data.content_type || 'Unknown type'}</p>`;
                        };
                        previewContainer.appendChild(img);
                    }
                    
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('attachment-view').style.display = 'block';
                    
                    // Update Previous button state
                    const prevBtn = document.getElementById('prev-btn');
                    if (currentOrder === 'random') {
                        prevBtn.disabled = true;
                        prevBtn.title = 'Previous is not available in random order';
                    } else {
                        prevBtn.disabled = false;
                        prevBtn.title = '';
                    }
                    
                    return;
                }
                
                // If we've exhausted attempts, show no attachments message
                document.getElementById('loading').style.display = 'none';
                document.getElementById('no-attachments').style.display = 'block';
                document.getElementById('no-attachments').textContent = 'No attachments found matching your filter criteria.';
                
            } catch (error) {
                console.error('Error loading attachment:', error);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `Error: ${error.message}`;
            }
        }
        
        async function nextAttachment() {
            if (!currentAttachmentId) return;
            
            // Disable all buttons during loading
            const buttons = ['prev-btn', 'next-btn', 'keep-btn', 'delete-btn'];
            buttons.forEach(id => document.getElementById(id).disabled = true);
            
            // Increment offset for non-random orders
            if (currentOrder !== 'random') {
                currentOffset++;
            }
            
            // Move to next attachment
            await loadAttachment();
            
            // Re-enable buttons (loadAttachment will handle Previous button state)
            buttons.forEach(id => {
                const btn = document.getElementById(id);
                if (id !== 'prev-btn') {
                    btn.disabled = false;
                }
            });
            // Delete button state is set by loadAttachment based on PDF status
        }
        
        async function previousAttachment() {
            if (!currentAttachmentId) return;
            
            // Disable Previous button for random order
            if (currentOrder === 'random') {
                return;
            }
            
            // Disable all buttons during loading
            const buttons = ['prev-btn', 'next-btn', 'keep-btn', 'delete-btn'];
            buttons.forEach(id => document.getElementById(id).disabled = true);
            
            // Decrement offset for ordered views
            if (currentOffset > 0) {
                currentOffset--;
            } else {
                // Wrap around to end - set to a large number and let loadAttachment handle it
                currentOffset = 999999;
            }
            
            // Move to previous attachment
            await loadAttachment();
            
            // Re-enable buttons (loadAttachment will handle Previous button state)
            buttons.forEach(id => {
                const btn = document.getElementById(id);
                if (id !== 'prev-btn') {
                    btn.disabled = false;
                }
            });
            // Delete button state is set by loadAttachment based on PDF status
        }
        
        async function keepAttachment() {
            if (!currentAttachmentId) return;
            
            // Use nextAttachment logic
            await nextAttachment();
        }
        
        async function deleteAttachment() {
            if (!currentAttachmentId) return;
            
            const confirmDelete = document.getElementById('confirm-delete-checkbox').checked;
            if (confirmDelete) {
                if (!confirm('Are you sure you want to delete this attachment?')) {
                    return;
                }
            }
            
            // Disable all buttons during deletion
            const buttons = ['prev-btn', 'next-btn', 'keep-btn', 'delete-btn'];
            buttons.forEach(id => document.getElementById(id).disabled = true);
            
            try {
                const response = await fetch(`${API_BASE}/attachments/${currentAttachmentId}`, {
                    method: 'DELETE'
                });
                
                if (!response.ok) {
                    throw new Error('Failed to delete attachment');
                }
                
                // Increment offset for non-random orders
                if (currentOrder !== 'random') {
                    currentOffset++;
                }
                
                // Move to next attachment
                await loadAttachment();
                
                // Re-enable buttons (loadAttachment will handle Previous button state)
                const buttons = ['prev-btn', 'next-btn', 'keep-btn', 'delete-btn'];
                buttons.forEach(id => {
                    const btn = document.getElementById(id);
                    if (id !== 'prev-btn') {
                        btn.disabled = false;
                    }
                });
                
            } catch (error) {
                console.error('Error deleting attachment:', error);
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `Error deleting attachment: ${error.message}`;
                
                // Re-enable buttons on error
                const buttons = ['prev-btn', 'next-btn', 'keep-btn', 'delete-btn'];
                buttons.forEach(id => {
                    const btn = document.getElementById(id);
                    if (id !== 'prev-btn' || currentOrder !== 'random') {
                        btn.disabled = false;
                    }
                });
            }
        }
        
        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }
        
        // Load initial attachment
        loadAttachment();
        
        // Reload when PDF checkbox changes
        document.getElementById('show-pdf-checkbox').addEventListener('change', function() {
            if (currentOrder === 'random') {
                currentOffset = 0;
            }
            loadAttachment();
        });
        
        // Reload when order changes
        document.getElementById('order-select').addEventListener('change', function() {
            currentOffset = 0;
            loadAttachment();
        });
        
        // Reload when min size changes
        document.getElementById('min-size-select').addEventListener('change', function() {
            currentOffset = 0;
            loadAttachment();
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/attachments-images-grid", response_class=HTMLResponse)
async def images_grid_viewer():
    """Serve the image grid viewer web page."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Grid Viewer - Museum of Dave</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .content {
            padding: 20px;
        }
        
        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .pagination {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .pagination button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
        }
        
        .pagination button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .pagination span {
            font-weight: 600;
            color: #555;
        }
        
        .delete-selected-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
            font-size: 1em;
        }
        
        .delete-selected-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .images-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .image-item {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px;
            background: #f8f9fa;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .image-item:hover {
            border-color: #667eea;
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        .image-item.selected {
            border-color: #f5576c;
            background: #ffe8e8;
        }
        
        .image-checkbox {
            margin-bottom: 8px;
            cursor: pointer;
        }
        
        .image-checkbox input {
            margin-right: 8px;
            cursor: pointer;
        }
        
        .image-preview {
            width: 100%;
            height: 150px;
            object-fit: cover;
            border-radius: 6px;
            margin-bottom: 8px;
        }
        
        .image-info {
            font-size: 0.85em;
            color: #555;
        }
        
        .image-info div {
            margin-bottom: 4px;
        }
        
        .image-id {
            font-weight: 600;
            color: #667eea;
        }
        
        .image-size {
            color: #666;
        }
        
        .view-full-btn {
            width: 100%;
            padding: 6px 12px;
            margin-top: 8px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.85em;
            transition: all 0.3s ease;
        }
        
        .view-full-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(79, 172, 254, 0.4);
        }
        
        .image-modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.9);
            cursor: pointer;
        }
        
        .image-modal-content {
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
            margin-top: 5%;
            animation: zoom 0.3s;
        }
        
        .pdf-modal-content {
            margin: auto;
            display: block;
            width: 90%;
            height: 90vh;
            margin-top: 2%;
            border: none;
            animation: zoom 0.3s;
        }
        
        @keyframes zoom {
            from {transform: scale(0)}
            to {transform: scale(1)}
        }
        
        .close-modal {
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close-modal:hover {
            color: #bbb;
        }
        
        .metadata-modal {
            display: none;
            position: fixed;
            z-index: 1001;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            overflow: auto;
        }
        
        .metadata-modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 30px;
            border-radius: 12px;
            width: 80%;
            max-width: 800px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: zoom 0.3s;
        }
        
        .metadata-section {
            margin-bottom: 25px;
        }
        
        .metadata-section h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }
        
        .metadata-row {
            display: grid;
            grid-template-columns: 180px 1fr;
            gap: 10px;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
            font-size: 0.95em;
        }
        
        .metadata-row:last-child {
            border-bottom: none;
        }
        
        .metadata-label {
            font-weight: 600;
            color: #555;
        }
        
        .metadata-value {
            color: #333;
            word-break: break-word;
        }
        
        .close-metadata-modal {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close-metadata-modal:hover {
            color: #000;
        }
        
        .view-metadata-btn {
            width: 100%;
            padding: 6px 12px;
            margin-top: 8px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.85em;
            transition: all 0.3s ease;
        }
        
        .view-metadata-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .view-email-btn {
            width: 100%;
            padding: 6px 12px;
            margin-top: 8px;
            border: none;
            border-radius: 6px;
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
            color: white;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.85em;
            transition: all 0.3s ease;
        }
        
        .view-email-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(86, 171, 47, 0.4);
        }
        
        .email-modal {
            display: none;
            position: fixed;
            z-index: 1002;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            overflow: auto;
        }
        
        .email-modal-content {
            background-color: #fefefe;
            margin: 2% auto;
            padding: 20px;
            border-radius: 12px;
            width: 90%;
            max-width: 1000px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: zoom 0.3s;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        .email-content {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            background: white;
            margin-top: 15px;
        }
        
        .email-content iframe {
            width: 100%;
            min-height: 600px;
            border: none;
            border-radius: 6px;
        }
        
        .close-email-modal {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        
        .close-email-modal:hover {
            color: #000;
        }
        
        .loading {
            text-align: center;
            padding: 60px;
            font-size: 1.2em;
            color: #666;
        }
        
        .error {
            background: #fee;
            color: #c33;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ Image Grid Viewer</h1>
            <p>View and manage images (50 per page)</p>
        </div>
        <div class="content">
            <div class="controls">
                <div class="sort-controls">
                    <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9em; color: #555;">
                        <input type="checkbox" id="show-all-types-checkbox" onchange="syncTopControls(); changeSortOrder();" style="cursor: pointer;">
                        <span>Show all file types</span>
                    </label>
                    <label style="font-size: 0.9em; color: #555;">Sort by:</label>
                    <select id="sort-order-select" onchange="syncTopControls(); changeSortOrder();">
                        <option value="id">ID</option>
                        <option value="size">Size</option>
                        <option value="date">Date</option>
                    </select>
                    <select id="sort-direction-select" onchange="syncTopControls(); changeSortOrder();">
                        <option value="asc">Ascending</option>
                        <option value="desc">Descending</option>
                    </select>
                </div>
                <div class="pagination">
                    <button id="prev-page-btn" onclick="previousPage()">Previous</button>
                    <span id="page-info">Page 1 of 1</span>
                    <button id="next-page-btn" onclick="nextPage()">Next</button>
                </div>
                <button class="delete-selected-btn" id="delete-selected-btn" onclick="deleteSelected()" disabled>Delete Selected</button>
            </div>
            
            <div id="images-grid" class="images-grid" style="display: none;"></div>
            
            <div class="controls" id="bottom-controls">
                <div class="sort-controls">
                    <label style="display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9em; color: #555;">
                        <input type="checkbox" id="show-all-types-checkbox-bottom" onchange="syncBottomControls(); changeSortOrder();" style="cursor: pointer;">
                        <span>Show all file types</span>
                    </label>
                    <label style="font-size: 0.9em; color: #555;">Sort by:</label>
                    <select id="sort-order-select-bottom" onchange="syncBottomControls(); changeSortOrder();">
                        <option value="id">ID</option>
                        <option value="size">Size</option>
                        <option value="date">Date</option>
                    </select>
                    <select id="sort-direction-select-bottom" onchange="syncBottomControls(); changeSortOrder();">
                        <option value="asc">Ascending</option>
                        <option value="desc">Descending</option>
                    </select>
                </div>
                <div class="pagination">
                    <button id="prev-page-btn-bottom" onclick="previousPage()">Previous</button>
                    <span id="page-info-bottom">Page 1 of 1</span>
                    <button id="next-page-btn-bottom" onclick="nextPage()">Next</button>
                </div>
                <button class="delete-selected-btn" id="delete-selected-btn-bottom" onclick="deleteSelected()" disabled>Delete Selected</button>
            </div>
            
            <div id="image-modal" class="image-modal" onclick="closeModal()">
                <span class="close-modal">&times;</span>
                <img class="image-modal-content" id="modal-image" style="display: none;">
                <iframe class="pdf-modal-content" id="modal-pdf" style="display: none;"></iframe>
            </div>
            
            <div id="metadata-modal" class="metadata-modal" onclick="closeMetadataModal(event)">
                <div class="metadata-modal-content" onclick="event.stopPropagation()">
                    <span class="close-metadata-modal" onclick="closeMetadataModal(event)">&times;</span>
                    <div id="metadata-content"></div>
                </div>
            </div>
            
            <div id="email-modal" class="email-modal" onclick="closeEmailModal(event)">
                <div class="email-modal-content" onclick="event.stopPropagation()">
                    <span class="close-email-modal" onclick="closeEmailModal(event)">&times;</span>
                    <h2 style="color: #667eea; margin-bottom: 15px;">Email Content</h2>
                    <div id="email-metadata-display" style="margin-bottom: 20px;"></div>
                    <div id="email-content" class="email-content"></div>
                </div>
            </div>
            
            <div id="loading" class="loading">Loading images...</div>
            <div id="error" class="error" style="display: none;"></div>
            <div id="images-grid" class="images-grid" style="display: none;"></div>
        </div>
    </div>
    
    <script>
        let currentPage = 1;
        const pageSize = 50;
        let totalPages = 1;
        let currentSortOrder = 'id';
        let currentSortDirection = 'asc';
        const API_BASE = window.location.origin;
        const selectedImages = new Set();
        
        async function loadImages(page) {
            try {
                document.getElementById('loading').style.display = 'block';
                document.getElementById('images-grid').style.display = 'none';
                document.getElementById('error').style.display = 'none';
                
                // Get values from top controls (they should be synced)
                const sortOrder = document.getElementById('sort-order-select').value;
                const sortDirection = document.getElementById('sort-direction-select').value;
                const showAllTypes = document.getElementById('show-all-types-checkbox').checked;
                currentSortOrder = sortOrder;
                currentSortDirection = sortDirection;
                
                // Sync bottom controls to match top
                syncTopControls();
                
                const allTypesParam = showAllTypes ? '&all_types=true' : '';
                const response = await fetch(`${API_BASE}/attachments/images?page=${page}&page_size=${pageSize}&order=${sortOrder}&direction=${sortDirection}${allTypesParam}`);
                
                if (!response.ok) {
                    throw new Error(`Failed to load images: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                currentPage = data.page;
                totalPages = data.total_pages;
                
                // Update pagination info (both top and bottom)
                document.getElementById('page-info').textContent = `Page ${currentPage} of ${totalPages}`;
                document.getElementById('page-info-bottom').textContent = `Page ${currentPage} of ${totalPages}`;
                document.getElementById('prev-page-btn').disabled = currentPage <= 1;
                document.getElementById('prev-page-btn-bottom').disabled = currentPage <= 1;
                document.getElementById('next-page-btn').disabled = currentPage >= totalPages;
                document.getElementById('next-page-btn-bottom').disabled = currentPage >= totalPages;
                
                // Clear previous selections for this page
                selectedImages.clear();
                updateDeleteButton();
                
                // Render images
                const grid = document.getElementById('images-grid');
                grid.innerHTML = '';
                
                if (data.images.length === 0) {
                    grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: #666;">No images found</div>';
                } else {
                    data.images.forEach(image => {
                        const item = document.createElement('div');
                        item.className = 'image-item';
                        item.dataset.id = image.attachment_id;
                        
                        const checkbox = document.createElement('div');
                        checkbox.className = 'image-checkbox';
                        checkbox.innerHTML = `
                            <input type="checkbox" id="img-${image.attachment_id}" onchange="toggleSelection(${image.attachment_id})">
                            <label for="img-${image.attachment_id}">Select</label>
                        `;
                        
                        const img = document.createElement('img');
                        img.className = 'image-preview';
                        img.src = `${API_BASE}/attachments/${image.attachment_id}?preview=true`;
                        img.alt = image.filename || 'Image';
                        img.onerror = function() {
                            this.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="200" height="150"%3E%3Crect fill="%23ddd" width="200" height="150"/%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3ENo Preview%3C/text%3E%3C/svg%3E';
                        };
                        
                        const info = document.createElement('div');
                        info.className = 'image-info';
                        const sizeStr = image.size ? formatBytes(image.size) : 'Unknown';
                        const contentType = image.content_type || 'Unknown';
                        info.innerHTML = `
                            <div class="image-id">ID: ${image.attachment_id}</div>
                            <div class="image-size">Size: ${sizeStr}</div>
                            <div style="font-size: 0.8em; color: #888; margin-top: 4px;">${contentType}</div>
                        `;
                        
                        const viewFullBtn = document.createElement('button');
                        viewFullBtn.className = 'view-full-btn';
                        viewFullBtn.textContent = 'View Full Size';
                        viewFullBtn.onclick = function(e) {
                            e.stopPropagation();
                            showFullImage(image.attachment_id);
                        };
                        
                        const viewMetadataBtn = document.createElement('button');
                        viewMetadataBtn.className = 'view-metadata-btn';
                        viewMetadataBtn.textContent = 'View Metadata';
                        viewMetadataBtn.onclick = function(e) {
                            e.stopPropagation();
                            showMetadata(image);
                        };
                        
                        const viewEmailBtn = document.createElement('button');
                        viewEmailBtn.className = 'view-email-btn';
                        viewEmailBtn.textContent = 'View Email';
                        viewEmailBtn.onclick = function(e) {
                            e.stopPropagation();
                            showEmail(image.email_id);
                        };
                        
                        item.appendChild(checkbox);
                        item.appendChild(img);
                        item.appendChild(info);
                        item.appendChild(viewFullBtn);
                        item.appendChild(viewMetadataBtn);
                        item.appendChild(viewEmailBtn);
                        
                        item.onclick = function(e) {
                            if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL') {
                                const checkbox = this.querySelector('input[type="checkbox"]');
                                checkbox.checked = !checkbox.checked;
                                toggleSelection(image.attachment_id);
                            }
                        };
                        
                        grid.appendChild(item);
                    });
                }
                
                document.getElementById('loading').style.display = 'none';
                document.getElementById('images-grid').style.display = 'grid';
                
            } catch (error) {
                console.error('Error loading images:', error);
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = `Error: ${error.message}`;
            }
        }
        
        function toggleSelection(imageId) {
            const checkbox = document.getElementById(`img-${imageId}`);
            const item = document.querySelector(`[data-id="${imageId}"]`);
            
            if (checkbox.checked) {
                selectedImages.add(imageId);
                item.classList.add('selected');
            } else {
                selectedImages.delete(imageId);
                item.classList.remove('selected');
            }
            
            updateDeleteButton();
        }
        
        function updateDeleteButton() {
            const btn = document.getElementById('delete-selected-btn');
            const btnBottom = document.getElementById('delete-selected-btn-bottom');
            const btnText = selectedImages.size > 0 ? `Delete Selected (${selectedImages.size})` : 'Delete Selected';
            btn.disabled = selectedImages.size === 0;
            btn.textContent = btnText;
            btnBottom.disabled = selectedImages.size === 0;
            btnBottom.textContent = btnText;
        }
        
        async function deleteSelected() {
            if (selectedImages.size === 0) return;
            
            if (!confirm(`Are you sure you want to delete ${selectedImages.size} image(s)?`)) {
                return;
            }
            
            const deleteBtn = document.getElementById('delete-selected-btn');
            deleteBtn.disabled = true;
            deleteBtn.textContent = 'Deleting...';
            
            const idsToDelete = Array.from(selectedImages);
            let successCount = 0;
            let failCount = 0;
            
            for (const id of idsToDelete) {
                try {
                    const response = await fetch(`${API_BASE}/attachments/${id}`, {
                        method: 'DELETE'
                    });
                    
                    if (response.ok) {
                        successCount++;
                    } else {
                        failCount++;
                    }
                } catch (error) {
                    console.error(`Error deleting image ${id}:`, error);
                    failCount++;
                }
            }
            
            // Reload current page
            await loadImages(currentPage);
            
            if (failCount > 0) {
                alert(`Deleted ${successCount} image(s). ${failCount} failed.`);
            }
        }
        
        function previousPage() {
            if (currentPage > 1) {
                loadImages(currentPage - 1);
            }
        }
        
        function nextPage() {
            if (currentPage < totalPages) {
                loadImages(currentPage + 1);
            }
        }
        
        function syncTopControls() {
            // Sync bottom controls to top controls
            document.getElementById('show-all-types-checkbox-bottom').checked = document.getElementById('show-all-types-checkbox').checked;
            document.getElementById('sort-order-select-bottom').value = document.getElementById('sort-order-select').value;
            document.getElementById('sort-direction-select-bottom').value = document.getElementById('sort-direction-select').value;
        }
        
        function syncBottomControls() {
            // Sync top controls to bottom controls
            document.getElementById('show-all-types-checkbox').checked = document.getElementById('show-all-types-checkbox-bottom').checked;
            document.getElementById('sort-order-select').value = document.getElementById('sort-order-select-bottom').value;
            document.getElementById('sort-direction-select').value = document.getElementById('sort-direction-select-bottom').value;
        }
        
        function changeSortOrder() {
            currentPage = 1;
            loadImages(1);
        }
        
        function showMetadata(imageData) {
            const modal = document.getElementById('metadata-modal');
            const content = document.getElementById('metadata-content');
            
            const formatDate = (dateStr) => {
                if (!dateStr) return 'Unknown';
                try {
                    return new Date(dateStr).toLocaleString();
                } catch {
                    return dateStr;
                }
            };
            
            const formatBytesHelper = (bytes) => {
                if (!bytes) return 'Unknown';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
            };
            
            content.innerHTML = `
                <div class="metadata-section">
                    <h3>Attachment Information</h3>
                    <div class="metadata-row">
                        <span class="metadata-label">ID:</span>
                        <span class="metadata-value">${imageData.attachment_id || 'Unknown'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Filename:</span>
                        <span class="metadata-value">${imageData.filename || 'Unknown'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Content Type:</span>
                        <span class="metadata-value">${imageData.content_type || 'Unknown'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Size:</span>
                        <span class="metadata-value">${formatBytesHelper(imageData.size)}</span>
                    </div>
                </div>
                
                <div class="metadata-section">
                    <h3>Email Metadata</h3>
                    <div class="metadata-row">
                        <span class="metadata-label">Email ID:</span>
                        <span class="metadata-value">${imageData.email_id || 'Unknown'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Subject:</span>
                        <span class="metadata-value">${imageData.email_subject || 'No subject'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">From:</span>
                        <span class="metadata-value">${imageData.email_from || 'Unknown'}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Date:</span>
                        <span class="metadata-value">${formatDate(imageData.email_date)}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Folder:</span>
                        <span class="metadata-value">${imageData.email_folder || 'Unknown'}</span>
                    </div>
                </div>
            `;
            
            modal.style.display = 'block';
        }
        
        function closeMetadataModal(event) {
            if (event) {
                event.stopPropagation();
            }
            const modal = document.getElementById('metadata-modal');
            modal.style.display = 'none';
        }
        
        async function showEmail(emailId) {
            const modal = document.getElementById('email-modal');
            const content = document.getElementById('email-content');
            const metadataDisplay = document.getElementById('email-metadata-display');
            
            modal.style.display = 'block';
            metadataDisplay.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;">Loading metadata...</div>';
            content.innerHTML = '<div style="text-align: center; padding: 40px; color: #666;">Loading email...</div>';
            
            try {
                // Fetch email metadata first
                const metadataResponse = await fetch(`${API_BASE}/emails/${emailId}/metadata`);
                let metadataHtml = '';
                
                if (metadataResponse.ok) {
                    const metadata = await metadataResponse.json();
                    
                    const formatDate = (dateStr) => {
                        if (!dateStr) return 'Unknown';
                        try {
                            return new Date(dateStr).toLocaleString();
                        } catch {
                            return dateStr;
                        }
                    };
                    
                    metadataHtml = `
                        <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                            <h3 style="color: #667eea; margin-bottom: 12px; font-size: 1.2em; border-bottom: 2px solid #667eea; padding-bottom: 8px;"></h3>
                            <div style="display: grid; grid-template-columns: 150px 1fr; gap: 8px; font-size: 0.9em;">
                                <div style="font-weight: 600; color: #555;">Subject:</div>
                                <div style="color: #333;">${metadata.subject || 'No subject'}</div>
                                <div style="font-weight: 600; color: #555;">From:</div>
                                <div style="color: #333;">${metadata.from_address || 'Unknown'}</div>
                                <div style="font-weight: 600; color: #555;">To:</div>
                                <div style="color: #333;">${metadata.to_addresses || 'Unknown'}</div>
                                ${metadata.cc_addresses ? `
                                <div style="font-weight: 600; color: #555;">CC:</div>
                                <div style="color: #333;">${metadata.cc_addresses}</div>
                                ` : ''}
                                ${metadata.bcc_addresses ? `
                                <div style="font-weight: 600; color: #555;">BCC:</div>
                                <div style="color: #333;">${metadata.bcc_addresses}</div>
                                ` : ''}
                                <div style="font-weight: 600; color: #555;">Date:</div>
                                <div style="color: #333;">${formatDate(metadata.date)}</div>
                                <div style="font-weight: 600; color: #555;">Folder:</div>
                                <div style="color: #333;">${metadata.folder || 'Unknown'}</div>
                                <div style="font-weight: 600; color: #555;">UID:</div>
                                <div style="color: #333;">${metadata.uid || 'Unknown'}</div>
                            </div>
                        </div>
                    `;
                }
                
                metadataDisplay.innerHTML = metadataHtml;
                
                // Fetch email HTML content (endpoint will fall back to plain text if HTML not available)
                const response = await fetch(`${API_BASE}/emails/${emailId}/html`);
                
                if (!response.ok) {
                    // If HTML endpoint fails, try plain text as fallback
                    const textResponse = await fetch(`${API_BASE}/emails/${emailId}/text`);
                    if (textResponse.ok) {
                        const textContent = await textResponse.text();
                        // Wrap plain text in HTML for display
                        const htmlContent = `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
    </style>
</head>
<body>
${textContent}
</body>
</html>`;
                        content.innerHTML = '';
                        const iframe = document.createElement('iframe');
                        iframe.srcdoc = htmlContent;
                        iframe.style.width = '100%';
                        iframe.style.minHeight = '600px';
                        iframe.style.border = 'none';
                        iframe.style.borderRadius = '6px';
                        content.appendChild(iframe);
                    } else {
                        throw new Error(`Failed to load email: ${response.statusText}`);
                    }
                } else {
                    const htmlContent = await response.text();
                    
                    // Create an iframe to display the HTML email content
                    content.innerHTML = '';
                    const iframe = document.createElement('iframe');
                    iframe.srcdoc = htmlContent;
                    iframe.style.width = '100%';
                    iframe.style.minHeight = '600px';
                    iframe.style.border = 'none';
                    iframe.style.borderRadius = '6px';
                    content.appendChild(iframe);
                }
                
            } catch (error) {
                console.error('Error loading email:', error);
                content.innerHTML = `<div style="color: #c33; padding: 20px; text-align: center;">Error loading email: ${error.message}</div>`;
            }
        }
        
        function closeEmailModal(event) {
            if (event) {
                event.stopPropagation();
            }
            const modal = document.getElementById('email-modal');
            const content = document.getElementById('email-content');
            const metadataDisplay = document.getElementById('email-metadata-display');
            modal.style.display = 'none';
            // Clear content to stop loading
            content.innerHTML = '';
            metadataDisplay.innerHTML = '';
        }
        
        function showFullImage(imageId) {
            const modal = document.getElementById('image-modal');
            const modalImg = document.getElementById('modal-image');
            const modalPdf = document.getElementById('modal-pdf');
            
            // Get attachment info to check content type
            fetch(`${API_BASE}/attachments/${imageId}/info`)
                .then(response => response.json())
                .then(data => {
                    const contentType = data.content_type ? data.content_type.toLowerCase() : '';
                    const isPdf = contentType === 'application/pdf';
                    
                    modal.style.display = 'block';
                    
                    if (isPdf) {
                        // Show PDF in iframe
                        modalImg.style.display = 'none';
                        modalPdf.style.display = 'block';
                        modalPdf.src = `${API_BASE}/attachments/${imageId}`;
                    } else {
                        // Show image normally
                        modalPdf.style.display = 'none';
                        modalImg.style.display = 'block';
                        modalImg.src = `${API_BASE}/attachments/${imageId}`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching attachment info:', error);
                    // Fallback: try as image
                    modalImg.style.display = 'block';
                    modalPdf.style.display = 'none';
                    modalImg.src = `${API_BASE}/attachments/${imageId}`;
                });
        }
        
        function closeModal() {
            const modal = document.getElementById('image-modal');
            const modalImg = document.getElementById('modal-image');
            const modalPdf = document.getElementById('modal-pdf');
            modal.style.display = 'none';
            // Clear sources to stop loading
            modalImg.src = '';
            modalPdf.src = '';
        }
        
        // Close modal when clicking the X
        document.addEventListener('DOMContentLoaded', function() {
            const closeBtn = document.querySelector('.close-modal');
            if (closeBtn) {
                closeBtn.onclick = closeModal;
            }
            
            // Close modal on Escape key
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    closeModal();
                    closeMetadataModal();
                    closeEmailModal();
                }
            });
        });
        
        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }
        
        // Load initial page
        loadImages(1);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)
