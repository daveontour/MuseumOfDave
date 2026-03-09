"""Facebook Places import and view routes."""
import subprocess
import re
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Query
from pydantic import BaseModel
from typing import Optional, List

from ....database.models import Locations
from ....utils.docker_utils import translate_path_to_container
from ...deps import db
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ImportFacebookPlacesRequest(BaseModel):
    """Request model for importing Facebook places from JSON file."""
    file_path: str


class ImportFacebookPlacesResponse(BaseModel):
    """Response model for Facebook places import."""
    success: bool
    places_imported: int
    places_created: int
    places_updated: int
    errors: List[str]
    status_message: Optional[str] = None


class FacebookPlaceResponse(BaseModel):
    """Response model for a Facebook place."""
    id: int
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    region: Optional[str] = None
    altitude: Optional[float] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class FacebookPlacesListResponse(BaseModel):
    """Response model for list of Facebook places."""
    places: List[FacebookPlaceResponse]
    total: int


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

facebook_places_job = ImportJob(
    name="Facebook Places import",
    initial_progress={
        "status": "idle",
        "status_line": None,
        "places_imported": 0,
        "places_created": 0,
        "places_updated": 0,
        "errors": [],
        "error_message": None,
    },
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_import_processor_path() -> Path:
    """Resolve path to import-processor binary."""
    import os
    env_path = os.environ.get("IMPORT_PROCESSOR_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    import_processor_dir = project_root / "import-processor"
    if os.name == "nt":
        binary = import_processor_dir / "import-processor.exe"
    else:
        binary = import_processor_dir / "import-processor"
    if not binary.exists():
        raise FileNotFoundError(
            f"import-processor not found at {binary}. "
            "Build it with: cd import-processor && go build -o import-processor ./cmd/import-processor"
        )
    return binary


def _parse_facebook_places_stdout(stdout: str):
    """Parse import-processor facebook-places stdout."""
    places_imported = 0
    places_created = 0
    places_updated = 0
    errors: list[str] = []
    status_parts: list[str] = []
    match = re.search(
        r"Places imported: (\d+) \(created: (\d+), updated: (\d+)\)",
        stdout,
    )
    if match:
        places_imported = int(match.group(1))
        places_created = int(match.group(2))
        places_updated = int(match.group(3))
        status_parts.append(f"Places imported: {places_imported} (created: {places_created}, updated: {places_updated})")
    in_errors = False
    for line in stdout.splitlines():
        line = line.rstrip()
        if line == "Errors/warnings:":
            in_errors = True
            continue
        if in_errors and line.startswith("  - "):
            errors.append(line[4:].strip())
    status_message = "Import completed successfully. " + "; ".join(status_parts) if status_parts else "Import completed."
    if errors:
        status_message += f" {len(errors)} error(s)/warning(s) reported."
    return places_imported, places_created, places_updated, errors, status_message


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_facebook_places_background_subprocess(file_path: str):
    """Background task: run import-processor facebook-places, stream stderr lines via SSE, broadcast completion."""
    facebook_places_job.start()

    facebook_places_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        places_imported=0,
        places_created=0,
        places_updated=0,
        errors=[],
    )
    facebook_places_job.broadcast("status", {"status_line": "Starting import-processor..."})

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        path_str = str(Path(translate_path_to_container(file_path)).resolve())
        proc = subprocess.Popen(
            [str(binary), "facebook-places", "--path", path_str],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in iter(proc.stderr.readline, ""):
            if facebook_places_job.cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                facebook_places_job.update_state(status="cancelled", status_line="Import cancelled.")
                facebook_places_job.broadcast("cancelled", facebook_places_job.get_state())
                break
            line = line.rstrip()
            if line:
                facebook_places_job.update_state(status_line=line)
                facebook_places_job.broadcast("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_places_job.cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            facebook_places_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
            facebook_places_job.broadcast("error", facebook_places_job.get_state())
        elif not facebook_places_job.cancelled.is_set():
            places_imported, places_created, places_updated, errors, status_message = _parse_facebook_places_stdout(stdout or "")
            facebook_places_job.update_state(
                status="completed",
                status_line=status_message,
                places_imported=places_imported,
                places_created=places_created,
                places_updated=places_updated,
                errors=errors,
            )
            facebook_places_job.broadcast("completed", facebook_places_job.get_state())
    except FileNotFoundError as e:
        facebook_places_job.update_state(status="error", error_message=str(e), status_line=str(e))
        facebook_places_job.broadcast("error", facebook_places_job.get_state())
    except Exception as e:
        err_msg = str(e)
        facebook_places_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
        facebook_places_job.broadcast("error", facebook_places_job.get_state())
    finally:
        state = facebook_places_job.get_state()
        _record_import_control_last_run("facebook_places", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        facebook_places_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/facebook/import-places", response_model=ImportFacebookPlacesResponse)
async def import_facebook_places(
    request: ImportFacebookPlacesRequest,
    background_tasks: BackgroundTasks,
):
    """Import places from a Facebook posts JSON file using import-processor."""
    facebook_places_job.assert_not_running()

    file_path = Path(translate_path_to_container(request.file_path))
    print(f"Facebook Places Import directory_path: {file_path} (Dockerized: {file_path.exists()})")
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {request.file_path}"
        )
    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a file: {request.file_path}"
        )

    background_tasks.add_task(
        import_facebook_places_background_subprocess,
        str(file_path),
    )

    return ImportFacebookPlacesResponse(
        success=True,
        places_imported=0,
        places_created=0,
        places_updated=0,
        errors=[],
        status_message="Import started",
    )


@router.get("/facebook/import-places/stream")
async def stream_facebook_places_import_progress(request: Request):
    """Stream Facebook Places import progress via Server-Sent Events (stderr lines)."""
    return facebook_places_job.create_stream_response(request)


@router.post("/facebook/import-places/cancel")
async def cancel_facebook_places_import():
    """Cancel Facebook Places import if in progress."""
    return facebook_places_job.cancel()


@router.get("/facebook/import-places/status")
async def get_facebook_places_import_status():
    """Get current status of Facebook Places import."""
    return facebook_places_job.status()


@router.get("/facebook/places", response_model=FacebookPlacesListResponse)
async def get_facebook_places(
    name: Optional[str] = Query(None, description="Filter by place name (partial match, case-insensitive)"),
    region: Optional[str] = Query(None, description="Filter by region (partial match, case-insensitive)"),
    limit: Optional[int] = Query(100, description="Maximum number of places to return", ge=1, le=1000),
    offset: Optional[int] = Query(0, description="Number of places to skip", ge=0)
):
    """Retrieve Facebook places imported from Facebook posts JSON."""
    session = db.get_session()
    try:
        query = session.query(Locations).filter(Locations.source == 'facebook')

        if name:
            query = query.filter(Locations.name.ilike(f'%{name}%'))

        if region:
            query = query.filter(Locations.region.ilike(f'%{region}%'))

        total = query.count()

        places = query.order_by(Locations.name).offset(offset).limit(limit).all()

        places_list = [
            FacebookPlaceResponse(
                id=place.id,
                name=place.name,
                description=place.description,
                address=place.address,
                latitude=place.latitude,
                longitude=place.longitude,
                region=place.region,
                altitude=place.altitude,
                source=place.source,
                source_reference=place.source_reference,
                created_at=place.created_at,
                updated_at=place.updated_at
            )
            for place in places
        ]

        return FacebookPlacesListResponse(
            places=places_list,
            total=total
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving Facebook places: {str(e)}"
        )
    finally:
        session.close()
