"""Facebook All (combined) import routes."""
import subprocess
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional

from ....utils.docker_utils import translate_path_to_container
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ImportFacebookAllRequest(BaseModel):
    """Request model for Facebook All import."""
    directory_path: str
    user_name: Optional[str] = None


class ImportFacebookAllResponse(BaseModel):
    """Response model for Facebook All import."""
    message: str
    directory_path: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

facebook_all_job = ImportJob(
    name="Facebook All import",
    initial_progress={
        "status": "idle",
        "status_line": None,
        "error_message": None,
        # per-importer last status lines
        "messenger": {"status_line": None},
        "albums": {"status_line": None},
        "places": {"status_line": None},
        "posts": {"status_line": None},
        # messenger stats
        "conversations": 0,
        "messages_imported": 0,
        "messages_created": 0,
        "messages_updated": 0,
        "att_found": 0,
        "att_missing": 0,
        "messenger_errors": 0,
        # albums stats
        "albums_processed": 0,
        "albums_imported": 0,
        "album_images_imported": 0,
        "album_images_found": 0,
        "album_images_missing": 0,
        "albums_errors": 0,
        # places stats
        "places_imported": 0,
        "places_created": 0,
        "places_updated": 0,
        # posts stats
        "posts_processed": 0,
        "posts_imported": 0,
        "posts_updated": 0,
        "with_media": 0,
        "images_imported": 0,
        "images_found": 0,
        "images_missing": 0,
        "posts_errors": 0,
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


def _parse_facebook_all_stderr_line(line: str) -> tuple:
    """Parse a stderr line from facebook-all, returning (source, content)."""
    for prefix, source in [
        ("[FACEBOOK] ", "messenger"),
        ("[ALBUMS] ", "albums"),
        ("[PLACES] ", "places"),
        ("[POSTS] ", "posts"),
    ]:
        if line.startswith(prefix):
            return source, line[len(prefix):]
    return None, line


def _parse_facebook_all_stdout(stdout: str) -> dict:
    """Parse import-processor facebook-all stdout."""
    stats = {}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("FACEBOOK_COMPLETE: "):
            parts = line[len("FACEBOOK_COMPLETE: "):].split()
            kv = dict(p.split("=", 1) for p in parts if "=" in p)
            stats["conversations"] = int(kv.get("conversations", 0))
            stats["messages_imported"] = int(kv.get("messages", 0))
            stats["messages_created"] = int(kv.get("created", 0))
            stats["messages_updated"] = int(kv.get("updated", 0))
            stats["att_found"] = int(kv.get("att_found", 0))
            stats["att_missing"] = int(kv.get("att_missing", 0))
            stats["messenger_errors"] = int(kv.get("errors", 0))
        elif line.startswith("ALBUMS_COMPLETE: "):
            parts = line[len("ALBUMS_COMPLETE: "):].split()
            kv = dict(p.split("=", 1) for p in parts if "=" in p)
            stats["albums_processed"] = int(kv.get("albums", 0))
            stats["albums_imported"] = int(kv.get("albums_imported", 0))
            stats["album_images_imported"] = int(kv.get("images", 0))
            stats["album_images_found"] = int(kv.get("found", 0))
            stats["album_images_missing"] = int(kv.get("missing", 0))
            stats["albums_errors"] = int(kv.get("errors", 0))
        elif line.startswith("PLACES_COMPLETE: "):
            parts = line[len("PLACES_COMPLETE: "):].split()
            kv = dict(p.split("=", 1) for p in parts if "=" in p)
            stats["places_imported"] = int(kv.get("places", 0))
            stats["places_created"] = int(kv.get("created", 0))
            stats["places_updated"] = int(kv.get("updated", 0))
        elif line.startswith("POSTS_COMPLETE: "):
            parts = line[len("POSTS_COMPLETE: "):].split()
            kv = dict(p.split("=", 1) for p in parts if "=" in p)
            stats["posts_processed"] = int(kv.get("posts", 0))
            stats["posts_imported"] = int(kv.get("new", 0))
            stats["posts_updated"] = int(kv.get("updated", 0))
            stats["with_media"] = int(kv.get("with_media", 0))
            stats["images_imported"] = int(kv.get("images", 0))
            stats["images_found"] = int(kv.get("found", 0))
            stats["images_missing"] = int(kv.get("missing", 0))
            stats["posts_errors"] = int(kv.get("errors", 0))
    return stats


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_facebook_all_background_subprocess(directory_path: str, user_name: Optional[str]):
    """Background task: run import-processor facebook-all, stream stderr via SSE, broadcast completion."""
    facebook_all_job.start()

    facebook_all_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        conversations=0, messages_imported=0, messages_created=0, messages_updated=0,
        att_found=0, att_missing=0, messenger_errors=0,
        albums_processed=0, albums_imported=0, album_images_imported=0,
        album_images_found=0, album_images_missing=0, albums_errors=0,
        places_imported=0, places_created=0, places_updated=0,
        posts_processed=0, posts_imported=0, posts_updated=0,
        with_media=0, images_imported=0, images_found=0, images_missing=0, posts_errors=0,
    )
    facebook_all_job.broadcast("status", {"status_line": "Starting import-processor..."})

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        path_str = str(Path(translate_path_to_container(directory_path)).resolve())
        args = [str(binary), "facebook-all", "--path", path_str]
        if user_name:
            args.extend(["--user-name", user_name])
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in iter(proc.stderr.readline, ""):
            if facebook_all_job.cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                facebook_all_job.update_state(status="cancelled", status_line="Import cancelled.")
                facebook_all_job.broadcast("cancelled", facebook_all_job.get_state())
                break
            line = line.rstrip()
            if line:
                source, _content = _parse_facebook_all_stderr_line(line)
                facebook_all_job.update_state(status_line=line)
                facebook_all_job.broadcast("status", {"status_line": line, "source": source})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_all_job.cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            facebook_all_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
            facebook_all_job.broadcast("error", facebook_all_job.get_state())
        elif not facebook_all_job.cancelled.is_set():
            parsed = _parse_facebook_all_stdout(stdout or "")
            status_msg = "Import completed with errors" if "with errors" in (stdout or "") else "Import completed"
            facebook_all_job.update_state(status="completed", status_line=status_msg, **parsed)
            facebook_all_job.broadcast("completed", facebook_all_job.get_state())
    except FileNotFoundError as e:
        facebook_all_job.update_state(status="error", error_message=str(e), status_line=str(e))
        facebook_all_job.broadcast("error", facebook_all_job.get_state())
    except Exception as e:
        err_msg = str(e)
        facebook_all_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
        facebook_all_job.broadcast("error", facebook_all_job.get_state())
    finally:
        state = facebook_all_job.get_state()
        _record_import_control_last_run("facebook_all", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        facebook_all_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/facebook/all/import", response_model=ImportFacebookAllResponse)
async def import_facebook_all(
    request: ImportFacebookAllRequest,
    background_tasks: BackgroundTasks,
):
    """Import all Facebook data (Messenger, albums, places, posts) in parallel using import-processor."""
    facebook_all_job.assert_not_running()

    input_path = Path(translate_path_to_container(request.directory_path)).resolve()
    if not input_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist: {request.directory_path}"
        )

    background_tasks.add_task(
        import_facebook_all_background_subprocess,
        str(input_path),
        request.user_name,
    )

    return ImportFacebookAllResponse(
        message="Facebook All import started",
        directory_path=request.directory_path,
        timestamp=datetime.utcnow(),
    )


@router.get("/facebook/all/import/stream")
async def stream_facebook_all_import_progress(request: Request):
    """Stream Facebook All import progress via Server-Sent Events (SSE)."""
    return facebook_all_job.create_stream_response(request)


@router.post("/facebook/all/import/cancel")
async def cancel_facebook_all_import():
    """Cancel Facebook All import if in progress."""
    return facebook_all_job.cancel()


@router.get("/facebook/all/import/status")
async def get_facebook_all_import_status():
    """Get current status of Facebook All import."""
    return facebook_all_job.status()
