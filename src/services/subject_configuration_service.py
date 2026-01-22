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

    def create_or_update_configuration(self, subject_name: str, system_instructions: str, core_system_instructions: Optional[str] = None, gender: Optional[str] = None) -> SubjectConfiguration:
        """Create or update the subject configuration (singleton pattern).
        
        Args:
            subject_name: Name of the subject person
            system_instructions: System instructions/prompt text
            core_system_instructions: Core system instructions (optional, only updated if provided)
            gender: Gender of the subject (optional, defaults to "Male" if not provided)
            
        Returns:
            Created or updated SubjectConfiguration instance
            
        Raises:
            ValidationError: If subject_name or system_instructions is invalid
        """
        if not subject_name or not subject_name.strip():
            raise ValidationError("Subject name is required")
        if not system_instructions or not system_instructions.strip():
            raise ValidationError("System instructions are required")
        
        # Default gender to "Male" if not provided
        if gender is None:
            gender = "Male"
        
        session = self.db.get_session()
        try:
            # Check if configuration already exists
            configuration = session.query(SubjectConfiguration).first()
            
            if configuration:
                # Update existing configuration
                configuration.subject_name = subject_name.strip()
                configuration.system_instructions = system_instructions.strip()
                configuration.gender = gender.strip()
                if core_system_instructions is not None:
                    configuration.core_system_instructions = core_system_instructions.strip()
                configuration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new configuration
                # If core_system_instructions not provided, load from file
                if core_system_instructions is None:
                    core_system_instructions = self._load_core_instructions_from_file()
                
                configuration = SubjectConfiguration(
                    subject_name=subject_name.strip(),
                    gender=gender.strip(),
                    system_instructions=system_instructions.strip(),
                    core_system_instructions=core_system_instructions.strip() if core_system_instructions else ''
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

    def get_core_system_instructions(self) -> str:
        """Get core system instructions with fallback to file.
        
        Returns:
            Core system instructions from database if available, otherwise from file
        """
        configuration = self.get_configuration()
        
        if configuration and configuration.core_system_instructions:
            return configuration.core_system_instructions
        
        # Fallback to file
        return self._load_core_instructions_from_file()

    def _load_core_instructions_from_file(self) -> str:
        """Load core system instructions from file.
        
        Returns:
            Core system instructions from file, or empty string if file not found
        """
        try:
            file_path = Path('src/api/static/data/system_instructions_core.txt')
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
        except Exception as e:
            print(f"[SubjectConfigurationService] Error reading core system instructions file: {e}")
        
        return ""

    def _load_chat_instructions_from_file(self) -> str:
        """Load chat system instructions from file.
        
        Returns:
            Chat system instructions from file, or empty string if file not found
        """
        try:
            file_path = Path('src/api/static/data/system_instructions_chat.txt')
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
        except Exception as e:
            print(f"[SubjectConfigurationService] Error reading chat system instructions file: {e}")
        
        return ""

    def initialize_from_files(self) -> SubjectConfiguration:
        """Initialize subject configuration from files at startup.
        
        Always loads core_system_instructions from file.
        If no system_instructions exists in database, also loads from file.
        
        Returns:
            Created or updated SubjectConfiguration instance
        """
        # Always load core instructions from file
        core_instructions = self._load_core_instructions_from_file()
        
        session = self.db.get_session()
        try:
            configuration = session.query(SubjectConfiguration).first()
            
            if configuration:
                # Update core instructions (always overwrite)
                configuration.core_system_instructions = core_instructions
                
                # Only update system_instructions if it's empty/null
                if not configuration.system_instructions or not configuration.system_instructions.strip():
                    chat_instructions = self._load_chat_instructions_from_file()
                    if chat_instructions:
                        configuration.system_instructions = chat_instructions
                
                configuration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new configuration with both instructions from files
                chat_instructions = self._load_chat_instructions_from_file()
                configuration = SubjectConfiguration(
                    subject_name="Dave",  # Default subject name
                    gender="Male",  # Default gender
                    system_instructions=chat_instructions,
                    core_system_instructions=core_instructions
                )
                session.add(configuration)
            
            session.commit()
            session.refresh(configuration)
            return configuration
        finally:
            session.close()
