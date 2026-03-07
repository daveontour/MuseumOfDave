"""Relationship and contact routes."""
import asyncio
import json
import math
import os
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import text, func, or_

from ...database.models import Contacts, Message, EmailMatches, EmailClassifications, EmailExclusions
from ..deps import db
from .. import state as import_state

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ContactResponse(BaseModel):
    """Response model for a contact."""
    id: int
    name: str
    email: Optional[str] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    is_subject: bool = False
    is_contact: bool = False
    is_group: bool = False
    is_organization: bool = False
    is_individual: bool = False
    is_company: bool = False
    is_government: bool = False
    is_non_profit: bool = False
    is_educational: bool = False
    facebook: bool = False
    instagram: bool = False
    linkedin: bool = False
    youtube: bool = False
    whatsapp: bool = False
    signal: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ContactResponseShort(BaseModel):
    """Response model for a contact."""
    id: int
    name: str
    email: Optional[str] = None
    numemail: Optional[int] = None
    facebookid: Optional[str] = None
    numfacebook: Optional[int] = None
    whatsappid: Optional[str] = None
    numwhatsapp: Optional[int] = None
    imessageid: Optional[str] = None
    numimessages: Optional[int] = None
    smsid: Optional[str] = None
    numsms: Optional[int] = None
    instagramid: Optional[str] = None
    numinstagram: Optional[int] = None


class ContactsListResponse(BaseModel):
    """Response model for list of contacts."""
    contacts: List[ContactResponseShort]
    total: int


class ContactNameId(BaseModel):
    """Minimal contact model: id and name only."""
    id: int
    name: str


class EmailMatchResponse(BaseModel):
    """Response model for an email match."""
    id: int
    primary_name: str
    email: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmailMatchCreate(BaseModel):
    """Request model for creating an email match."""
    primary_name: str
    email: str


class EmailMatchUpdate(BaseModel):
    """Request model for updating an email match."""
    primary_name: Optional[str] = None
    email: Optional[str] = None


class EmailClassificationResponse(BaseModel):
    """Response model for an email classification row."""
    id: int
    name: str
    classification: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmailClassificationCreate(BaseModel):
    """Request model for creating an email classification."""
    name: str
    classification: str


class EmailClassificationUpdate(BaseModel):
    """Request model for updating an email classification."""
    name: Optional[str] = None
    classification: Optional[str] = None


class EmailExclusionResponse(BaseModel):
    """Response model for an email exclusion row."""
    id: int
    email: str
    name: str
    name_email: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmailExclusionCreate(BaseModel):
    """Request model for creating an email exclusion."""
    email: str = ""
    name: str = ""
    name_email: bool = False


class EmailExclusionUpdate(BaseModel):
    """Request model for updating an email exclusion."""
    email: Optional[str] = None
    name: Optional[str] = None
    name_email: Optional[bool] = None


class ContactsNamesListResponse(BaseModel):
    """Response model for light contact list (id and name only)."""
    contacts: List[ContactNameId]


class RelationshipGraphNode(BaseModel):
    """Node for the relationship graph."""
    id: str
    name: str
    contact_type: Optional[str] = None  # friend, family, colleague, acquaintance, business, social, promotional, unknown
    num_emails: Optional[int] = None
    num_imessages: Optional[int] = None
    num_facebook: Optional[int] = None
    num_whatsapp: Optional[int] = None
    num_sms: Optional[int] = None
    num_instagram: Optional[int] = None


class RelationshipGraphLink(BaseModel):
    """Link/edge for the relationship graph."""
    source: str
    target: str
    strength: int


class RelationshipGraphSampleResponse(BaseModel):
    """Response model for sample relationship graph data (mocked)."""
    nodes: List[RelationshipGraphNode]
    links: List[RelationshipGraphLink]


class UpdateClassificationRequest(BaseModel):
    """Request to update a contact's classification."""
    name: str
    classification: str  # friend, family, colleague, acquaintance, business, social, promotional, spam, unknown


class BulkDeleteContactsRequest(BaseModel):
    """Request to delete multiple contacts by ID."""
    ids: List[int]


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

REL_TYPE_KEYS = [
    "friend", "family", "colleague", "acquaintance", "business",
    "social", "promotional", "spam", "important", "unknown"
]

VALID_REL_TYPES = frozenset(
    ["friend", "family", "colleague", "acquaintance", "business", "social", "promotional", "spam", "important", "unknown"]
)

# Source filter: SQL condition template for contact (use to_contact. or from_contact. as prefix)
SOURCE_TO_CONDITION = {
    "email": "({p}numemails > 0 OR ({p}email IS NOT NULL AND {p}email != ''))",
    "facebook": "({p}numfacebook > 0 OR ({p}facebookid IS NOT NULL AND {p}facebookid != ''))",
    "whatsapp": "({p}numwhatsapp > 0 OR ({p}whatsappid IS NOT NULL AND {p}whatsappid != ''))",
    "sms-imessage": "({p}numsms > 0 OR {p}smsid IS NOT NULL OR {p}numimessages > 0 OR {p}imessageid IS NOT NULL)",
    "instagram": "({p}numinstagram > 0 OR ({p}instagramid IS NOT NULL AND {p}instagramid != ''))",
}

