"""Filesystem images import routes."""
import os
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional, List

from ....config import get_config
from ....utils.docker_utils import translate_path_to_container
from ...deps import db, config_service
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ImportFilesystemImagesRequest(BaseModel):
    """Request model for Filesystem Images import."""
    root_directory: str
    max_images: Optional[int] = None
    create_thumb_and_get_exif: bool = False
    reference_mode: bool = False


class ImportFilesystemImagesResponse(BaseModel):
    """Response model for Filesystem Images import."""
    message: str
    root_directory: str
    files_processed: int = 0
    total_files: int = 0
    images_imported: int = 0
    images_referenced: int = 0
    images_updated: int = 0
    errors: int = 0
    timestamp: datetime


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

filesystem_import_job = ImportJob(
    name="Filesystem images import",
    initial_progress={
        "status": "idle",
        "status_line": None,
        "current_file": None,
        "files_processed": 0,
        "total_files": 0,
        "images_imported": 0,
        "images_referenced": 0,
        "images_updated": 0,
        "errors": 0,
        "error_messages": [],
    },
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_import_processor_path() -> Path:
    """Resolve path to import-processor binary."""
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


def _parse_filesystem_stdout(stdout: str):
    """Parse import-processor filesystem stdout."""
    import re
    total_files = 0
    files_processed = 0
    images_imported = 0
    images_referenced = 0
    images_updated = 0
    errors = 0
    error_messages: list[str] = []
    m1 = re.search(r"Total files: (\d+)", stdout)
    if m1:
        total_files = int(m1.group(1))
    m2 = re.search(r"Files processed: (\d+)", stdout)
    if m2:
        files_processed = int(m2.group(1))
    m3 = re.search(r"Images imported: (\d+)", stdout)
    if m3:
        images_imported = int(m3.group(1))
    m_ref = re.search(r"Images referenced: (\d+)", stdout)
    if m_ref:
        images_referenced = int(m_ref.group(1))
    m4 = re.search(r"Images updated: (\d+)", stdout)
    if m4:
        images_updated = int(m4.group(1))
    m5 = re.search(r"Errors: (\d+)", stdout)
    if m5:
        errors = int(m5.group(1))
    in_errors = False
    for line in stdout.splitlines():
        line = line.rstrip()
        if line == "Error messages:":
            in_errors = True
            continue
        if in_errors and line.startswith("  - "):
            error_messages.append(line[4:].strip())
    status_parts: list[str] = []
    if total_files > 0:
        status_parts.append(f"Total files: {total_files}")
    if files_processed > 0:
        status_parts.append(f"Processed: {files_processed}")
    if images_imported > 0 or images_referenced > 0 or images_updated > 0:
        status_parts.append(f"Imported: {images_imported}, Referenced: {images_referenced}, Updated: {images_updated}")
    if errors > 0:
        status_parts.append(f"Errors: {errors}")
    status_message = "Import completed. " + "; ".join(status_parts) if status_parts else "Import completed."
    return (total_files, files_processed, images_imported, images_referenced, images_updated, errors, error_messages, status_message)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_filesystem_background_subprocess(
    directory_paths: List[str],
    max_images: Optional[int],
    exclude_patterns: List[str],
    reference_mode: bool = False,
):
    """Background task: run import-processor filesystem, stream stderr via SSE, broadcast completion."""
    filesystem_import_job.start()

    filesystem_import_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        current_file=None,
        files_processed=0,
        total_files=0,
        images_imported=0,
        images_referenced=0,
        images_updated=0,
        errors=0,
        error_messages=[],
    )
    filesystem_import_job.broadcast("status", {"status_line": "Starting import-processor..."})

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        args = [str(binary), "filesystem"]
        for p in directory_paths:
            args.extend(["--path", str(Path(translate_path_to_container(p)).resolve())])
        for pat in exclude_patterns:
            args.extend(["--exclude", pat])
        if max_images and max_images > 0:
            args.extend(["--max", str(max_images)])
        if reference_mode:
            args.append("--reference")
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_parts: list[str] = []

        def read_stderr():
            try:
                for line in iter(proc.stderr.readline, ""):
                    if filesystem_import_job.cancelled.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        filesystem_import_job.update_state(status_line=line)
                        filesystem_import_job.broadcast("status", {"status_line": line})
            except Exception:
                pass

        def read_stdout():
            try:
                while True:
                    chunk = proc.stdout.read(8192)
                    if not chunk:
                        break
                    stdout_parts.append(chunk)
            except Exception:
                pass

        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread.start()
        stdout_thread.start()
        stderr_thread.join()
        stdout_thread.join()
        stdout = "".join(stdout_parts)
        if filesystem_import_job.cancelled.is_set():
            proc.terminate()
            proc.wait(timeout=10)
            filesystem_import_job.update_state(status="cancelled", status_line="Import cancelled.")
            filesystem_import_job.broadcast("cancelled", filesystem_import_job.get_state())
        else:
            proc.wait(timeout=120)
            if proc.returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
                filesystem_import_job.update_state(status="error", error_messages=[err_msg], status_line=err_msg)
                filesystem_import_job.broadcast("error", filesystem_import_job.get_state())
            else:
                total, proc_count, imp, ref, upd, errs, err_msgs, status_message = _parse_filesystem_stdout(stdout or "")
                filesystem_import_job.update_state(
                    status="completed",
                    status_line=status_message,
                    total_files=total,
                    files_processed=proc_count,
                    images_imported=imp,
                    images_referenced=ref,
                    images_updated=upd,
                    errors=errs,
                    error_messages=err_msgs,
                )
                filesystem_import_job.broadcast("completed", filesystem_import_job.get_state())
    except FileNotFoundError as e:
        filesystem_import_job.update_state(status="error", error_messages=[str(e)], status_line=str(e))
        filesystem_import_job.broadcast("error", filesystem_import_job.get_state())
    except Exception as e:
        err_msg = str(e)
        filesystem_import_job.update_state(status="error", error_messages=[err_msg], status_line=err_msg)
        filesystem_import_job.broadcast("error", filesystem_import_job.get_state())
    finally:
        state = filesystem_import_job.get_state()
        result = state.get("status", "error")
        msg = (state.get("error_messages") or [None])[0] if result == "error" else None
        _record_import_control_last_run("filesystem", result, msg)
        filesystem_import_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/images/import", response_model=ImportFilesystemImagesResponse)
