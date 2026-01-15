"""Message service for business logic."""

import re
from typing import List
from sqlalchemy import func, case, text

from ..database import Database
from ..database.models import IMessage
from .exceptions import NotFoundError
from .dto import ChatSessionsResult, ChatSessionInfo


class MessageService:
    """Service for message-related business logic."""

    def __init__(self, db: Database):
        """Initialize message service with database connection."""
        self.db = db

    def get_chat_sessions(self) -> ChatSessionsResult:
        """Get list of unique chat session names from messages table.
        
        Returns:
            ChatSessionsResult with contacts_and_groups and other arrays
        """
        session = self.db.get_session()
        try:
            # Query distinct chat_session values with message counts, attachment counts, and service types
            try:
                results = session.query(
                    IMessage.chat_session,
                    func.count(IMessage.id).label('message_count'),
                    func.sum(
                        case((IMessage.attachment_data.isnot(None), 1), else_=0)
                    ).label('attachment_count'),
                    func.max(IMessage.service).label('primary_service'),
                    func.max(IMessage.message_date).label('last_message_date'),
                    func.count(case((IMessage.service.ilike('%iMessage%'), 1), else_=None)).label('imessage_count'),
                    func.count(case((IMessage.service.ilike('%SMS%'), 1), else_=None)).label('sms_count'),
                    func.count(case((IMessage.service == 'WhatsApp', 1), else_=None)).label('whatsapp_count'),
                    func.count(case((IMessage.service == 'Facebook Messenger', 1), else_=None)).label('facebook_count'),
                    func.count(case((IMessage.service == 'Instagram', 1), else_=None)).label('instagram_count')
                ).filter(
                    IMessage.chat_session.isnot(None)
                ).group_by(
                    IMessage.chat_session
                ).order_by(
                    func.max(IMessage.message_date).desc()
                ).all()
            except Exception as table_error:
                # If table doesn't exist or has wrong name, try querying the old table name directly
                error_msg = str(table_error).lower()
                if 'does not exist' in error_msg or 'relation' in error_msg or 'table' in error_msg:
                    # Try querying the old 'imessages' table name
                    try:
                        results = session.execute(text("""
                            SELECT 
                                chat_session,
                                COUNT(id) as message_count,
                                SUM(CASE WHEN attachment_data IS NOT NULL THEN 1 ELSE 0 END) as attachment_count,
                                MAX(service) as primary_service,
                                MAX(message_date) as last_message_date,
                                COUNT(CASE WHEN service ILIKE '%iMessage%' THEN 1 END) as imessage_count,
                                COUNT(CASE WHEN service ILIKE '%SMS%' THEN 1 END) as sms_count,
                                COUNT(CASE WHEN service = 'WhatsApp' THEN 1 END) as whatsapp_count,
                                COUNT(CASE WHEN service = 'Facebook Messenger' THEN 1 END) as facebook_count,
                                COUNT(CASE WHEN service = 'Instagram' THEN 1 END) as instagram_count
                            FROM imessages
                            WHERE chat_session IS NOT NULL
                            GROUP BY chat_session
                            ORDER BY MAX(message_date) DESC
                        """)).fetchall()
                    except Exception:
                        # If that also fails, return empty results
                        results = []
                else:
                    raise
            
            def is_phone_number(chat_session: str) -> bool:
                """Check if chat_session is primarily a phone number."""
                if not chat_session:
                    return False
                # Remove common separators and check if it's mostly digits
                cleaned = re.sub(r'[\s\-\(\)]', '', chat_session)
                # Check if it starts with + followed by digits, or is mostly digits
                if cleaned.startswith('+'):
                    # Remove + and check if rest is digits
                    return cleaned[1:].isdigit() and len(cleaned[1:]) >= 7
                # Check if it's mostly digits (at least 7 digits)
                digit_count = sum(1 for c in cleaned if c.isdigit())
                return digit_count >= 7 and len(cleaned) <= 20
            
            contacts_and_groups = []
            other_sessions = []
            
            for result in results:
                imessage_count = result[5] or 0
                sms_count = result[6] or 0
                whatsapp_count = result[7] or 0
                facebook_count = result[8] if len(result) > 8 else 0
                instagram_count = result[9] if len(result) > 9 else 0
                total_count = result[1] or 0
                last_message_date = result[4]
                
                # Determine message type: 'imessage', 'sms', 'whatsapp', 'facebook', 'instagram', or 'mixed'
                non_zero_counts = sum([
                    1 if imessage_count > 0 else 0,
                    1 if sms_count > 0 else 0,
                    1 if whatsapp_count > 0 else 0,
                    1 if facebook_count > 0 else 0,
                    1 if instagram_count > 0 else 0
                ])
                
                if non_zero_counts == 1:
                    # Only one service type
                    if imessage_count > 0:
                        message_type = 'imessage'
                    elif sms_count > 0:
                        message_type = 'sms'
                    elif whatsapp_count > 0:
                        message_type = 'whatsapp'
                    elif facebook_count > 0:
                        message_type = 'facebook'
                    elif instagram_count > 0:
                        message_type = 'instagram'
                    else:
                        message_type = 'mixed'
                else:
                    message_type = 'mixed'
                
                session_info = ChatSessionInfo(
                    chat_session=result[0],
                    message_count=total_count,
                    attachment_count=result[2] or 0,
                    primary_service=result[3],
                    last_message_date=last_message_date,
                    imessage_count=imessage_count,
                    sms_count=sms_count,
                    whatsapp_count=whatsapp_count,
                    facebook_count=facebook_count,
                    instagram_count=instagram_count,
                    message_type=message_type
                )
                
                # Categorize: phone numbers go to "other", names go to "contacts_and_groups"
                if is_phone_number(result[0]):
                    other_sessions.append(session_info)
                else:
                    contacts_and_groups.append(session_info)
            
            return ChatSessionsResult(
                contacts_and_groups=contacts_and_groups,
                other=other_sessions
            )
        finally:
            session.close()

    def get_conversation_messages(self, chat_session: str) -> List[IMessage]:
        """Get messages for a specific chat session.
        
        Args:
            chat_session: Name of the chat session
            
        Returns:
            List of IMessage instances ordered by date
        """
        session = self.db.get_session()
        try:
            messages = session.query(IMessage).filter(
                IMessage.chat_session == chat_session
            ).order_by(IMessage.message_date.asc()).all()
            
            return messages
        finally:
            session.close()
