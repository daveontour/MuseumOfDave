"""FastAPI HTTP Server."""

import os
import threading
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
