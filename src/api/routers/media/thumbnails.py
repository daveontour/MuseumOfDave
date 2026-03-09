"""Thumbnail processing routes."""
import os
import subprocess
import threading
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func

from ...deps import db
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

thumbnails_job = ImportJob(
    name="Thumbnail processing",
    initial_progress={
        "phase": None,
        "phase1_scanned": 0,
        "phase1_updated": 0,
        "phase2_scanned": 0,
        "phase2_total": 0,
        "phase2_processed": 0,
        "phase2_errors": 0,
        "status": "idle",
        "error_message": None,
        "status_line": None,
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


def _parse_thumbnails_stdout(stdout: str):
    """Parse import-processor thumbnails stdout."""
    import re
    total = 0
    processed = 0
    errors = 0
    m1 = re.search(r"Total items to process: (\d+)", stdout)
    if m1:
        total = int(m1.group(1))
    m2 = re.search(r"Successfully processed: (\d+)", stdout)
    if m2:
        processed = int(m2.group(1))
    m3 = re.search(r"Errors: (\d+)", stdout)
    if m3:
        errors = int(m3.group(1))
    status_parts: list[str] = []
    if total > 0:
        status_parts.append(f"Total: {total}")
    if processed > 0:
        status_parts.append(f"Processed: {processed}")
    if errors > 0:
        status_parts.append(f"Errors: {errors}")
    status_message = "Thumbnail processing completed. " + "; ".join(status_parts) if status_parts else "Thumbnail processing completed."
    return (total, processed, errors, status_message)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def process_thumbnails_background_subprocess(reprocess: bool = False):
    """Background task: run import-processor thumbnails, stream stderr via SSE, broadcast completion."""
    thumbnails_job.start()

    thumbnails_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        phase=None,
        phase1_scanned=0,
        phase1_updated=0,
        phase2_scanned=0,
        phase2_total=0,
        phase2_processed=0,
        phase2_errors=0,
    )
    thumbnails_job.broadcast("status", {"status_line": "Starting import-processor..."})

    session = db.get_session()
    session.execute(func.update_location_regions())
    session.execute(func.update_image_location_regions())
    session.commit()

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        args = [str(binary), "thumbnails"]
        if reprocess:
            args.append("--reprocess")
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
                    if thumbnails_job.cancelled.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        thumbnails_job.update_state(status_line=line)
                        thumbnails_job.broadcast("status", {"status_line": line})
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
        if thumbnails_job.cancelled.is_set():
            proc.terminate()
            proc.wait(timeout=10)
            thumbnails_job.update_state(status="cancelled", status_line="Processing cancelled.")
            thumbnails_job.broadcast("cancelled", thumbnails_job.get_state())
        else:
            proc.wait(timeout=600)
            if proc.returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
                thumbnails_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
                thumbnails_job.broadcast("error", thumbnails_job.get_state())
            else:
                total, processed, errors, status_message = _parse_thumbnails_stdout(stdout or "")
                thumbnails_job.update_state(
                    status="completed",
                    status_line=status_message,
                    phase2_total=total,
                    phase2_processed=processed,
                    phase2_errors=errors,
                )
                thumbnails_job.broadcast("completed", thumbnails_job.get_state())
    except FileNotFoundError as e:
        thumbnails_job.update_state(status="error", error_message=str(e), status_line=str(e))
        thumbnails_job.broadcast("error", thumbnails_job.get_state())
    except Exception as e:
        err_msg = str(e)
        thumbnails_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
        thumbnails_job.broadcast("error", thumbnails_job.get_state())
    finally:
        #Update the region information for the locations
        session = db.get_session()
        session.execute(func.update_location_regions())
        session.execute(func.update_image_location_regions())
        session.commit()

        state = thumbnails_job.get_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("thumbnails", result, msg)
        thumbnails_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/images/process-thumbnails")
async def start_thumbnail_processing(
    background_tasks: BackgroundTasks,
    reprocess: bool = False,
):
    """Start thumbnail processing."""
    thumbnails_job.assert_not_running()

    background_tasks.add_task(
        process_thumbnails_background_subprocess,
        reprocess,
    )

    return {
        "message": "Thumbnail processing started",
        "status": "started"
    }


@router.post("/images/process-thumbnails/async")
async def start_thumbnail_processing_async(
    background_tasks: BackgroundTasks,
    reprocess: bool = False,
):
    """Start thumbnail processing asynchronously."""
    thumbnails_job.assert_not_running()

    background_tasks.add_task(
        process_thumbnails_background_subprocess,
        reprocess,
    )

    return JSONResponse(status_code=202, content={"status": "accepted"})


@router.get("/images/process-thumbnails/stream")
async def stream_thumbnail_processing_progress(request: Request):
    """Stream thumbnail processing progress via Server-Sent Events (SSE)."""
    return thumbnails_job.create_stream_response(request)


@router.post("/images/process-thumbnails/cancel")
async def cancel_thumbnail_processing():
    """Cancel thumbnail processing if it is in progress."""
    return thumbnails_job.cancel()


@router.get("/images/process-thumbnails/status")
async def get_thumbnail_processing_status():
    """Get the current status of thumbnail processing."""
    return thumbnails_job.status()
