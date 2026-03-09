"""Images CRUD, search, serving, and Facebook album view routes."""
import mimetypes
import math
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import or_, func, and_
from sqlalchemy.orm import joinedload

from ....database import Database, FacebookAlbum
from ....database.models import MediaMetadata, MediaBlob, AlbumMedia
from ....database.storage import ImageStorage
from ....services import ImageService
from ....services.exceptions import ServiceException, ValidationError, NotFoundError
from ....services.dto import ImageSearchFilters, MediaMetadataUpdate
from ...deps import db

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MediaMetadataResponse(BaseModel):
    """Response model for image metadata."""
    id: int
    media_blob_id: int
    description: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: bool = False
    media_type: Optional[str] = None
    processed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    year: Optional[int] = None
    month: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    rating: int = 5
    has_gps: bool = False
    google_maps_url: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Images search/CRUD + getLocations routes
# ---------------------------------------------------------------------------

@router.get("/images/search", response_model=List[MediaMetadataResponse])
async def search_images(
    title: Optional[str] = Query(None, description="Filter by title (partial match, case-insensitive)"),
    description: Optional[str] = Query(None, description="Filter by description (partial match, case-insensitive)"),
    author: Optional[str] = Query(None, description="Filter by author (partial match, case-insensitive)"),
    tags: Optional[str] = Query(None, description="Filter by tags (partial match, case-insensitive)"),
    categories: Optional[str] = Query(None, description="Filter by categories (partial match, case-insensitive)"),
    source: Optional[str] = Query(None, description="Filter by source (exact match, case-insensitive)"),
    source_reference: Optional[str] = Query(None, description="Filter by source_reference (partial match, case-insensitive)"),
    media_type: Optional[str] = Query(None, description="Filter by media type/MIME type (partial match, case-insensitive)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    has_gps: Optional[bool] = Query(None, description="Filter by whether image has GPS data"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating (1-5)"),
    rating_min: Optional[int] = Query(None, ge=1, le=5, description="Filter by minimum rating (1-5)"),
    rating_max: Optional[int] = Query(None, ge=1, le=5, description="Filter by maximum rating (1-5)"),
    available_for_task: Optional[bool] = Query(None, description="Filter by available_for_task flag"),
    processed: Optional[bool] = Query(None, description="Filter by processed flag"),
    region: Optional[str] = Query(None, description="Filter by region (partial match, case-insensitive)")
):
    """Search images by metadata criteria."""
    image_service = ImageService(db=db)
    try:
        filters = ImageSearchFilters(
            title=title,
            description=description,
            author=author,
            tags=tags,
            categories=categories,
            source=source,
            source_reference=source_reference,
            media_type=media_type,
            year=year,
            month=month,
            has_gps=has_gps,
            rating=rating,
            rating_min=rating_min,
            rating_max=rating_max,
            available_for_task=available_for_task,
            processed=processed,
            region=region
        )

        images = image_service.search_images(filters)

        return [MediaMetadataResponse(**image_service.to_response_model(img)) for img in images]
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching images: {str(e)}"
        )


@router.get("/images/years")
async def get_distinct_years():
    """Get list of distinct years from media_items table."""
    session = db.get_session()
    try:
        years = session.query(func.distinct(MediaMetadata.year)).filter(
            MediaMetadata.year.isnot(None)
        ).order_by(
            MediaMetadata.year.desc()
        ).all()

        year_list = [year[0] for year in years]

        return {"years": year_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct years: {str(e)}"
        )
    finally:
        session.close()


@router.get("/images/tags")
async def get_distinct_tags():
    """Get list of distinct tags from media_items table."""
    session = db.get_session()
    try:
        tag_records = session.query(MediaMetadata.tags).filter(
            MediaMetadata.tags.isnot(None),
            MediaMetadata.tags != ''
        ).all()

        all_tags = set()
        for record in tag_records:
            if record[0]:
                tags = [tag.strip() for tag in record[0].split(',') if tag.strip()]
                all_tags.update(tags)

        tag_list = sorted(list(all_tags))

        return {"tags": tag_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct tags: {str(e)}"
        )
    finally:
        session.close()


