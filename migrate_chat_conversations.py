"""
Migration script to create chat_conversations and chat_turns tables.

This script creates the database tables for chat conversation persistence.
The tables will also be created automatically when the application starts
via Base.metadata.create_all(), but this script can be run standalone
for explicit migrations.

Usage:
    python migrate_chat_conversations.py
"""

from src.database import Database
from src.config import get_config
from src.database.models import Base, ChatConversation, ChatTurn
from sqlalchemy import text


def migrate():
    """Create chat_conversations and chat_turns tables."""
    print("Starting migration: Creating chat_conversations and chat_turns tables...")
    
    config = get_config()
    db = Database(config)
    
    try:
        # Create tables using SQLAlchemy
        print("Creating tables...")
        Base.metadata.create_all(db.engine, tables=[ChatConversation.__table__, ChatTurn.__table__])
        print("✓ Tables created successfully")
        
        # Verify tables exist
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('chat_conversations', 'chat_turns')
            """))
            tables = [row[0] for row in result]
            
            if 'chat_conversations' in tables and 'chat_turns' in tables:
                print("✓ Migration completed successfully")
                print(f"  - Created table: chat_conversations")
                print(f"  - Created table: chat_turns")
            else:
                print("⚠ Warning: Some tables may not have been created")
                print(f"  Found tables: {tables}")
                
    except Exception as e:
        print(f"✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = migrate()
    exit(0 if success else 1)
