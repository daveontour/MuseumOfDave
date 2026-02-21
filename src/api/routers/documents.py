"""Reference document routes."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import or_, and_

from ...database import ReferenceDocument
from ...services import ReferenceDocumentService
from ...services.exceptions import ServiceException, ValidationError, NotFoundError
from ...services.dto import FileData, DocumentMetadata, DocumentUpdate
from ..deps import db

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/reference-documents", response_model=List[ReferenceDocumentResponse])
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


@router.get("/reference-documents/{document_id}", response_model=ReferenceDocumentResponse)
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


@router.get("/reference-documents/{document_id}/download")
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


@router.post("/reference-documents", response_model=ReferenceDocumentResponse)
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


@router.put("/reference-documents/{document_id}", response_model=ReferenceDocumentResponse)
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


@router.delete("/reference-documents/{document_id}")
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
