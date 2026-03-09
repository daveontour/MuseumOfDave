"""Reference import routes (import referenced images into database)."""
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request

from ....database.models import MediaMetadata, MediaBlob
from ....utils.docker_utils import translate_path_to_container
from ...deps import db
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

reference_import_job = ImportJob(
    name="Reference import",
    initial_progress={
        "status": "idle",
        "status_line": None,
        "total": 0,
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "error_message": None,
        "error_messages": [],
    },
)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_reference_images_background():
    """Background task: import referenced images into database (copy file bytes to media_blob)."""
    reference_import_job.start()

    reference_import_job.update_state(
        status="in_progress",
        status_line="Starting reference import...",
        total=0,
        processed=0,
        imported=0,
        skipped=0,
        errors=0,
        error_message=None,
        error_messages=[],
    )
    reference_import_job.broadcast("status", {"status_line": "Starting reference import..."})

    try:
        session = db.get_session()
        try:
            items = session.query(MediaMetadata).filter(
                MediaMetadata.is_referenced == True,
                MediaMetadata.source_reference.isnot(None),
                MediaMetadata.source_reference != "",
            ).all()
            total = len(items)
        finally:
            session.close()

        reference_import_job.update_state(total=total)
        status_line = f"Found {total} referenced images to import"
        reference_import_job.update_state(status_line=status_line)
        reference_import_job.broadcast("progress", reference_import_job.get_state())

        imported = 0
        skipped = 0
        errors = 0
        error_messages = []

        for i, item in enumerate(items):
            if reference_import_job.cancelled.is_set():
                reference_import_job.update_state(
                    status="cancelled",
                    status_line="Processing cancelled.",
                    processed=i,
                    imported=imported,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                )
                reference_import_job.broadcast("cancelled", reference_import_job.get_state())
                break

            path_str = translate_path_to_container(item.source_reference)
            path = Path(path_str)

            if not path.exists() or not path.is_file():
                skipped += 1
                err_msg = f"File not found: {item.source_reference}"
                error_messages.append(err_msg)
                reference_import_job.update_state(
                    processed=i + 1,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                    status_line=f"Item {i + 1}/{total}: skipped (file not found)",
                )
                reference_import_job.broadcast("progress", reference_import_job.get_state())
                continue

            try:
                image_data = path.read_bytes()
            except (IOError, OSError) as e:
                errors += 1
                err_msg = f"Failed to read {item.source_reference}: {e}"
                error_messages.append(err_msg)
                reference_import_job.update_state(
                    processed=i + 1,
                    errors=errors,
                    error_messages=error_messages,
                    status_line=f"Item {i + 1}/{total}: error reading file",
                )
                reference_import_job.broadcast("progress", reference_import_job.get_state())
                continue

            sess = db.get_session()
            try:
                blob = sess.query(MediaBlob).filter(MediaBlob.id == item.media_blob_id).first()
                meta = sess.query(MediaMetadata).filter(MediaMetadata.id == item.id).first()
                if blob and meta:
                    blob.image_data = image_data
                    blob.updated_at = datetime.now(timezone.utc)
                    meta.is_referenced = False
                    meta.updated_at = datetime.now(timezone.utc)
                    sess.commit()
                    imported += 1
                else:
                    errors += 1
                    err_msg = f"media_item {item.id} or blob not found"
                    error_messages.append(err_msg)
            except Exception as e:
                sess.rollback()
                errors += 1
                err_msg = f"Failed to update media_item {item.id}: {e}"
                error_messages.append(err_msg)
            finally:
                sess.close()

            reference_import_job.update_state(
                processed=i + 1,
                imported=imported,
                skipped=skipped,
                errors=errors,
                error_messages=error_messages,
                status_line=f"Item {i + 1}/{total}: {imported} imported, {skipped} skipped, {errors} errors",
            )
            reference_import_job.broadcast("progress", reference_import_job.get_state())

        if not reference_import_job.cancelled.is_set():
            status_msg = f"Completed: {imported} imported, {skipped} skipped, {errors} errors"
            reference_import_job.update_state(
                status="completed",
                status_line=status_msg,
                processed=total,
                imported=imported,
                skipped=skipped,
                errors=errors,
                error_message="; ".join(error_messages[:5]) if error_messages else None,
                error_messages=error_messages,
            )
            reference_import_job.broadcast("completed", reference_import_job.get_state())

    except Exception as e:
        err_msg = str(e)
        reference_import_job.update_state(
            status="error",
            error_message=err_msg,
            status_line=err_msg,
        )
        reference_import_job.broadcast("error", reference_import_job.get_state())
    finally:
        state = reference_import_job.get_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("reference_import", result, msg)
        reference_import_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/images/import-reference")
async def start_reference_import(background_tasks: BackgroundTasks):
    """Start importing referenced images into the database."""
    reference_import_job.assert_not_running()

    background_tasks.add_task(import_reference_images_background)

    return {"message": "Reference import started", "status": "started"}


@router.get("/images/import-reference/stream")
async def stream_reference_import_progress(request: Request):
    """Stream reference import progress via Server-Sent Events."""
    return reference_import_job.create_stream_response(request)


@router.post("/images/import-reference/cancel")
async def cancel_reference_import():
    """Cancel reference import if in progress."""
    return reference_import_job.cancel()


@router.get("/images/import-reference/status")
async def get_reference_import_status():
    """Get current status of reference import."""
    return reference_import_job.status()
