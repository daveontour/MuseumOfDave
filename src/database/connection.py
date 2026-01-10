"""Database connection and management."""

from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from ..config import Config, get_config


class Database:
    """Database connection and management."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize database connection."""
        if config is None:
            config = get_config()
        self.config = config
        self.engine = create_engine(
            config.db.connection_string,
            pool_pre_ping=True,
            echo=False,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all tables if they don't exist."""
        # Try to create pgvector extension if available
        try:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
        except Exception:
            # pgvector extension not available, continue without it
            pass

        # Try to create pg_trgm extension for full-text search
        pg_trgm_available = False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                conn.commit()
                pg_trgm_available = True
        except Exception:
            # pg_trgm extension not available, will skip GIN index
            pass

        # Create tables
        print("Creating tables...")
        from .models import Base
        Base.metadata.create_all(self.engine)
        
        # Create index for plain_text column
        try:
            with self.engine.connect() as conn:
                if pg_trgm_available:
                    # Create GIN index with trigram operator class for full-text search
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_plain_text_fts "
                        "ON emails USING gin (plain_text gin_trgm_ops)"
                    ))
                else:
                    # Create simple btree index for basic searches
                    conn.execute(text(
                        "CREATE INDEX IF NOT EXISTS idx_plain_text_btree "
                        "ON emails (plain_text)"
                    ))
                conn.commit()
        except Exception:
            # If we can't create index, that's okay - searches will still work, just slower
            pass

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def check_database_exists(self) -> bool:
        """Check if database exists."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
