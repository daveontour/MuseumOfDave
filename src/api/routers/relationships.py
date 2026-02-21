"""Relationship and contact routes."""
import json
import math
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import text
from sqlalchemy.orm import joinedload

from ...database.models import Contacts, Relationship, IMessage
from ...services.relationship_service import RelationshipService
from ..deps import db

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateContactsFromChatSessionsResponse(BaseModel):
    """Response model for creating contacts from chat sessions."""
    message: str
    total_sessions: int
    contacts_created: int
    contacts_existing: int
    errors: List[str] = []


class CreateContactsFromEmailsResponse(BaseModel):
    """Response model for creating contacts from emails."""
    message: str
    total_addresses: int
    contacts_created: int
    contacts_existing: int
    errors: List[str] = []


class MatchedContactPair(BaseModel):
    """Model for a pair of matched contacts."""
    contact_id_1: int
    name_1: str
    contact_id_2: int
    name_2: str
    match_reason: str


class MergeContactsResponse(BaseModel):
    """Response model for merging contacts."""
    message: str
    matched_contacts: List[MatchedContactPair]
    contacts_merged: int


class ContactInfo(BaseModel):
    """Contact information model."""
    id: int
    name: str
    email: Optional[str] = None


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


class RelationshipResponse(BaseModel):
    """Response model for a relationship."""
    id: int
    source: ContactInfo
    target: ContactInfo
    type: str
    description: Optional[str] = None
    ai_description: Optional[str] = None
    strength: Optional[int] = None
    is_active: bool
    is_personal: bool
    is_deleted: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RelationshipsListResponse(BaseModel):
    """Response model for list of relationships."""
    relationships: List[RelationshipResponse]
    total: int


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

    print(sql)

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


def find_likely_matching_contacts():
    """Find likely matching contacts."""

    sql = """WITH normalized_contacts AS (
    SELECT
        id,
        name,
        -- Lowercase email for case-insensitive match
        LOWER(email) as clean_email,
        -- Lowercase name for matching
        LOWER(name) as clean_name,

        -- IMPROVED CLEANING LOGIC:
        -- 1. Strip non-digits.
        -- 2. Check if the result is at least 7 digits long.
        -- 3. If valid, keep it; otherwise set to NULL.
        CASE
            WHEN LENGTH(REGEXP_REPLACE(whatsappid, '\D', '', 'g')) >= 7
            THEN REGEXP_REPLACE(whatsappid, '\D', '', 'g')
            ELSE NULL
        END as clean_whatsapp,

        CASE
            WHEN LENGTH(REGEXP_REPLACE(smsid, '\D', '', 'g')) >= 7
            THEN REGEXP_REPLACE(smsid, '\D', '', 'g')
            ELSE NULL
        END as clean_sms,

        CASE
            WHEN LENGTH(REGEXP_REPLACE(imessageid, '\D', '', 'g')) >= 7
            THEN REGEXP_REPLACE(imessageid, '\D', '', 'g')
            ELSE NULL
        END as clean_imessage

    FROM contacts
)
SELECT
    A.id AS contact_id_1,
    A.name AS name_1,
    B.id AS contact_id_2,
    B.name AS name_2,
    CASE
        WHEN A.clean_email = B.clean_email THEN 'Shared Email'
        WHEN A.clean_name = B.clean_name THEN 'Exact Name Match'
        -- Check if any phone number in A matches any phone number in B
        WHEN (A.clean_whatsapp IS NOT NULL AND A.clean_whatsapp IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage)) OR
             (A.clean_sms IS NOT NULL AND A.clean_sms IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage)) OR
             (A.clean_imessage IS NOT NULL AND A.clean_imessage IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage))
             THEN 'Shared Phone Number'
        ELSE 'Unknown'
    END AS match_reason
FROM normalized_contacts A
JOIN normalized_contacts B ON A.id < B.id
WHERE
    (A.clean_email = B.clean_email AND A.clean_email IS NOT NULL)
    OR
    (A.clean_name = B.clean_name AND A.clean_name IS NOT NULL)
    OR
    (   -- Cross-check all phone columns against each other
        (A.clean_whatsapp IS NOT NULL AND A.clean_whatsapp IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage)) OR
        (A.clean_sms IS NOT NULL AND A.clean_sms IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage)) OR
        (A.clean_imessage IS NOT NULL AND A.clean_imessage IN (B.clean_whatsapp, B.clean_sms, B.clean_imessage))
    )
ORDER BY A.id;"""

    session = db.get_session()
    try:
        contacts = session.execute(text(sql)).fetchall()
        return contacts
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error finding likely matching contacts: {str(e)}"
        )
    finally:
        session.close()


