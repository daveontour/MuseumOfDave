"""Sensitive and private data routes."""

import base64
import json
import traceback
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func

from ...database.models import SensitiveData, utcnow
from ..deps import db

router = APIRouter()


# ---------------------------------------------------------------------------
# Encoding helpers
#
# Details are stored as base64 so they appear as gibberish without a password.
# Any non-empty password triggers decoding on read and encoding on write.
# ---------------------------------------------------------------------------

def _encode(text: str) -> str:
    """Base64-encode plaintext for storage."""
    if text is None:
        return None
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _decode(encoded: str) -> str:
    """Base64-decode stored text. Returns the encoded value if decoding fails."""
    if encoded is None:
        return None
    try:
        return base64.b64decode(encoded.encode("ascii")).decode("utf-8")
    except Exception:
        return encoded


def _has_password(password: Optional[str]) -> bool:
    return bool(password and password.strip())


MASKED_CONTENT = "********************************"


def _serialise(record: SensitiveData, decode: bool, always_mask: bool = False) -> dict:
    details = MASKED_CONTENT if always_mask else (_decode(record.details) if decode else MASKED_CONTENT)
    return {
        "id": record.id,
        "description": record.description,
        "details": details,
        "is_private": record.is_private,
        "is_sensitive": record.is_sensitive,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class SensitiveDataRequest(BaseModel):
    description: str
    details: Optional[str] = None
    is_private: bool = False
    is_sensitive: bool = False
    password: Optional[str] = None


class SensitiveDataUpdateRequest(BaseModel):
    description: Optional[str] = None
    details: Optional[str] = None
    is_private: Optional[bool] = None
    is_sensitive: Optional[bool] = None
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes — count first to avoid FastAPI matching "count" as an {id}
# ---------------------------------------------------------------------------

@router.get("/sensitive-data/count")
async def count_sensitive_data():
    """Return the total number of sensitive data records."""
    session = db.get_session()
    try:
        count = session.query(func.count(SensitiveData.id)).scalar() or 0
        return {"count": count}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error counting records: {str(e)}")
    finally:
        session.close()


@router.get("/sensitive-data")
async def list_sensitive_data(password: Optional[str] = Query(None)):
    """List all sensitive data records ordered by created_at descending.

    Details are always returned as masked (********************************).
    Use GET /sensitive-data/{id} with password to view a record's content.
    """
    session = db.get_session()
    try:
        records = (
            session.query(SensitiveData)
            .order_by(SensitiveData.created_at.desc())
            .all()
        )
        return [_serialise(r, decode=False, always_mask=True) for r in records]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing records: {str(e)}")
    finally:
        session.close()


@router.get("/sensitive-data/hints")
async def get_password_hints():
    """Return a list of password hints to help users remember their password."""
    hints_path = Path(__file__).parent.parent / "static" / "data" / "password_hints.json"
    try:
        with open(hints_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        hints = data.get("hints", [])
        return {"hints": hints if isinstance(hints, list) else []}
    except FileNotFoundError:
        return {"hints": []}
    except (json.JSONDecodeError, OSError) as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading hints: {str(e)}")


@router.get("/sensitive-data/{record_id}")
async def get_sensitive_data(record_id: int, password: Optional[str] = Query(None)):
    """Get a single sensitive data record by ID.

    When any password is provided, details are decoded before returning.
    """
    session = db.get_session()
    try:
        record = session.query(SensitiveData).filter(SensitiveData.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
        decode = _has_password(password)
        return _serialise(record, decode)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting record: {str(e)}")
    finally:
        session.close()


@router.post("/sensitive-data", status_code=201)
async def create_sensitive_data(request: SensitiveDataRequest):
    """Create a new sensitive data record.

    A password must be supplied to create a record. Details are base64-encoded
    before storage. Any non-empty password is accepted.
    """
    if not _has_password(request.password):
        raise HTTPException(status_code=403, detail="A password is required to create records")

    session = db.get_session()
    try:
        record = SensitiveData(
            description=request.description,
            details=_encode(request.details),
            is_private=request.is_private,
            is_sensitive=request.is_sensitive,
        )
        if not request.is_private and not request.is_sensitive:
            record.is_sensitive = True
        if request.is_sensitive:
            record.is_private = True

        session.add(record)
        session.commit()
        session.refresh(record)
        return _serialise(record, decode=True)
    except Exception as e:
        session.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating record: {str(e)}")
    finally:
        session.close()


@router.put("/sensitive-data/{record_id}")
async def update_sensitive_data(record_id: int, request: SensitiveDataUpdateRequest):
    """Update an existing sensitive data record.

    A password must be supplied to update a record. Any non-empty password is accepted.
    """
    if not _has_password(request.password):
        raise HTTPException(status_code=403, detail="A password is required to update records")

    session = db.get_session()
    try:
        record = session.query(SensitiveData).filter(SensitiveData.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found")

        if request.description is not None:
            record.description = request.description
        if request.details is not None:
            record.details = _encode(request.details)
        if request.is_private is not None:
            record.is_private = request.is_private
        if request.is_sensitive is not None:
            record.is_sensitive = request.is_sensitive

        if not request.is_private and not request.is_sensitive:
            record.is_sensitive = True
        if request.is_sensitive:
            record.is_private = True

        record.updated_at = utcnow()
        session.commit()
        session.refresh(record)
        return _serialise(record, decode=True)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating record: {str(e)}")
    finally:
        session.close()


@router.delete("/sensitive-data/{record_id}")
async def delete_sensitive_data(record_id: int, password: Optional[str] = Query(None)):
    """Delete a sensitive data record.

    A password must be supplied to delete a record. Any non-empty password is accepted.
    """
    if not _has_password(password):
        raise HTTPException(status_code=403, detail="A password is required to delete records")

    session = db.get_session()
    try:
        record = session.query(SensitiveData).filter(SensitiveData.id == record_id).first()
        if not record:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
        session.delete(record)
        session.commit()
        return {"success": True, "message": f"Record {record_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error deleting record: {str(e)}")
    finally:
        session.close()
