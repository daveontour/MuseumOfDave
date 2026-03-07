"""Saved chat response CRUD endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import saved_response_service

router = APIRouter()


class SavedResponseCreate(BaseModel):
    title: str
    content: str
    voice: Optional[str] = None
    llm_provider: Optional[str] = None


class SavedResponseUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    voice: Optional[str] = None
    llm_provider: Optional[str] = None


@router.get("/api/saved-responses")
async def list_saved_responses():
    """Return all saved responses, newest first."""
    rows = saved_response_service.list_all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "content": r.content,
            "voice": r.voice,
            "llm_provider": r.llm_provider,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/api/saved-responses/{id}")
async def get_saved_response(id: int):
    """Get a single saved response by ID."""
    row = saved_response_service.get_by_id(id)
    if not row:
        raise HTTPException(status_code=404, detail="Saved response not found")
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "voice": row.voice,
        "llm_provider": row.llm_provider,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/api/saved-responses")
async def create_saved_response(item: SavedResponseCreate):
    """Create a new saved response."""
    if not item.title or not item.title.strip():
        raise HTTPException(status_code=400, detail="Title must not be empty")
    row = saved_response_service.create(
        item.title.strip(),
        item.content or "",
        voice=item.voice,
        llm_provider=item.llm_provider,
    )
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "voice": row.voice,
        "llm_provider": row.llm_provider,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.put("/api/saved-responses/{id}")
async def update_saved_response(id: int, item: SavedResponseUpdate):
    """Update a saved response."""
    row = saved_response_service.update(
        id,
        title=item.title,
        content=item.content,
        voice=item.voice,
        llm_provider=item.llm_provider,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Saved response not found")
    return {
        "id": row.id,
        "title": row.title,
        "content": row.content,
        "voice": row.voice,
        "llm_provider": row.llm_provider,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.delete("/api/saved-responses/{id}")
async def delete_saved_response(id: int):
    """Delete a saved response."""
    deleted = saved_response_service.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved response not found")
    return {"deleted": True, "id": id}
