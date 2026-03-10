"""Interests CRUD endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..deps import db
from ...database.models import Interest

router = APIRouter()


class InterestCreate(BaseModel):
    name: str


class InterestUpdate(BaseModel):
    name: str


class InterestResponse(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/api/interests", response_model=list[InterestResponse])
async def list_interests():
    """List all interests."""
    session = db.get_session()
    try:
        rows = session.query(Interest).order_by(Interest.name).all()
        return [
            InterestResponse(
                id=r.id,
                name=r.name or "",
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    finally:
        session.close()


@router.get("/api/interests/{interest_id}", response_model=InterestResponse)
async def get_interest(interest_id: int):
    """Get a single interest by ID."""
    session = db.get_session()
    try:
        row = session.query(Interest).filter(Interest.id == interest_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Interest not found: id={interest_id}")
        return InterestResponse(
            id=row.id,
            name=row.name or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    finally:
        session.close()


@router.post("/api/interests", response_model=InterestResponse)
async def create_interest(req: InterestCreate):
    """Create a new interest."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    session = db.get_session()
    try:
        existing = session.query(Interest).filter(Interest.name == name).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Interest already exists: {name}")
        row = Interest(name=name)
        session.add(row)
        session.commit()
        session.refresh(row)
        return InterestResponse(
            id=row.id,
            name=row.name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/api/interests/{interest_id}", response_model=InterestResponse)
async def update_interest(interest_id: int, req: InterestUpdate):
    """Update an existing interest."""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    session = db.get_session()
    try:
        row = session.query(Interest).filter(Interest.id == interest_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Interest not found: id={interest_id}")
        existing = session.query(Interest).filter(Interest.name == name, Interest.id != interest_id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Interest already exists: {name}")
        row.name = name
        session.commit()
        session.refresh(row)
        return InterestResponse(
            id=row.id,
            name=row.name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/api/interests/{interest_id}")
async def delete_interest(interest_id: int):
    """Delete an interest by ID."""
    session = db.get_session()
    try:
        row = session.query(Interest).filter(Interest.id == interest_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Interest not found: id={interest_id}")
        session.delete(row)
        session.commit()
        return {"message": "Interest deleted", "id": interest_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