def merge_two_contacts(contact_id_1: int, contact_id_2: int):
    """Merge two contacts."""

    session = db.get_session()
    try:
        contact_1 = session.query(Contacts).filter(Contacts.id == contact_id_1).first()
        contact_2 = session.query(Contacts).filter(Contacts.id == contact_id_2).first()

        if  contact_1 and  contact_2:
            # pass
            # raise HTTPException(
            #     status_code=404,
            #     detail=f"Contact with ID {contact_id_1} or {contact_id_2} not found"
            # )

        #merge the contacts

            def choose_better_name(name1: str, name2: str) -> str:
                """Choose the better name and fix capitalization.

                Prefers names that don't look like email addresses.
                Applies title case capitalization.
                """
                def is_email_like(name: str) -> bool:
                    """Check if name looks like an email address."""
                    if not name:
                        return True
                    return '@' in name or '.' in name.split()[-1] if name.split() else False

                def fix_capitalization(name: str) -> str:
                    """Fix capitalization to title case, handling special cases."""
                    if not name:
                        return name

                    # Don't modify if it looks like an email
                    if '@' in name:
                        return name

                    # Split into words and capitalize each
                    words = name.split()
                    capitalized_words = []

                    for word in words:
                        # Handle common prefixes (Mc, Mac, O', etc.)
                        if len(word) > 2 and word[1:2].islower():
                            # Already has mixed case, preserve it
                            capitalized_words.append(word)
                        elif word.lower() in ['van', 'de', 'der', 'von', 'la', 'le', 'du', 'da', 'di', 'del', 'della']:
                            # Keep lowercase for common prefixes
                            capitalized_words.append(word.lower())
                        elif word.startswith("Mc") and len(word) > 2:
                            # McName -> McName
                            capitalized_words.append(word[0] + word[1].upper() + word[2:].lower())
                        elif word.startswith("Mac") and len(word) > 3:
                            # MacName -> MacName
                            capitalized_words.append(word[:3] + word[3:].capitalize())
                        elif word.startswith("O'") and len(word) > 2:
                            # O'Name -> O'Name
                            capitalized_words.append(word[:2] + word[2:].capitalize())
                        else:
                            # Standard title case
                            capitalized_words.append(word.capitalize())

                    return ' '.join(capitalized_words)

                # Choose the better name
                name1_is_email = is_email_like(name1)
                name2_is_email = is_email_like(name2)

                if name1_is_email and not name2_is_email:
                    # name2 is better
                    return fix_capitalization(name2)
                elif name2_is_email and not name1_is_email:
                    # name1 is better
                    return fix_capitalization(name1)
                elif not name1_is_email and not name2_is_email:
                    # Both are valid names, prefer the longer one (more complete)
                    if len(name1.strip()) >= len(name2.strip()):
                        return fix_capitalization(name1)
                    else:
                        return fix_capitalization(name2)
                else:
                    # Both look like emails, use name1 and fix capitalization
                    return fix_capitalization(name1)

            # Choose the better name
            name1 = contact_1.name or ""
            name2 = contact_2.name or ""
            chosen_name = choose_better_name(name1, name2)

            # Determine which name was chosen and add the other to alternative_names
            # Compare normalized versions to see which one was selected
            name1_normalized = name1.strip().lower()
            name2_normalized = name2.strip().lower()
            chosen_normalized = chosen_name.strip().lower()

            # Add the name that wasn't chosen to alternative_names
            if chosen_normalized == name1_normalized and name2:
                # name1 was chosen, add name2 to alternatives
                other_name = name2
            elif chosen_normalized == name2_normalized and name1:
                # name2 was chosen, add name1 to alternatives
                other_name = name1
            else:
                # If names are the same or one is empty, just use the chosen name
                other_name = None

            contact_1.name = chosen_name
            if other_name and other_name.strip():
                # Don't add if the alternative name is the same as the chosen name
                if other_name.strip().lower() != chosen_name.strip().lower():
                    if contact_1.alternative_names:
                        # Check if other_name is already in alternative_names
                        alt_names_list = [n.strip() for n in contact_1.alternative_names.split(',')]
                        if other_name.strip() not in alt_names_list:
                            contact_1.alternative_names = f"{contact_1.alternative_names}, {other_name}"
                    else:
                        contact_1.alternative_names = other_name
            contact_1.email = f"{contact_1.email}, {contact_2.email}"
            contact_1.numemails = contact_1.numemails + contact_2.numemails
            contact_1.facebookid = f"{contact_1.facebookid}, {contact_2.facebookid}"
            contact_1.numfacebook = contact_1.numfacebook + contact_2.numfacebook
            contact_1.whatsappid = f"{contact_1.whatsappid}, {contact_2.whatsappid}"
            contact_1.numwhatsapp = contact_1.numwhatsapp + contact_2.numwhatsapp
            contact_1.imessageid = f"{contact_1.imessageid}, {contact_2.imessageid}"
            contact_1.numimessages = contact_1.numimessages + contact_2.numimessages
            contact_1.smsid = f"{contact_1.smsid}, {contact_2.smsid}"
            contact_1.numsms = contact_1.numsms + contact_2.numsms
            contact_1.instagramid = f"{contact_1.instagramid}, {contact_2.instagramid}"
            contact_1.numinstagram = contact_1.numinstagram + contact_2.numinstagram
            session.commit()

            #delete the second contact
            session.delete(contact_2)
            session.commit()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error merging contacts: {str(e)}"
        )
    finally:
        session.close()


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


