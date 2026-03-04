"""Subject Configuration service for managing subject name and system instructions."""

import os
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
import re

from ..database import Database
from ..database.models import SubjectConfiguration, Contacts
from .exceptions import NotFoundError, ValidationError


class SubjectConfigurationService:
    """Service for subject configuration-related business logic."""

    def __init__(self, db: Database):
        """Initialize the service with a database instance.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    def _normalize_phone_numbers(self, phone_numbers: Optional[str]) -> Optional[str]:
        """Normalize phone numbers by removing spaces, leading zeros, and '+' signs.
        
        Args:
            phone_numbers: Comma-separated phone numbers string
            
        Returns:
            Normalized comma-separated phone numbers string, or None if input is empty
        """
        if not phone_numbers or not phone_numbers.strip():
            return None
        
        # Split by comma and normalize each number
        numbers = [num.strip() for num in phone_numbers.split(',')]
        normalized_numbers = []
        
        for number in numbers:
            if not number:
                continue
            
            # Remove spaces, '+', and leading zeros
            normalized = re.sub(r'[\s+]', '', number)  # Remove spaces and +
            normalized = normalized.lstrip('0')  # Remove leading zeros
            
            if normalized:  # Only add if there's something left
                normalized_numbers.append(normalized)
        
        if normalized_numbers:
            return ', '.join(normalized_numbers)  # Join with comma-space for readability
        return None

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

    def create_or_update_configuration(self, subject_name: str, system_instructions: str, core_system_instructions: Optional[str] = None, gender: Optional[str] = None, family_name: Optional[str] = None, other_names: Optional[str] = None, email_addresses: Optional[str] = None, phone_numbers: Optional[str] = None, whatsapp_handle: Optional[str] = None, instagram_handle: Optional[str] = None) -> SubjectConfiguration:
        """Create or update the subject configuration (singleton pattern).
        
        Args:
            subject_name: Name of the subject person
            system_instructions: System instructions/prompt text
            core_system_instructions: Core system instructions (optional, only updated if provided)
            gender: Gender of the subject (optional, defaults to "Male" if not provided)
            family_name: Family name of the subject (optional)
            other_names: Other names, comma-separated (optional)
            email_addresses: Email addresses, comma-separated (optional)
            phone_numbers: Phone numbers, comma-separated (optional, will be normalized)
            whatsapp_handle: WhatsApp handle (optional)
            instagram_handle: Instagram handle (optional)
            
        Returns:
            Created or updated SubjectConfiguration instance
            
        Raises:
            ValidationError: If subject_name or system_instructions is invalid
        """
        if not subject_name or not subject_name.strip():
            raise ValidationError("Subject name is required")
        if not system_instructions or not system_instructions.strip():
            system_instructions = self._load_chat_instructions_from_file()

        
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
                if family_name is not None:
                    configuration.family_name = family_name.strip() if family_name.strip() else None
                if other_names is not None:
                    configuration.other_names = other_names.strip() if other_names.strip() else None
                if email_addresses is not None:
                    configuration.email_addresses = email_addresses.strip() if email_addresses.strip() else None
                if phone_numbers is not None:
                    configuration.phone_numbers = self._normalize_phone_numbers(phone_numbers)
                if whatsapp_handle is not None:
                    configuration.whatsapp_handle = whatsapp_handle.strip() if whatsapp_handle.strip() else None
                if instagram_handle is not None:
                    configuration.instagram_handle = instagram_handle.strip() if instagram_handle.strip() else None
                configuration.updated_at = datetime.now(timezone.utc)
            else:
                # Create new configuration
                # If core_system_instructions not provided, load from file
                if core_system_instructions is None:
                    core_system_instructions = self._load_core_instructions_from_file()
                
                configuration = SubjectConfiguration(
                    subject_name=subject_name.strip(),
                    gender=gender.strip(),
                    family_name=family_name.strip() if family_name and family_name.strip() else None,
                    other_names=other_names.strip() if other_names and other_names.strip() else None,
                    email_addresses=email_addresses.strip() if email_addresses and email_addresses.strip() else None,
                    phone_numbers=self._normalize_phone_numbers(phone_numbers),
                    whatsapp_handle=whatsapp_handle.strip() if whatsapp_handle and whatsapp_handle.strip() else None,
                    instagram_handle=instagram_handle.strip() if instagram_handle and instagram_handle.strip() else None,
                    system_instructions=system_instructions.strip(),
                    core_system_instructions=core_system_instructions.strip() if core_system_instructions else ''
                )
                session.add(configuration)
            
            # Create or update the corresponding Contacts entry with is_subject=True
            # Do this before commit so we can do a single commit for both operations
            # Prepare contact values from parameters (will be same as what's stored)
            contact_subject_name = subject_name.strip()
            contact_family_name = family_name.strip() if family_name and family_name.strip() else None
            contact_email_addresses = email_addresses.strip() if email_addresses and email_addresses.strip() else None
            contact_phone_numbers = self._normalize_phone_numbers(phone_numbers)
            contact_whatsapp_handle = whatsapp_handle.strip() if whatsapp_handle and whatsapp_handle.strip() else None
            contact_instagram_handle = instagram_handle.strip() if instagram_handle and instagram_handle.strip() else None
            
            self._sync_contacts_entry(
                session=session,
                subject_name=contact_subject_name,
                family_name=contact_family_name,
                email_addresses=contact_email_addresses,
                phone_numbers=contact_phone_numbers,
                whatsapp_handle=contact_whatsapp_handle,
                instagram_handle=contact_instagram_handle
            )
            
            # Single commit for both SubjectConfiguration and Contacts changes
            session.commit()
            session.refresh(configuration)
            # Expunge the object from the session so it can be used after session closes
            # This prevents DetachedInstanceError when accessing attributes after return
            session.expunge(configuration)
            return configuration
        finally:
            session.close()
    
    def _sync_contacts_entry(self, session, subject_name: str, family_name: Optional[str] = None, email_addresses: Optional[str] = None, phone_numbers: Optional[str] = None, whatsapp_handle: Optional[str] = None, instagram_handle: Optional[str] = None):
        """Create or update the Contacts entry for the subject.
        
        Args:
            session: Database session
            subject_name: Subject's name
            family_name: Family name (optional)
            email_addresses: Comma-separated email addresses (optional)
            phone_numbers: Comma-separated phone numbers (optional, already normalized)
            whatsapp_handle: WhatsApp handle (optional)
            instagram_handle: Instagram handle (optional)
        """
        # Build the contact name - use subject_name, optionally with family_name
        contact_name = subject_name
        if family_name:
            contact_name = f"{subject_name} {family_name}".strip()
        
        # Find existing contact with is_subject=True
        subject_contact = session.query(Contacts).filter(Contacts.id == 0).first()
        
        if subject_contact:
            # Update existing contact
            subject_contact.name = contact_name
            if email_addresses is not None:
                subject_contact.email = email_addresses
            if phone_numbers is not None:
                # Store phone numbers in smsid field (or combine with existing)
                # Note: Contacts model doesn't have a dedicated phone_numbers field,
                # so we'll use smsid as a general phone number field
                subject_contact.smsid = phone_numbers
            if whatsapp_handle is not None:
                subject_contact.whatsappid = whatsapp_handle
            if instagram_handle is not None:
                subject_contact.instagramid = instagram_handle
            subject_contact.updated_at = datetime.now(timezone.utc)
        else:
            # Create new contact
            subject_contact = Contacts(
                name=contact_name,
                is_subject=True,
                email=email_addresses,
                smsid=phone_numbers,  # Using smsid field for phone numbers
                whatsappid=whatsapp_handle,
                instagramid=instagram_handle
            )
            session.add(subject_contact)

    def update_writing_style_ai(self, writing_style_ai: Optional[str]) -> Optional[SubjectConfiguration]:
        """Update the writing_style_ai field of the subject configuration.
        
        Args:
            writing_style_ai: The AI-generated writing style summary (markdown), or None to clear
            
        Returns:
            Updated SubjectConfiguration if one exists, None otherwise
        """
        session = self.db.get_session()
        try:
            configuration = session.query(SubjectConfiguration).first()
            if not configuration:
                return None
            configuration.writing_style_ai = writing_style_ai.strip() if writing_style_ai and writing_style_ai.strip() else None
            configuration.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(configuration)
            session.expunge(configuration)
            return configuration
        finally:
            session.close()

    def update_psychological_profile_ai(self, psychological_profile_ai: Optional[str]) -> Optional[SubjectConfiguration]:
        """Update the psychological_profile_ai field of the subject configuration.
        
        Args:
            psychological_profile_ai: The AI-generated psychological profile (markdown), or None to clear
            
        Returns:
            Updated SubjectConfiguration if one exists, None otherwise
        """
        session = self.db.get_session()
        try:
            configuration = session.query(SubjectConfiguration).first()
            if not configuration:
                return None
            configuration.psychological_profile_ai = psychological_profile_ai.strip() if psychological_profile_ai and psychological_profile_ai.strip() else None
            configuration.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(configuration)
            session.expunge(configuration)
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

    def get_gender(self) -> Optional[str]:
        """Get the subject's gender.
        
        Returns:
            Gender if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.gender if configuration else None

    def get_family_name(self) -> Optional[str]:
        """Get the subject's family name.
        
        Returns:
            Family name if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.family_name if configuration else None

    def get_other_names(self) -> Optional[str]:
        """Get the subject's other names (comma-separated).
        
        Returns:
            Other names if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.other_names if configuration else None

    def get_email_addresses(self) -> Optional[str]:
        """Get the subject's email addresses (comma-separated).
        
        Returns:
            Email addresses if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.email_addresses if configuration else None

    def get_phone_numbers(self) -> Optional[str]:
        """Get the subject's phone numbers (comma-separated).
        
        Returns:
            Phone numbers if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.phone_numbers if configuration else None

    def get_whatsapp_handle(self) -> Optional[str]:
        """Get the subject's WhatsApp handle.
        
        Returns:
            WhatsApp handle if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.whatsapp_handle if configuration else None

    def get_instagram_handle(self) -> Optional[str]:
        """Get the subject's Instagram handle.
        
        Returns:
            Instagram handle if configuration exists, None otherwise
        """
        configuration = self.get_configuration()
        return configuration.instagram_handle if configuration else None

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
        return """
                You are an expert on {SUBJECT_NAME}'s life.
                Your personality, name and viewpoint are referred to later in this prompt. Alway tryo to be true to your assigned personality.

                Do not mention referring to {SUBJECT_NAME}'s bio in your response, treat the bio as your own information.
                Always refer to {SUBJECT_NAME}'s biography, biographical notes, and biographical data before responding.
                Refer to {SUBJECT_NAME} as 'he' or 'him' or 'his' or '{SUBJECT_NAME}'

                If any person is mentioned, check {SUBJECT_NAME}'s bio for information about that person.

                If there is any ambiguity about a person, prompt the user to ask for more information to clarify.

                The name 'Ellen' refers to Ellen O'Gorman also known as 'Elle'. There is an Ellen in emails from TasNetworks which is not the same person and should be ignored.
                The name 'Peter' could refer to Peter Wagstaff, Peter Burton, Peter Hinrichsen or Peter Cooper, prompt the user to ask for more information to clarify.
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

                #get the default subject name and family name from the environment variables
                default_subject_name = os.getenv("DEFAULT_SUBJECT_NAME")
                default_subject_family_name = os.getenv("DEFAULT_SUBJECT_FAMILY_NAME")
                default_gender = os.getenv("DEFAULT_SUBJECT_GENDER")

                configuration = SubjectConfiguration(
                    subject_name=default_subject_name,  # Default subject name
                    gender=default_gender,  # Default gender
                    family_name=default_subject_family_name,  # Default family name
                    system_instructions=chat_instructions,
                    core_system_instructions=core_instructions
                )
                session.add(configuration)
            
            session.commit()
            session.refresh(configuration)
            return configuration
        finally:
            session.close()
