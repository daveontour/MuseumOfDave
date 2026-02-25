"""Artefacts gallery routes."""

import json
import uuid
from datetime import datetime
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import or_

from PIL import Image

from ...database.models import Artefact, ArtefactMedia, MediaMetadata, MediaBlob
from ...database.models import utcnow
from ..deps import db

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ArtefactMediaItemResponse(BaseModel):
    """A single media item linked to an artefact."""
    id: int                    # ArtefactMedia.id (the link row)
    media_item_id: int         # MediaMetadata.id
    media_blob_id: Optional[int]
    sort_order: int
    media_type: Optional[str]
    title: Optional[str]
    thumbnail_url: str         # e.g. /images/{media_blob_id}?preview=true&type=blob


class ArtefactResponse(BaseModel):
    """Full artefact with its linked media items."""
    id: int
    name: str
    description: Optional[str]
    tags: Optional[str]
    story: Optional[str]
    created_at: datetime
    updated_at: datetime
    media_items: List[ArtefactMediaItemResponse]


class ArtefactSummaryResponse(BaseModel):
    """Lightweight artefact for gallery grid (no full story text)."""
    id: int
    name: str
    description: Optional[str]
    tags: Optional[str]
    created_at: datetime
    updated_at: datetime
    primary_thumbnail_url: Optional[str]   # first linked image thumbnail, or None


class CreateArtefactRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[str] = None
    story: Optional[str] = None


class UpdateArtefactRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    story: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_thumbnail(image_bytes: bytes, size: tuple = (400, 400)) -> bytes:
    """Generate a JPEG thumbnail from raw image bytes."""
    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail(size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _artefact_media_response(link: ArtefactMedia) -> ArtefactMediaItemResponse:
    meta = link.media_item
    blob_id = meta.media_blob_id if meta else None
    thumbnail_url = f"/images/{blob_id}?preview=true&type=blob" if blob_id else ""
    return ArtefactMediaItemResponse(
        id=link.id,
        media_item_id=link.media_item_id,
        media_blob_id=blob_id,
        sort_order=link.sort_order,
        media_type=meta.media_type if meta else None,
        title=meta.title if meta else None,
        thumbnail_url=thumbnail_url,
    )


def _artefact_full_response(artefact: Artefact) -> ArtefactResponse:
    return ArtefactResponse(
        id=artefact.id,
        name=artefact.name,
        description=artefact.description,
        tags=artefact.tags,
        story=artefact.story,
        created_at=artefact.created_at,
        updated_at=artefact.updated_at,
        media_items=[_artefact_media_response(link) for link in artefact.media],
    )


def _artefact_summary_response(artefact: Artefact) -> ArtefactSummaryResponse:
    primary_url = None
    if artefact.media:
        first = artefact.media[0]
        blob_id = first.media_item.media_blob_id if first.media_item else None
        if blob_id:
            primary_url = f"/images/{blob_id}?preview=true&type=blob"
    return ArtefactSummaryResponse(
        id=artefact.id,
        name=artefact.name,
        description=artefact.description,
        tags=artefact.tags,
        created_at=artefact.created_at,
        updated_at=artefact.updated_at,
        primary_thumbnail_url=primary_url,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/artefacts", response_model=List[ArtefactSummaryResponse])
async def list_artefacts(
    search: Optional[str] = Query(None, description="Search in name, description, tags, story"),
    tags: Optional[str] = Query(None, description="Filter by tag (partial match)"),
):
    """List all artefacts with optional search/filter."""
    session = db.get_session()
    try:
        query = session.query(Artefact)
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Artefact.name.ilike(term),
                    Artefact.description.ilike(term),
                    Artefact.tags.ilike(term),
                    Artefact.story.ilike(term),
                )
            )
        if tags:
            query = query.filter(Artefact.tags.ilike(f"%{tags}%"))
        artefacts = query.order_by(Artefact.updated_at.desc()).all()
        return [_artefact_summary_response(a) for a in artefacts]
    finally:
        session.close()


