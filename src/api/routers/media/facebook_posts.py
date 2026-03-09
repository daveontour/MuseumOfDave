"""Facebook Posts import and view routes."""
import mimetypes
import subprocess
import re
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import or_, func

from ....database.models import MediaMetadata, PostMedia, FacebookPost
from ....utils.docker_utils import translate_path_to_container
from ...deps import db
from ...import_job import ImportJob
from ...state import _record_import_control_last_run

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ImportFacebookPostsRequest(BaseModel):
    """Request model for Facebook Posts import."""
    file_path: str
    export_root: Optional[str] = None


class ImportFacebookPostsResponse(BaseModel):
    """Response model for Facebook Posts import."""
    message: str
    file_path: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Job instance
# ---------------------------------------------------------------------------

facebook_posts_job = ImportJob(
    name="Facebook Posts import",
    initial_progress={
        "current_post": None,
        "posts_processed": 0,
        "total_posts": 0,
        "posts_imported": 0,
        "posts_updated": 0,
        "with_media": 0,
        "images_imported": 0,
        "images_found": 0,
        "images_missing": 0,
        "errors": 0,
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


def _parse_facebook_posts_stdout(stdout: str):
    """Parse import-processor facebook-posts stdout."""
    posts_processed = 0
    posts_imported = 0
    posts_updated = 0
    with_media = 0
    images_imported = 0
    images_found = 0
    images_missing = 0
    errors = 0
    status_parts: list[str] = []
    m1 = re.search(r"Processed (\d+) post\(s\)", stdout)
    if m1:
        posts_processed = int(m1.group(1))
    m2 = re.search(r"Posts imported: (\d+) new, (\d+) updated", stdout)
    if m2:
        posts_imported = int(m2.group(1))
        posts_updated = int(m2.group(2))
    m3 = re.search(r"Posts with media: (\d+)", stdout)
    if m3:
        with_media = int(m3.group(1))
    m4 = re.search(r"Images imported: (\d+) \(found: (\d+), missing: (\d+)\)", stdout)
    if m4:
        images_imported = int(m4.group(1))
        images_found = int(m4.group(2))
        images_missing = int(m4.group(3))
    m5 = re.search(r"Errors: (\d+)", stdout)
    if m5:
        errors = int(m5.group(1))
    if posts_processed > 0:
        status_parts.append(f"Processed {posts_processed} post(s)")
    if posts_imported > 0 or posts_updated > 0:
        status_parts.append(f"{posts_imported} new, {posts_updated} updated")
    if with_media > 0:
        status_parts.append(f"{with_media} with media ({images_imported} images)")
    if errors > 0:
        status_parts.append(f"{errors} error(s)")
    status_message = "Import completed. " + "; ".join(status_parts) if status_parts else "Import completed."
    return posts_processed, posts_imported, posts_updated, with_media, images_imported, images_found, images_missing, errors, status_message


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def import_facebook_posts_background_subprocess(file_path: str, export_root: Optional[str]):
    """Background task: run import-processor facebook-posts, stream stderr via SSE, broadcast completion."""
    facebook_posts_job.start()

    facebook_posts_job.update_state(
        status="in_progress",
        status_line="Starting import-processor...",
        posts_processed=0,
        total_posts=0,
        posts_imported=0,
        posts_updated=0,
        with_media=0,
        images_imported=0,
        images_found=0,
        images_missing=0,
        errors=0,
    )
    facebook_posts_job.broadcast("status", {"status_line": "Starting import-processor..."})

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        path_str = str(Path(translate_path_to_container(file_path)).resolve())
        args = [str(binary), "facebook-posts", "--path", path_str]
        # if export_root:
        #     args.extend(["--export-root", str(Path(translate_path_to_container(export_root)).resolve())])
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for line in iter(proc.stderr.readline, ""):
            if facebook_posts_job.cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                facebook_posts_job.update_state(status="cancelled", status_line="Import cancelled.")
                facebook_posts_job.broadcast("cancelled", facebook_posts_job.get_state())
                break
            line = line.rstrip()
            if line:
                facebook_posts_job.update_state(status_line=line)
                facebook_posts_job.broadcast("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_posts_job.cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            facebook_posts_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
            facebook_posts_job.broadcast("error", facebook_posts_job.get_state())
        elif not facebook_posts_job.cancelled.is_set():
            posts_processed, posts_imported, posts_updated, with_media, images_imported, images_found, images_missing, errors, status_message = _parse_facebook_posts_stdout(stdout or "")
            facebook_posts_job.update_state(
                status="completed",
                status_line=status_message,
                posts_processed=posts_processed,
                total_posts=posts_processed,
                posts_imported=posts_imported,
                posts_updated=posts_updated,
                with_media=with_media,
                images_imported=images_imported,
                images_found=images_found,
                images_missing=images_missing,
                errors=errors,
            )
            facebook_posts_job.broadcast("completed", facebook_posts_job.get_state())
    except FileNotFoundError as e:
        facebook_posts_job.update_state(status="error", error_message=str(e), status_line=str(e))
        facebook_posts_job.broadcast("error", facebook_posts_job.get_state())
    except Exception as e:
        err_msg = str(e)
        facebook_posts_job.update_state(status="error", error_message=err_msg, status_line=err_msg)
        facebook_posts_job.broadcast("error", facebook_posts_job.get_state())
    finally:
        state = facebook_posts_job.get_state()
        _record_import_control_last_run("facebook_posts", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        facebook_posts_job.finish()


# ---------------------------------------------------------------------------
# Import routes
# ---------------------------------------------------------------------------

@router.post("/facebook/posts/import", response_model=ImportFacebookPostsResponse)
async def import_facebook_posts(
    request: ImportFacebookPostsRequest,
    background_tasks: BackgroundTasks,
):
    """Import Facebook Posts from a JSON file or directory using import-processor."""
    facebook_posts_job.assert_not_running()

    input_path = Path(translate_path_to_container(request.file_path)).resolve()
    if not input_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Path does not exist: {request.file_path}"
        )

    background_tasks.add_task(
        import_facebook_posts_background_subprocess,
        str(input_path),
        request.export_root,
    )

    return ImportFacebookPostsResponse(
        message="Facebook Posts import started",
        file_path=request.file_path,
        timestamp=datetime.utcnow(),
    )


@router.get("/facebook/posts/import/stream")
async def stream_facebook_posts_import_progress(request: Request):
    """Stream Facebook Posts import progress via Server-Sent Events (SSE)."""
    return facebook_posts_job.create_stream_response(request)


@router.post("/facebook/posts/import/cancel")
async def cancel_facebook_posts_import():
    """Cancel Facebook Posts import if in progress."""
    return facebook_posts_job.cancel()


@router.get("/facebook/posts/import/status")
async def get_facebook_posts_import_status():
    """Get current status of Facebook Posts import."""
    return facebook_posts_job.status()


# ---------------------------------------------------------------------------
# View routes
# ---------------------------------------------------------------------------

@router.get("/facebook/posts")
async def get_facebook_posts(
    search: Optional[str] = Query(None, description="Search post text or title"),
    post_ids: Optional[str] = Query(None, description="Comma-separated post IDs to filter to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List Facebook posts sorted newest-first, with optional search, post_ids filter, and pagination."""
    session = db.get_session()
    try:
        query = session.query(
            FacebookPost.id,
            FacebookPost.timestamp,
            FacebookPost.title,
            FacebookPost.post_text,
            FacebookPost.external_url,
            FacebookPost.post_type,
            func.count(func.distinct(PostMedia.id)).label("media_count"),
        ).outerjoin(
            PostMedia, FacebookPost.id == PostMedia.post_id
        ).group_by(FacebookPost.id)

        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    FacebookPost.post_text.ilike(pattern),
                    FacebookPost.title.ilike(pattern),
                )
            )

        if post_ids:
            ids = [int(x.strip()) for x in post_ids.split(",") if x.strip()]
            if ids:
                query = query.filter(FacebookPost.id.in_(ids))

        query = query.order_by(FacebookPost.timestamp.desc().nullslast())
        total = query.count()
        offset = (page - 1) * page_size
        rows = query.offset(offset).limit(page_size).all()

        result = []
        for row in rows:
            result.append({
                "id": row.id,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "title": row.title,
                "post_text": row.post_text,
                "external_url": row.external_url,
                "post_type": row.post_type,
                "media_count": row.media_count or 0,
            })
        return {"total": total, "page": page, "page_size": page_size, "posts": result}
    finally:
        session.close()


@router.get("/facebook/posts/{post_id}/media")
async def get_facebook_post_media(post_id: int):
    """Get all media items for a specific Facebook post."""
    session = db.get_session()
    try:
        media_items = session.query(MediaMetadata).join(
            PostMedia, MediaMetadata.id == PostMedia.media_item_id
        ).filter(
            PostMedia.post_id == post_id
        ).order_by(
            MediaMetadata.created_at.asc()
        ).all()

        result = []
        for mi in media_items:
            result.append({
                "id": mi.id,
                "title": mi.title,
                "description": mi.description,
                "media_type": mi.media_type,
                "created_at": mi.created_at.isoformat() if mi.created_at else None,
            })
        return result
    finally:
        session.close()


@router.get("/facebook/posts/media/{media_id}")
async def get_facebook_post_media_blob(media_id: int):
    """Serve the image blob for a Facebook post media item."""
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).join(
            PostMedia, MediaMetadata.id == PostMedia.media_item_id
        ).filter(
            MediaMetadata.id == media_id
        ).first()

        if not media_item:
            raise HTTPException(status_code=404, detail=f"Media item {media_id} not found")

        if not media_item.media_blob or not media_item.media_blob.image_data:
            raise HTTPException(status_code=404, detail=f"Media item {media_id} has no image data")

        content_type = media_item.media_type or "image/jpeg"
        if media_item.title:
            guessed_type, _ = mimetypes.guess_type(media_item.title)
            if guessed_type:
                content_type = guessed_type

        return Response(content=media_item.media_blob.image_data, media_type=content_type)
    finally:
        session.close()
