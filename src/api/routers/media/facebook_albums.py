"""Facebook Albums import routes."""
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, List

from ....utils.docker_utils import translate_path_to_container
from ...deps import db, config_service
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ImportFacebookAlbumsRequest(BaseModel):
    """Request model for Facebook Albums import."""
    directory_path: str


class ImportFacebookAlbumsResponse(BaseModel):
    """Response model for Facebook Albums import."""
    message: str
    directory_path: str
    albums_processed: int
    albums_imported: int
    images_imported: int
    images_found: int
    images_missing: int
    missing_image_filenames: List[str] = []
    errors: int
    timestamp: datetime
    status_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

facebook_albums_job = ImportJob(
    name="Facebook Albums import",
    initial_progress={
        "current_album": None,
        "albums_processed": 0,
        "total_albums": 0,
        "albums_imported": 0,
        "images_imported": 0,
        "images_found": 0,
        "images_missing": 0,
        "missing_image_filenames": [],
        "errors": 0,
        "status": "idle",
        "error_message": None,
        "status_line": None,
    },
)


# ---------------------------------------------------------------------------
# Helper
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


def _parse_facebook_albums_stdout(stdout: str):
    """Parse import-processor facebook-albums stdout."""
    import re
    albums_processed = 0
    albums_imported = 0
    images_imported = 0
    images_found = 0
    images_missing = 0
    errors = 0
    missing_filenames: list[str] = []
    status_parts: list[str] = []
    m1 = re.search(r"Processed (\d+) album\(s\)", stdout)
    if m1:
        albums_processed = int(m1.group(1))
    m2 = re.search(r"Albums imported: (\d+)", stdout)
    if m2:
        albums_imported = int(m2.group(1))
    m3 = re.search(r"Images imported: (\d+) \(found: (\d+), missing: (\d+)\)", stdout)
    if m3:
        images_imported = int(m3.group(1))
        images_found = int(m3.group(2))
        images_missing = int(m3.group(3))
    m4 = re.search(r"Errors: (\d+)", stdout)
    if m4:
        errors = int(m4.group(1))
    in_missing = False
    for line in stdout.splitlines():
        line = line.rstrip()
        if line == "Missing image files:":
            in_missing = True
            continue
        if in_missing and line.startswith("  - "):
            missing_filenames.append(line[4:].strip())
    if albums_processed > 0:
        status_parts.append(f"Processed {albums_processed} album(s)")
    if albums_imported > 0:
        status_parts.append(f"Imported {albums_imported} album(s) with {images_imported} image(s)")
    if images_found > 0 or images_missing > 0:
        status_parts.append(f"Found {images_found}, {images_missing} missing")
    if errors > 0:
        status_parts.append(f"{errors} error(s)")
    status_message = "Import completed successfully. " + "; ".join(status_parts) if status_parts else "Import completed."
    return albums_processed, albums_imported, images_imported, images_found, images_missing, errors, missing_filenames, status_message


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_facebook_albums_background_subprocess(directory_path: str):
    """Background task: run import-processor facebook-albums, stream stderr lines via SSE, broadcast completion."""
    facebook_albums_job.start()

    facebook_albums_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        albums_processed=0,
        total_albums=0,
        albums_imported=0,
        images_imported=0,
        images_found=0,
        images_missing=0,
        missing_image_filenames=[],
        errors=0,
    )
    facebook_albums_job.broadcast("status", {"status_line": "Starting import-processor..."})

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        path_str = str(Path(translate_path_to_container(directory_path)).resolve())
        proc = subprocess.Popen(
            [str(binary), "facebook-albums", "--path", path_str],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in iter(proc.stderr.readline, ""):
            if facebook_albums_job.cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                facebook_albums_job.update_state(status="cancelled", status_line="Import cancelled.")
                facebook_albums_job.broadcast("cancelled", facebook_albums_job.get_state())
                break
            line = line.rstrip()
            if line:
                facebook_albums_job.update_state(status_line=line)
                facebook_albums_job.broadcast("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_albums_job.cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            facebook_albums_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
            facebook_albums_job.broadcast("error", facebook_albums_job.get_state())
        elif not facebook_albums_job.cancelled.is_set():
            albums_processed, albums_imported, images_imported, images_found, images_missing, errors, missing_filenames, status_message = _parse_facebook_albums_stdout(stdout or "")
            facebook_albums_job.update_state(
                status="completed",
                status_line=status_message,
                albums_processed=albums_processed,
                total_albums=albums_processed,
                albums_imported=albums_imported,
                images_imported=images_imported,
                images_found=images_found,
                images_missing=images_missing,
                missing_image_filenames=missing_filenames,
                errors=errors,
            )
            facebook_albums_job.broadcast("completed", facebook_albums_job.get_state())
    except FileNotFoundError as e:
        facebook_albums_job.update_state(status="error", error_message=str(e), status_line=str(e))
        facebook_albums_job.broadcast("error", facebook_albums_job.get_state())
    except Exception as e:
        err_msg = str(e)
        facebook_albums_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
        facebook_albums_job.broadcast("error", facebook_albums_job.get_state())
    finally:
        state = facebook_albums_job.get_state()
        _record_import_control_last_run("facebook_albums", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        facebook_albums_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/facebook/albums/import", response_model=ImportFacebookAlbumsResponse)
async def import_facebook_albums(
    request: ImportFacebookAlbumsRequest,
    background_tasks: BackgroundTasks,
):
    """Import Facebook Albums from a directory structure using import-processor."""
    facebook_albums_job.assert_not_running()

    directory_path = Path(translate_path_to_container(request.directory_path)).resolve()
    print(f"Facebook Albums Import directory_path: {directory_path} (Dockerized: {directory_path.exists()})")
    if not directory_path.exists() or not directory_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Directory does not exist or is not a directory: {request.directory_path}"
        )

    background_tasks.add_task(
        import_facebook_albums_background_subprocess,
        str(directory_path),
    )

    return ImportFacebookAlbumsResponse(
        message="Facebook Albums import started",
        directory_path=request.directory_path,
        albums_processed=0,
        albums_imported=0,
        images_imported=0,
        images_found=0,
        images_missing=0,
        missing_image_filenames=[],
        errors=0,
        timestamp=datetime.utcnow(),
        status_message=None,
    )


@router.get("/facebook/albums/import/stream")
async def stream_facebook_albums_import_progress(request: Request):
    """Stream Facebook Albums import progress via Server-Sent Events (SSE)."""
    return facebook_albums_job.create_stream_response(request)


@router.post("/facebook/albums/import/cancel")
async def cancel_facebook_albums_import():
    """Cancel Facebook Albums import if in progress."""
    return facebook_albums_job.cancel()


@router.get("/facebook/albums/import/status")
async def get_facebook_albums_import_status():
    """Get current status of Facebook Albums import."""
    return facebook_albums_job.status()
