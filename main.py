"""
Main entry point for Museum of Dave application.
Creates database tables and starts the API server.
"""

import uvicorn
from src.database import Database
from src.config import get_config
from src.api import app


def main():
    """Main function - initialize database and start API server."""
    print("Initializing Museum of Dave application...")
    
    # Initialize database and create tables
    config = get_config()
    db = Database(config)
    db.create_tables()
    print("Database tables created/verified.")
    
    # Start the API server
    print("Starting API server on http://0.0.0.0:8000")
    print("API documentation available at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
