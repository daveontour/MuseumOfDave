"""Image export routes (export all images to filesystem)."""
import mimetypes
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import joinedload

from ....database.models import MediaMetadata
from ....utils.docker_utils import translate_path_to_container
from ...deps import db
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExportImagesRequest(BaseModel):
    """Request model for exporting images to filesystem."""
    target_directory: str


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

image_export_job = ImportJob(
    name="Image export",
    initial_progress={
        "status": "idle",
        "status_line": None,
        "total": 0,
        "processed": 0,
        "exported": 0,
        "skipped": 0,
        "errors": 0,
        "error_message": None,
        "error_messages": [],
    },
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_extension_for_media_type(media_type: Optional[str]) -> str:
    """Get file extension from media_type. Returns 'jpg' as fallback."""
    mt = media_type or "image/jpeg"
    ext = mimetypes.guess_extension(mt)
    if ext:
        return ext.lstrip(".")
    return "jpg"


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def export_images_background(target_directory: str):
    """Background task: export all images to filesystem with subdirs of max 200 files."""
    print(f"[ImageExport] Starting export to: {target_directory}")

    image_export_job.start()

    image_export_job.update_state(
        status="in_progress",
        status_line="Starting image export...",
        total=0,
        processed=0,
        exported=0,
        skipped=0,
        errors=0,
        error_message=None,
        error_messages=[],
    )
    image_export_job.broadcast("status", {"status_line": "Starting image export..."})

    try:
        path_str = translate_path_to_container(target_directory)
        target_dir = Path(path_str).resolve()
        print(f"[ImageExport] Resolved target dir: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=True)

        session = db.get_session()
        try:
            total = session.query(MediaMetadata).count()
        finally:
            session.close()

        print(f"[ImageExport] Found {total} images to export")

        image_export_job.update_state(total=total)
        status_line = f"Found {total} images to export"
        image_export_job.update_state(status_line=status_line)
        image_export_job.broadcast("progress", image_export_job.get_state())

        exported = 0
        skipped = 0
        errors = 0
        error_messages = []
        last_id = 0

        for i in range(total):
            if image_export_job.cancelled.is_set():
                image_export_job.update_state(
                    status="cancelled",
                    status_line="Export cancelled.",
                    processed=i,
                    exported=exported,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                )
                image_export_job.broadcast("cancelled", image_export_job.get_state())
                break

            sess = db.get_session()
            try:
                item = (
                    sess.query(MediaMetadata)
                    .options(joinedload(MediaMetadata.media_blob))
                    .filter(MediaMetadata.id > last_id)
                    .order_by(MediaMetadata.id)
                    .limit(1)
                    .first()
                )
                if not item:
                    break
                last_id = item.id
                item_id = item.id
                media_type = item.media_type
                is_referenced = item.is_referenced
                source_reference = item.source_reference
                image_data = None
                if item.media_blob and item.media_blob.image_data:
                    image_data = bytes(item.media_blob.image_data)
            finally:
                sess.close()

            if image_data is None:
                if is_referenced and source_reference:
                    src_path = Path(translate_path_to_container(source_reference))
                    if src_path.exists() and src_path.is_file():
                        try:
                            image_data = src_path.read_bytes()
                        except (IOError, OSError) as e:
                            errors += 1
                            err_msg = f"Failed to read {source_reference}: {e}"
                            error_messages.append(err_msg)
                            image_export_job.update_state(
                                processed=i + 1,
                                errors=errors,
                                error_messages=error_messages,
                                status_line=f"Item {i + 1}/{total}: error reading file",
                            )
                            image_export_job.broadcast("progress", image_export_job.get_state())
                            continue
                    else:
                        skipped += 1
                        err_msg = f"File not found: {source_reference}"
                        error_messages.append(err_msg)
                        image_export_job.update_state(
                            processed=i + 1,
                            skipped=skipped,
                            errors=errors,
                            error_messages=error_messages,
                            status_line=f"Item {i + 1}/{total}: skipped (file not found)",
                        )
                        image_export_job.broadcast("progress", image_export_job.get_state())
                        continue
                else:
                    skipped += 1
                    error_messages.append(f"media_item {item_id}: no image data")
                    image_export_job.update_state(
                        processed=i + 1,
                        skipped=skipped,
                        errors=errors,
                        error_messages=error_messages,
                        status_line=f"Item {i + 1}/{total}: skipped (no data)",
                    )
                    image_export_job.broadcast("progress", image_export_job.get_state())
                    continue

            ext = _get_extension_for_media_type(media_type)
            subdir_index = i // 400
            subdir_name = f"{subdir_index:03d}"
            subdir_path = target_dir / subdir_name
            subdir_path.mkdir(parents=True, exist_ok=True)
            filename = f"{item_id}.{ext}"
            file_path = subdir_path / filename

            try:
                file_path.write_bytes(image_data)
                exported += 1
            except (IOError, OSError) as e:
                errors += 1
                err_msg = f"Failed to write {file_path}: {e}"
                error_messages.append(err_msg)

            image_export_job.update_state(
                processed=i + 1,
                exported=exported,
                skipped=skipped,
                errors=errors,
                error_messages=error_messages,
                status_line=f"Item {i + 1}/{total}: {exported} exported, {skipped} skipped, {errors} errors",
            )
            image_export_job.broadcast("progress", image_export_job.get_state())

        if not image_export_job.cancelled.is_set():
            status_msg = f"Completed: {exported} exported, {skipped} skipped, {errors} errors"
            print(f"[ImageExport] {status_msg}")
            image_export_job.update_state(
                status="completed",
                status_line=status_msg,
                processed=total,
                exported=exported,
                skipped=skipped,
                errors=errors,
                error_message="; ".join(error_messages[:5]) if error_messages else None,
                error_messages=error_messages,
            )
            image_export_job.broadcast("completed", image_export_job.get_state())

    except Exception as e:
        import traceback
        err_msg = str(e)
        print(f"[ImageExport] Error: {err_msg}")
        traceback.print_exc()
        image_export_job.update_state(
            status="error",
            error_message=err_msg,
            status_line=err_msg,
        )
        image_export_job.broadcast("error", image_export_job.get_state())
    finally:
        state = image_export_job.get_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("image_export", result, msg)
        image_export_job.finish()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/images/export")
async def start_image_export(request: ExportImagesRequest, background_tasks: BackgroundTasks):
    """Start exporting all images to the specified directory."""
    target_directory = request.target_directory.strip()
    if not target_directory:
        raise HTTPException(status_code=400, detail="target_directory is required")

    image_export_job.assert_not_running()

    background_tasks.add_task(export_images_background, target_directory)

    return {"message": "Image export started", "status": "started"}


@router.get("/images/export/stream")
async def stream_image_export_progress(request: Request):
    """Stream image export progress via Server-Sent Events."""
    return image_export_job.create_stream_response(request)


@router.post("/images/export/cancel")
async def cancel_image_export():
    """Cancel image export if in progress."""
    return image_export_job.cancel()


@router.get("/images/export/status")
async def get_image_export_status():
    """Get current status of image export."""
    return image_export_job.status()
