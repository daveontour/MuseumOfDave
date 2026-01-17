"""Image service for business logic."""

import os
from io import BytesIO
from typing import List, Optional, Dict, Any
from datetime import datetime
from PIL import Image

from sqlalchemy import and_
from sqlalchemy.orm import Session

from ..database import Database
from ..database.models import MediaMetadata, MediaBlob, FacebookAlbum, Attachment, Email, AlbumMedia
from ..database.storage import ImageStorage
from .exceptions import NotFoundError, ValidationError
from ..imageimport.filesystemimport import create_thumbnail
from .dto import (
    ImageSearchFilters,
    MediaMetadataUpdate,
    BulkUpdateResult,
    BulkDeleteResult,
    ImageContent,
)

# Try to register HEIF/HEIC support if pillow-heif is available
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False


class ImageService:
    """Service for image-related business logic."""

    def __init__(self, db: Database):
        """Initialize image service with database connection."""
        self.db = db
        self.storage = ImageStorage(db=db)

    def search_images(self, filters: ImageSearchFilters) -> List[MediaMetadata]:
        """Search images by metadata criteria.
        
        Args:
            filters: ImageSearchFilters with search criteria
            
        Returns:
            List of MediaMetadata objects matching criteria
        """
        session = self.db.get_session()
        try:
            # Start building query
            query = session.query(MediaMetadata)
            filter_list = []
            
            # Text field filters (partial match, case-insensitive)
            if filters.title:
                filter_list.append(MediaMetadata.title.ilike(f"%{filters.title}%"))
            
            if filters.description:
                filter_list.append(MediaMetadata.description.ilike(f"%{filters.description}%"))
            
            if filters.author:
                filter_list.append(MediaMetadata.author.ilike(f"%{filters.author}%"))
            
            if filters.tags:
                filter_list.append(MediaMetadata.tags.ilike(f"%{filters.tags}%"))
            
            if filters.categories:
                filter_list.append(MediaMetadata.categories.ilike(f"%{filters.categories}%"))
            
            if filters.source:
                filter_list.append(MediaMetadata.source.ilike(filters.source))
            
            if filters.source_reference:
                filter_list.append(MediaMetadata.source_reference.ilike(f"%{filters.source_reference}%"))
            
            if filters.media_type:
                filter_list.append(MediaMetadata.media_type.ilike(f"%{filters.media_type}%"))
            
            if filters.region:
                filter_list.append(MediaMetadata.region.ilike(f"%{filters.region}%"))
            
            # Numeric filters
            if filters.year is not None:
                filter_list.append(MediaMetadata.year == filters.year)
            
            if filters.month is not None:
                filter_list.append(MediaMetadata.month == filters.month)
            
            # Rating filters
            if filters.rating is not None:
                filter_list.append(MediaMetadata.rating == filters.rating)
            else:
                if filters.rating_min is not None:
                    filter_list.append(MediaMetadata.rating >= filters.rating_min)
                if filters.rating_max is not None:
                    filter_list.append(MediaMetadata.rating <= filters.rating_max)
            
            # Boolean filters
            if filters.has_gps is not None:
                filter_list.append(MediaMetadata.has_gps == filters.has_gps)
            
            if filters.available_for_task is not None:
                filter_list.append(MediaMetadata.available_for_task == filters.available_for_task)
            
            if filters.processed is not None:
                filter_list.append(MediaMetadata.processed == filters.processed)
            
            if filters.location_processed is not None:
                filter_list.append(MediaMetadata.location_processed == filters.location_processed)
            
            if filters.image_processed is not None:
                filter_list.append(MediaMetadata.image_processed == filters.image_processed)

            filter_list.append(MediaMetadata.media_type.like('image/%'))
            
            # Apply all filters with AND logic
            if filter_list:
                query = query.filter(and_(*filter_list))
            
            # Sort by created_at descending (newest first)
            query = query.order_by(MediaMetadata.created_at.desc())
            
            # Execute query
            images = query.all()
            
            return images
        finally:
            session.close()

    def bulk_update_tags(self, image_ids: List[int], tags: str) -> BulkUpdateResult:
        """Bulk update multiple images with tags.
        
        Args:
            image_ids: List of image metadata IDs to update
            tags: Tags to apply (will be appended to existing tags)
            
        Returns:
            BulkUpdateResult with updated_count and errors
            
        Raises:
            ValidationError: If image_ids or tags are invalid
        """
        if not image_ids or not isinstance(image_ids, list):
            raise ValidationError("image_ids must be a non-empty list")
        
        if not tags or not isinstance(tags, str) or not tags.strip():
            raise ValidationError("tags must be a non-empty string")
        
        updated_count = 0
        errors = []
        
        # Get existing tags for all images in one query
        session = self.db.get_session()
        try:
            metadata_list = session.query(MediaMetadata).filter(MediaMetadata.id.in_(image_ids)).all()
            metadata_dict = {m.id: m for m in metadata_list}
        finally:
            session.close()
        
        # Update each image
        for image_id in image_ids:
            try:
                metadata = metadata_dict.get(image_id)
                if metadata:
                    # Merge tags: append new tags to existing ones
                    existing_tags = metadata.tags or ''
                    if existing_tags:
                        new_tags = f"{existing_tags}, {tags.strip()}"
                    else:
                        new_tags = tags.strip()
                    
                    # Update using the storage method
                    updated = self.storage.update_image_metadata(
                        metadata_id=image_id,
                        tags=new_tags
                    )
                    if updated:
                        updated_count += 1
                else:
                    errors.append(f"Image {image_id} not found")
            except Exception as e:
                errors.append(f"Error updating image {image_id}: {str(e)}")
        
        return BulkUpdateResult(
            updated_count=updated_count,
            errors=errors if errors else None
        )

    def bulk_delete_images(self, image_ids: List[int]) -> BulkDeleteResult:
        """Bulk delete multiple images by their metadata IDs.
        
        Args:
            image_ids: List of image metadata IDs to delete
            
        Returns:
            BulkDeleteResult with deleted_count and errors
            
        Raises:
            ValidationError: If image_ids is invalid
        """
        if not image_ids or not isinstance(image_ids, list):
            raise ValidationError("image_ids must be a non-empty list")
        
        deleted_count = 0
        errors = []
        
        for image_id in image_ids:
            try:
                deleted = self.storage.delete_image_by_metadata_id(image_id)
                if deleted:
                    deleted_count += 1
                else:
                    errors.append(f"Image {image_id} not found")
            except Exception as e:
                errors.append(f"Error deleting image {image_id}: {str(e)}")
        
        return BulkDeleteResult(
            deleted_count=deleted_count,
            errors=errors if errors else None
        )

    def update_image_metadata(
        self,
        image_id: int,
        updates: MediaMetadataUpdate
    ) -> MediaMetadata:
        """Update image metadata fields.
        
        Args:
            image_id: The metadata ID of the image to update
            updates: MediaMetadataUpdate with fields to update
            
        Returns:
            Updated MediaMetadata instance
            
        Raises:
            NotFoundError: If image not found
            ValidationError: If rating is invalid
        """
        # Validate rating if provided
        if updates.rating is not None:
            if updates.rating < 1 or updates.rating > 5:
                raise ValidationError("Rating must be between 1 and 5")
        
        # Update metadata
        updated_metadata = self.storage.update_image_metadata(
            metadata_id=image_id,
            description=updates.description,
            tags=updates.tags,
            rating=updates.rating
        )
        
        if not updated_metadata:
            raise NotFoundError(f"Image with metadata ID {image_id} not found")
        
        return updated_metadata

    def get_image_content(
        self,
        image_id: int,
        id_type: str = "blob",
        preview: bool = False,
        convert_heic: bool = True
    ) -> ImageContent:
        """Get image content by ID.
        
        Args:
            image_id: The ID of the image (blob ID or metadata ID)
            id_type: Type of ID - 'blob' for image_blob.id or 'metadata' for image_information.id
            preview: If True, return thumbnail instead of full image
            convert_heic: If True, convert HEIC images to JPG format
            
        Returns:
            ImageContent with content, content_type, and filename
            
        Raises:
            NotFoundError: If image not found or has no content
        """
        # Get image blob based on type
        if id_type == "metadata":
            image_blob = self.storage.get_image_by_metadata_id(image_id)
        else:
            image_blob = self.storage.get_image_by_blob_id(image_id)
        
        if not image_blob:
            raise NotFoundError(f"Image with ID {image_id} (type: {id_type}) not found")
        
        # Determine content
        if preview:
            content = image_blob.thumbnail_data
            if content is None:
                raise NotFoundError(f"Image with ID {image_id} has no thumbnail available")
            content_type = "image/jpeg"  # Thumbnails are always JPEG
            filename = "image_thumb.jpg"
        else:
            content = image_blob.image_data
            if content is None:
                raise NotFoundError(f"Image with ID {image_id} has no image data")
            
            # Get content type from metadata
            session = self.db.get_session()
            try:
                if id_type == "metadata":
                    # We already know the metadata ID, so query directly
                    metadata = session.query(MediaMetadata).filter(
                        MediaMetadata.id == image_id
                    ).first()
                else:
                    # Query metadata by blob_id
                    metadata = session.query(MediaMetadata).filter(
                        MediaMetadata.media_blob_id == image_blob.id
                    ).first()
                
                if metadata and metadata.media_type:
                    content_type = metadata.media_type
                else:
                    content_type = "image/jpeg"  # Default
                filename = metadata.source_reference.split(os.sep)[-1] if metadata and metadata.source_reference else "image"
            finally:
                session.close()
            
            # Convert HEIC to JPG if requested
            if convert_heic and content_type and content_type.lower() in ('image/heic', 'image/heif'):
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
                except Exception:
                    # If conversion fails, return original image
                    pass  # Fall through to return original content
        
        return ImageContent(
            content=content,
            content_type=content_type,
            filename=filename
        )

    @staticmethod
    def to_response_model(image: MediaMetadata) -> dict:
        """Convert MediaMetadata domain model to response dictionary.
        
        Args:
            image: MediaMetadata instance
            
        Returns:
            Dictionary matching MediaMetadataResponse structure
        """
        return {
            "id": image.id,
            "media_blob_id": image.media_blob_id,
            "description": image.description,
            "title": image.title,
            "author": image.author,
            "tags": image.tags,
            "categories": image.categories,
            "notes": image.notes,
            "available_for_task": image.available_for_task,
            "media_type": image.media_type,
            "processed": image.processed,
            "location_processed": image.location_processed,
            "image_processed": image.image_processed,
            "created_at": image.created_at,
            "updated_at": image.updated_at,
            "year": image.year,
            "month": image.month,
            "latitude": image.latitude,
            "longitude": image.longitude,
            "altitude": image.altitude,
            "rating": image.rating,
            "has_gps": image.has_gps,
            "google_maps_url": image.google_maps_url,
            "region": image.region,
            "source": image.source,
            "source_reference": image.source_reference
        }
