"""Custom voices CRUD endpoints + merged voice list."""

import json
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import db
from ...database.models import CustomVoice

router = APIRouter()

_VOICE_FILE = 'src/api/static/data/voice_instructions.json'


def _load_builtin_voices() -> dict:
    try:
        with open(_VOICE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _slugify(name: str) -> str:
    """Convert a display name to a safe key: lowercase, spaces→underscores, strip non-alnum."""
    slug = name.strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return f"custom_{slug}"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class VoiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    instructions: str
    creativity: float = 0.5


class VoiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    creativity: Optional[float] = None


class CustomVoiceResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str]
    instructions: str
    creativity: float
    is_custom: bool = True
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/voices")
async def list_voices():
    """Return all built-in voices merged with custom DB voices.

    Each entry includes an ``is_custom`` flag.  Built-in voices come first,
    followed by custom voices ordered alphabetically by name.
    """
    builtin = _load_builtin_voices()
    result = []
    for key, info in builtin.items():
        result.append({
            "key": key,
            "name": info.get("name", key),
            "description": info.get("description", ""),
            "instructions": info.get("instructions", ""),
            "creativity": info.get("creativity", 0.5),
            "is_custom": False,
            "id": None,
        })

    session = db.get_session()
    try:
        rows = session.query(CustomVoice).order_by(CustomVoice.name).all()
        for row in rows:
            result.append({
                "id": row.id,
                "key": row.key,
                "name": row.name,
                "description": row.description or "",
                "instructions": row.instructions,
                "creativity": row.creativity,
                "is_custom": True,
            })
    finally:
        session.close()

    return result


@router.get("/api/voices/custom", response_model=list[CustomVoiceResponse])
async def list_custom_voices():
    """Return only the user-defined custom voices."""
    session = db.get_session()
    try:
        rows = session.query(CustomVoice).order_by(CustomVoice.name).all()
        return [
            CustomVoiceResponse(
                id=r.id, key=r.key, name=r.name, description=r.description,
                instructions=r.instructions, creativity=r.creativity,
                is_custom=True, created_at=r.created_at, updated_at=r.updated_at,
            )
            for r in rows
        ]
    finally:
        session.close()


@router.post("/api/voices", response_model=CustomVoiceResponse)
async def create_voice(req: VoiceCreate):
    """Create a new custom voice."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    instructions = (req.instructions or "").strip()
    if not instructions:
        raise HTTPException(status_code=400, detail="instructions are required")
    creativity = max(0.0, min(2.0, req.creativity))

    key = _slugify(name)

    # Ensure key doesn't clash with a built-in voice
    builtin = _load_builtin_voices()
    if key in builtin:
        raise HTTPException(status_code=409, detail=f"Key '{key}' conflicts with a built-in voice. Choose a different name.")

    session = db.get_session()
    try:
        existing = session.query(CustomVoice).filter(CustomVoice.key == key).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"A custom voice with key '{key}' already exists.")
        row = CustomVoice(
            key=key, name=name, description=req.description,
            instructions=instructions, creativity=creativity,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return CustomVoiceResponse(
            id=row.id, key=row.key, name=row.name, description=row.description,
            instructions=row.instructions, creativity=row.creativity,
            is_custom=True, created_at=row.created_at, updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/api/voices/{voice_id}", response_model=CustomVoiceResponse)
async def update_voice(voice_id: int, req: VoiceUpdate):
    """Update a custom voice by ID."""
    session = db.get_session()
    try:
        row = session.query(CustomVoice).filter(CustomVoice.id == voice_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Custom voice not found: id={voice_id}")
        if req.name is not None:
            name = req.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="name must not be empty")
            new_key = _slugify(name)
            builtin = _load_builtin_voices()
            if new_key in builtin:
                raise HTTPException(status_code=409, detail=f"Key '{new_key}' conflicts with a built-in voice.")
            conflict = session.query(CustomVoice).filter(
                CustomVoice.key == new_key, CustomVoice.id != voice_id
            ).first()
            if conflict:
                raise HTTPException(status_code=409, detail=f"Key '{new_key}' already used by another custom voice.")
            row.name = name
            row.key = new_key
        if req.description is not None:
            row.description = req.description
        if req.instructions is not None:
            instructions = req.instructions.strip()
            if not instructions:
                raise HTTPException(status_code=400, detail="instructions must not be empty")
            row.instructions = instructions
        if req.creativity is not None:
            row.creativity = max(0.0, min(2.0, req.creativity))
        session.commit()
        session.refresh(row)
        return CustomVoiceResponse(
            id=row.id, key=row.key, name=row.name, description=row.description,
            instructions=row.instructions, creativity=row.creativity,
            is_custom=True, created_at=row.created_at, updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/api/voices/{voice_id}")
async def delete_voice(voice_id: int):
    """Delete a custom voice by ID."""
    session = db.get_session()
    try:
        row = session.query(CustomVoice).filter(CustomVoice.id == voice_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Custom voice not found: id={voice_id}")
        session.delete(row)
        session.commit()
        return {"message": "Custom voice deleted", "id": voice_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