@router.post("/relationships/create-contacts-from-chat-sessions", response_model=CreateContactsFromChatSessionsResponse)
async def create_contacts_from_chat_sessions():
    """Create contact entries from distinct combinations of chat_session and service values in the messages table.

    This endpoint:
    1. Retrieves all distinct combinations of chat_session and service from the messages table
    2. Creates a contact entry for each chat_session/service combination
    3. Uses the chat_session value as the contact name
    4. Sets service-specific fields based on the service type:
       - iMessage: sets imessageid and numimessages
       - SMS: sets smsid and numsms
       - WhatsApp: sets whatsappid and numwhatsapp
       - Facebook Messenger: sets facebookid and numfacebook
       - Instagram: sets instagramid and numinstagram
    5. Skips sessions with less than 2 messages

    Returns:
        CreateContactsFromChatSessionsResponse with statistics:
        - total_sessions: Total number of distinct chat_session/service combinations found
        - contacts_created: Number of new contacts created
        - contacts_existing: Number of contacts that already existed (currently always 0)
        - errors: List of error messages if any

    Raises:
        HTTPException: 500 on error
    """
    relationship_service = RelationshipService(db=db)
    try:
        stats = relationship_service.create_contacts_from_chat_sessions()

        return CreateContactsFromChatSessionsResponse(
            message=f"Processed {stats['total_sessions']} chat sessions. Created {stats['contacts_created']} new contacts, {stats['contacts_existing']} already existed.",
            total_sessions=stats['total_sessions'],
            contacts_created=stats['contacts_created'],
            contacts_existing=stats['contacts_existing'],
            errors=stats['errors']
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating contacts from chat sessions: {str(e)}"
        )


@router.post("/relationships/create-contacts-from-emails", response_model=CreateContactsFromEmailsResponse)
async def create_contacts_from_emails():
    """Create contact entries from distinct email addresses in the emails table.

    This endpoint:
    1. Retrieves all distinct from_address values from the emails table
    2. Retrieves all distinct to_addresses values and splits comma-separated addresses
    3. Creates a contact entry for each unique email address that doesn't already exist
    4. Uses the email address as the contact name and email field

    Returns:
        CreateContactsFromEmailsResponse with statistics:
        - total_addresses: Total number of unique email addresses found
        - contacts_created: Number of new contacts created
        - contacts_existing: Number of contacts that already existed
        - errors: List of error messages if any

    Raises:
        HTTPException: 500 on error
    """
    relationship_service = RelationshipService(db=db)
    try:
        stats = relationship_service.create_contacts_from_emails()

        return CreateContactsFromEmailsResponse(
            message=f"Processed {stats['total_addresses']} unique email addresses. Created {stats['contacts_created']} new contacts, {stats['contacts_existing']} already existed.",
            total_addresses=stats['total_addresses'],
            contacts_created=stats['contacts_created'],
            contacts_existing=stats['contacts_existing'],
            errors=stats['errors']
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating contacts from emails: {str(e)}"
        )


