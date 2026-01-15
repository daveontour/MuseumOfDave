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
            pool_size=10,  # Number of connections to maintain in the pool
            max_overflow=20,  # Maximum number of connections beyond pool_size
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_timeout=30,  # Timeout for getting a connection from the pool
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
        
        # Create update_location_regions function
        try:
            with self.engine.connect() as conn:
                conn.execute(text("""
                    CREATE OR REPLACE FUNCTION update_location_regions()
                    RETURNS void AS $$
                    DECLARE
                        loc RECORD;
                        region_text TEXT;
                    BEGIN
                        FOR loc IN SELECT id, latitude, longitude FROM locations LOOP
                            -- Basic logic to determine region
                    
                            IF loc.latitude BETWEEN -44 AND -10 AND loc.longitude BETWEEN 110 AND 152 THEN
                                region_text := 'aus';
                            ELSIF loc.latitude BETWEEN 24 AND 26 AND loc.longitude BETWEEN 54 AND 56 THEN
                                region_text := 'dxb';
                            ELSIF loc.latitude BETWEEN 35 AND 70 AND loc.longitude BETWEEN -10 AND 30 THEN
                                region_text := 'eur';
                            ELSIF loc.latitude BETWEEN 20 AND 50 AND loc.longitude BETWEEN -128 AND -65 THEN
                                region_text := 'usa';
                            ELSIF loc.latitude BETWEEN -40 AND 35 AND loc.longitude BETWEEN -20 AND 50 THEN
                                region_text := 'af';
                            ELSIF loc.latitude BETWEEN 10 AND 40 AND loc.longitude BETWEEN 30 AND 60 THEN
                                region_text := 'me';
                            ELSIF loc.latitude BETWEEN -12 AND 54 AND loc.longitude BETWEEN 68 AND 152 THEN
                                region_text := 'asia';
                            ELSIF loc.latitude BETWEEN 9 AND 26 AND loc.longitude BETWEEN -76 AND -116 THEN
                                region_text := 'central_america';        
                            ELSIF loc.latitude BETWEEN 12 AND 25 AND loc.longitude BETWEEN -58 AND -85 THEN
                                region_text := 'carribean';        
                            ELSIF loc.latitude BETWEEN -47 AND -34 AND loc.longitude BETWEEN 163 AND 179 THEN
                                region_text := 'nz';        
                            ELSIF loc.latitude BETWEEN -56 AND 12 AND loc.longitude BETWEEN -99 AND -26 THEN
                                region_text := 'south_america'; 
                            ELSE
                                region_text := 'oth';
                            END IF;

                            -- Update the region field
                            UPDATE locations
                            SET region = region_text
                            WHERE id = loc.id;
                        END LOOP;
                    END;
                    $$ LANGUAGE plpgsql;
                """))
                conn.commit()
                print("Created/updated update_location_regions() function.")
        except Exception as e:
            # Log error but don't fail - function creation is optional
            print(f"Warning: Could not create update_location_regions() function: {e}")
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