# Map source filter to relationship.type values (r.type in the relationships table)
SOURCE_TO_RELATIONSHIP_TYPES = {
    "email": ["email"],
    "facebook": ["facebook"],
    "whatsapp": ["whatsapp"],
    "sms-imessage": ["sms", "imessage"],
    "instagram": ["instagram"],
}


# Source keys to SQL condition for contacts (no prefix)
SOURCE_TO_CONTACT_CONDITION = {
    "email": "numemails > 0",
    "facebook": "numfacebook > 0",
    "whatsapp": "numwhatsapp > 0",
    "sms-imessage": "(numsms > 0 OR numimessages > 0)",
    "instagram": "numinstagram > 0",
}

SOURCE_TO_SUM_CONDITION = {
    "email": "COALESCE(numemails, 0)",
    "facebook": "COALESCE(numfacebook, 0)",
    "whatsapp": "COALESCE(numwhatsapp, 0)",
    "sms-imessage": "COALESCE(numsms, 0) + COALESCE(numimessages, 0)",
    "instagram": "COALESCE(numinstagram, 0)",
}


def _get_email_classifications_path() -> Path:
    """Path to email_classifications.json in import-processor directory."""
    return Path(__file__).resolve().parent.parent.parent.parent / "import-processor" / "email_classifications.json"


def _migrate_classifications_to_rel_type(data: dict) -> dict:
    """Convert old is_* keys to rel_type keys (friend, family, etc.)."""
    old_to_new = {
        "is_friend": "friend", "is_family": "family", "is_colleague": "colleague",
        "is_acquaintance": "acquaintance", "is_business": "business", "is_social": "social",
        "is_promotional": "promotional", "is_spam": "spam", "is_important": "important",
        "is_unknown": "unknown",
    }
    migrated = {}
    for k, v in data.items():
        new_key = old_to_new.get(k, k)
        if isinstance(v, list):
            migrated[new_key] = v
        else:
            migrated[new_key] = v
    for key in REL_TYPE_KEYS:
        if key not in migrated:
            migrated[key] = []
    return migrated


def _get_relationship_graph_from_db(types: Optional[List[str]] = None, sources: Optional[List[str]] = None, max_nodes: int = 100) -> RelationshipGraphSampleResponse:
    """Fetch relationship graph data from database (filtered contacts as nodes)."""
    valid_types = [t for t in (types or []) if t in VALID_REL_TYPES]
    valid_sources = [s for s in (sources or []) if s in SOURCE_TO_CONTACT_CONDITION]

    # Types: default to friend, acquaintance, unknown; or use provided filter
    if valid_types:
        type_placeholders = ", ".join(f"'{t}'" for t in valid_types)
        type_clause = f"rel_type IN ({type_placeholders})"
    else:
        type_clause = "rel_type IN ('friend', 'acquaintance', 'unknown')"

    # Sources: default to any activity; or require at least one of the selected sources
    if valid_sources:
        source_conds = [SOURCE_TO_CONTACT_CONDITION[s] for s in valid_sources]
        source_clause = " OR ".join(source_conds)
        sum_clause = " + ".join(SOURCE_TO_SUM_CONDITION[s] for s in valid_sources)
    else:
        source_clause = "numwhatsapp > 0 OR numemails > 0 OR numimessages > 0 OR numsms > 0 OR numfacebook > 0 OR numinstagram > 0"
        sum_clause = "COALESCE(numemails, 0) + COALESCE(numfacebook, 0) + COALESCE(numwhatsapp, 0) + COALESCE(numsms, 0) + COALESCE(numimessages, 0) + COALESCE(numinstagram, 0)"
    sql = f"""
        SELECT
            id,
            name,
            rel_type,
            is_group,
            (numimessages > 0) AS has_imessage,
            (numwhatsapp > 0) AS has_whatsapp,
            (numemails > 0) AS has_email,
            (numfacebook > 0) AS has_facebook,
            (numsms > 0) AS has_sms_imessage,
            (numinstagram > 0) AS has_instagram,
            numemails,
            numimessages,
            numfacebook,
            numwhatsapp,
            numsms,
            numinstagram,
            {sum_clause} as total
        FROM contacts
        WHERE (id = 0 OR (
            {type_clause}
            AND ({source_clause})
            AND (({sum_clause}) > 3)
        ))
        ORDER BY total DESC
        LIMIT {max(1, min(max_nodes, 1000))}
    """


    session = db.get_session()
    try:
        rows = session.execute(text(sql)).fetchall()
    finally:
        session.close()

    # Build nodes: subject (id=0) first if present, then others
    nodes = []
    subject_name = "Subject"
    node_totals = {}  # node_id -> total for link strength
    for row in rows:
        cid = row.id
        name = row.name or ""
        rel_type = row.rel_type or "unknown"
        total = getattr(row, "total", None) or 0
        if cid == 0:
            subject_name = name or subject_name
        node_id = "0" if cid == 0 else (name or str(cid))
        nodes.append(RelationshipGraphNode(
            id=node_id,
            name=name or str(cid),
            contact_type=rel_type,
            num_emails=getattr(row, "numemails", None),
            num_imessages=getattr(row, "numimessages", None),
            num_facebook=getattr(row, "numfacebook", None),
            num_whatsapp=getattr(row, "numwhatsapp", None),
            num_sms=getattr(row, "numsms", None),
            num_instagram=getattr(row, "numinstagram", None),
        ))
        if cid != 0:
            node_totals[node_id] = total

    # Subject first if not already
    if nodes and nodes[0].id != "0":
        subject_node = next((n for n in nodes if n.id == "0"), None)
        if subject_node:
            nodes = [subject_node] + [n for n in nodes if n.id != "0"]
        else:
            nodes = [RelationshipGraphNode(id="0", name=subject_name, contact_type=None)] + nodes

    if not nodes:
        sess = db.get_session()
        try:
            sub = sess.execute(text("SELECT name FROM contacts WHERE id = 0")).fetchone()
            if sub and sub[0]:
                subject_name = sub[0]
        finally:
            sess.close()
        nodes = [RelationshipGraphNode(id="0", name=subject_name, contact_type=None)]

    # Add link from each non-subject node to subject, strength = contact total (ln-scaled 1-10)
    links = []
    max_raw = max(node_totals.values()) if node_totals else 1
    ln_max = math.log(max_raw + 1)
    for node in nodes:
        if node.id != "0":
            raw = node_totals.get(node.id, 0)
            if ln_max > 0:
                strength = round(1 + 9 * math.log(raw + 1) / ln_max)
            else:
                strength = 1
            strength = max(1, min(10, strength))
            links.append(RelationshipGraphLink(source=node.id, target="0", strength=strength))

    return RelationshipGraphSampleResponse(nodes=nodes, links=links)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/relationship/strength", response_model=RelationshipGraphSampleResponse)