@router.get("/relationships", response_model=RelationshipsListResponse)
async def get_relationships(
    source_id: Optional[int] = Query(None, description="Filter by source contact ID"),
    target_id: Optional[int] = Query(None, description="Filter by target contact ID"),
    contact_id: Optional[int] = Query(None, description="Filter by contact ID (as source or target)"),
    type: Optional[str] = Query(None, description="Filter by relationship type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_personal: Optional[bool] = Query(None, description="Filter by personal status"),
    include_deleted: bool = Query(False, description="Include deleted relationships"),
    limit: Optional[int] = Query(100, description="Maximum number of relationships to return", ge=1, le=1000),
    offset: Optional[int] = Query(0, description="Number of relationships to skip", ge=0)
):
    """Retrieve relationships between contacts.

    Returns relationships with source and target contact information (id, name, email).

    Args:
        source_id: Optional filter by source contact ID
        target_id: Optional filter by target contact ID
        contact_id: Optional filter by contact ID (returns relationships where contact is source or target)
        type: Optional filter by relationship type
        is_active: Optional filter by active status
        is_personal: Optional filter by personal status
        include_deleted: Whether to include deleted relationships (default: False)
        limit: Maximum number of relationships to return (default: 100, max: 1000)
        offset: Number of relationships to skip for pagination (default: 0)

    Returns:
        RelationshipsListResponse with list of relationships and total count
    """
    session = db.get_session()
    try:
        # Base query
        query = session.query(Relationship)

        # Apply filters
        if source_id is not None:
            query = query.filter(Relationship.source_id == source_id)

        if target_id is not None:
            query = query.filter(Relationship.target_id == target_id)

        if contact_id is not None:
            query = query.filter(
                (Relationship.source_id == contact_id) | (Relationship.target_id == contact_id)
            )

        if type is not None:
            query = query.filter(Relationship.type.ilike(f'%{type}%'))

        if is_active is not None:
            query = query.filter(Relationship.is_active == is_active)

        if is_personal is not None:
            query = query.filter(Relationship.is_personal == is_personal)

        if not include_deleted:
            query = query.filter(Relationship.is_deleted == False)

        # Get total count before pagination
        total = query.count()

        # Apply pagination and eager load contacts
        relationships = query.options(
            joinedload(Relationship.source),
            joinedload(Relationship.target)
        ).order_by(Relationship.created_at.desc()).offset(offset).limit(limit).all()

        # Convert to response models
        relationships_list = []
        for rel in relationships:
            # Access source and target contacts (already loaded via joinedload)
            source_contact = rel.source
            target_contact = rel.target

            if source_contact and target_contact:
                relationships_list.append(
                    RelationshipResponse(
                        id=rel.id,
                        source=ContactInfo(
                            id=source_contact.id,
                            name=source_contact.name,
                            email=source_contact.email
                        ),
                        target=ContactInfo(
                            id=target_contact.id,
                            name=target_contact.name,
                            email=target_contact.email
                        ),
                        type=rel.type,
                        description=rel.description,
                        ai_description=rel.ai_description,
                        strength=rel.strength,
                        is_active=rel.is_active,
                        is_personal=rel.is_personal,
                        is_deleted=rel.is_deleted,
                        created_at=rel.created_at,
                        updated_at=rel.updated_at
                    )
                )

        return RelationshipsListResponse(
            relationships=relationships_list,
            total=total
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving relationships: {str(e)}"
        )
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
    limit: Optional[int] = Query(0, description="Maximum number of contacts to return (0 for all)", ge=0, le=1000),
    offset: Optional[int] = Query(0, description="Number of contacts to skip", ge=0)
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

        # Get total count before pagination
        total = query.count()

        # Apply pagination
        if limit > 0:
            contacts = query.order_by(Contacts.name).offset(offset).limit(limit).all()
        else:
            contacts = query.order_by(Contacts.name).offset(offset).all()

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
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")
    finally:
        session.close()

    # Update email_classifications.json (new format: keys = rel_type values)
    classifications_path = _get_email_classifications_path()
    try:
        data = {}
        if classifications_path.exists():
            with open(classifications_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data = _migrate_classifications_to_rel_type(data)
        else:
            data = {k: [] for k in REL_TYPE_KEYS}
        for key in REL_TYPE_KEYS:
            data[key] = [n for n in data[key] if n.strip().lower() != req.name.strip().lower()]
        if classification != "unknown":
            if req.name not in data[classification]:
                data[classification].append(req.name)
        with open(classifications_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update email_classifications.json: {str(e)}")

    return {"message": "Classification updated", "name": req.name, "classification": classification}


@router.post("/contacts/extract")
async def extract_contacts():
    """Extract contacts from messages table and populate the contacts table."""
    session = db.get_session()
    try:
        sql = """
        SELECT
            chat_session,
            is_group_chat,
            COUNT(CASE WHEN service = 'WhatsApp' THEN 1 END) AS number_of_whatsapp,
            COUNT(CASE WHEN service = 'iMessage' THEN 1 END) AS number_of_imessage,
            COUNT(CASE WHEN service = 'Facebook Messenger' THEN 1 END) AS number_of_facebook,
            COUNT(CASE WHEN service = 'SMS' THEN 1 END) AS number_of_sms,
            COUNT(CASE WHEN service = 'Instagram' THEN 1 END) AS number_of_insta,
            COUNT(*) AS total
        FROM
            messages
        GROUP BY
            chat_session, is_group_chat
        ORDER BY
            is_group_chat, total DESC
        """
        rows = session.execute(text(sql)).fetchall()
        created = 0
        updated = 0
        for row in rows:
            chat_session = row.chat_session
            if not chat_session or not str(chat_session).strip():
                continue
            existing = session.query(Contacts).filter(Contacts.name == chat_session).first()
            if existing:
                existing.is_group = bool(row.is_group_chat)
                existing.numwhatsapp = row.number_of_whatsapp or 0
                existing.numimessages = row.number_of_imessage or 0
                existing.numfacebook = row.number_of_facebook or 0
                existing.numsms = row.number_of_sms or 0
                existing.numinstagram = row.number_of_insta or 0
                existing.total = row.total or 0
                if row.number_of_whatsapp and row.number_of_whatsapp > 0:
                    existing.whatsappid = existing.whatsappid or chat_session
                if row.number_of_imessage and row.number_of_imessage > 0:
                    existing.imessageid = existing.imessageid or chat_session
                if row.number_of_sms and row.number_of_sms > 0:
                    existing.smsid = existing.smsid or chat_session
                if row.number_of_facebook and row.number_of_facebook > 0:
                    existing.facebookid = existing.facebookid or chat_session
                if row.number_of_insta and row.number_of_insta > 0:
                    existing.instagramid = existing.instagramid or chat_session
                updated += 1
            else:
                contact = Contacts(
                    name=chat_session,
                    is_group=bool(row.is_group_chat),
                    numwhatsapp=row.number_of_whatsapp or 0,
                    numimessages=row.number_of_imessage or 0,
                    numfacebook=row.number_of_facebook or 0,
                    numsms=row.number_of_sms or 0,
                    numinstagram=row.number_of_insta or 0,
                    total=row.total or 0,
                    whatsappid=chat_session if (row.number_of_whatsapp or 0) > 0 else None,
                    imessageid=chat_session if (row.number_of_imessage or 0) > 0 else None,
                    smsid=chat_session if (row.number_of_sms or 0) > 0 else None,
                    facebookid=chat_session if (row.number_of_facebook or 0) > 0 else None,
                    instagramid=chat_session if (row.number_of_insta or 0) > 0 else None,
                )
                session.add(contact)
                created += 1
        session.commit()
        return {"created": created, "updated": updated}
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting contacts: {str(e)}"
        )
    finally:
        session.close()


@router.get("/merge-contacts", response_model=MergeContactsResponse)
async def merge_contacts():
    """Merge likely matching contacts.

    Returns:
        MergeContactsResponse with:
        - message: Summary message
        - matched_contacts: List of matched contact pairs
        - contacts_merged: Number of contact pairs merged
    """
    likely_matching_contacts = find_likely_matching_contacts()
    matched_contacts_list = []
    contacts_merged = 0

    for row in likely_matching_contacts:
        contact_id_1, name_1, contact_id_2, name_2, match_reason = row

        # Add to matched contacts list
        matched_contacts_list.append(MatchedContactPair(
            contact_id_1=contact_id_1,
            name_1=name_1,
            contact_id_2=contact_id_2,
            name_2=name_2,
            match_reason=match_reason
        ))

        # Merge the contacts
        if contact_id_1 < contact_id_2:
            merge_two_contacts(contact_id_1, contact_id_2)
        else:
            merge_two_contacts(contact_id_2, contact_id_1)

        contacts_merged += 1

    return MergeContactsResponse(
        message=f"Found {len(matched_contacts_list)} matching contact pairs. Merged {contacts_merged} pairs.",
        matched_contacts=matched_contacts_list,
        contacts_merged=contacts_merged
    )
