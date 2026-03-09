"""Media routes: Facebook Albums, Filesystem Images, Thumbnails, Facebook Places, Images CRUD."""
import math
import os
import re
import subprocess
import threading
import json
import asyncio
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, BackgroundTasks, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy import or_, func, and_
from sqlalchemy.orm import joinedload

from ...database import Database, FacebookAlbum
from ...database.models import MediaMetadata, MediaBlob, AlbumMedia, Locations, ImportControlLastRun, FacebookPost, PostMedia
from ...database.storage import ImageStorage
from ...services import ImageService
from ...services.exceptions import ServiceException, ValidationError, NotFoundError
from ...services.dto import ImageSearchFilters, MediaMetadataUpdate
from ...config import get_config
from ...utils.docker_utils import translate_path_to_container
from ..deps import db, config_service
from ..state import (
    facebook_albums_import_lock,
    facebook_albums_import_cancelled,
    facebook_albums_import_in_progress,
    update_facebook_albums_progress_state,
    get_facebook_albums_progress_state,
    broadcast_facebook_albums_progress_event_sync,
    facebook_albums_sse_clients,
    facebook_albums_sse_clients_lock,
    filesystem_import_lock,
    filesystem_import_cancelled,
    filesystem_import_in_progress,
    update_filesystem_import_progress_state,
    get_filesystem_import_progress_state,
    broadcast_filesystem_import_progress_event_sync,
    filesystem_import_sse_clients,
    filesystem_import_sse_clients_lock,
    thumbnail_processing_lock,
    thumbnail_processing_cancelled,
    thumbnail_processing_in_progress,
    update_thumbnail_processing_progress_state,
    get_thumbnail_processing_progress_state,
    broadcast_thumbnail_processing_event_sync,
    thumbnail_processing_sse_clients,
    thumbnail_processing_sse_clients_lock,
    facebook_places_import_lock,
    facebook_places_import_cancelled,
    facebook_places_import_in_progress,
    update_facebook_places_progress_state,
    get_facebook_places_progress_state,
    broadcast_facebook_places_progress_event_sync,
    facebook_places_sse_clients,
    facebook_places_sse_clients_lock,
    reference_import_lock,
    reference_import_cancelled,
    reference_import_in_progress,
    update_reference_import_progress_state,
    get_reference_import_progress_state,
    broadcast_reference_import_event_sync,
    reference_import_sse_clients,
    reference_import_sse_clients_lock,
    image_export_lock,
    image_export_cancelled,
    image_export_in_progress,
    update_image_export_progress_state,
    get_image_export_progress_state,
    broadcast_image_export_event_sync,
    image_export_sse_clients,
    image_export_sse_clients_lock,
    _record_import_control_last_run,
    facebook_posts_import_lock,
    facebook_posts_import_cancelled,
    facebook_posts_import_in_progress,
    update_facebook_posts_progress_state,
    get_facebook_posts_progress_state,
    broadcast_facebook_posts_progress_event_sync,
    facebook_posts_sse_clients,
    facebook_posts_sse_clients_lock,
    facebook_all_import_lock,
    facebook_all_import_cancelled,
    facebook_all_import_in_progress,
    update_facebook_all_progress_state,
    get_facebook_all_progress_state,
    broadcast_facebook_all_progress_event_sync,
    facebook_all_sse_clients,
    facebook_all_sse_clients_lock,
)

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


class ExportImagesRequest(BaseModel):
    """Request model for exporting images to filesystem."""
    target_directory: str


class MediaMetadataResponse(BaseModel):
    """Response model for image metadata."""
    id: int
    media_blob_id: int
    description: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    tags: Optional[str] = None
    categories: Optional[str] = None
    notes: Optional[str] = None
    available_for_task: bool = False
    media_type: Optional[str] = None
    processed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    year: Optional[int] = None
    month: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    rating: int = 5
    has_gps: bool = False
    google_maps_url: Optional[str] = None
    region: Optional[str] = None
    source: Optional[str] = None
    source_reference: Optional[str] = None

    class Config:
        from_attributes = True


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
# Helper functions
# ---------------------------------------------------------------------------