@router.get("/artefacts/export")
async def export_artefacts():
    """Export all artefacts as a downloadable JSON file. Image binary data is not included.
    Media references include source/source_reference so they can be re-linked on import
    if the same images exist in the target system.
    """
    session = db.get_session()
    try:
        artefacts_list = session.query(Artefact).order_by(Artefact.id).all()
        export_data = []
        for artefact in artefacts_list:
            media_refs = []
            for link in artefact.media:
                meta = link.media_item
                if meta:
                    media_refs.append({
                        "sort_order": link.sort_order,
                        "media_type": meta.media_type,
                        "title": meta.title,
                        "description": meta.description,
                        "tags": meta.tags,
                        "source": meta.source,
                        "source_reference": meta.source_reference,
                        "year": meta.year,
                        "month": meta.month,
                    })
            export_data.append({
                "name": artefact.name,
                "description": artefact.description,
                "tags": artefact.tags,
                "story": artefact.story,
                "created_at": artefact.created_at.isoformat() if artefact.created_at else None,
                "media_refs": media_refs,
            })
        payload = json.dumps({"version": 1, "artefacts": export_data}, indent=2, ensure_ascii=False)
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="artefacts_export.json"'},
        )
    finally:
        session.close()


@router.post("/artefacts/import")
async def import_artefacts(file: UploadFile = File(...)):
    """Import artefacts from a JSON file produced by the export endpoint.
    Image binaries are not imported; media links are re-established by matching
    source and source_reference values against existing MediaMetadata records.
    """
    raw = await file.read()
    try:
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(data, dict) or "artefacts" not in data:
        raise HTTPException(status_code=400, detail="JSON must contain an 'artefacts' key")

    artefact_list = data["artefacts"]
    if not isinstance(artefact_list, list):
        raise HTTPException(status_code=400, detail="'artefacts' must be a list")

    session = db.get_session()
    created = 0
    skipped_media = 0
    linked_media = 0
    try:
        for item in artefact_list:
            name = (item.get("name") or "").strip()
            if not name:
                continue

            artefact = Artefact(
                name=name,
                description=item.get("description"),
                tags=item.get("tags"),
                story=item.get("story"),
            )
            session.add(artefact)
            session.flush()  # get artefact.id
            created += 1

            for ref in (item.get("media_refs") or []):
                src = ref.get("source")
                src_ref = ref.get("source_reference")
                if not src or not src_ref:
                    skipped_media += 1
                    continue
                meta = session.query(MediaMetadata).filter(
                    MediaMetadata.source == src,
                    MediaMetadata.source_reference == src_ref,
                ).first()
                if meta:
                    existing_link = session.query(ArtefactMedia).filter(
                        ArtefactMedia.artefact_id == artefact.id,
                        ArtefactMedia.media_item_id == meta.id,
                    ).first()
                    if not existing_link:
                        link = ArtefactMedia(
                            artefact_id=artefact.id,
                            media_item_id=meta.id,
                            sort_order=ref.get("sort_order", 0),
                        )
                        session.add(link)
                        linked_media += 1
                else:
                    skipped_media += 1

        session.commit()
        return {
            "message": (
                f"Import complete: {created} artefact(s) created, "
                f"{linked_media} photo link(s) restored, "
                f"{skipped_media} photo reference(s) skipped (images not found in this system)."
            ),
            "created": created,
            "linked_media": linked_media,
            "skipped_media": skipped_media,
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        session.close()


@router.get("/artefacts/{artefact_id}", response_model=ArtefactResponse)
async def get_artefact(artefact_id: int):
    """Get a single artefact with all media items."""
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")
        return _artefact_full_response(artefact)
    finally:
        session.close()


@router.post("/artefacts", response_model=ArtefactResponse)
async def create_artefact(req: CreateArtefactRequest):
    """Create a new artefact."""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Artefact name is required")
    session = db.get_session()
    try:
        artefact = Artefact(
            name=req.name.strip(),
            description=req.description,
            tags=req.tags,
            story=req.story,
        )
        session.add(artefact)
        session.commit()
        session.refresh(artefact)
        return _artefact_full_response(artefact)
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating artefact: {str(e)}")
    finally:
        session.close()


@router.put("/artefacts/{artefact_id}", response_model=ArtefactResponse)
async def update_artefact(artefact_id: int, req: UpdateArtefactRequest):
    """Update artefact fields."""
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")
        if req.name is not None:
            if not req.name.strip():
                raise HTTPException(status_code=400, detail="Artefact name cannot be empty")
            artefact.name = req.name.strip()
        if req.description is not None:
            artefact.description = req.description
        if req.tags is not None:
            artefact.tags = req.tags
        if req.story is not None:
            artefact.story = req.story
        artefact.updated_at = utcnow()
        session.commit()
        session.refresh(artefact)
        return _artefact_full_response(artefact)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating artefact: {str(e)}")
    finally:
        session.close()


@router.delete("/artefacts/{artefact_id}")
async def delete_artefact(artefact_id: int):
    """Delete an artefact and its owned media (source='artefact')."""
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")

        # Collect media items that were uploaded for this artefact specifically
        orphan_media_ids = []
        for link in artefact.media:
            meta = session.query(MediaMetadata).filter(
                MediaMetadata.id == link.media_item_id
            ).first()
            if meta and meta.source == "artefact":
                # Only delete if not linked to any other artefact
                other_links = session.query(ArtefactMedia).filter(
                    ArtefactMedia.media_item_id == link.media_item_id,
                    ArtefactMedia.artefact_id != artefact_id,
                ).count()
                if other_links == 0:
                    orphan_media_ids.append(link.media_item_id)

        # Delete the artefact (cascade deletes ArtefactMedia rows)
        session.delete(artefact)
        session.flush()

        # Now delete orphaned artefact-sourced media
        for mid in orphan_media_ids:
            meta = session.query(MediaMetadata).filter(MediaMetadata.id == mid).first()
            if meta:
                blob = session.query(MediaBlob).filter(MediaBlob.id == meta.media_blob_id).first()
                session.delete(meta)
                if blob:
                    session.delete(blob)

        session.commit()
        return {"message": f"Artefact {artefact_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting artefact: {str(e)}")
    finally:
        session.close()


@router.get("/artefacts/{artefact_id}/thumbnail")
async def get_artefact_thumbnail(artefact_id: int):
    """Return the primary thumbnail image for an artefact (first linked image)."""
    session = db.get_session()
    try:
        link = (
            session.query(ArtefactMedia)
            .filter(ArtefactMedia.artefact_id == artefact_id)
            .order_by(ArtefactMedia.sort_order)
            .first()
        )
        if not link:
            raise HTTPException(status_code=404, detail="No media found for this artefact")
        meta = session.query(MediaMetadata).filter(MediaMetadata.id == link.media_item_id).first()
        if not meta:
            raise HTTPException(status_code=404, detail="Media metadata not found")
        blob = session.query(MediaBlob).filter(MediaBlob.id == meta.media_blob_id).first()
        if not blob:
            raise HTTPException(status_code=404, detail="Media blob not found")
        data = blob.thumbnail_data or blob.image_data
        if not data:
            raise HTTPException(status_code=404, detail="No image data available")
        return Response(content=data, media_type="image/jpeg")
    finally:
        session.close()


@router.post("/artefacts/{artefact_id}/media/upload", response_model=ArtefactResponse)
async def upload_artefact_media(
    artefact_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
):
    """Upload a new image and link it to the artefact."""
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")

        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        # Validate it opens as an image
        try:
            Image.open(BytesIO(image_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid image")

        media_type = file.content_type or "image/jpeg"

        # Generate thumbnail
        try:
            thumbnail_bytes = _make_thumbnail(image_bytes)
        except Exception:
            thumbnail_bytes = None

        # Determine current max sort_order for this artefact
        max_order = session.query(ArtefactMedia).filter(
            ArtefactMedia.artefact_id == artefact_id
        ).count()

        # Create blob
        blob = MediaBlob(image_data=image_bytes, thumbnail_data=thumbnail_bytes)
        session.add(blob)
        session.flush()

        # Create metadata
        safe_title = title or (file.filename or f"artefact_{artefact_id}_image")
        meta = MediaMetadata(
            media_blob_id=blob.id,
            title=safe_title,
            media_type=media_type,
            source="artefact",
            source_reference=f"artefact:{artefact_id}:{uuid.uuid4().hex[:8]}",
            processed=True,
        )
        session.add(meta)
        session.flush()

        # Create junction link
        link = ArtefactMedia(
            artefact_id=artefact_id,
            media_item_id=meta.id,
            sort_order=max_order,
        )
        session.add(link)
        artefact.updated_at = utcnow()
        session.commit()
        session.refresh(artefact)
        return _artefact_full_response(artefact)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error uploading media: {str(e)}")
    finally:
        session.close()


@router.post("/artefacts/{artefact_id}/media/{media_item_id}", response_model=ArtefactResponse)
async def link_existing_media(artefact_id: int, media_item_id: int):
    """Link an existing MediaMetadata item to an artefact."""
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")
        meta = session.query(MediaMetadata).filter(MediaMetadata.id == media_item_id).first()
        if not meta:
            raise HTTPException(status_code=404, detail=f"Media item {media_item_id} not found")

        # Prevent duplicate links
        existing = session.query(ArtefactMedia).filter(
            ArtefactMedia.artefact_id == artefact_id,
            ArtefactMedia.media_item_id == media_item_id,
        ).first()
        if existing:
            return _artefact_full_response(artefact)

        max_order = session.query(ArtefactMedia).filter(
            ArtefactMedia.artefact_id == artefact_id
        ).count()
        link = ArtefactMedia(
            artefact_id=artefact_id,
            media_item_id=media_item_id,
            sort_order=max_order,
        )
        session.add(link)
        artefact.updated_at = utcnow()
        session.commit()
        session.refresh(artefact)
        return _artefact_full_response(artefact)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error linking media: {str(e)}")
    finally:
        session.close()


@router.delete("/artefacts/{artefact_id}/media/{media_item_id}", response_model=ArtefactResponse)
async def unlink_artefact_media(artefact_id: int, media_item_id: int):
    """Remove a media item link from an artefact.
    If the media item was uploaded specifically for this artefact (source='artefact')
    and has no other links, also delete the media item itself.
    """
    session = db.get_session()
    try:
        artefact = session.query(Artefact).filter(Artefact.id == artefact_id).first()
        if not artefact:
            raise HTTPException(status_code=404, detail=f"Artefact {artefact_id} not found")

        link = session.query(ArtefactMedia).filter(
            ArtefactMedia.artefact_id == artefact_id,
            ArtefactMedia.media_item_id == media_item_id,
        ).first()
        if not link:
            raise HTTPException(status_code=404, detail="Media link not found")

        # Check if media should be deleted (artefact-owned and no other links)
        meta = session.query(MediaMetadata).filter(MediaMetadata.id == media_item_id).first()
        delete_media = False
        if meta and meta.source == "artefact":
            other = session.query(ArtefactMedia).filter(
                ArtefactMedia.media_item_id == media_item_id,
                ArtefactMedia.id != link.id,
            ).count()
            delete_media = (other == 0)

        session.delete(link)
        session.flush()

        if delete_media and meta:
            blob = session.query(MediaBlob).filter(MediaBlob.id == meta.media_blob_id).first()
            session.delete(meta)
            if blob:
                session.delete(blob)

        artefact.updated_at = utcnow()
        session.commit()
        session.refresh(artefact)
        return _artefact_full_response(artefact)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing media: {str(e)}")
    finally:
        session.close()
