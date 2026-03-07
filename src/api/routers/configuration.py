"""Application configuration CRUD endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import config_service

router = APIRouter()


class ConfigurationItem(BaseModel):
    key: str
    value: Optional[str] = None
    is_mandatory: Optional[bool] = None
    description: Optional[str] = None


class ConfigurationResponse(BaseModel):
    id: int
    key: str
    value: Optional[str]
    is_mandatory: bool
    description: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/api/configuration")
async def list_configuration():
    """Return all configuration key-value pairs stored in the database."""
    rows = config_service.get_all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "value": r.value,
            "is_mandatory": r.is_mandatory,
            "description": r.description,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


@router.post("/api/configuration")
async def upsert_configuration(item: ConfigurationItem):
    """Create or update a configuration key-value pair."""
    if not item.key or not item.key.strip():
        raise HTTPException(status_code=400, detail="Key must not be empty")
    try:
        row = config_service.set(
            item.key.strip(),
            item.value,
            is_mandatory=item.is_mandatory,
            description=item.description,
        )
        return {
            "id": row.id,
            "key": row.key,
            "value": row.value,
            "is_mandatory": row.is_mandatory,
            "description": row.description,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/configuration/{key}")
async def delete_configuration(key: str):
    """Delete a configuration key from the database (reverts to .env fallback)."""
    deleted = config_service.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found in database")
    return {"deleted": True, "key": key}


@router.post("/api/configuration/seed")
async def seed_configuration():
    """Re-seed the database from .env for any KNOWN_KEYS not yet present."""
    count = config_service.seed_from_env()
    return {"seeded": count, "message": f"Seeded {count} new key(s) from .env"}
