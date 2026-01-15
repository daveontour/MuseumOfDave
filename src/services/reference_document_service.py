"""Reference document service for business logic."""

import mimetypes
from typing import Optional
from fastapi import UploadFile

from ..database import Database
from ..database.models import ReferenceDocument
from .exceptions import ValidationError, NotFoundError
from .dto import FileValidationResult, FileData, DocumentMetadata, DocumentUpdate


class ReferenceDocumentService:
    """Service for reference document-related business logic."""

    def __init__(self, db: Database):
        """Initialize reference document service with database connection."""
        self.db = db

    def validate_file(self, file: UploadFile, file_content: bytes) -> FileValidationResult:
        """Validate uploaded file.
        
        Args:
            file: UploadFile object
            file_content: File content as bytes
            
        Returns:
            FileValidationResult with validation status and content_type
            
        Raises:
            ValidationError: If file is invalid
        """
        if not file.filename:
            raise ValidationError("No file provided")
        
        if not file_content:
            raise ValidationError("File is empty")
        
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
            guessed_type, _ = mimetypes.guess_type(file.filename)
            if guessed_type and guessed_type in allowed_types:
                content_type = guessed_type
            else:
                raise ValidationError(
                    f"File type {content_type} not allowed. Allowed types: documents and images."
                )
        
        return FileValidationResult(
            is_valid=True,
            content_type=content_type
        )

    def create_document(
        self,
        file_data: FileData,
        metadata: DocumentMetadata
    ) -> ReferenceDocument:
        """Create a new reference document.
        
        Args:
            file_data: FileData with file information
            metadata: DocumentMetadata with document metadata
            
        Returns:
            Created ReferenceDocument instance
        """
        session = self.db.get_session()
        try:
            document = ReferenceDocument(
                filename=file_data.filename,
                title=metadata.title,
                description=metadata.description,
                author=metadata.author,
                content_type=file_data.content_type,
                size=file_data.size,
                data=file_data.content,
                tags=metadata.tags,
                categories=metadata.categories,
                notes=metadata.notes,
                available_for_task=metadata.available_for_task
            )
            
            session.add(document)
            session.commit()
            session.refresh(document)
            
            return document
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_document(
        self,
        document_id: int,
        updates: DocumentUpdate
    ) -> ReferenceDocument:
        """Update reference document metadata.
        
        Args:
            document_id: ID of document to update
            updates: DocumentUpdate with fields to update
            
        Returns:
            Updated ReferenceDocument instance
            
        Raises:
            NotFoundError: If document not found
        """
        session = self.db.get_session()
        try:
            document = session.query(ReferenceDocument).filter(
                ReferenceDocument.id == document_id
            ).first()
            
            if not document:
                raise NotFoundError(f"Reference document with ID {document_id} not found")
            
            # Update fields if provided
            if updates.title is not None:
                document.title = updates.title
            if updates.description is not None:
                document.description = updates.description
            if updates.author is not None:
                document.author = updates.author
            if updates.tags is not None:
                document.tags = updates.tags
            if updates.categories is not None:
                document.categories = updates.categories
            if updates.notes is not None:
                document.notes = updates.notes
            if updates.available_for_task is not None:
                document.available_for_task = updates.available_for_task
            
            session.commit()
            session.refresh(document)
            
            return document
        except NotFoundError:
            raise
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def to_response_model(document: ReferenceDocument) -> dict:
        """Convert ReferenceDocument domain model to response dictionary.
        
        Args:
            document: ReferenceDocument instance
            
        Returns:
            Dictionary matching ReferenceDocumentResponse structure
        """
        return {
            "id": document.id,
            "filename": document.filename,
            "title": document.title,
            "description": document.description,
            "author": document.author,
            "content_type": document.content_type,
            "size": document.size,
            "tags": document.tags,
            "categories": document.categories,
            "notes": document.notes,
            "available_for_task": document.available_for_task,
            "created_at": document.created_at,
            "updated_at": document.updated_at
        }
