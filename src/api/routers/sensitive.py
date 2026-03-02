"""Sensitive and private data routes."""

import base64
import json
import secrets
import subprocess
import traceback
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


def _has_password(password: Optional[str]) -> bool:
    return bool(password and password.strip())


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


class MasterKeyRequest(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# Routes — count first to avoid FastAPI matching "count" as an {id}
# ---------------------------------------------------------------------------

_DATAHANDLER = Path(__file__).parent.parent.parent.parent / "datahandler" / "datahandler"


@router.post("/sensitive-data/master-key", status_code=201)
async def generate_master_key(request: MasterKeyRequest):
    """Generate a new RSA master key pair via the datahandler external command.

    This clears any existing master keys and creates a fresh trusted key for the
    provided password. The password is passed directly to the external command.
    """
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "generatemasterkey", request.password],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error generating master key: {result.stderr.strip()}")
        return {"message": result.stdout.strip()}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating master key: {str(e)}")


@router.get("/sensitive-data/count")
async def count_sensitive_data():
    """Return the total number of sensitive data records."""
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "getrecordcount"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error counting records: {result.stderr.strip()}")
        return json.loads(result.stdout)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error counting records: {str(e)}")


@router.get("/sensitive-data")
async def list_sensitive_data(password: Optional[str] = Query(None)):
    """List all sensitive data records via the datahandler external command.

    Returns records as JSON from stdout. If no password is supplied a random
    string is used so the command still runs but details remain unreadable.
    """
    effective_password = password if _has_password(password) else secrets.token_hex(32)
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "getrecords", effective_password],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error listing records: {result.stderr.strip()}")
        return json.loads(result.stdout)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listing records: {str(e)}")


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
    effective_password = password if _has_password(password) else secrets.token_hex(32)
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "getrecord", str(record_id), effective_password],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error getting record: {result.stderr.strip()}")
        return json.loads(result.stdout)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting record: {str(e)}")


@router.post("/sensitive-data", status_code=201)
async def create_sensitive_data(request: SensitiveDataRequest):
    """Create a new sensitive data record.

    A password must be supplied to create a record. Details are base64-encoded
    before storage. Any non-empty password is accepted.
    """
    if not _has_password(request.password):
        raise HTTPException(status_code=403, detail="A password is required to create records")

    payload = {
        "description": request.description,
        "details": request.details or "",
        "is_private": request.is_private,
        "is_sensitive": request.is_sensitive,
    }
    stdin_data = base64.b64encode(json.dumps(payload).encode()).decode()
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "createrecord", request.password],
            input=stdin_data,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error creating record: {result.stderr.strip()}")
        return {"message": result.stdout.strip()}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating record: {str(e)}")


@router.put("/sensitive-data/{record_id}")
async def update_sensitive_data(record_id: int, request: SensitiveDataUpdateRequest):
    """Update an existing sensitive data record.

    A password must be supplied to update a record. Any non-empty password is accepted.
    """
    if not _has_password(request.password):
        raise HTTPException(status_code=403, detail="A password is required to update records")

    payload = {
        "description": request.description or "",
        "details": request.details or "",
        "is_private": request.is_private or False,
        "is_sensitive": request.is_sensitive or False,
    }
    stdin_data = base64.b64encode(json.dumps(payload).encode()).decode()
    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "updaterecord", str(record_id), request.password],
            input=stdin_data,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error updating record: {result.stderr.strip()}")
        return {"message": result.stdout.strip()}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error updating record: {str(e)}")


@router.delete("/sensitive-data/{record_id}")
async def delete_sensitive_data(record_id: int, password: Optional[str] = Query(None)):
    """Delete a sensitive data record.

    A password must be supplied to delete a record. Any non-empty password is accepted.
    """
    if not _has_password(password):
        raise HTTPException(status_code=403, detail="A password is required to delete records")

    try:
        result = subprocess.run(
            [str(_DATAHANDLER), "deleterecord", str(record_id), password],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Error deleting record: {result.stderr.strip()}")
        return {"success": True, "message": result.stdout.strip()}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error deleting record: {str(e)}")