def _get_import_processor_path() -> Path:
    """Resolve path to import-processor binary. Uses IMPORT_PROCESSOR_PATH env if set."""
    env_path = os.environ.get("IMPORT_PROCESSOR_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    project_root = Path(__file__).resolve().parent.parent.parent.parent
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


def _parse_facebook_places_stdout(stdout: str) -> tuple[int, int, int, list[str], str]:
    """Parse import-processor facebook-places stdout. Returns (places_imported, places_created, places_updated, errors, status_message)."""
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


def _parse_filesystem_stdout(stdout: str) -> tuple[int, int, int, int, int, int, list[str], str]:
    """Parse import-processor filesystem stdout. Returns (total_files, files_processed, images_imported, images_referenced, images_updated, errors, error_messages, status_message)."""
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


def _parse_thumbnails_stdout(stdout: str) -> tuple[int, int, int, str]:
    """Parse import-processor thumbnails stdout. Returns (total, processed, errors, status_message)."""
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


def _parse_facebook_albums_stdout(stdout: str) -> tuple[int, int, int, int, int, int, list[str], str]:
    """Parse import-processor facebook-albums stdout. Returns (albums_processed, albums_imported, images_imported, images_found, images_missing, errors, missing_filenames, status_message)."""
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


def _parse_facebook_posts_stdout(stdout: str) -> tuple[int, int, int, int, int, int, int, int, str]:
    """Parse import-processor facebook-posts stdout.
    Returns (posts_processed, posts_imported, posts_updated, with_media, images_imported, images_found, images_missing, errors, status_message).
    """
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
# Background task functions
# ---------------------------------------------------------------------------

def import_facebook_albums_background_subprocess(directory_path: str):
    """Background task: run import-processor facebook-albums, stream stderr lines via SSE, broadcast completion."""
    global facebook_albums_import_in_progress

    with facebook_albums_import_lock:
        facebook_albums_import_in_progress = True
        facebook_albums_import_cancelled.clear()

    update_facebook_albums_progress_state(
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
    broadcast_facebook_albums_progress_event_sync("status", {"status_line": "Starting import-processor..."})

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
        # Read stderr line by line and broadcast each
        for line in iter(proc.stderr.readline, ""):
            if facebook_albums_import_cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                update_facebook_albums_progress_state(status="cancelled", status_line="Import cancelled.")
                broadcast_facebook_albums_progress_event_sync("cancelled", get_facebook_albums_progress_state())
                break
            line = line.rstrip()
            if line:
                update_facebook_albums_progress_state(status_line=line)
                broadcast_facebook_albums_progress_event_sync("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_albums_import_cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            update_facebook_albums_progress_state(status="error", error_message=err_msg, status_line=err_msg)
            broadcast_facebook_albums_progress_event_sync("error", get_facebook_albums_progress_state())
        elif not facebook_albums_import_cancelled.is_set():
            albums_processed, albums_imported, images_imported, images_found, images_missing, errors, missing_filenames, status_message = _parse_facebook_albums_stdout(stdout or "")
            update_facebook_albums_progress_state(
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
            broadcast_facebook_albums_progress_event_sync("completed", get_facebook_albums_progress_state())
    except FileNotFoundError as e:
        update_facebook_albums_progress_state(status="error", error_message=str(e), status_line=str(e))
        broadcast_facebook_albums_progress_event_sync("error", get_facebook_albums_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_facebook_albums_progress_state(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_facebook_albums_progress_event_sync("error", get_facebook_albums_progress_state())
    finally:
        state = get_facebook_albums_progress_state()
        _record_import_control_last_run("facebook_albums", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        with facebook_albums_import_lock:
            facebook_albums_import_in_progress = False


def import_filesystem_background_subprocess(
    directory_paths: List[str],
    max_images: Optional[int],
    exclude_patterns: List[str],
    reference_mode: bool = False,
):
    """Background task: run import-processor filesystem, stream stderr via SSE, broadcast completion."""
    global filesystem_import_in_progress

    with filesystem_import_lock:
        filesystem_import_in_progress = True
        filesystem_import_cancelled.clear()

    update_filesystem_import_progress_state(
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
    broadcast_filesystem_import_progress_event_sync("status", {"status_line": "Starting import-processor..."})

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
                    if filesystem_import_cancelled.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        update_filesystem_import_progress_state(status_line=line)
                        broadcast_filesystem_import_progress_event_sync("status", {"status_line": line})
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
        if filesystem_import_cancelled.is_set():
            proc.terminate()
            proc.wait(timeout=10)
            update_filesystem_import_progress_state(status="cancelled", status_line="Import cancelled.")
            broadcast_filesystem_import_progress_event_sync("cancelled", get_filesystem_import_progress_state())
        else:
            proc.wait(timeout=120)
            if proc.returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
                update_filesystem_import_progress_state(status="error", error_messages=[err_msg], status_line=err_msg)
                broadcast_filesystem_import_progress_event_sync("error", get_filesystem_import_progress_state())
            else:
                total, proc_count, imp, ref, upd, errs, err_msgs, status_message = _parse_filesystem_stdout(stdout or "")
                update_filesystem_import_progress_state(
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
                broadcast_filesystem_import_progress_event_sync("completed", get_filesystem_import_progress_state())
    except FileNotFoundError as e:
        update_filesystem_import_progress_state(status="error", error_messages=[str(e)], status_line=str(e))
        broadcast_filesystem_import_progress_event_sync("error", get_filesystem_import_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_filesystem_import_progress_state(status="error", error_messages=[err_msg], status_line=err_msg)
        broadcast_filesystem_import_progress_event_sync("error", get_filesystem_import_progress_state())
    finally:
        state = get_filesystem_import_progress_state()
        result = state.get("status", "error")
        msg = (state.get("error_messages") or [None])[0] if result == "error" else None
        _record_import_control_last_run("filesystem", result, msg)
        with filesystem_import_lock:
            filesystem_import_in_progress = False


def process_thumbnails_background_subprocess(reprocess: bool = False):
    """Background task: run import-processor thumbnails, stream stderr via SSE, broadcast completion."""
    global thumbnail_processing_in_progress

    with thumbnail_processing_lock:
        thumbnail_processing_in_progress = True
        thumbnail_processing_cancelled.clear()

    update_thumbnail_processing_progress_state(
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
    broadcast_thumbnail_processing_event_sync("status", {"status_line": "Starting import-processor..."})

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
                    if thumbnail_processing_cancelled.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        update_thumbnail_processing_progress_state(status_line=line)
                        broadcast_thumbnail_processing_event_sync("status", {"status_line": line})
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
        if thumbnail_processing_cancelled.is_set():
            proc.terminate()
            proc.wait(timeout=10)
            update_thumbnail_processing_progress_state(status="cancelled", status_line="Processing cancelled.")
            broadcast_thumbnail_processing_event_sync("cancelled", get_thumbnail_processing_progress_state())
        else:
            proc.wait(timeout=600)
            if proc.returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
                update_thumbnail_processing_progress_state(status="error", error_message=err_msg, status_line=err_msg)
                broadcast_thumbnail_processing_event_sync("error", get_thumbnail_processing_progress_state())
            else:
                total, processed, errors, status_message = _parse_thumbnails_stdout(stdout or "")
                update_thumbnail_processing_progress_state(
                    status="completed",
                    status_line=status_message,
                    phase2_total=total,
                    phase2_processed=processed,
                    phase2_errors=errors,
                )
                broadcast_thumbnail_processing_event_sync("completed", get_thumbnail_processing_progress_state())
    except FileNotFoundError as e:
        update_thumbnail_processing_progress_state(status="error", error_message=str(e), status_line=str(e))
        broadcast_thumbnail_processing_event_sync("error", get_thumbnail_processing_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_thumbnail_processing_progress_state(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_thumbnail_processing_event_sync("error", get_thumbnail_processing_progress_state())
    finally:

        #Update the region information for the locations
        session = db.get_session()
        session.execute(func.update_location_regions())
        session.execute(func.update_image_location_regions())
        session.commit()

        state = get_thumbnail_processing_progress_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("thumbnails", result, msg)
        with thumbnail_processing_lock:
            thumbnail_processing_in_progress = False


def import_facebook_places_background_subprocess(file_path: str):
    """Background task: run import-processor facebook-places, stream stderr lines via SSE, broadcast completion."""
    global facebook_places_import_in_progress

    with facebook_places_import_lock:
        facebook_places_import_in_progress = True
        facebook_places_import_cancelled.clear()

    update_facebook_places_progress_state(
        status="in_progress",
        status_line="Starting import-processor...",
        places_imported=0,
        places_created=0,
        places_updated=0,
        errors=[],
    )
    broadcast_facebook_places_progress_event_sync("status", {"status_line": "Starting import-processor..."})

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
            if facebook_places_import_cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                update_facebook_places_progress_state(status="cancelled", status_line="Import cancelled.")
                broadcast_facebook_places_progress_event_sync("cancelled", get_facebook_places_progress_state())
                break
            line = line.rstrip()
            if line:
                update_facebook_places_progress_state(status_line=line)
                broadcast_facebook_places_progress_event_sync("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_places_import_cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            update_facebook_places_progress_state(status="error", error_message=err_msg, status_line=err_msg)
            broadcast_facebook_places_progress_event_sync("error", get_facebook_places_progress_state())
        elif not facebook_places_import_cancelled.is_set():
            places_imported, places_created, places_updated, errors, status_message = _parse_facebook_places_stdout(stdout or "")
            update_facebook_places_progress_state(
                status="completed",
                status_line=status_message,
                places_imported=places_imported,
                places_created=places_created,
                places_updated=places_updated,
                errors=errors,
            )
            broadcast_facebook_places_progress_event_sync("completed", get_facebook_places_progress_state())
    except FileNotFoundError as e:
        update_facebook_places_progress_state(status="error", error_message=str(e), status_line=str(e))
        broadcast_facebook_places_progress_event_sync("error", get_facebook_places_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_facebook_places_progress_state(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_facebook_places_progress_event_sync("error", get_facebook_places_progress_state())
    finally:
        state = get_facebook_places_progress_state()
        _record_import_control_last_run("facebook_places", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        with facebook_places_import_lock:
            facebook_places_import_in_progress = False


# ---------------------------------------------------------------------------
# Facebook Albums import routes
# ---------------------------------------------------------------------------

@router.post("/facebook/albums/import", response_model=ImportFacebookAlbumsResponse)
async def import_facebook_albums(
    request: ImportFacebookAlbumsRequest,
    background_tasks: BackgroundTasks,
):
    """Import Facebook Albums from a directory structure using import-processor.

    Starts the import-processor in the background and returns immediately.
    Connect to GET /facebook/albums/import/stream for real-time stderr status updates.

    Args:
        request: Import request containing directory_path
        background_tasks: FastAPI background tasks

    Returns:
        Response indicating import has started
    """
    global facebook_albums_import_in_progress

    with facebook_albums_import_lock:
        if facebook_albums_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Facebook Albums import is already in progress",
            )

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
    """Stream Facebook Albums import progress via Server-Sent Events (SSE).

    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()

        # Add client queue to list
        with facebook_albums_sse_clients_lock:
            facebook_albums_sse_clients.append(client_queue)

        try:
            # Send initial state
            initial_state = get_facebook_albums_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with facebook_albums_sse_clients_lock:
                if client_queue in facebook_albums_sse_clients:
                    facebook_albums_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/facebook/albums/import/cancel")
async def cancel_facebook_albums_import():
    """Cancel Facebook Albums import if in progress.

    Returns:
        Status message indicating cancellation request
    """
    global facebook_albums_import_in_progress

    with facebook_albums_import_lock:
        if not facebook_albums_import_in_progress:
            return {"message": "No Facebook Albums import in progress"}

        facebook_albums_import_cancelled.set()
        return {"message": "Facebook Albums import cancellation requested"}


@router.get("/facebook/albums/import/status")
async def get_facebook_albums_import_status():
    """Get current status of Facebook Albums import.

    Returns:
        Status information about Facebook Albums import
    """
    global facebook_albums_import_in_progress

    progress_state = get_facebook_albums_progress_state()

    with facebook_albums_import_lock:
        return {
            "in_progress": facebook_albums_import_in_progress,
            "cancelled": facebook_albums_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Filesystem images import routes
# ---------------------------------------------------------------------------

@router.post("/images/import", response_model=ImportFilesystemImagesResponse)
async def import_filesystem_images(
    request: ImportFilesystemImagesRequest,
    background_tasks: BackgroundTasks
):
    """Import images from filesystem directory(ies).

    Args:
        request: Import request containing root_directory (semicolon-separated paths), optional max_images, and create_thumbnail flag
        background_tasks: FastAPI background tasks

    Returns:
        Response indicating import has started

    Raises:
        HTTPException: 400 if import is already in progress or directory invalid
    """
    global filesystem_import_in_progress

    with filesystem_import_lock:
        if filesystem_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Filesystem images import is already in progress"
            )

    # Parse semicolon-separated directory paths
    directory_paths_str = request.root_directory
    directory_paths = [path.strip() for path in directory_paths_str.split(';') if path.strip()]

    if not directory_paths:
        raise HTTPException(
            status_code=400,
            detail="At least one directory path is required"
        )

    # Validate all directory paths
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

    # Start background import task
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
    """Stream Filesystem import progress via Server-Sent Events (SSE).

    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()

        # Add client queue to list
        with filesystem_import_sse_clients_lock:
            filesystem_import_sse_clients.append(client_queue)

        try:
            # Send initial state
            initial_state = get_filesystem_import_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # If already completed/cancelled/error, send final state and return
            if initial_state.get("status") in ("completed", "cancelled", "error"):
                final_event = {
                    "type": initial_state["status"],
                    "data": initial_state
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                return

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                    progress_state = get_filesystem_import_progress_state()
                    if progress_state.get("status") in ("completed", "cancelled", "error"):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with filesystem_import_sse_clients_lock:
                if client_queue in filesystem_import_sse_clients:
                    filesystem_import_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/images/import/cancel")
async def cancel_filesystem_import():
    """Cancel Filesystem import if it is in progress.

    Returns:
        Success message indicating cancellation status
    """
    global filesystem_import_in_progress

    with filesystem_import_lock:
        if not filesystem_import_in_progress:
            return {
                "message": "No Filesystem import is currently in progress",
                "cancelled": False
            }

        filesystem_import_cancelled.set()

        return {
            "message": "Filesystem import cancellation requested. Processing will stop after current image completes.",
            "cancelled": True
        }


@router.get("/images/import/status")
async def get_filesystem_import_status():
    """Get the current status of Filesystem import.

    Returns:
        Status information about Filesystem import
    """
    global filesystem_import_in_progress

    progress_state = get_filesystem_import_progress_state()

    with filesystem_import_lock:
        return {
            "in_progress": filesystem_import_in_progress,
            "cancelled": filesystem_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Thumbnail processing routes
# ---------------------------------------------------------------------------

@router.post("/images/process-thumbnails")
async def start_thumbnail_processing(
    background_tasks: BackgroundTasks,
    reprocess: bool = False,
):
    """Start thumbnail processing.

    Args:
        reprocess: If True, reprocess all image items including already processed (re-extract EXIF).

    Returns:
        Response indicating processing has started

    Raises:
        HTTPException: 400 if processing is already in progress
    """
    global thumbnail_processing_in_progress

    with thumbnail_processing_lock:
        if thumbnail_processing_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Thumbnail processing is already in progress"
            )

    # Start background processing task
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
    """Start thumbnail processing asynchronously.

    Fire-and-forget: starts processing and returns immediately with no status.
    Use /images/process-thumbnails for a response indicating processing has started.

    Args:
        reprocess: If True, reprocess all image items including already processed (re-extract EXIF).

    Raises:
        HTTPException: 400 if processing is already in progress
    """
    global thumbnail_processing_in_progress

    with thumbnail_processing_lock:
        if thumbnail_processing_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Thumbnail processing is already in progress"
            )

    background_tasks.add_task(
        process_thumbnails_background_subprocess,
        reprocess,
    )

    return JSONResponse(status_code=202, content={"status": "accepted"})


@router.get("/images/process-thumbnails/stream")
async def stream_thumbnail_processing_progress(request: Request):
    """Stream thumbnail processing progress via Server-Sent Events (SSE).

    Returns:
        StreamingResponse with SSE events containing progress updates
    """
    async def event_generator():
        # Create a queue for this client
        client_queue = asyncio.Queue()

        # Add client queue to list
        with thumbnail_processing_sse_clients_lock:
            thumbnail_processing_sse_clients.append(client_queue)

        try:
            # Send initial state
            initial_state = get_thumbnail_processing_progress_state()
            event_data = {
                "type": "progress",
                "data": initial_state
            }
            yield f"data: {json.dumps(event_data)}\n\n"

            # If already completed/cancelled/error, send final state and return
            if initial_state.get("status") in ("completed", "cancelled", "error"):
                final_event = {
                    "type": initial_state["status"],
                    "data": initial_state
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                return

            # Keep connection alive and send events
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with timeout
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                    progress_state = get_thumbnail_processing_progress_state()
                    if progress_state.get("status") in ("completed", "cancelled", "error"):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in thumbnail processing SSE stream: {e}")
                    break
        finally:
            # Remove client queue from list
            with thumbnail_processing_sse_clients_lock:
                if client_queue in thumbnail_processing_sse_clients:
                    thumbnail_processing_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/images/process-thumbnails/cancel")
async def cancel_thumbnail_processing():
    """Cancel thumbnail processing if it is in progress.

    Returns:
        Success message indicating cancellation status
    """
    global thumbnail_processing_in_progress

    with thumbnail_processing_lock:
        if not thumbnail_processing_in_progress:
            return {
                "message": "No thumbnail processing is currently in progress",
                "cancelled": False
            }

        thumbnail_processing_cancelled.set()

        return {
            "message": "Thumbnail processing cancellation requested. Processing will stop after current item completes.",
            "cancelled": True
        }


@router.get("/images/process-thumbnails/status")
async def get_thumbnail_processing_status():
    """Get the current status of thumbnail processing.

    Returns:
        Status information about thumbnail processing
    """
    global thumbnail_processing_in_progress

    progress_state = get_thumbnail_processing_progress_state()

    with thumbnail_processing_lock:
        return {
            "in_progress": thumbnail_processing_in_progress,
            "cancelled": thumbnail_processing_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Reference import (import referenced images into database) routes
# ---------------------------------------------------------------------------

def import_reference_images_background():
    """Background task: import referenced images into database (copy file bytes to media_blob)."""
    global reference_import_in_progress

    with reference_import_lock:
        reference_import_in_progress = True
        reference_import_cancelled.clear()

    update_reference_import_progress_state(
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
    broadcast_reference_import_event_sync("status", {"status_line": "Starting reference import..."})

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

        update_reference_import_progress_state(total=total)
        status_line = f"Found {total} referenced images to import"
        update_reference_import_progress_state(status_line=status_line)
        broadcast_reference_import_event_sync("progress", get_reference_import_progress_state())

        imported = 0
        skipped = 0
        errors = 0
        error_messages = []

        for i, item in enumerate(items):
            if reference_import_cancelled.is_set():
                update_reference_import_progress_state(
                    status="cancelled",
                    status_line="Processing cancelled.",
                    processed=i,
                    imported=imported,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                )
                broadcast_reference_import_event_sync("cancelled", get_reference_import_progress_state())
                break

            path_str = translate_path_to_container(item.source_reference)
            path = Path(path_str)

            if not path.exists() or not path.is_file():
                skipped += 1
                err_msg = f"File not found: {item.source_reference}"
                error_messages.append(err_msg)
                update_reference_import_progress_state(
                    processed=i + 1,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                    status_line=f"Item {i + 1}/{total}: skipped (file not found)",
                )
                broadcast_reference_import_event_sync("progress", get_reference_import_progress_state())
                continue

            try:
                image_data = path.read_bytes()
            except (IOError, OSError) as e:
                errors += 1
                err_msg = f"Failed to read {item.source_reference}: {e}"
                error_messages.append(err_msg)
                update_reference_import_progress_state(
                    processed=i + 1,
                    errors=errors,
                    error_messages=error_messages,
                    status_line=f"Item {i + 1}/{total}: error reading file",
                )
                broadcast_reference_import_event_sync("progress", get_reference_import_progress_state())
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

            update_reference_import_progress_state(
                processed=i + 1,
                imported=imported,
                skipped=skipped,
                errors=errors,
                error_messages=error_messages,
                status_line=f"Item {i + 1}/{total}: {imported} imported, {skipped} skipped, {errors} errors",
            )
            broadcast_reference_import_event_sync("progress", get_reference_import_progress_state())

        if not reference_import_cancelled.is_set():
            status_msg = f"Completed: {imported} imported, {skipped} skipped, {errors} errors"
            update_reference_import_progress_state(
                status="completed",
                status_line=status_msg,
                processed=total,
                imported=imported,
                skipped=skipped,
                errors=errors,
                error_message="; ".join(error_messages[:5]) if error_messages else None,
                error_messages=error_messages,
            )
            broadcast_reference_import_event_sync("completed", get_reference_import_progress_state())

    except Exception as e:
        err_msg = str(e)
        update_reference_import_progress_state(
            status="error",
            error_message=err_msg,
            status_line=err_msg,
        )
        broadcast_reference_import_event_sync("error", get_reference_import_progress_state())
    finally:
        state = get_reference_import_progress_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("reference_import", result, msg)
        with reference_import_lock:
            reference_import_in_progress = False


@router.post("/images/import-reference")
async def start_reference_import(background_tasks: BackgroundTasks):
    """Start importing referenced images into the database.

    Reads files from source_reference, stores bytes in media_blob.image_data,
    and sets is_referenced=False.

    Returns:
        Response indicating import has started
    """
    global reference_import_in_progress

    with reference_import_lock:
        if reference_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Reference import is already in progress"
            )

    background_tasks.add_task(import_reference_images_background)

    return {"message": "Reference import started", "status": "started"}


@router.get("/images/import-reference/stream")
async def stream_reference_import_progress(request: Request):
    """Stream reference import progress via Server-Sent Events."""
    async def event_generator():
        client_queue = asyncio.Queue()

        with reference_import_sse_clients_lock:
            reference_import_sse_clients.append(client_queue)

        try:
            initial_state = get_reference_import_progress_state()
            event_data = {"type": "progress", "data": initial_state}
            yield f"data: {json.dumps(event_data)}\n\n"

            if initial_state.get("status") in ("completed", "cancelled", "error"):
                final_event = {"type": initial_state["status"], "data": initial_state}
                yield f"data: {json.dumps(final_event)}\n\n"
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                    progress_state = get_reference_import_progress_state()
                    if progress_state.get("status") in ("completed", "cancelled", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in reference import SSE stream: {e}")
                    break
        finally:
            with reference_import_sse_clients_lock:
                if client_queue in reference_import_sse_clients:
                    reference_import_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/images/import-reference/cancel")
async def cancel_reference_import():
    """Cancel reference import if in progress."""
    global reference_import_in_progress

    with reference_import_lock:
        if not reference_import_in_progress:
            return {"message": "No reference import is currently in progress", "cancelled": False}

    reference_import_cancelled.set()

    return {
        "message": "Reference import cancellation requested. Processing will stop after current image completes.",
        "cancelled": True,
    }


@router.get("/images/import-reference/status")
async def get_reference_import_status():
    """Get current status of reference import."""
    global reference_import_in_progress

    progress_state = get_reference_import_progress_state()

    with reference_import_lock:
        return {
            "in_progress": reference_import_in_progress,
            "cancelled": reference_import_cancelled.is_set(),
            **progress_state,
        }


# ---------------------------------------------------------------------------
# Image export (export all images to filesystem) routes
# ---------------------------------------------------------------------------

def _get_extension_for_media_type(media_type: Optional[str]) -> str:
    """Get file extension from media_type. Returns 'jpg' as fallback."""
    mt = media_type or "image/jpeg"
    ext = mimetypes.guess_extension(mt)
    if ext:
        return ext.lstrip(".")
    return "jpg"


def export_images_background(target_directory: str):
    """Background task: export all images to filesystem with subdirs of max 200 files."""
    global image_export_in_progress

    print(f"[ImageExport] Starting export to: {target_directory}")

    with image_export_lock:
        image_export_in_progress = True
        image_export_cancelled.clear()

    update_image_export_progress_state(
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
    broadcast_image_export_event_sync("status", {"status_line": "Starting image export..."})

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

        update_image_export_progress_state(total=total)
        status_line = f"Found {total} images to export"
        update_image_export_progress_state(status_line=status_line)
        broadcast_image_export_event_sync("progress", get_image_export_progress_state())

        exported = 0
        skipped = 0
        errors = 0
        error_messages = []
        last_id = 0

        for i in range(total):
            if image_export_cancelled.is_set():
                update_image_export_progress_state(
                    status="cancelled",
                    status_line="Export cancelled.",
                    processed=i,
                    exported=exported,
                    skipped=skipped,
                    errors=errors,
                    error_messages=error_messages,
                )
                broadcast_image_export_event_sync("cancelled", get_image_export_progress_state())
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
                            update_image_export_progress_state(
                                processed=i + 1,
                                errors=errors,
                                error_messages=error_messages,
                                status_line=f"Item {i + 1}/{total}: error reading file",
                            )
                            broadcast_image_export_event_sync("progress", get_image_export_progress_state())
                            continue
                    else:
                        skipped += 1
                        err_msg = f"File not found: {source_reference}"
                        error_messages.append(err_msg)
                        update_image_export_progress_state(
                            processed=i + 1,
                            skipped=skipped,
                            errors=errors,
                            error_messages=error_messages,
                            status_line=f"Item {i + 1}/{total}: skipped (file not found)",
                        )
                        broadcast_image_export_event_sync("progress", get_image_export_progress_state())
                        continue
                else:
                    skipped += 1
                    error_messages.append(f"media_item {item_id}: no image data")
                    update_image_export_progress_state(
                        processed=i + 1,
                        skipped=skipped,
                        errors=errors,
                        error_messages=error_messages,
                        status_line=f"Item {i + 1}/{total}: skipped (no data)",
                    )
                    broadcast_image_export_event_sync("progress", get_image_export_progress_state())
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

            update_image_export_progress_state(
                processed=i + 1,
                exported=exported,
                skipped=skipped,
                errors=errors,
                error_messages=error_messages,
                status_line=f"Item {i + 1}/{total}: {exported} exported, {skipped} skipped, {errors} errors",
            )
            broadcast_image_export_event_sync("progress", get_image_export_progress_state())

        if not image_export_cancelled.is_set():
            status_msg = f"Completed: {exported} exported, {skipped} skipped, {errors} errors"
            print(f"[ImageExport] {status_msg}")
            update_image_export_progress_state(
                status="completed",
                status_line=status_msg,
                processed=total,
                exported=exported,
                skipped=skipped,
                errors=errors,
                error_message="; ".join(error_messages[:5]) if error_messages else None,
                error_messages=error_messages,
            )
            broadcast_image_export_event_sync("completed", get_image_export_progress_state())

    except Exception as e:
        import traceback
        err_msg = str(e)
        print(f"[ImageExport] Error: {err_msg}")
        traceback.print_exc()
        update_image_export_progress_state(
            status="error",
            error_message=err_msg,
            status_line=err_msg,
        )
        broadcast_image_export_event_sync("error", get_image_export_progress_state())
    finally:
        state = get_image_export_progress_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        _record_import_control_last_run("image_export", result, msg)
        with image_export_lock:
            image_export_in_progress = False


@router.post("/images/export")
async def start_image_export(request: ExportImagesRequest, background_tasks: BackgroundTasks):
    """Start exporting all images to the specified directory.

    Creates subdirectories (000, 001, 002, ...) so each contains at most 400 files.

    Returns:
        Response indicating export has started
    """
    global image_export_in_progress

    target_directory = request.target_directory.strip()
    if not target_directory:
        raise HTTPException(status_code=400, detail="target_directory is required")

    with image_export_lock:
        if image_export_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Image export is already in progress"
            )

    background_tasks.add_task(export_images_background, target_directory)

    return {"message": "Image export started", "status": "started"}


@router.get("/images/export/stream")
async def stream_image_export_progress(request: Request):
    """Stream image export progress via Server-Sent Events."""
    async def event_generator():
        client_queue = asyncio.Queue()

        with image_export_sse_clients_lock:
            image_export_sse_clients.append(client_queue)

        try:
            initial_state = get_image_export_progress_state()
            event_data = {"type": "progress", "data": initial_state}
            yield f"data: {json.dumps(event_data)}\n\n"

            if initial_state.get("status") in ("completed", "cancelled", "error"):
                final_event = {"type": initial_state["status"], "data": initial_state}
                yield f"data: {json.dumps(final_event)}\n\n"
                return

            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                    progress_state = get_image_export_progress_state()
                    if progress_state.get("status") in ("completed", "cancelled", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except Exception as e:
                    print(f"Error in image export SSE stream: {e}")
                    break
        finally:
            with image_export_sse_clients_lock:
                if client_queue in image_export_sse_clients:
                    image_export_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/images/export/cancel")
async def cancel_image_export():
    """Cancel image export if in progress."""
    global image_export_in_progress

    with image_export_lock:
        if not image_export_in_progress:
            return {"message": "No image export is currently in progress", "cancelled": False}

    image_export_cancelled.set()

    return {
        "message": "Image export cancellation requested. Processing will stop after current image completes.",
        "cancelled": True,
    }


@router.get("/images/export/status")
async def get_image_export_status():
    """Get current status of image export."""
    global image_export_in_progress

    progress_state = get_image_export_progress_state()

    with image_export_lock:
        return {
            "in_progress": image_export_in_progress,
            "cancelled": image_export_cancelled.is_set(),
            **progress_state,
        }


# ---------------------------------------------------------------------------
# Facebook Posts import background task + routes
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


def import_facebook_posts_background_subprocess(file_path: str, export_root: Optional[str]):
    """Background task: run import-processor facebook-posts, stream stderr via SSE, broadcast completion."""
    global facebook_posts_import_in_progress

    with facebook_posts_import_lock:
        facebook_posts_import_in_progress = True
        facebook_posts_import_cancelled.clear()

    update_facebook_posts_progress_state(
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
    broadcast_facebook_posts_progress_event_sync("status", {"status_line": "Starting import-processor..."})

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
            if facebook_posts_import_cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                update_facebook_posts_progress_state(status="cancelled", status_line="Import cancelled.")
                broadcast_facebook_posts_progress_event_sync("cancelled", get_facebook_posts_progress_state())
                break
            line = line.rstrip()
            if line:
                update_facebook_posts_progress_state(status_line=line)
                broadcast_facebook_posts_progress_event_sync("status", {"status_line": line})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_posts_import_cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            update_facebook_posts_progress_state(status="error", error_message=err_msg, status_line=err_msg)
            broadcast_facebook_posts_progress_event_sync("error", get_facebook_posts_progress_state())
        elif not facebook_posts_import_cancelled.is_set():
            posts_processed, posts_imported, posts_updated, with_media, images_imported, images_found, images_missing, errors, status_message = _parse_facebook_posts_stdout(stdout or "")
            update_facebook_posts_progress_state(
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
            broadcast_facebook_posts_progress_event_sync("completed", get_facebook_posts_progress_state())
    except FileNotFoundError as e:
        update_facebook_posts_progress_state(status="error", error_message=str(e), status_line=str(e))
        broadcast_facebook_posts_progress_event_sync("error", get_facebook_posts_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_facebook_posts_progress_state(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_facebook_posts_progress_event_sync("error", get_facebook_posts_progress_state())
    finally:
        state = get_facebook_posts_progress_state()
        _record_import_control_last_run("facebook_posts", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        with facebook_posts_import_lock:
            facebook_posts_import_in_progress = False


@router.post("/facebook/posts/import", response_model=ImportFacebookPostsResponse)
async def import_facebook_posts(
    request: ImportFacebookPostsRequest,
    background_tasks: BackgroundTasks,
):
    """Import Facebook Posts from a JSON file or directory using import-processor."""
    global facebook_posts_import_in_progress

    with facebook_posts_import_lock:
        if facebook_posts_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Facebook Posts import is already in progress",
            )

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
    async def event_generator():
        client_queue = asyncio.Queue()
        with facebook_posts_sse_clients_lock:
            facebook_posts_sse_clients.append(client_queue)
        try:
            initial_state = get_facebook_posts_progress_state()
            yield f"data: {json.dumps({'type': 'progress', 'data': initial_state})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except Exception:
                    break
        finally:
            with facebook_posts_sse_clients_lock:
                if client_queue in facebook_posts_sse_clients:
                    facebook_posts_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/facebook/posts/import/cancel")
async def cancel_facebook_posts_import():
    """Cancel Facebook Posts import if in progress."""
    global facebook_posts_import_in_progress

    with facebook_posts_import_lock:
        if not facebook_posts_import_in_progress:
            return {"message": "No Facebook Posts import in progress"}
        facebook_posts_import_cancelled.set()
        return {"message": "Facebook Posts import cancellation requested"}


@router.get("/facebook/posts/import/status")
async def get_facebook_posts_import_status():
    """Get current status of Facebook Posts import."""
    global facebook_posts_import_in_progress

    progress_state = get_facebook_posts_progress_state()
    with facebook_posts_import_lock:
        return {
            "in_progress": facebook_posts_import_in_progress,
            "cancelled": facebook_posts_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Facebook All (combined) import background task + routes
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


def _parse_facebook_all_stderr_line(line: str) -> tuple:
    """Parse a stderr line from facebook-all, returning (source, content).
    source is 'messenger', 'albums', 'places', 'posts', or None.
    """
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
    """Parse import-processor facebook-all stdout.
    Returns a dict of combined stats from all four importers.
    """
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


def import_facebook_all_background_subprocess(directory_path: str, user_name: Optional[str]):
    """Background task: run import-processor facebook-all, stream stderr via SSE, broadcast completion."""
    global facebook_all_import_in_progress

    with facebook_all_import_lock:
        facebook_all_import_in_progress = True
        facebook_all_import_cancelled.clear()

    update_facebook_all_progress_state(
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
    broadcast_facebook_all_progress_event_sync("status", {"status_line": "Starting import-processor..."})

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
            if facebook_all_import_cancelled.is_set():
                proc.terminate()
                proc.wait(timeout=10)
                update_facebook_all_progress_state(status="cancelled", status_line="Import cancelled.")
                broadcast_facebook_all_progress_event_sync("cancelled", get_facebook_all_progress_state())
                break
            line = line.rstrip()
            if line:
                source, _content = _parse_facebook_all_stderr_line(line)
                update_facebook_all_progress_state(status_line=line)
                broadcast_facebook_all_progress_event_sync("status", {"status_line": line, "source": source})
        stdout, _ = proc.communicate()
        if proc.returncode != 0 and not facebook_all_import_cancelled.is_set():
            err_msg = (stdout or "").strip() or f"Process exited with code {proc.returncode}"
            update_facebook_all_progress_state(status="error", error_message=err_msg, status_line=err_msg)
            broadcast_facebook_all_progress_event_sync("error", get_facebook_all_progress_state())
        elif not facebook_all_import_cancelled.is_set():
            parsed = _parse_facebook_all_stdout(stdout or "")
            status_msg = "Import completed with errors" if "with errors" in (stdout or "") else "Import completed"
            update_facebook_all_progress_state(status="completed", status_line=status_msg, **parsed)
            broadcast_facebook_all_progress_event_sync("completed", get_facebook_all_progress_state())
    except FileNotFoundError as e:
        update_facebook_all_progress_state(status="error", error_message=str(e), status_line=str(e))
        broadcast_facebook_all_progress_event_sync("error", get_facebook_all_progress_state())
    except Exception as e:
        err_msg = str(e)
        update_facebook_all_progress_state(status="error", error_message=err_msg, status_line=err_msg)
        broadcast_facebook_all_progress_event_sync("error", get_facebook_all_progress_state())
    finally:
        state = get_facebook_all_progress_state()
        _record_import_control_last_run("facebook_all", state.get("status", "error"), state.get("error_message") or state.get("status_line"))
        with facebook_all_import_lock:
            facebook_all_import_in_progress = False


@router.post("/facebook/all/import", response_model=ImportFacebookAllResponse)
async def import_facebook_all(
    request: ImportFacebookAllRequest,
    background_tasks: BackgroundTasks,
):
    """Import all Facebook data (Messenger, albums, places, posts) in parallel using import-processor."""
    global facebook_all_import_in_progress

    with facebook_all_import_lock:
        if facebook_all_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Facebook All import is already in progress",
            )

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
    async def event_generator():
        client_queue = asyncio.Queue()
        with facebook_all_sse_clients_lock:
            facebook_all_sse_clients.append(client_queue)
        try:
            initial_state = get_facebook_all_progress_state()
            yield f"data: {json.dumps({'type': 'progress', 'data': initial_state})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    continue
        finally:
            with facebook_all_sse_clients_lock:
                if client_queue in facebook_all_sse_clients:
                    facebook_all_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/facebook/all/import/cancel")
async def cancel_facebook_all_import():
    """Cancel Facebook All import if in progress."""
    global facebook_all_import_in_progress

    with facebook_all_import_lock:
        if not facebook_all_import_in_progress:
            return {"message": "No Facebook All import in progress"}
        facebook_all_import_cancelled.set()
        return {"message": "Facebook All import cancellation requested"}


@router.get("/facebook/all/import/status")
async def get_facebook_all_import_status():
    """Get current status of Facebook All import."""
    global facebook_all_import_in_progress

    progress_state = get_facebook_all_progress_state()
    with facebook_all_import_lock:
        return {
            "in_progress": facebook_all_import_in_progress,
            "cancelled": facebook_all_import_cancelled.is_set(),
            **progress_state
        }


# ---------------------------------------------------------------------------
# Facebook Posts view routes
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


# ---------------------------------------------------------------------------
# Facebook album view routes
# ---------------------------------------------------------------------------

@router.get("/facebook/albums")
async def get_facebook_albums():
    """Get list of all Facebook albums.

    Returns:
        List of albums with id, name, description, cover_photo_uri, image_count
    """
    session = db.get_session()
    try:
        albums = session.query(
            FacebookAlbum.id,
            FacebookAlbum.name,
            FacebookAlbum.description,
            FacebookAlbum.cover_photo_uri,
            func.count(func.distinct(AlbumMedia.id)).label('image_count')
        ).outerjoin(
            AlbumMedia, FacebookAlbum.id == AlbumMedia.album_id
        ).group_by(
            FacebookAlbum.id
        ).order_by(
            FacebookAlbum.name
        ).all()

        result = []
        for album in albums:
            result.append({
                "id": album.id,
                "name": album.name,
                "description": album.description,
                "cover_photo_uri": album.cover_photo_uri,
                "image_count": album.image_count or 0
            })

        return result
    finally:
        session.close()


@router.get("/facebook/albums/{album_id}/images")
async def get_facebook_album_images(album_id: int):
    """Get all images for a specific Facebook album.

    Args:
        album_id: The ID of the album

    Returns:
        List of images with id, title, description, media_type, created_at
    """
    session = db.get_session()
    try:
        # Query MediaMetadata via AlbumMedia junction table
        media_items = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            AlbumMedia.album_id == album_id
        ).order_by(
            MediaMetadata.created_at.asc()
        ).all()

        result = []
        for media_item in media_items:
            result.append({
                "id": media_item.id,
                "title": media_item.title,
                "description": media_item.description,
                "media_type": media_item.media_type,
                "created_at": media_item.created_at.isoformat() if media_item.created_at else None
            })

        return result
    finally:
        session.close()


@router.get("/facebook/albums/images/{image_id}")
async def get_facebook_album_image(image_id: int):
    """Get image data for a specific Facebook album image.

    Args:
        image_id: The ID of the media item

    Returns:
        Image file content with appropriate MIME type

    Raises:
        HTTPException: 404 if image not found or not linked to an album
    """
    session = db.get_session()
    try:
        # Query MediaMetadata and verify it's linked to an album via AlbumMedia
        media_item = session.query(MediaMetadata).join(
            AlbumMedia, MediaMetadata.id == AlbumMedia.media_item_id
        ).filter(
            MediaMetadata.id == image_id
        ).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found or not linked to an album"
            )

        # Get MediaBlob
        if not media_item.media_blob or not media_item.media_blob.image_data:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} has no image data"
            )

        # Determine content type from media_type
        content_type = media_item.media_type or "image/jpeg"
        if media_item.title:
            guessed_type, _ = mimetypes.guess_type(media_item.title)
            if guessed_type:
                content_type = guessed_type

        return Response(
            content=media_item.media_blob.image_data,
            media_type=content_type
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Images search/CRUD + getLocations routes
# ---------------------------------------------------------------------------

@router.get("/images/search", response_model=List[MediaMetadataResponse])
async def search_images(
    title: Optional[str] = Query(None, description="Filter by title (partial match, case-insensitive)"),
    description: Optional[str] = Query(None, description="Filter by description (partial match, case-insensitive)"),
    author: Optional[str] = Query(None, description="Filter by author (partial match, case-insensitive)"),
    tags: Optional[str] = Query(None, description="Filter by tags (partial match, case-insensitive)"),
    categories: Optional[str] = Query(None, description="Filter by categories (partial match, case-insensitive)"),
    source: Optional[str] = Query(None, description="Filter by source (exact match, case-insensitive)"),
    source_reference: Optional[str] = Query(None, description="Filter by source_reference (partial match, case-insensitive)"),
    media_type: Optional[str] = Query(None, description="Filter by media type/MIME type (partial match, case-insensitive)"),
    year: Optional[int] = Query(None, description="Filter by year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Filter by month (1-12)"),
    has_gps: Optional[bool] = Query(None, description="Filter by whether image has GPS data"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating (1-5)"),
    rating_min: Optional[int] = Query(None, ge=1, le=5, description="Filter by minimum rating (1-5)"),
    rating_max: Optional[int] = Query(None, ge=1, le=5, description="Filter by maximum rating (1-5)"),
    available_for_task: Optional[bool] = Query(None, description="Filter by available_for_task flag"),
    processed: Optional[bool] = Query(None, description="Filter by processed flag"),
    region: Optional[str] = Query(None, description="Filter by region (partial match, case-insensitive)")
):
    """Search images by metadata criteria.

    All parameters are optional. When multiple parameters are provided, they are combined with AND logic.
    Text fields support partial matching (case-insensitive) unless otherwise specified.

    Args:
        title: Partial match on image title
        description: Partial match on image description
        author: Partial match on image author
        tags: Partial match on tags (comma-separated)
        categories: Partial match on categories (comma-separated)
        source: Exact match on source (case-insensitive)
        source_reference: Partial match on source_reference (file path)
        media_type: Partial match on media type/MIME type
        year: Filter by year
        month: Filter by month (1-12)
        has_gps: Filter by GPS data presence
        rating: Exact match on rating (1-5)
        rating_min: Minimum rating (1-5)
        rating_max: Maximum rating (1-5)
        available_for_task: Filter by available_for_task flag
        processed: Filter by processed flag
        region: Partial match on region

    Returns:
        List of MediaMetadataResponse objects matching all specified criteria
    """
    image_service = ImageService(db=db)
    try:
        # Build filters from query parameters
        filters = ImageSearchFilters(
            title=title,
            description=description,
            author=author,
            tags=tags,
            categories=categories,
            source=source,
            source_reference=source_reference,
            media_type=media_type,
            year=year,
            month=month,
            has_gps=has_gps,
            rating=rating,
            rating_min=rating_min,
            rating_max=rating_max,
            available_for_task=available_for_task,
            processed=processed,
            region=region
        )

        # Search images using service
        images = image_service.search_images(filters)

        # Convert to response models
        return [MediaMetadataResponse(**image_service.to_response_model(img)) for img in images]
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error searching images: {str(e)}"
        )


@router.get("/images/years")
async def get_distinct_years():
    """Get list of distinct years from media_items table.

    Returns:
        List of distinct years (integers) sorted in descending order
    """
    session = db.get_session()
    try:
        # Query distinct years from MediaMetadata where year is not null
        years = session.query(func.distinct(MediaMetadata.year)).filter(
            MediaMetadata.year.isnot(None)
        ).order_by(
            MediaMetadata.year.desc()
        ).all()

        # Extract year values from tuples and return as list
        year_list = [year[0] for year in years]

        return {"years": year_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct years: {str(e)}"
        )
    finally:
        session.close()


@router.get("/images/tags")
async def get_distinct_tags():
    """Get list of distinct tags from media_items table.

    Tags are stored as comma-separated strings, so this endpoint extracts
    all unique individual tags from all tag fields.

    Returns:
        List of distinct tags (strings) sorted alphabetically
    """
    session = db.get_session()
    try:
        # Query all tags from MediaMetadata where tags is not null
        tag_records = session.query(MediaMetadata.tags).filter(
            MediaMetadata.tags.isnot(None),
            MediaMetadata.tags != ''
        ).all()

        # Extract and split comma-separated tags
        all_tags = set()
        for record in tag_records:
            if record[0]:
                # Split by comma and clean up whitespace
                tags = [tag.strip() for tag in record[0].split(',') if tag.strip()]
                all_tags.update(tags)

        # Convert to sorted list
        tag_list = sorted(list(all_tags))

        return {"tags": tag_list}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving distinct tags: {str(e)}"
        )
    finally:
        session.close()


@router.get("/getLocations")
async def get_locations():
    """Get metadata of media items that have GPS data set.

    Returns:
        List of media items with GPS coordinates, including:
        - id: Media item ID
        - latitude: Latitude coordinate
        - longitude: Longitude coordinate
        - altitude: Altitude (if available)
        - title: Media title
        - description: Media description
        - year: Year the media was taken
        - month: Month the media was taken
        - tags: Tags associated with the media
        - google_maps_url: Google Maps URL (if available)
        - region: Region name (if available)
        - created_at: Creation timestamp
        - source: Source of the media item (if available)
        - source_reference: Source reference (if available)
    """
    session = db.get_session()
    try:
        # Query media items with GPS data
        # Filter by has_gps=True OR (latitude is not None AND longitude is not None)
        media_items = session.query(MediaMetadata).filter(
            or_(
                MediaMetadata.has_gps == True,
                and_(
                    MediaMetadata.latitude.isnot(None),
                    MediaMetadata.longitude.isnot(None)
                )
            )
        ).all()

        # Build response list
        locations = []
        for item in media_items:
            location_data = {
                "id": item.id,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "altitude": item.altitude,
                "title": item.title,
                "description": item.description,
                "year": item.year,
                "month": item.month,
                "tags": item.tags,
                "google_maps_url": item.google_maps_url,
                "region": item.region,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "media_type": item.media_type,
                "source": item.source,
                "source_reference": item.source_reference
            }
            locations.append(location_data)

        return {"locations": locations}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving locations: {str(e)}"
        )
    finally:
        session.close()


@router.get("/images/{image_id}")
async def get_image_content(
    image_id: int,
    type: str = Query("blob", pattern="^(blob|metadata)$", description="Type of ID: 'blob' for media_blob.id or 'metadata' for media_items.id"),
    preview: bool = Query(False, description="If True, return thumbnail instead of full image"),
    convert_heic_to_jpg: bool = Query(True, description="If True, convert HEIC images to JPG format before returning")
):
    """Get image content by ID.

    Args:
        image_id: The ID of the image (blob ID or metadata ID depending on type parameter)
        type: Type of ID - 'blob' for media_blob.id or 'metadata' for media_items.id (default: 'blob')
        preview: If True, return thumbnail instead of full image
        convert_heic_to_jpg: If True, convert HEIC images to JPG format before returning (default: True)

    Returns:
        Image binary data with appropriate content-type

    Raises:
        HTTPException: 404 if image not found or has no content
    """
    image_service = ImageService(db=db)
    try:
        image_content = image_service.get_image_content(
            image_id=image_id,
            id_type=type,
            preview=preview,
            convert_heic=convert_heic_to_jpg
        )
        # Set Content-Disposition header
        safe_filename = image_content.filename.replace('"', '\\"')
        headers = {
            "Content-Disposition": f'inline; filename="{safe_filename}"'
        }

        return Response(
            content=image_content.content,
            media_type=image_content.content_type,
            headers=headers
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image: {str(e)}"
        )


@router.put("/images/bulk-update")
async def bulk_update_images(update_data: Dict[str, Any]):
    """Bulk update multiple images with tags.

    Args:
        update_data: Dictionary containing:
            - image_ids: List of image metadata IDs to update
            - tags: Tags to apply (will be appended to existing tags)

    Returns:
        Success message with count of updated images

    Raises:
        HTTPException: 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        image_ids = update_data.get("image_ids", [])
        tags = update_data.get("tags")

        # Bulk update using service
        result = image_service.bulk_update_tags(image_ids, tags)

        return {
            "message": f"Updated {result.updated_count} image(s)",
            "updated_count": result.updated_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk updating images: {str(e)}"
        )


@router.get("/images/{image_id}/metadata", response_model=MediaMetadataResponse)
async def get_image_metadata(image_id: int):
    """Get image metadata by ID.

    Args:
        image_id: The metadata ID of the image

    Returns:
        MediaMetadataResponse with full image metadata

    Raises:
        HTTPException: 404 if image not found
    """
    session = db.get_session()
    try:
        media_item = session.query(MediaMetadata).filter(MediaMetadata.id == image_id).first()

        if not media_item:
            raise HTTPException(
                status_code=404,
                detail=f"Image with ID {image_id} not found"
            )

        # Convert to response model
        return MediaMetadataResponse(
            id=media_item.id,
            media_blob_id=media_item.media_blob_id,
            description=media_item.description,
            title=media_item.title,
            author=media_item.author,
            tags=media_item.tags,
            categories=media_item.categories,
            notes=media_item.notes,
            available_for_task=media_item.available_for_task,
            media_type=media_item.media_type,
            processed=media_item.processed,
            created_at=media_item.created_at,
            updated_at=media_item.updated_at,
            year=media_item.year,
            month=media_item.month,
            latitude=media_item.latitude,
            longitude=media_item.longitude,
            altitude=media_item.altitude,
            rating=media_item.rating or 5,
            has_gps=media_item.has_gps,
            google_maps_url=media_item.google_maps_url,
            region=media_item.region,
            source=media_item.source,
            source_reference=media_item.source_reference
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving image metadata: {str(e)}"
        )
    finally:
        session.close()


@router.put("/images/{image_id}")
async def update_image_metadata(image_id: int, update_data: Dict[str, Any]):
    """Update image metadata fields.

    Args:
        image_id: The metadata ID of the image to update
        update_data: Dictionary containing fields to update (description, tags, rating)

    Returns:
        Success message with updated image ID

    Raises:
        HTTPException: 404 if image not found, 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        # Extract allowed fields
        updates = MediaMetadataUpdate(
            description=update_data.get("description"),
            tags=update_data.get("tags"),
            rating=update_data.get("rating")
        )

        # Update metadata using service
        updated_metadata = image_service.update_image_metadata(image_id, updates)

        return {
            "message": f"Image {image_id} updated successfully",
            "image_id": image_id,
            "updated_fields": {
                "description": updates.description is not None,
                "tags": updates.tags is not None,
                "rating": updates.rating is not None
            }
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating image: {str(e)}"
        )


@router.delete("/images/bulk-delete")
async def bulk_delete_images(delete_data: Dict[str, Any]):
    """Bulk delete multiple images by their metadata IDs.

    Args:
        delete_data: Dictionary containing:
            - image_ids: List of image metadata IDs to delete

    Returns:
        Success message with count of deleted images

    Raises:
        HTTPException: 400 if validation fails
    """
    image_service = ImageService(db=db)
    try:
        image_ids = delete_data.get("image_ids", [])

        # Bulk delete using service
        result = image_service.bulk_delete_images(image_ids)

        return {
            "message": f"Deleted {result.deleted_count} image(s)",
            "deleted_count": result.deleted_count,
            "errors": result.errors
        }
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error bulk deleting images: {str(e)}"
        )


@router.delete("/images/{image_id}")
async def delete_image(image_id: int):
    """Delete an image by metadata ID.

    Args:
        image_id: The metadata ID of the image to delete

    Returns:
        Success message with image ID

    Raises:
        HTTPException: 404 if image not found
    """
    storage = ImageStorage(db=db)
    try:
        deleted = storage.delete_image_by_metadata_id(image_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Image with metadata ID {image_id} not found"
            )
        return {"message": f"Image {image_id} deleted successfully", "image_id": image_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting image: {str(e)}"
        )


@router.delete("/images")
async def delete_images(
    all: bool = Query(False, description="If True, delete all images"),
    start_id: Optional[int] = Query(None, description="Start of ID range (inclusive)"),
    end_id: Optional[int] = Query(None, description="End of ID range (inclusive)")
):
    """Delete images with options to delete all or by ID range.

    Args:
        all: If True, delete all images (requires explicit confirmation)
        start_id: Start of ID range for deletion (inclusive)
        end_id: End of ID range for deletion (inclusive)

    Returns:
        Success message with count of deleted images

    Raises:
        HTTPException: 400 if parameters are invalid, 404 if no images found
    """
    session = db.get_session()
    try:
        # Validate parameters
        if all and (start_id is not None or end_id is not None):
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both 'all=true' and ID range parameters"
            )

        if not all and start_id is None and end_id is None:
            raise HTTPException(
                status_code=400,
                detail="Must specify either 'all=true' or at least one of 'start_id' or 'end_id'"
            )

        # Build query
        query = session.query(MediaMetadata)

        if all:
            # Delete all images
            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found to delete"
                )

            # Delete all metadata records (cascade will delete blobs)
            deleted_count = query.delete(synchronize_session=False)
            session.commit()

            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count
            }
        else:
            # Delete by ID range
            if start_id is not None and end_id is not None:
                if start_id > end_id:
                    raise HTTPException(
                        status_code=400,
                        detail="start_id must be less than or equal to end_id"
                    )
                query = query.filter(
                    and_(
                        MediaMetadata.id >= start_id,
                        MediaMetadata.id <= end_id
                    )
                )
            elif start_id is not None:
                query = query.filter(MediaMetadata.id >= start_id)
            elif end_id is not None:
                query = query.filter(MediaMetadata.id <= end_id)

            # Count before deletion
            count = query.count()
            if count == 0:
                raise HTTPException(
                    status_code=404,
                    detail="No images found in the specified range"
                )

            # Delete metadata records (cascade will delete blobs)
            # Need to load relationships for cascade to work properly
            metadata_records = query.all()
            deleted_count = 0
            for metadata in metadata_records:
                # Load the relationship to ensure cascade works
                _ = metadata.image_blob
                session.delete(metadata)
                deleted_count += 1

            session.commit()

            return {
                "message": f"Successfully deleted {deleted_count} image(s)",
                "deleted_count": deleted_count,
                "start_id": start_id,
                "end_id": end_id
            }
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting images: {str(e)}"
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Facebook Places import + view routes
# ---------------------------------------------------------------------------

@router.post("/facebook/import-places", response_model=ImportFacebookPlacesResponse)
async def import_facebook_places(
    request: ImportFacebookPlacesRequest,
    background_tasks: BackgroundTasks,
):
    """Import places from a Facebook posts JSON file using import-processor.

    Starts the import-processor in the background and returns immediately.
    Connect to GET /facebook/import-places/stream for real-time stderr status updates.
    """
    global facebook_places_import_in_progress

    with facebook_places_import_lock:
        if facebook_places_import_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Facebook Places import is already in progress",
            )

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
    async def event_generator():
        client_queue = asyncio.Queue()
        with facebook_places_sse_clients_lock:
            facebook_places_sse_clients.append(client_queue)
        try:
            initial_state = get_facebook_places_progress_state()
            yield f"data: {json.dumps({'type': 'progress', 'data': initial_state})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                except Exception as e:
                    print(f"Error in Facebook Places SSE stream: {e}")
                    break
        finally:
            with facebook_places_sse_clients_lock:
                if client_queue in facebook_places_sse_clients:
                    facebook_places_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/facebook/import-places/cancel")
async def cancel_facebook_places_import():
    """Cancel Facebook Places import if in progress."""
    global facebook_places_import_in_progress
    with facebook_places_import_lock:
        if not facebook_places_import_in_progress:
            return {"message": "No Facebook Places import in progress"}
        facebook_places_import_cancelled.set()
        return {"message": "Facebook Places import cancellation requested"}


@router.get("/facebook/import-places/status")
async def get_facebook_places_import_status():
    """Get current status of Facebook Places import."""
    global facebook_places_import_in_progress
    progress_state = get_facebook_places_progress_state()
    with facebook_places_import_lock:
        return {
            "in_progress": facebook_places_import_in_progress,
            "cancelled": facebook_places_import_cancelled.is_set(),
            **progress_state
        }


@router.get("/facebook/places", response_model=FacebookPlacesListResponse)
async def get_facebook_places(
    name: Optional[str] = Query(None, description="Filter by place name (partial match, case-insensitive)"),
    region: Optional[str] = Query(None, description="Filter by region (partial match, case-insensitive)"),
    limit: Optional[int] = Query(100, description="Maximum number of places to return", ge=1, le=1000),
    offset: Optional[int] = Query(0, description="Number of places to skip", ge=0)
):
    """Retrieve Facebook places imported from Facebook posts JSON.

    Returns all locations where source='facebook', optionally filtered by name or region.

    Args:
        name: Optional filter by place name (partial match)
        region: Optional filter by region (partial match)
        limit: Maximum number of places to return (default: 100, max: 1000)
        offset: Number of places to skip for pagination (default: 0)

    Returns:
        FacebookPlacesListResponse with list of places and total count
    """
    session = db.get_session()
    try:
        # Base query: filter by source='facebook'
        query = session.query(Locations).filter(Locations.source == 'facebook')

        # Apply filters
        if name:
            query = query.filter(Locations.name.ilike(f'%{name}%'))

        if region:
            query = query.filter(Locations.region.ilike(f'%{region}%'))

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        places = query.order_by(Locations.name).offset(offset).limit(limit).all()

        # Convert to response models
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
