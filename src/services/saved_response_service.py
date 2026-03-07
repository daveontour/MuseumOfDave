"""Service for saved chat response CRUD operations."""

from typing import List, Optional

from ..database import Database
from ..database.models import SavedResponse


class SavedResponseService:
    """Handles saved response storage and retrieval."""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        title: str,
        content: str,
        voice: Optional[str] = None,
        llm_provider: Optional[str] = None,
    ) -> SavedResponse:
        """Create a new saved response."""
        session = self.db.get_session()
        try:
            row = SavedResponse(
                title=title.strip(),
                content=content,
                voice=voice,
                llm_provider=llm_provider,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def list_all(self) -> List[SavedResponse]:
        """List all saved responses, newest first."""
        session = self.db.get_session()
        try:
            return session.query(SavedResponse).order_by(SavedResponse.created_at.desc()).all()
        finally:
            session.close()

    def get_by_id(self, id: int) -> Optional[SavedResponse]:
        """Get a saved response by ID."""
        session = self.db.get_session()
        try:
            return session.query(SavedResponse).filter(SavedResponse.id == id).first()
        finally:
            session.close()

    def update(
        self,
        id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        voice: Optional[str] = None,
        llm_provider: Optional[str] = None,
    ) -> Optional[SavedResponse]:
        """Update a saved response."""
        session = self.db.get_session()
        try:
            row = session.query(SavedResponse).filter(SavedResponse.id == id).first()
            if not row:
                return None
            if title is not None:
                row.title = title.strip()
            if content is not None:
                row.content = content
            if voice is not None:
                row.voice = voice
            if llm_provider is not None:
                row.llm_provider = llm_provider
            session.commit()
            session.refresh(row)
            return row
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, id: int) -> bool:
        """Delete a saved response. Returns True if deleted."""
        session = self.db.get_session()
        try:
            row = session.query(SavedResponse).filter(SavedResponse.id == id).first()
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