async def get_relationship_strength(
    types: Optional[str] = Query(None, description="Comma-separated contact types: friend, family, colleague, acquaintance, business, social, promotional, unknown"),
    sources: Optional[str] = Query(None, description="Comma-separated sources: email, facebook, whatsapp, sms-imessage, instagram"),
    max_nodes: int = Query(100, description="Maximum number of nodes to return", ge=1, le=1000)
):
    """Return relationship graph data from database (relationships involving contact id 0)."""
    type_list = [t.strip().lower() for t in types.split(",") if t.strip()] if types else None
    source_list = [s.strip().lower() for s in sources.split(",") if s.strip()] if sources else None
    return _get_relationship_graph_from_db(types=type_list, sources=source_list, max_nodes=max_nodes)


ALLOWED_CONTACT_ORDER_COLUMNS = frozenset(
    {"id", "name", "email", "numemails", "numsms", "numwhatsapp", "numimessages", "numinstagram", "numfacebook"}
)


@router.get("/contacts/names", response_model=ContactsNamesListResponse)
async def get_contacts_names():
    """Light endpoint: return all contacts with id and name only. No filtering."""
    session = db.get_session()
    try:
        query = session.query(Contacts.id, Contacts.name)
        query = query.filter(
                or_(
                    Contacts.name.is_(None),
                    (Contacts.name == ''),
                    Contacts.name.op('!~')('^[0-9\\s+]+$'),
                )
            )
        msg_sum = (
                func.coalesce(Contacts.numemails, 0)
                + func.coalesce(Contacts.numfacebook, 0)
                + func.coalesce(Contacts.numwhatsapp, 0)
                + func.coalesce(Contacts.numsms, 0)
                + func.coalesce(Contacts.numimessages, 0)
                + func.coalesce(Contacts.numinstagram, 0)
            )
        query = query.filter(msg_sum > 0)
        rows = query.order_by(Contacts.name).all()
        # rows = session.query(Contacts.id, Contacts.name).order_by(Contacts.name).all()
        return ContactsNamesListResponse(
            contacts=[ContactNameId(id=r[0], name=r[1] or "") for r in rows]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving contacts: {str(e)}")
    finally:
        session.close()


@router.get("/contacts", response_model=ContactsListResponse)
async def get_contacts(
    name: Optional[str] = Query(None, description="Filter by name (partial match, case-insensitive)"),
    email: Optional[str] = Query(None, description="Filter by email (partial match, case-insensitive)"),
    is_subject: Optional[bool] = Query(None, description="Filter by is_subject flag"),
    is_contact: Optional[bool] = Query(None, description="Filter by is_contact flag"),
    is_group: Optional[bool] = Query(None, description="Filter by is_group flag"),
    is_organization: Optional[bool] = Query(None, description="Filter by is_organization flag"),
    is_individual: Optional[bool] = Query(None, description="Filter by is_individual flag"),
    is_company: Optional[bool] = Query(None, description="Filter by is_company flag"),
    is_government: Optional[bool] = Query(None, description="Filter by is_government flag"),
    is_non_profit: Optional[bool] = Query(None, description="Filter by is_non_profit flag"),
    is_educational: Optional[bool] = Query(None, description="Filter by is_educational flag"),
    has_messages: Optional[bool] = Query(None, description="Filter to contacts with at least 1 message"),
    email_contains_at: Optional[bool] = Query(None, description="Filter to contacts with at least 1 '@' in the email field"),
    exclude_phone_numbers: Optional[bool] = Query(None, description="Exclude contacts whose name contains only digits, whitespace and '+'"),
    search: Optional[str] = Query(None, description="Partial case-insensitive match on name or email"),
    limit: Optional[int] = Query(0, description="Maximum number of contacts to return (0 for all)", ge=0, le=1000),
    offset: Optional[int] = Query(0, description="Number of contacts to skip", ge=0),
    order_by: Optional[str] = Query("name", description="Column to sort by"),
    order: Optional[str] = Query("asc", description="Sort direction: asc or desc")
):
    """Retrieve contacts from the database.

    Returns contacts with all their fields including id, name, and email.

    Args:
        name: Optional filter by name (partial match, case-insensitive)
        email: Optional filter by email (partial match, case-insensitive)
        is_subject: Optional filter by is_subject flag
        is_contact: Optional filter by is_contact flag
        is_group: Optional filter by is_group flag
        is_organization: Optional filter by is_organization flag
        is_individual: Optional filter by is_individual flag
        is_company: Optional filter by is_company flag
        is_government: Optional filter by is_government flag
        is_non_profit: Optional filter by is_non_profit flag
        is_educational: Optional filter by is_educational flag
        limit: Maximum number of contacts to return (default: 100, max: 1000)
        offset: Number of contacts to skip for pagination (default: 0)

    Returns:
        ContactsListResponse with list of contacts and total count
    """
    session = db.get_session()
    try:
        # Base query
        query = session.query(Contacts)

        # Apply filters
        if name:
            query = query.filter(Contacts.name.ilike(f'%{name}%'))

        if email:
            query = query.filter(Contacts.email.ilike(f'%{email}%'))

        if search and search.strip():
            term = search.strip()
            pattern = f'%{term}%'
            query = query.filter(
                or_(
                    Contacts.name.ilike(pattern),
                    Contacts.email.ilike(pattern),
                )
            )

        if is_subject is not None:
            query = query.filter(Contacts.is_subject == is_subject)

        if is_contact is not None:
            query = query.filter(Contacts.is_contact == is_contact)

        if is_group is not None:
            query = query.filter(Contacts.is_group == is_group)

        if is_organization is not None:
            query = query.filter(Contacts.is_organization == is_organization)

        if is_individual is not None:
            query = query.filter(Contacts.is_individual == is_individual)

        if is_company is not None:
            query = query.filter(Contacts.is_company == is_company)

        if is_government is not None:
            query = query.filter(Contacts.is_government == is_government)

        if is_non_profit is not None:
            query = query.filter(Contacts.is_non_profit == is_non_profit)

        if is_educational is not None:
            query = query.filter(Contacts.is_educational == is_educational)

        if has_messages is True:
            msg_sum = (
                func.coalesce(Contacts.numemails, 0)
                + func.coalesce(Contacts.numfacebook, 0)
                + func.coalesce(Contacts.numwhatsapp, 0)
                + func.coalesce(Contacts.numsms, 0)
                + func.coalesce(Contacts.numimessages, 0)
                + func.coalesce(Contacts.numinstagram, 0)
            )
            query = query.filter(msg_sum > 0)

        if email_contains_at is True:
            query = query.filter(Contacts.email.ilike('%@%'))

        if exclude_phone_numbers is True:
            query = query.filter(
                or_(
                    Contacts.name.is_(None),
                    (Contacts.name == ''),
                    Contacts.name.op('!~')('^[0-9\\s+]+$'),
                )
            )

        # Get total count before pagination
        total = query.count()

        # Apply ordering
        order_col = order_by.lower() if order_by else "name"
        order_dir = order.lower() if order else "asc"
        if order_col not in ALLOWED_CONTACT_ORDER_COLUMNS:
            order_col = "name"
        if order_dir not in ("asc", "desc"):
            order_dir = "asc"
        order_attr = getattr(Contacts, order_col)
        if order_dir == "desc":
            order_attr = order_attr.desc().nulls_last()

        # Apply pagination
        if limit > 0:
            contacts = query.order_by(order_attr).offset(offset).limit(limit).all()
        else:
            contacts = query.order_by(order_attr).offset(offset).all()

        # Convert to response models
        contacts_list = [
            ContactResponseShort(
                id=contact.id,
                name=contact.name,
                email=contact.email,
                numemail=contact.numemails,
                facebookid=contact.facebookid,
                numfacebook=contact.numfacebook,
                whatsappid=contact.whatsappid,
                numwhatsapp=contact.numwhatsapp,
                imessageid=contact.imessageid,
                numimessages=contact.numimessages,
                smsid=contact.smsid,
                numsms=contact.numsms,
                instagramid=contact.instagramid,
                numinstagram=contact.numinstagram
            )
            for contact in contacts
        ]

        return ContactsListResponse(
            contacts=contacts_list,
            total=total
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving contacts: {str(e)}"
        )
    finally:
        session.close()


@router.post("/contacts/bulk-delete")
async def bulk_delete_contacts(req: BulkDeleteContactsRequest):
    """Delete multiple contacts by ID. Skips subject (id=0) and non-existent IDs."""
    if not req.ids:
        return {"message": "No contacts to delete", "deleted": [], "skipped": []}
    ids = [i for i in req.ids if i != 0]
    if not ids:
        return {"message": "Cannot delete the subject (id=0)", "deleted": [], "skipped": req.ids}
    session = db.get_session()
    try:
        deleted = []
        for contact_id in ids:
            contact = session.query(Contacts).filter(Contacts.id == contact_id).first()
            if contact:
                session.delete(contact)
                deleted.append(contact_id)
        session.commit()
        return {"message": f"Deleted {len(deleted)} contact(s)", "deleted": deleted, "skipped": [i for i in ids if i not in deleted]}
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting contacts: {str(e)}")
    finally:
        session.close()


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: int):
    """Delete a contact by ID. Cannot delete the subject (id=0)."""
    if contact_id == 0:
        raise HTTPException(status_code=400, detail="Cannot delete the subject (contact id=0)")
    session = db.get_session()
    try:
        contact = session.query(Contacts).filter(Contacts.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=404, detail=f"Contact not found: id={contact_id}")
        session.delete(contact)
        session.commit()
        return {"message": "Contact deleted", "id": contact_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting contact: {str(e)}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Email matches (primary_name + email pairs for contact merging)
# ---------------------------------------------------------------------------

@router.get("/email-matches", response_model=List[EmailMatchResponse])
async def get_email_matches(
    primary_name: Optional[str] = Query(None, description="Filter by primary name (partial match, case-insensitive)"),
):
    """List all email matches from the email_matches table."""
    session = db.get_session()
    try:
        q = session.query(EmailMatches).order_by(EmailMatches.primary_name, EmailMatches.email)
        if primary_name and primary_name.strip():
            term = f"%{primary_name.strip()}%"
            q = q.filter(EmailMatches.primary_name.ilike(term))
        rows = q.all()
        return [
            EmailMatchResponse(
                id=r.id,
                primary_name=r.primary_name or "",
                email=r.email or "",
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    finally:
        session.close()


@router.get("/email-matches/{match_id}", response_model=EmailMatchResponse)
async def get_email_match(match_id: int):
    """Get a single email match by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailMatches).filter(EmailMatches.id == match_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email match not found: id={match_id}")
        return EmailMatchResponse(
            id=row.id,
            primary_name=row.primary_name or "",
            email=row.email or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    finally:
        session.close()


@router.post("/email-matches", response_model=EmailMatchResponse)
async def create_email_match(req: EmailMatchCreate):
    """Create a new email match."""
    pn = (req.primary_name or "").strip()
    em = (req.email or "").strip()
    if not pn:
        raise HTTPException(status_code=400, detail="primary_name is required")
    if not em:
        raise HTTPException(status_code=400, detail="email is required")
    session = db.get_session()
    try:
        existing = session.query(EmailMatches).filter(
            EmailMatches.primary_name == pn,
            EmailMatches.email == em,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Email match already exists: {pn} / {em}")
        row = EmailMatches(primary_name=pn, email=em)
        session.add(row)
        session.commit()
        session.refresh(row)  # Populate id, created_at, updated_at from DB
        return EmailMatchResponse(
            id=row.id,
            primary_name=row.primary_name,
            email=row.email,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/email-matches/{match_id}", response_model=EmailMatchResponse)
async def update_email_match(match_id: int, req: EmailMatchUpdate):
    """Update an existing email match."""
    session = db.get_session()
    try:
        row = session.query(EmailMatches).filter(EmailMatches.id == match_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email match not found: id={match_id}")
        if req.primary_name is not None:
            pn = req.primary_name.strip()
            if not pn:
                raise HTTPException(status_code=400, detail="primary_name cannot be empty")
            row.primary_name = pn
        if req.email is not None:
            em = req.email.strip()
            if not em:
                raise HTTPException(status_code=400, detail="email cannot be empty")
            row.email = em
        session.commit()
        session.refresh(row)
        return EmailMatchResponse(
            id=row.id,
            primary_name=row.primary_name,
            email=row.email,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/email-matches/{match_id}")
async def delete_email_match(match_id: int):
    """Delete an email match by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailMatches).filter(EmailMatches.id == match_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email match not found: id={match_id}")
        session.delete(row)
        session.commit()
        return {"message": "Email match deleted", "id": match_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Email exclusions (email/name patterns and name+email pairs) used by import-processor
# ---------------------------------------------------------------------------

@router.get("/email-exclusions", response_model=List[EmailExclusionResponse])
async def get_email_exclusions(
    search: Optional[str] = Query(None, description="Filter by email or name (partial match, case-insensitive)"),
    name_email: Optional[bool] = Query(None, description="Filter by name_email type"),
):
    """List all email exclusions from the email_exclusions table."""
    session = db.get_session()
    try:
        q = session.query(EmailExclusions).order_by(EmailExclusions.email, EmailExclusions.name)
        if search and search.strip():
            term = f"%{search.strip()}%"
            q = q.filter(or_(EmailExclusions.email.ilike(term), EmailExclusions.name.ilike(term)))
        if name_email is not None:
            q = q.filter(EmailExclusions.name_email == name_email)
        rows = q.all()
        return [
            EmailExclusionResponse(
                id=r.id,
                email=r.email or "",
                name=r.name or "",
                name_email=r.name_email or False,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    finally:
        session.close()


@router.get("/email-exclusions/{exclusion_id}", response_model=EmailExclusionResponse)
async def get_email_exclusion(exclusion_id: int):
    """Get a single email exclusion by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailExclusions).filter(EmailExclusions.id == exclusion_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email exclusion not found: id={exclusion_id}")
        return EmailExclusionResponse(
            id=row.id,
            email=row.email or "",
            name=row.name or "",
            name_email=row.name_email or False,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    finally:
        session.close()


@router.post("/email-exclusions", response_model=EmailExclusionResponse)
async def create_email_exclusion(req: EmailExclusionCreate):
    """Create a new email exclusion."""
    em = (req.email or "").strip()
    nm = (req.name or "").strip()
    name_email = req.name_email
    if name_email:
        if not em or not nm:
            raise HTTPException(status_code=400, detail="Both email and name are required for name+email pair")
    else:
        if not em and not nm:
            raise HTTPException(status_code=400, detail="Either email or name is required")
        if em and nm:
            raise HTTPException(status_code=400, detail="For email or name pattern, only one field should be set (use name+email pair for both)")
    session = db.get_session()
    try:
        existing = session.query(EmailExclusions).filter(
            EmailExclusions.email == em,
            EmailExclusions.name == nm,
            EmailExclusions.name_email == name_email,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email exclusion already exists")
        row = EmailExclusions(email=em, name=nm, name_email=name_email)
        session.add(row)
        session.commit()
        session.refresh(row)
        return EmailExclusionResponse(
            id=row.id,
            email=row.email,
            name=row.name,
            name_email=row.name_email,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/email-exclusions/{exclusion_id}", response_model=EmailExclusionResponse)
async def update_email_exclusion(exclusion_id: int, req: EmailExclusionUpdate):
    """Update an existing email exclusion."""
    session = db.get_session()
    try:
        row = session.query(EmailExclusions).filter(EmailExclusions.id == exclusion_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email exclusion not found: id={exclusion_id}")
        if req.email is not None:
            em = req.email.strip()
            row.email = em
        if req.name is not None:
            nm = req.name.strip()
            row.name = nm
        if req.name_email is not None:
            row.name_email = req.name_email
        em = row.email or ""
        nm = row.name or ""
        name_email = row.name_email
        if name_email:
            if not em or not nm:
                raise HTTPException(status_code=400, detail="Both email and name are required for name+email pair")
        else:
            if not em and not nm:
                raise HTTPException(status_code=400, detail="Either email or name is required")
            if em and nm:
                raise HTTPException(status_code=400, detail="For email or name pattern, only one field should be set")
        session.commit()
        session.refresh(row)
        return EmailExclusionResponse(
            id=row.id,
            email=row.email,
            name=row.name,
            name_email=row.name_email,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/email-exclusions/{exclusion_id}")
async def delete_email_exclusion(exclusion_id: int):
    """Delete an email exclusion by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailExclusions).filter(EmailExclusions.id == exclusion_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email exclusion not found: id={exclusion_id}")
        session.delete(row)
        session.commit()
        return {"message": "Email exclusion deleted", "id": exclusion_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Email classifications (name + classification for contact rel_type) used by import-processor
# ---------------------------------------------------------------------------


def _apply_classification_to_contacts(session, name: str, classification: str) -> None:
    """Update contacts matching name (or alternative_names) to the given rel_type. Skips subject (id=0)."""
    nm_lower = (name or "").strip().lower()
    if not nm_lower:
        return
    contacts = session.query(Contacts).filter(Contacts.id != 0).all()
    for c in contacts:
        names_to_check = []
        if c.name:
            names_to_check.append(c.name.strip().lower())
        if c.alternative_names:
            for alt in c.alternative_names.split(","):
                alt = alt.strip().lower()
                if alt:
                    names_to_check.append(alt)
        if nm_lower in names_to_check:
            c.rel_type = classification


@router.get("/email-classifications/options")
async def get_email_classification_options():
    """Return list of valid classification values for the dropdown."""
    return {"classifications": list(REL_TYPE_KEYS)}


@router.get("/email-classifications", response_model=List[EmailClassificationResponse])
async def get_email_classifications(
    name: Optional[str] = Query(None, description="Filter by name (partial match, case-insensitive)"),
    classification: Optional[str] = Query(None, description="Filter by classification"),
):
    """List all email classifications from the email_classifications table."""
    session = db.get_session()
    try:
        q = session.query(EmailClassifications).order_by(EmailClassifications.classification, EmailClassifications.name)
        if name and name.strip():
            term = f"%{name.strip()}%"
            q = q.filter(EmailClassifications.name.ilike(term))
        if classification and classification.strip() and classification.strip() in VALID_REL_TYPES:
            q = q.filter(EmailClassifications.classification == classification.strip())
        rows = q.all()
        return [
            EmailClassificationResponse(
                id=r.id,
                name=r.name or "",
                classification=r.classification or "",
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]
    finally:
        session.close()


@router.get("/email-classifications/{class_id}", response_model=EmailClassificationResponse)
async def get_email_classification(class_id: int):
    """Get a single email classification by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailClassifications).filter(EmailClassifications.id == class_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email classification not found: id={class_id}")
        return EmailClassificationResponse(
            id=row.id,
            name=row.name or "",
            classification=row.classification or "",
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    finally:
        session.close()


@router.post("/email-classifications", response_model=EmailClassificationResponse)
async def create_email_classification(req: EmailClassificationCreate):
    """Create a new email classification."""
    nm = (req.name or "").strip()
    cl = (req.classification or "").strip().lower()
    if not nm:
        raise HTTPException(status_code=400, detail="name is required")
    if not cl or cl not in VALID_REL_TYPES:
        raise HTTPException(status_code=400, detail=f"classification must be one of: {', '.join(REL_TYPE_KEYS)}")
    session = db.get_session()
    try:
        existing = session.query(EmailClassifications).filter(
            EmailClassifications.name == nm,
            EmailClassifications.classification == cl,
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Classification already exists: {nm} / {cl}")
        row = EmailClassifications(name=nm, classification=cl)
        session.add(row)
        session.commit()
        session.refresh(row)
        _apply_classification_to_contacts(session, nm, cl)
        session.commit()
        return EmailClassificationResponse(
            id=row.id,
            name=row.name,
            classification=row.classification,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.put("/email-classifications/{class_id}", response_model=EmailClassificationResponse)
async def update_email_classification(class_id: int, req: EmailClassificationUpdate):
    """Update an existing email classification."""
    session = db.get_session()
    try:
        row = session.query(EmailClassifications).filter(EmailClassifications.id == class_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email classification not found: id={class_id}")
        if req.name is not None:
            nm = req.name.strip()
            if not nm:
                raise HTTPException(status_code=400, detail="name cannot be empty")
            row.name = nm
        if req.classification is not None:
            cl = req.classification.strip().lower()
            if not cl or cl not in VALID_REL_TYPES:
                raise HTTPException(status_code=400, detail=f"classification must be one of: {', '.join(REL_TYPE_KEYS)}")
            row.classification = cl
        session.commit()
        session.refresh(row)
        _apply_classification_to_contacts(session, row.name, row.classification)
        session.commit()
        return EmailClassificationResponse(
            id=row.id,
            name=row.name,
            classification=row.classification,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/email-classifications/{class_id}")
async def delete_email_classification(class_id: int):
    """Delete an email classification by ID."""
    session = db.get_session()
    try:
        row = session.query(EmailClassifications).filter(EmailClassifications.id == class_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Email classification not found: id={class_id}")
        session.delete(row)
        session.commit()
        return {"message": "Email classification deleted", "id": class_id}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

# ---------------------------------------------------------------------------
# Email classifications used by the relationships graph
# ---------------------------------------------------------------------------



@router.patch("/contacts/update-classification")
async def update_contact_classification(req: UpdateClassificationRequest):
    """Update a contact's classification in the database and email_classifications.json."""
    classification = (req.classification or "").strip().lower()
    if not classification or classification not in VALID_REL_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid classification '{req.classification}'. Must be one of: friend, family, colleague, acquaintance, business, social, promotional, spam, important, unknown"
        )

    session = db.get_session()
    try:
        contact = session.query(Contacts).filter(Contacts.name == req.name).first()
        if not contact:
            raise HTTPException(status_code=404, detail=f"Contact not found: {req.name}")
        if contact.id == 0:
            raise HTTPException(status_code=400, detail="Cannot change classification of the subject (contact id=0)")

        contact.rel_type = classification

        # Update or create email_classifications table entry
        nm = req.name.strip()
        existing = session.query(EmailClassifications).filter(
            func.lower(EmailClassifications.name) == nm.lower()
        ).first()
        if classification == "unknown":
            if existing:
                session.delete(existing)
        elif existing:
            existing.classification = classification
        else:
            session.add(EmailClassifications(name=nm, classification=classification))

        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")
    finally:
        session.close()

    # # Update email_classifications.json (new format: keys = rel_type values)
    # classifications_path = _get_email_classifications_path()
    # try:
    #     data = {}
    #     if classifications_path.exists():
    #         with open(classifications_path, "r", encoding="utf-8") as f:
    #             data = json.load(f)
    #         data = _migrate_classifications_to_rel_type(data)
    #     else:
    #         data = {k: [] for k in REL_TYPE_KEYS}
    #     for key in REL_TYPE_KEYS:
    #         data[key] = [n for n in data[key] if n.strip().lower() != req.name.strip().lower()]
    #     if classification != "unknown":
    #         if req.name not in data[classification]:
    #             data[classification].append(req.name)
    #     with open(classifications_path, "w", encoding="utf-8") as f:
    #         json.dump(data, f, indent=2)
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Failed to update email_classifications.json: {str(e)}")

    return {"message": "Classification updated", "name": req.name, "classification": classification}


def _get_import_processor_path() -> Path:
    """Resolve path to import-processor binary."""
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


def _contacts_extract_background_subprocess():
    """Background task: run import-processor contacts, stream stderr via SSE."""
    with import_state.contacts_extract_lock:
        import_state.contacts_extract_in_progress = True
    import_state.contacts_extract_cancelled.clear()

    import_state.update_contacts_extract_progress_state(
        status="in_progress",
        status_line="Starting contacts import and normalisation...",
        error_message=None,
    )
    import_state.broadcast_contacts_extract_event_sync(
        "status", {"status_line": "Starting contacts import and normalisation..."}
    )

    try:
        binary = _get_import_processor_path()
        cwd = binary.parent
        args = [str(binary), "contacts"]
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
                    if import_state.contacts_extract_cancelled.is_set():
                        proc.terminate()
                        return
                    line = line.rstrip()
                    if line:
                        import_state.update_contacts_extract_progress_state(status_line=line)
                        import_state.broadcast_contacts_extract_event_sync("status", {"status_line": line})
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

        # Use proc.wait() as primary completion signal; pipe EOF can lag on Windows
        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
            raise RuntimeError("Contacts extract timed out after 300 seconds")

        # Drain pipes (threads get EOF once process has exited)
        stderr_thread.join(timeout=5)
        stdout_thread.join(timeout=5)
        stdout = "".join(stdout_parts)

        if import_state.contacts_extract_cancelled.is_set():
            import_state.update_contacts_extract_progress_state(
                status="cancelled", status_line="Contacts extract cancelled."
            )
            import_state.broadcast_contacts_extract_event_sync(
                "cancelled", import_state.get_contacts_extract_progress_state()
            )
        else:
            returncode = proc.returncode
            if returncode is not None and returncode != 0:
                err_msg = (stdout or "").strip() or f"Process exited with code {returncode}"
                import_state.update_contacts_extract_progress_state(
                    status="error", error_message=err_msg, status_line=err_msg
                )
                import_state.broadcast_contacts_extract_event_sync(
                    "error", import_state.get_contacts_extract_progress_state()
                )
            else:
                state = import_state.get_contacts_extract_progress_state()
                status_line = state.get("status_line") or "Contacts extract completed successfully."
                import_state.update_contacts_extract_progress_state(
                    status="completed", status_line=status_line
                )
                import_state.broadcast_contacts_extract_event_sync(
                    "completed", import_state.get_contacts_extract_progress_state()
                )
    except FileNotFoundError as e:
        import_state.update_contacts_extract_progress_state(
            status="error", error_message=str(e), status_line=str(e)
        )
        import_state.broadcast_contacts_extract_event_sync(
            "error", import_state.get_contacts_extract_progress_state()
        )
    except Exception as e:
        err_msg = str(e)
        import_state.update_contacts_extract_progress_state(
            status="error", error_message=err_msg, status_line=err_msg
        )
        import_state.broadcast_contacts_extract_event_sync(
            "error", import_state.get_contacts_extract_progress_state()
        )
    finally:
        state = import_state.get_contacts_extract_progress_state()
        result = state.get("status", "error")
        msg = state.get("error_message") or state.get("status_line")
        import_state._record_import_control_last_run("contacts", result, msg)
        with import_state.contacts_extract_lock:
            import_state.contacts_extract_in_progress = False


@router.post("/contacts/extract")
async def extract_contacts(background_tasks: BackgroundTasks):
    """Run import-processor contacts subcommand to merge/normalise contacts from database.

    Starts the import-processor in the background and returns immediately.
    Connect to GET /contacts/extract/stream for progress updates via SSE.
    """
    with import_state.contacts_extract_lock:
        if import_state.contacts_extract_in_progress:
            raise HTTPException(
                status_code=400,
                detail="Contacts extract is already in progress"
            )

    background_tasks.add_task(_contacts_extract_background_subprocess)
    return {"message": "Contacts extract started", "status": "started"}


@router.get("/contacts/extract/stream")
async def stream_contacts_extract_progress(request: Request):
    """Stream contacts extract progress via Server-Sent Events (SSE)."""
    async def event_generator():
        client_queue = asyncio.Queue()
        with import_state.contacts_extract_sse_clients_lock:
            import_state.contacts_extract_sse_clients.append(client_queue)

        try:
            initial_state = import_state.get_contacts_extract_progress_state()
            event_data = {"type": "progress", "data": initial_state}
            yield f"data: {json.dumps(event_data)}\n\n"

            if initial_state.get("status") in ("completed", "cancelled", "error"):
                return

            while True:
                try:
                    if await request.is_disconnected():
                        break
                    message = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield message
                    progress_state = import_state.get_contacts_extract_progress_state()
                    if progress_state.get("status") in ("completed", "cancelled", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except Exception:
                    break
        finally:
            with import_state.contacts_extract_sse_clients_lock:
                if client_queue in import_state.contacts_extract_sse_clients:
                    import_state.contacts_extract_sse_clients.remove(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/contacts/extract/status")
async def get_contacts_extract_status():
    """Get current contacts extract status."""
    with import_state.contacts_extract_lock:
        in_progress = import_state.contacts_extract_in_progress
    state = import_state.get_contacts_extract_progress_state()
    return {
        "in_progress": in_progress,
        "cancelled": import_state.contacts_extract_cancelled.is_set(),
        **state,
    }


@router.post("/contacts/extract/cancel")
async def cancel_contacts_extract():
    """Cancel contacts extract if in progress."""
    with import_state.contacts_extract_lock:
        if not import_state.contacts_extract_in_progress:
            return {
                "message": "No contacts extract is currently in progress",
                "cancelled": False,
            }

    import_state.contacts_extract_cancelled.set()
    return {
        "message": "Contacts extract cancellation requested.",
        "cancelled": True,
    }