async def import_filesystem_images(
    request: ImportFilesystemImagesRequest,
    background_tasks: BackgroundTasks
):
    """Import images from filesystem directory(ies)."""
    filesystem_import_job.assert_not_running()

    directory_paths_str = request.root_directory
    directory_paths = [path.strip() for path in directory_paths_str.split(';') if path.strip()]

    if not directory_paths:
        raise HTTPException(
            status_code=400,
            detail="At least one directory path is required"
        )

    invalid_paths = []
    validated_paths = []
    for path_str in directory_paths:
        directory_path = Path(translate_path_to_container(path_str))
        print(f"Filesystem Image Import directory_path: {directory_path} (Dockerized: {directory_path.exists()})")
        if not directory_path.exists() or not directory_path.is_dir():
            invalid_paths.append(path_str)
        else:
            validated_paths.append(str(directory_path))

    if invalid_paths:
        raise HTTPException(
            status_code=400,
            detail=f"One or more directories do not exist or are not directories: {', '.join(invalid_paths)}"
        )

    config = get_config()
    exclude_patterns = config.get_filesystem_exclude_patterns(config_service=config_service)

    background_tasks.add_task(
        import_filesystem_background_subprocess,
        validated_paths,
        request.max_images,
        exclude_patterns,
        request.reference_mode,
    )

    return ImportFilesystemImagesResponse(
        message="Filesystem images import started",
        root_directory=request.root_directory,
        files_processed=0,
        total_files=0,
        images_imported=0,
        images_updated=0,
        errors=0,
        timestamp=datetime.utcnow()
    )


@router.get("/images/import/stream")
async def stream_filesystem_import_progress(request: Request):
    """Stream Filesystem import progress via Server-Sent Events (SSE)."""
    return filesystem_import_job.create_stream_response(request)


@router.post("/images/import/cancel")
async def cancel_filesystem_import():
    """Cancel Filesystem import if it is in progress."""
    return filesystem_import_job.cancel()


@router.get("/images/import/status")
async def get_filesystem_import_status():
    """Get the current status of Filesystem import."""
    return filesystem_import_job.status()