@router.get("/getLocations")
async def get_locations():
    """Get metadata of media items that have GPS data set."""
    session = db.get_session()
    try:
        media_items = session.query(MediaMetadata).filter(
            or_(
                MediaMetadata.has_gps == True,
                and_(
                    MediaMetadata.latitude.isnot(None),
                    MediaMetadata.longitude.isnot(None)
                )
            )
        ).all()

        locations = []
        for item in media_items:
            location_data = {
                "id": item.id,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "altitude": item.altitude,
                "title": item.title,
                "description": item.description,
                "year": item.year,
                "month": item.month,
                "tags": item.tags,
                "google_maps_url": item.google_maps_url,
                "region": item.region,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "media_type": item.media_type,
                "source": item.source,
                "source_reference": item.source_reference
            }
            locations.append(location_data)

        return {"locations": locations}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving locations: {str(e)}"
        )
    finally:
        session.close()


@router.get("/images/{image_id}")
async def get_image_content(
    image_id: int,
    type: str = Query("blob", pattern="^(blob|metadata)$", description="Type of ID: 'blob' for media_blob.id or 'metadata' for media_items.id"),
    preview: bool = Query(False, description="If True, return thumbnail instead of full image"),
    convert_heic_to_jpg: bool = Query(True, description="If True, convert HEIC images to JPG format before returning")
):
    """Get image content by ID."""
    image_service = ImageService(db=db)
    try:
        image_content = image_service.get_image_content(
            image_id=image_id,
            id_type=type,
            preview=preview,
            convert_heic=convert_heic_to_jpg
        )
        safe_filename = image_content.filename.replace('"', '\\"')
        headers = {
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }

        return Response(
            content=image_content.content,
            media_type=image_content.content_type,
            headers=headers
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image: {str(e)}"
        )


@router.put("/images/bulk-update")
async def bulk_update_images(update_data: Dict[str, Any]):
    """Bulk update multiple images with tags."""
    image_service = ImageService(db=db)
    try:
        image_ids = update_data.get("image_ids", [])
        tags = update_data.get("tags")

        result = image_service.bulk_update_tags(image_ids, tags)

        return {
            "message": f"Updated {result.updated_count} image(s)",
            "updated_count": result.updated_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk updating images: {str(e)}"
        )


