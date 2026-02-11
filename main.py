"""
Main entry point for Museum of Dave application.
Creates database tables and starts the API server.
"""

from sys import platform
from googleapiclient.discovery import os
import uvicorn
from src.database import Database
from src.config import get_config
from src.api import app

import shutil
import subprocess

from src.services.relationship_service import RelationshipService


def main():
    """Main function - initialize database and start API server."""
    print("Initializing Museum of Dave application...")
    
    # Initialize database and create tables
    config = get_config()
    db = Database(config)
    db.create_tables()
    print("Database tables created/verified.")
    
    # Initialize subject configuration from files
    from src.services.subject_configuration_service import SubjectConfigurationService
    config_service = SubjectConfigurationService(db=db)
    config_service.initialize_from_files()
    print("Subject configuration initialized from files.")
    
    # Start the API server
    print("Starting API server on http://0.0.0.0:8000")
    print("API documentation available at http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)

def testContactExtract():
    """Test the contact extraction service."""
    config = get_config()
    db = Database(config)
    relationship_service = RelationshipService(db=db)
    relationship_service.merge_duplicate_email_contacts()
   # from_addresses = relationship_service.get_all_email_contacts()
    # #to_addresses = relationship_service.get_to_addresses()
    # for address in from_addresses:
    #     print(address)
    # #print(f"To addresses: {to_addresses}")

if __name__ == "__main__":
    #test_imagemagick()
    main()
    # testContactExtract()