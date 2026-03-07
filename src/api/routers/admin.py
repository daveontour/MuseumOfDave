"""Admin, system, and utility routes."""
import json
import os
import platform
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, extract
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from ...database.models import (
    ImportControlLastRun,
    Message,
    MessageAttachment,
    MediaMetadata,
    MediaBlob,
    Attachment,
    AlbumMedia,
    FacebookAlbum,
    Contacts,
    Email,
    Artefact,
    ReferenceDocument,
    Places,
    Locations,
    CompleteProfile,
)
from ...config import get_config
from ..deps import db, templates, subject_config_service, config_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_subject_template_context():
    """Build template context dict from subject configuration."""
    subject_configuration = subject_config_service.get_configuration()
    if subject_configuration:
        subject_name = subject_configuration.subject_name
        subject_gender = subject_configuration.gender
        subject_family_name = subject_configuration.family_name
        subject_other_names = subject_configuration.other_names
        subject_email_addresses = subject_configuration.email_addresses
        subject_phone_numbers = subject_configuration.phone_numbers
        subject_whatsapp_handle = subject_configuration.whatsapp_handle
        subject_instagram_handle = subject_configuration.instagram_handle
    else:
        subject_name = "<Error>"
        subject_gender = "Male"
        subject_family_name = None
        subject_other_names = None
        subject_email_addresses = None
        subject_phone_numbers = None
        subject_whatsapp_handle = None
        subject_instagram_handle = None

    subject_name_possessive = subject_name + "'s"
    him = "him" if subject_gender == "Male" else "her"
    his = "his" if subject_gender == "Male" else "her"
    he = "he" if subject_gender == "Male" else "she"
    himself = "himself" if subject_gender == "Male" else "herself"
    owner_image = "male.png" if subject_gender == "Male" else "female.png"
    owner_image_small = "male_sm.png" if subject_gender == "Male" else "female_sm.png"
    admirer_image = "female.png" if subject_gender == "Male" else "male.png"
    admirer_image_small = "female_sm.png" if subject_gender == "Male" else "male_sm.png"

    return {
        "owners": subject_name_possessive,
        "owner": subject_name,
        "full_name": subject_name + " " + subject_family_name,
        "his": his,
        "he": he,
        "him": him,
        "himself": himself,
        "owner_image": owner_image,
        "owner_image_small": owner_image_small,
        "admirer_image": admirer_image,
        "admirer_image_small": admirer_image_small,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the new page."""

    platform_name = platform.system()
    if platform_name == "Windows":
        print("Windows platform detected")
    else:
        print("Linux platform detected")

    subject_context = get_subject_template_context()
    page_title = os.getenv("PAGE_TITLE", "Digital Museum of SUBJECT_NAME")
    page_title = page_title.replace("SUBJECT_NAME", subject_context["owner"])

    subject_configuration = subject_config_service.get_configuration()
    is_subject_not_init = (
        subject_configuration is not None  
        and subject_configuration.subject_name == "-"
        and subject_configuration.family_name == "-"
    )
    template_name = "non_user_init.template.html" if is_subject_not_init else "index.template.html"

    print(f"Page title: {page_title}")
    return templates.TemplateResponse(
        template_name,
        {"request": request, "page_title": page_title, **subject_context}
    )

@router.get("/api/suggestions")
async def get_suggestions():
    path = Path(__file__).parent.parent / "static" / "data" / "suggestions.json"
    content = path.read_text(encoding="utf-8")
    template = templates.env.from_string(content)
    subject_context = get_subject_template_context()
    rendered = template.render(
        **subject_context
    )
    return JSONResponse(
        content=json.loads(rendered),
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )

@router.get("/static/js/museum/foundation.js")
async def get_foundation_js():
    path = Path(__file__).parent.parent / "static" / "js" / "museum" / "foundation.js"
    content = path.read_text(encoding="utf-8")
    template = templates.env.from_string(content)
    subject_context = get_subject_template_context()
    rendered = template.render(
        **subject_context
    )
    return HTMLResponse(
        content=rendered,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
@router.get("/static/js/museum/modals-people.js")
async def get_foundation_js():
    path = Path(__file__).parent.parent / "static" / "js" / "museum" / "modals-people.js"
    content = path.read_text(encoding="utf-8")
    template = templates.env.from_string(content)
    subject_context = get_subject_template_context()
    rendered = template.render(
        **subject_context
    )
    return HTMLResponse(
        content=rendered,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )

@router.get("/health")
async def health_check():
    """Root endpoint - returns a welcome message."""
    return {
        "message": "Welcome to the Museum API",
        "endpoints": {
            "GET /": "This endpoint",
            "GET /health": "Health check endpoint",
            "POST /emails/process": "Process emails from a list of labels",
            "POST /emails/process/cancel": "Cancel email processing if in progress",
            "GET /emails/process/status": "Get current email processing status",
            "POST /imessages/import": "Import iMessages from a directory structure",
            "GET /imessages/import/stream": "Stream iMessage import progress via SSE",
            "POST /imessages/import/cancel": "Cancel iMessage import if in progress",
            "GET /imessages/import/status": "Get current iMessage import status",
            "GET /imessages/chat-sessions": "Get list of unique chat session names",
            "GET /imessages/conversation/{chat_session}": "Get all messages for a specific chat session",
            "DELETE /imessages/conversation/{chat_session}": "Delete a conversation",
            "GET /imessages/{message_id}/attachment": "Get attachment content for a message",
            "POST /chat/generate": "Generate a chat response using ChatService with Gemini LLM",
            "POST /writing-style/summarize": "Summarize the owner's writing style from a random sample of 5000 messages",
            "POST /whatsapp/import": "Import WhatsApp messages from a directory structure",
            "GET /whatsapp/import/stream": "Stream WhatsApp import progress via SSE",
            "POST /whatsapp/import/cancel": "Cancel WhatsApp import if in progress",
            "GET /whatsapp/import/status": "Get current WhatsApp import status",
            "POST /facebook/import": "Import Facebook Messenger messages from a directory structure",
            "GET /facebook/import/stream": "Stream Facebook Messenger import progress via SSE",
            "POST /facebook/import/cancel": "Cancel Facebook Messenger import if in progress",
            "GET /facebook/import/status": "Get current Facebook Messenger import status",
            "POST /instagram/import": "Import Instagram messages from a directory structure",
            "GET /instagram/import/stream": "Stream Instagram import progress via SSE",
            "POST /instagram/import/cancel": "Cancel Instagram import if in progress",
            "GET /instagram/import/status": "Get current Instagram import status",
            "POST /facebook/albums/import": "Import Facebook Albums from a directory structure",
            "GET /facebook/albums/import/stream": "Stream Facebook Albums import progress via SSE",
            "POST /facebook/albums/import/cancel": "Cancel Facebook Albums import if in progress",
            "GET /facebook/albums/import/status": "Get current Facebook Albums import status",
            "GET /facebook/albums": "Get list of all Facebook albums",
            "POST /facebook/import-places": "Import Facebook places from a posts JSON file",
            "GET /facebook/import-places/stream": "Stream Facebook Places import progress via SSE",
            "POST /facebook/import-places/cancel": "Cancel Facebook Places import if in progress",
            "GET /facebook/import-places/status": "Get current Facebook Places import status",
            "GET /facebook/places": "Retrieve Facebook places imported from Facebook posts JSON",
            "GET /relationship/strength": "Return relationship graph data (nodes and links) for strength visualization",
            "GET /contacts": "Retrieve contacts with all fields including id, name, and email",
            "GET /facebook/albums/{album_id}/images": "Get all images for a specific Facebook album",
            "GET /facebook/albums/images/{image_id}": "Get image data for a specific Facebook album image",
            "GET /emails/{email_id}/html": "Get email HTML content by ID",
            "GET /emails/{email_id}/text": "Get email plain text content by ID",
            "GET /emails/{email_id}/snippet": "Get email snippet by ID",
            "GET /emails/{email_id}/metadata": "Get email metadata by ID",
            "GET /emails/label": "Get metadata for all emails with given labels (query param: labels)",
            "GET /emails/folders": "Get list of available folders/labels from email server",
            "GET /emails/search": "Search emails by metadata criteria (from, to, month, year, subject, to_from, has_attachments)",
            "GET /attachments/{attachment_id}": "Get attachment content",
            "GET /attachments/random": "Get random attachment with email metadata",
            "GET /attachments/by-id": "Get attachment by ID order (query param: offset)",
            "GET /attachments/by-size": "Get attachment by size order (query params: order=asc|desc, offset)",
            "GET /attachments/count": "Get total count of attachments",
            "GET /attachments/{attachment_id}/info": "Get attachment info with email metadata",
            "DELETE /attachments/{attachment_id}": "Delete an attachment",
            "GET /attachments-viewer": "Attachment viewer web page",
            "GET /attachments/images": "Get images for grid display (query params: page, page_size, order, direction)",
            "GET /attachments-images-grid": "Image grid viewer web page"
        }
    }




# @router.get("/api/suggestions")
# async def get_suggestions():
#     path = Path(__file__).parent.parent / "static" / "data" / "Suggestions.json"
#     return FileResponse(
#         path,
#         media_type="application/json",
#         headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
#     )

@router.get("/api/dashboard")
async def get_dashboard():
    """Return aggregate stats for the Dashboard tab.

    Includes: message counts by service, contacts, images (imported/reference),
    Facebook albums, locations, places, thumbnail coverage, and other counts.
    """
    session = db.get_session()
    try:
        # Messages by service
        msg_by_service = (
            session.query(Message.service, func.count(Message.id))
            .group_by(Message.service)
            .all()
        )
        message_counts = {s or "unknown": c for s, c in msg_by_service}
        total_messages = sum(message_counts.values())

        # Messages by year (exclude null message_date)
        year_col = extract("year", Message.message_date)
        msg_by_year = (
            session.query(year_col.label("yr"), func.count(Message.id))
            .filter(Message.message_date.isnot(None))
            .group_by(year_col)
            .order_by(year_col)
            .all()
        )
        messages_by_year = {int(yr): c for yr, c in msg_by_year if yr is not None}

        # Emails by year (exclude null date)
        email_year_col = extract("year", Email.date)
        email_by_year = (
            session.query(email_year_col.label("yr"), func.count(Email.id))
            .filter(Email.date.isnot(None))
            .group_by(email_year_col)
            .order_by(email_year_col)
            .all()
        )
        emails_by_year = {int(yr): c for yr, c in email_by_year if yr is not None}

        # Top 20 messages by contact (sender), excluding subject
        subject_names_lower = set()
        config = subject_config_service.get_configuration()
        if config:
            if config.subject_name:
                subject_names_lower.add(config.subject_name.strip().lower())
            if config.family_name:
                full = f"{config.subject_name or ''} {config.family_name}".strip()
                if full:
                    subject_names_lower.add(full.lower())
        subject_contacts = session.query(Contacts.name).filter(Contacts.is_subject == True).all()  # noqa: E712
        for (name,) in subject_contacts:
            if name and name.strip():
                subject_names_lower.add(name.strip().lower())
        contact_0 = session.query(Contacts.name).filter(Contacts.id == 0).first()
        if contact_0 and contact_0[0] and contact_0[0].strip():
            subject_names_lower.add(contact_0[0].strip().lower())
        msg_by_sender = (
            session.query(Message.sender_name, func.count(Message.id))
            .filter(Message.sender_name.isnot(None))
            .filter(Message.sender_name != "")
            .group_by(Message.sender_name)
            .order_by(func.count(Message.id).desc())
            .limit(100)
            .all()
        )
        messages_by_contact = []
        for name, count in msg_by_sender:
            if name and name.strip().lower() not in subject_names_lower:
                messages_by_contact.append({"name": name.strip(), "count": count})
                if len(messages_by_contact) >= 20:
                    break

        # Contacts
        contacts_count = session.query(func.count(Contacts.id)).scalar() or 0

        # Contacts by category (rel_type); treat null/empty as "unknown"
        cat_col = func.coalesce(Contacts.rel_type, "unknown")
        contacts_by_cat = (
            session.query(cat_col, func.count(Contacts.id))
            .group_by(cat_col)
            .all()
        )
        contacts_by_category = {(c or "unknown").strip() or "unknown": n for c, n in contacts_by_cat}

        # Media: total, imported, reference - image types only (media_type like 'image/%')
        image_filter = MediaMetadata.media_type.like("image/%")
        total_images = (
            session.query(func.count(MediaMetadata.id)).filter(image_filter).scalar()
        ) or 0
        imported_images = (
            session.query(func.count(MediaMetadata.id))
            .filter(image_filter)
            .filter(MediaMetadata.is_referenced == False)  # noqa: E712
            .scalar()
        ) or 0
        reference_images = (
            session.query(func.count(MediaMetadata.id))
            .filter(image_filter)
            .filter(MediaMetadata.is_referenced == True)  # noqa: E712
            .scalar()
        ) or 0

        # Thumbnail coverage: image media_items with media_blob.thumbnail_data IS NOT NULL
        with_thumb = (
            session.query(func.count(MediaMetadata.id))
            .join(MediaBlob, MediaMetadata.media_blob_id == MediaBlob.id)
            .filter(image_filter)
            .filter(MediaBlob.thumbnail_data.isnot(None))
            .scalar()
        ) or 0
        thumbnail_pct = round(100.0 * with_thumb / total_images, 1) if total_images else 0

        # Images by region (image types only)
        region_col = func.coalesce(MediaMetadata.region, "Unknown")
        images_by_region_rows = (
            session.query(region_col, func.count(MediaMetadata.id))
            .filter(image_filter)
            .group_by(region_col)
            .order_by(func.count(MediaMetadata.id).desc())
            .all()
        )
        images_by_region = {(r or "Unknown").strip() or "Unknown": n for r, n in images_by_region_rows}

        # Facebook albums
        facebook_albums_count = session.query(func.count(FacebookAlbum.id)).scalar() or 0

        # Locations & Places
        locations_count = session.query(func.count(Locations.id)).scalar() or 0
        places_count = session.query(func.count(Places.id)).scalar() or 0

        # Optional extras
        emails_count = session.query(func.count(Email.id)).scalar() or 0
        artefacts_count = session.query(func.count(Artefact.id)).scalar() or 0
        reference_docs_count = (
            session.query(func.count(ReferenceDocument.id)).scalar() or 0
        )
        reference_docs_enabled = (
            session.query(func.count(ReferenceDocument.id))
            .filter(ReferenceDocument.available_for_task == True)  # noqa: E712
            .scalar()
        ) or 0
        reference_docs_disabled = reference_docs_count - reference_docs_enabled
        complete_profiles_count = (
            session.query(func.count(CompleteProfile.id)).scalar() or 0
        )

        # Subject complete profile: subject full name and whether they have one
        subject_full_name = None
        subject_has_complete_profile = False
        config = subject_config_service.get_configuration()
        if config:
            subject_full_name = f"{config.subject_name or ''} {config.family_name or ''}".strip()
            if not subject_full_name:
                subject_full_name = config.subject_name or "Subject"
            contact_0 = session.query(Contacts.name).filter(Contacts.id == 0).first()
            subject_names = {subject_full_name.lower(), (config.subject_name or "").lower()}
            if contact_0 and contact_0[0]:
                subject_names.add(contact_0[0].strip().lower())
            subject_names.discard("")
            if subject_names:
                cp = session.query(CompleteProfile).filter(
                    func.lower(CompleteProfile.name).in_(subject_names)
                ).first()
                subject_has_complete_profile = cp is not None and cp.profile is not None and len((cp.profile or "").strip()) > 0

        return {
            "message_counts": message_counts,
            "total_messages": total_messages,
            "messages_by_year": messages_by_year,
            "emails_by_year": emails_by_year,
            "messages_by_contact": messages_by_contact,
            "contacts_count": contacts_count,
            "contacts_by_category": contacts_by_category,
            "total_images": total_images,
            "imported_images": imported_images,
            "reference_images": reference_images,
            "images_by_region": images_by_region,
            "thumbnail_count": with_thumb,
            "thumbnail_percentage": thumbnail_pct,
            "facebook_albums_count": facebook_albums_count,
            "locations_count": locations_count,
            "places_count": places_count,
            "emails_count": emails_count,
            "artefacts_count": artefacts_count,
            "reference_docs_count": reference_docs_count,
            "reference_docs_enabled": reference_docs_enabled,
            "reference_docs_disabled": reference_docs_disabled,
            "complete_profiles_count": complete_profiles_count,
            "subject_full_name": subject_full_name or "Subject",
            "subject_has_complete_profile": subject_has_complete_profile,
        }
    finally:
        session.close()


@router.get("/api/import-control-last-run")
async def get_import_control_last_run():
    """Get last run time and result for each import control.

    Returns a dict keyed by import_type (whatsapp, facebook, instagram, imessage,
    facebook_albums, facebook_places, filesystem, thumbnails) with last_run_at (ISO),
    result (success/error/cancelled), and result_message.
    """
    session = db.get_session()
    try:
        rows = session.query(ImportControlLastRun).all()
        return {
            r.import_type: {
                "last_run_at": r.last_run_at.isoformat(),
                "result": r.result,
                "result_message": r.result_message,
            }
            for r in rows
        }
    finally:
        session.close()


@router.get("/api/control-defaults")
async def get_control_defaults():
    """Get default values for control tab inputs from environment variables.

    Returns:
        Dictionary of default values for all control tab inputs
    """
    config = get_config()
    return config.get_control_defaults(config_service=config_service)


@router.delete("/admin/empty-media-tables")
async def empty_media_tables():
    """Empty the attachments, media_blob, media_items, messages, and message_attachments tables.

    WARNING: This permanently deletes all data from these tables.

    Returns:
        Dictionary with deletion counts for each table
    """
    session = db.get_session()
    try:
        # Delete in order to respect foreign key constraints
        # 1. Delete message_attachments first (references messages and media_items)
        message_attachment_count = session.query(MessageAttachment).count()
        session.query(MessageAttachment).delete()

        # 2. Delete messages
        message_count = session.query(Message).count()
        session.query(Message).delete()

        # 3. Delete media_items (references media_blob)
        media_item_count = session.query(MediaMetadata).count()
        session.query(MediaMetadata).delete()

        # 4. Delete media_blob
        media_blob_count = session.query(MediaBlob).count()
        session.query(MediaBlob).delete()

        # 5. Delete attachments (old table, may not exist)
        attachment_count = 0
        try:
            attachment_count = session.query(Attachment).count()
            session.query(Attachment).delete()
        except Exception:
            # Table might not exist, ignore
            pass

        #6. Delete album_media (Facebook album images are now in unified media system)
        album_media_count = session.query(AlbumMedia).count()
        session.query(AlbumMedia).delete()

        #7. Delete facebook_albums
        facebook_album_count = session.query(FacebookAlbum).count()
        session.query(FacebookAlbum).delete()

        session.commit()

        return {
            "message": "Tables emptied successfully",
            "deleted_counts": {
                "message_attachments": message_attachment_count,
                "messages": message_count,
                "media_items": media_item_count,
                "media_blob": media_blob_count,
                "attachments": attachment_count,
                "album_media": album_media_count,
                "facebook_albums": facebook_album_count
            }
        }
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error emptying tables: {str(e)}")
    finally:
        session.close()
