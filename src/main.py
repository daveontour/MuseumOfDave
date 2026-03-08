"""
Main entry point for Museum application.
Creates database tables and starts the API server.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is in path when run as src/main.py
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import uvicorn
from src.database import Database
from src.config import get_config


def main(test: bool = False):
    """Main function - initialize database and start API server."""

    config = get_config()
    db = Database(config)
    if not db.check_database_exists():
        raise RuntimeError("Cannot connect to database. Ensure it exists (or can be created) and check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD.")
    db.create_tables()
    print("Database tables created/verified.")

    # Import app after tables exist so config_service queries succeed
    from src.api import app
    from src.api.deps import subject_config_service, config_service

    seeded = config_service.seed_from_env()
    if seeded:
        print(f"Configuration: seeded {seeded} key(s) from .env")
    subject_config_service.initialize_from_files()

    port = int(os.getenv("HOST_PORT", "8000"))
    print("Subject configuration initialized from files.")
    print(f"Starting API server on http://0.0.0.0:{port}")
    print(f"API documentation available at http://localhost:{port}/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-test", action="store_true", help="Enable test mode")
    args = parser.parse_args()
    main(test=args.test)
