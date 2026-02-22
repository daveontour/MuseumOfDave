"""Attachment routes."""
import os
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Response, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.types import Integer

from ...database.models import MediaMetadata, MediaBlob, Email
from ..deps import db, templates

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AttachmentInfoResponse(BaseModel):
    """Response model for attachment info with email metadata."""
    attachment_id: int
    filename: str
    content_type: str
    size: Optional[int]
    email_id: int
    email_subject: Optional[str]
    email_from: Optional[str]
    email_date: Optional[datetime]
    email_folder: Optional[str]


class ImageGridResponse(BaseModel):
    """Response model for image grid."""
    images: List[AttachmentInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/attachments/random", response_model=Optional[AttachmentInfoResponse])
async def get_random_attachment():
    """Get a random attachment with its email metadata."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).order_by(func.random()).first()

        if not media_item:
            return None

        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()

        if not email:
            return None

        content_type = media_item.media_type or "application/octet-stream"

        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@router.get("/attachments/by-id", response_model=Optional[AttachmentInfoResponse])
async def get_attachment_by_id_order(offset: int = Query(0, ge=0, description="Offset for pagination")):
    """Get attachment by ID order with offset."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).order_by(MediaMetadata.id.asc()).offset(offset).first()

        if not media_item:
            return None

        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()

        if not email:
            return None

        content_type = media_item.media_type or "application/octet-stream"

        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@router.get("/attachments/by-size", response_model=Optional[AttachmentInfoResponse])
async def get_attachment_by_size_order(
    order: str = Query("asc", pattern="^(asc|desc)$", description="Order: 'asc' for smallest to biggest, 'desc' for biggest to smallest"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get attachment by size order with offset."""
    session = db.get_session()
    try:
        query = session.query(MediaMetadata).join(MediaBlob).filter(
            MediaMetadata.source == "email_attachment"
        )

        if order == "asc":
            query = query.order_by(func.length(MediaBlob.image_data).asc().nullslast())
        else:
            query = query.order_by(func.length(MediaBlob.image_data).desc().nullslast())

        media_item = query.offset(offset).first()

        if not media_item:
            return None

        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()

        if not email:
            return None

        content_type = media_item.media_type or "application/octet-stream"

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


@router.get("/attachments/count")
async def get_attachment_count():
    """Get total count of attachments in the database."""
    session = db.get_session()
    try:
        count = session.query(MediaMetadata).filter(
            MediaMetadata.source == "email_attachment"
        ).count()
        return {"count": count}
    finally:
        session.close()


@router.get("/attachments/images", response_model=ImageGridResponse)
async def get_images_grid(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of images per page"),
    order: str = Query("id", pattern="^(id|size|date)$", description="Sort order: 'id', 'size', or 'date'"),
    direction: str = Query("asc", pattern="^(asc|desc)$", description="Sort direction: 'asc' or 'desc'"),
    all_types: bool = Query(False, description="If True, show all file types, not just images")
):
    """Get images for grid display with pagination and sorting."""
    session = db.get_session()
    try:
        offset = (page - 1) * page_size

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

        if order == "id":
            if direction == "asc":
                media_query = media_query.order_by(MediaMetadata.id.asc())
            else:
                media_query = media_query.order_by(MediaMetadata.id.desc())
        elif order == "size":
            if direction == "asc":
                media_query = media_query.order_by(func.length(MediaBlob.image_data).asc().nullslast())
            else:
                media_query = media_query.order_by(func.length(MediaBlob.image_data).desc().nullslast())
        elif order == "date":
            if direction == "asc":
                media_query = media_query.order_by(Email.date.asc().nullslast())
            else:
                media_query = media_query.order_by(Email.date.desc().nullslast())

        total = media_query.count()
        media_items = media_query.offset(offset).limit(page_size).all()

        image_list = []
        for media_item in media_items:
            email_id = int(media_item.source_reference)
            email = session.query(Email).filter(Email.id == email_id).first()

            if email:
                content_type = media_item.media_type or "application/octet-stream"
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

        total_pages = (total + page_size - 1) // page_size

        return ImageGridResponse(
            images=image_list,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    finally:
        session.close()


@router.get("/attachments/{attachment_id}/info", response_model=AttachmentInfoResponse)
async def get_attachment_info(attachment_id: int):
    """Get attachment information with email metadata."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )

        email_id = int(media_item.source_reference)
        email = session.query(Email).filter(Email.id == email_id).first()

        if not email:
            raise HTTPException(
                status_code=404,
                detail=f"Email for attachment {attachment_id} not found"
            )

        content_type = media_item.media_type or "application/octet-stream"

        return AttachmentInfoResponse(
            attachment_id=media_item.id,
            filename=media_item.title or "attachment",
            content_type=content_type,
            size=None,
            email_id=email.id,
            email_subject=email.subject,
            email_from=email.from_address,
            email_date=email.date,
            email_folder=email.folder
        )
    finally:
        session.close()


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(attachment_id: int):
    """Delete an attachment by ID (media_item_id)."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )

        media_blob = session.query(MediaBlob).filter(
            MediaBlob.id == media_item.media_blob_id
        ).first()

        if media_blob:
            other_items_count = session.query(MediaMetadata).filter(
                MediaMetadata.media_blob_id == media_blob.id
            ).count()

            session.delete(media_item)

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


@router.get("/attachments/{attachment_id}")
async def get_attachment_content(attachment_id: int, preview: bool = False):
    """Get attachment content by ID (media_item_id)."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(
            MediaMetadata.id == attachment_id,
            MediaMetadata.source == "email_attachment"
        ).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Attachment with ID {attachment_id} not found"
            )

        media_blob = session.query(MediaBlob).filter(
            MediaBlob.id == media_item.media_blob_id
        ).first()

        if not media_blob:
            raise HTTPException(
                status_code=404,
                detail=f"Media blob for attachment {attachment_id} not found"
            )

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


@router.get("/attachments-viewer", response_class=HTMLResponse)
async def attachments_viewer(request: Request):
    """Serve the attachment viewer web page."""
    return templates.TemplateResponse(
        "attachments_viewer.html",
        {"request": request}
    )


@router.get("/attachments-images-grid", response_class=HTMLResponse)
async def images_grid_viewer(request: Request):
    """Serve the image grid viewer web page."""
    return templates.TemplateResponse(
        "images_grid.html",
        {"request": request}
    )