@router.get("/images/{image_id}/metadata", response_model=MediaMetadataResponse)
async def get_image_metadata(image_id: int):
    """Get image metadata by ID."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(MediaMetadata.id == image_id).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found"
            )

        return MediaMetadataResponse(
            id=media_item.id,
            media_blob_id=media_item.media_blob_id,
            description=media_item.description,
            title=media_item.title,
            author=media_item.author,
            tags=media_item.tags,
            categories=media_item.categories,
            notes=media_item.notes,
            available_for_task=media_item.available_for_task,
            media_type=media_item.media_type,
            processed=media_item.processed,
            created_at=media_item.created_at,
            updated_at=media_item.updated_at,
            year=media_item.year,
            month=media_item.month,
            latitude=media_item.latitude,
            longitude=media_item.longitude,
            altitude=media_item.altitude,
            rating=media_item.rating or 5,
            has_gps=media_item.has_gps,
            google_maps_url=media_item.google_maps_url,
            region=media_item.region,
            source=media_item.source,
            source_reference=media_item.source_reference
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image metadata: {str(e)}"
        )
    finally:
        session.close()


@router.put("/images/{image_id}")
async def update_image_metadata(image_id: int, update_data: Dict[str, Any]):
    """Update image metadata fields."""
    image_service = ImageService(db=db)
    try:
        updates = MediaMetadataUpdate(
            description=update_data.get("description"),
            tags=update_data.get("tags"),
            rating=update_data.get("rating")
        )

        updated_metadata = image_service.update_image_metadata(image_id, updates)

        return {
            "message": f"Image {image_id} updated successfully",
            "image_id": image_id,
            "updated_fields": {
                "description": updates.description is not None,
                "tags": updates.tags is not None,
                "rating": updates.rating is not None
            }
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating image: {str(e)}"
        )


@router.delete("/images/bulk-delete")
async def bulk_delete_images(delete_data: Dict[str, Any]):
    """Bulk delete multiple images by their metadata IDs."""
    image_service = ImageService(db=db)
    try:
        image_ids = delete_data.get("image_ids", [])

        result = image_service.bulk_delete_images(image_ids)

        return {
            "message": f"Deleted {result.deleted_count} image(s)",
            "deleted_count": result.deleted_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk deleting images: {str(e)}"
        )


@router.delete("/images/{image_id}")
async def delete_image(image_id: int):
    """Delete an image by metadata ID."""
    storage = ImageStorage(db=db)
    try:
        deleted = storage.delete_image_by_metadata_id(image_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Image with metadata ID {image_id} not found"
            )
        return {"message": f"Image {image_id} deleted successfully", "image_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting image: {str(e)}"
        )


@router.delete("/images")
async def delete_images(
    all: bool = Query(False, description="If True, delete all images"),
    start_id: Optional[int] = Query(None, description="Start of ID range (inclusive)"),
    end_id: Optional[int] = Query(None, description="End of ID range (inclusive)")
):
    """Delete images with options to delete all or by ID range."""
    session = db.get_session()
    try:
        if all and (start_id is not None or end_id is not None):
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both 'all=true' and ID range parameters"
            )

        if not all and start_id is None and end_id is None:
            raise HTTPException(
                status_code=400,
                detail="Must specify either 'all=true' or at least one of 'start_id' or 'end_id'"
            )

        query = session.query(MediaMetadata)

        if all:
            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found to delete"
                )

            deleted_count = query.delete(synchronize_session=False)
            session.commit()

            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count
            }
        else:
            if start_id is not None and end_id is not None:
                if start_id > end_id:
                    raise HTTPException(
                        status_code=400,
                        detail="start_id must be less than or equal to end_id"
                    )
                query = query.filter(
                    and_(
                        MediaMetadata.id >= start_id,
                        MediaMetadata.id <= end_id
                    )
                )
            elif start_id is not None:
                query = query.filter(MediaMetadata.id >= start_id)
            elif end_id is not None:
                query = query.filter(MediaMetadata.id <= end_id)

            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found in the specified range"
                )

            metadata_records = query.all()
            deleted_count = 0
            for metadata in metadata_records:
                _ = metadata.image_blob
                session.delete(metadata)
                deleted_count += 1

            session.commit()

            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count,
                "start_id": start_id,
                "end_id": end_id
            }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting images: {str(e)}"
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Facebook album view routes
# ---------------------------------------------------------------------------

@router.get("/facebook/albums")
async def get_facebook_albums():
    """Get list of all Facebook albums."""
    session = db.get_session()
    try:
        albums = session.query(
            FacebookAlbum.id,
            FacebookAlbum.name,
            FacebookAlbum.description,
            FacebookAlbum.cover_photo_uri,
            func.count(func.distinct(AlbumMedia.id)).label('image_count')
        ).outerjoin(
            AlbumMedia, FacebookAlbum.id == AlbumMedia.album_id
        ).group_by(
            FacebookAlbum.id
        ).order_by(
            FacebookAlbum.name
        ).all()

        result = []
        for album in albums:
            result.append({
                "id": album.id,
                "name": album.name,
                "description": album.description,
                "cover_photo_uri": album.cover_photo_uri,
                "image_count": album.image_count or 0
            })

        return result
    finally:
        session.close()


@router.get("/facebook/albums/{album_id}/images")
async def get_facebook_album_images(album_id: int):
    """Get all images for a specific Facebook album."""
    session = db.get_session()
    try:
        media_items = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            AlbumMedia.album_id == album_id
        ).order_by(
            MediaMetadata.created_at.asc()
        ).all()

        result = []
        for media_item in media_items:
            result.append({
                "id": media_item.id,
                "title": media_item.title,
                "description": media_item.description,
                "media_type": media_item.media_type,
                "created_at": media_item.created_at.isoformat() if media_item.created_at else None
            })

        return result
    finally:
        session.close()


@router.get("/facebook/albums/images/{image_id}")
async def get_facebook_album_image(image_id: int):
    """Get image data for a specific Facebook album image."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            MediaMetadata.id == image_id
        ).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found or not linked to an album"
            )

        if not media_item.media_blob or not media_item.media_blob.image_data:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} has no image data"
            )

        content_type = media_item.media_type or "image/jpeg"
        if media_item.title:
            guessed_type, _ = mimetypes.guess_type(media_item.title)
            if guessed_type:
                content_type = guessed_type

        return Response(
            content=media_item.media_blob.image_data,
            media_type=content_type
        )
    finally:
        session.close()
