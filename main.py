"""
Main entry point for Museum application.
Creates database tables and starts the API server.
"""

import argparse
from sys import platform
from googleapiclient.discovery import os
import uvicorn
from src.database import Database
from src.config import get_config
from src.api import app

import shutil
import subprocess

from src.services.gemini_service import ChatService
from src.services.relationship_service import RelationshipService


def main( test: bool = False):
    """Main function - initialize database and start API server."""

    
    # Initialize database and create tables
    config = get_config()
    db = Database(config)
    db.create_tables()
    print("Database tables created/verified.")

    if test:
        print("Running in test mode")
        test_gemini_service(db)
    else :
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

def test_gemini_service(db: Database):
    """Test the Gemini service."""
    chat_service = ChatService()
    chat_service.set_database(db=db)

    chat_service.get_complete_profile_by_name("Dave Burton")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-test", action="store_true", help="Enable test mode")
    args = parser.parse_args()
    main(test=args.test)
