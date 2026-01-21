"""Chat Conversation service for managing chat conversations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy import desc, func

from ..database import Database
from ..database.models import ChatConversation, ChatTurn
from .exceptions import NotFoundError, ValidationError


class ChatConversationService:
    """Service for chat conversation-related business logic."""

    def __init__(self, db: Database):
        """Initialize the service with a database instance.
        
        Args:
            db: Database instance
        """
        self.db = db

    def create_conversation(self, title: str, voice: str) -> ChatConversation:
        """Create a new conversation.
        
        Args:
            title: User-provided conversation title
            voice: Voice to use for the conversation
            
        Returns:
            Created ChatConversation instance
            
        Raises:
            ValidationError: If title or voice is invalid
        """
        if not title or not title.strip():
            raise ValidationError("Conversation title is required")
        if not voice or not voice.strip():
            raise ValidationError("Voice is required")
        
        session = self.db.get_session()
        try:
            conversation = ChatConversation(
                title=title.strip(),
                voice=voice.strip()
            )
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            return conversation
        finally:
            session.close()

    def get_conversation(self, conversation_id: int) -> ChatConversation:
        """Get a conversation by ID.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            ChatConversation instance
            
        Raises:
            NotFoundError: If conversation doesn't exist
        """
        session = self.db.get_session()
        try:
            conversation = session.query(ChatConversation).filter(
                ChatConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise NotFoundError(f"Conversation with ID {conversation_id} not found")
            
            return conversation
        finally:
            session.close()

    def list_conversations(self, limit: Optional[int] = None, order_by: str = 'last_message_at') -> List[ChatConversation]:
        """List conversations, ordered by most recent activity.
        
        Args:
            limit: Optional limit on number of conversations to return
            order_by: Field to order by ('last_message_at' or 'created_at')
            
        Returns:
            List of ChatConversation instances
        """
        session = self.db.get_session()
        try:
            query = session.query(ChatConversation)
            
            # Order by specified field (descending for most recent first)
            if order_by == 'last_message_at':
                # Order by last_message_at, but put NULLs last
                query = query.order_by(
                    desc(ChatConversation.last_message_at).nullslast(),
                    desc(ChatConversation.created_at)
                )
            else:
                query = query.order_by(desc(ChatConversation.created_at))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        finally:
            session.close()

    def update_conversation(self, conversation_id: int, title: Optional[str] = None, voice: Optional[str] = None) -> ChatConversation:
        """Update conversation metadata.
        
        Args:
            conversation_id: ID of the conversation
            title: Optional new title
            voice: Optional new voice
            
        Returns:
            Updated ChatConversation instance
            
        Raises:
            NotFoundError: If conversation doesn't exist
            ValidationError: If title or voice is invalid
        """
        session = self.db.get_session()
        try:
            conversation = session.query(ChatConversation).filter(
                ChatConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise NotFoundError(f"Conversation with ID {conversation_id} not found")
            
            if title is not None:
                if not title.strip():
                    raise ValidationError("Conversation title cannot be empty")
                conversation.title = title.strip()
            
            if voice is not None:
                if not voice.strip():
                    raise ValidationError("Voice cannot be empty")
                conversation.voice = voice.strip()
            
            conversation.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(conversation)
            return conversation
        finally:
            session.close()

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its turns.
        
        Args:
            conversation_id: ID of the conversation
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If conversation doesn't exist
        """
        session = self.db.get_session()
        try:
            conversation = session.query(ChatConversation).filter(
                ChatConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise NotFoundError(f"Conversation with ID {conversation_id} not found")
            
            session.delete(conversation)
            session.commit()
            return True
        finally:
            session.close()

    def get_conversation_turns(self, conversation_id: int, limit: int = 30) -> List[ChatTurn]:
        """Get turns for a conversation, ordered by turn number (most recent last).
        
        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of turns to return (default 30)
            
        Returns:
            List of ChatTurn instances, ordered by turn_number ascending
        """
        session = self.db.get_session()
        try:
            # First verify conversation exists
            conversation = session.query(ChatConversation).filter(
                ChatConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise NotFoundError(f"Conversation with ID {conversation_id} not found")
            
            # Get total turn count
            total_turns = session.query(func.count(ChatTurn.id)).filter(
                ChatTurn.conversation_id == conversation_id
            ).scalar()
            
            # If we have more turns than limit, get the last N turns
            if total_turns > limit:
                # Get the starting turn number (total_turns - limit + 1)
                start_turn = total_turns - limit + 1
                turns = session.query(ChatTurn).filter(
                    ChatTurn.conversation_id == conversation_id,
                    ChatTurn.turn_number >= start_turn
                ).order_by(ChatTurn.turn_number.asc()).all()
            else:
                # Get all turns
                turns = session.query(ChatTurn).filter(
                    ChatTurn.conversation_id == conversation_id
                ).order_by(ChatTurn.turn_number.asc()).all()
            
            return turns
        finally:
            session.close()

    def save_turn(self, conversation_id: int, user_input: str, response_text: str, voice: str, temperature: float) -> ChatTurn:
        """Save a conversation turn.
        
        Args:
            conversation_id: ID of the conversation
            user_input: User's input message
            response_text: Assistant's response
            voice: Voice used for this turn
            temperature: Temperature used for this turn
            
        Returns:
            Created ChatTurn instance
            
        Raises:
            NotFoundError: If conversation doesn't exist
        """
        session = self.db.get_session()
        try:
            # Verify conversation exists
            conversation = session.query(ChatConversation).filter(
                ChatConversation.id == conversation_id
            ).first()
            
            if not conversation:
                raise NotFoundError(f"Conversation with ID {conversation_id} not found")
            
            # Get next turn number
            max_turn = session.query(func.max(ChatTurn.turn_number)).filter(
                ChatTurn.conversation_id == conversation_id
            ).scalar()
            
            turn_number = (max_turn or 0) + 1
            
            # Create turn
            turn = ChatTurn(
                conversation_id=conversation_id,
                user_input=user_input,
                response_text=response_text,
                voice=voice,
                temperature=temperature,
                turn_number=turn_number
            )
            session.add(turn)
            
            # Update conversation's last_message_at
            conversation.last_message_at = datetime.now(timezone.utc)
            conversation.updated_at = datetime.now(timezone.utc)
            
            session.commit()
            session.refresh(turn)
            return turn
        finally:
            session.close()
