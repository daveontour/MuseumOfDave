"""Subject Configuration service for managing subject name and system instructions."""

from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from ..database import Database
from ..database.models import SubjectConfiguration
from .exceptions import NotFoundError, ValidationError


class SubjectConfigurationService:
    """Service for subject configuration-related business logic."""

    def __init__(self, db: Database):
        """Initialize the service with a database instance.
        
        Args:
            db: Database instance
        """
        self.db = db

    def get_configuration(self) -> Optional[SubjectConfiguration]:
        """Get the current subject configuration.
        
        Returns:
            SubjectConfiguration instance if exists, None otherwise
        """
        session = self.db.get_session()
        try:
            # Since we're using singleton pattern, get the first (and only) record
            configuration = session.query(SubjectConfiguration).first()
            return configuration
        finally:
            session.close()

    def create_or_update_configuration(self, subject_name: str, system_instructions: str) -> SubjectConfiguration:
        """Create or update the subject configuration (singleton pattern).
        
        Args:
            subject_name: Name of the subject person
            system_instructions: System instructions/prompt text
            
        Returns:
            Created or updated SubjectConfiguration instance
            
        Raises:
            ValidationError: If subject_name or system_instructions is invalid
        """
        if not subject_name or not subject_name.strip():
            raise ValidationError("Subject name is required")
        if not system_instructions or not system_instructions.strip():
            raise ValidationError("System instructions are required")
        
        session = self.db.get_session()
        try:
            # Check if configuration already exists
            configuration = session.query(SubjectConfiguration).first()
            
            if configuration:
                # Update existing configuration
                configuration.subject_name = subject_name.strip()
                configuration.system_instructions = system_instructions.strip()
                configuration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new configuration
                configuration = SubjectConfiguration(
                    subject_name=subject_name.strip(),
                    system_instructions=system_instructions.strip()
                )
                session.add(configuration)
            
            session.commit()
            session.refresh(configuration)
            return configuration
        finally:
            session.close()

    def get_subject_name(self) -> Optional[str]:
        """Get the current subject name.
        
        Returns:
            Subject name if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.subject_name if configuration else None

    def get_system_instructions(self) -> str:
        """Get system instructions with fallback to file.
        
        Returns:
            System instructions from database if available, otherwise from file
        """
        configuration = self.get_configuration()
        
        if configuration and configuration.system_instructions:
            return configuration.system_instructions
        
        # Fallback to file
        try:
            file_path = Path('src/api/static/data/system_instructions_chat.txt')
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
        except Exception as e:
            print(f"[SubjectConfigurationService] Error reading system instructions file: {e}")
        
        # Final fallback to default instructions
        return """You are an expert on life in general
Always answer confidently, don't be afraid to say you don't know and that you might have to do deeper research. 
If not much information is available, prompt the user to ask for more information. 

Do not refer to yourself as a large language model.
Do not be overtly positive, express sympathy and empathy when appropriate but also remain realistic.
When responding, do not mention the source of the data.

Always include a json structure at the end of your response. 
In the json structure, include the name of the person you are responding as.
In the json structure, include the the full pathname or URI of any attachments of any images in the attachments of any email or data file that you use in your response.
"""
