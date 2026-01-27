"""Relationship service for managing relationships between contacts."""

from operator import or_
import re
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import distinct

from ..database import Database
from ..database.models import Relationship, Contacts, IMessage, Email
from .exceptions import NotFoundError, ValidationError


class RelationshipService:
    """Service for relationship-related business logic."""

    def __init__(self, db: Database):
        """Initialize the service with a database instance.
        
        Args:
            db: Database instance
        """
        self.db = db

    @staticmethod
    def parse_email_address(email_string: str) -> Tuple[Optional[str], str]:
        """Parse an email address string to extract name and email.
        
        Handles formats like:
        - "Mark James" <mark.james@fourcornersevents.com>
        - Mark James <mark.james@fourcornersevents.com>
        - mark.james@fourcornersevents.com
        
        Args:
            email_string: Email address string to parse
            
        Returns:
            Tuple of (name, email_address) where:
            - name: Extracted name (None if not found)
            - email_address: Extracted email address
        """
        if not email_string or not email_string.strip():
            return None, ""
        
        email_string = email_string.strip()
        
        # Pattern to match: "Name" <email@domain.com> or Name <email@domain.com>
        # This regex matches:
        # - Optional quoted name: "Name" or 'Name'
        # - Optional unquoted name: Name
        # - Email in angle brackets: <email@domain.com>
        pattern = r'^(?:"([^"]+)"|([^<]+))?\s*<([^>]+)>$|^(.+)$'
        match = re.match(pattern, email_string)
        
        if match:
            quoted_name = match.group(1)
            unquoted_name = match.group(2)
            email_in_brackets = match.group(3)
            plain_email = match.group(4)
            
            if email_in_brackets:
                # Format: "Name" <email> or Name <email>
                name = quoted_name or (unquoted_name.strip() if unquoted_name else None)
                email = email_in_brackets.strip()
                #remove any  single or double quotes from the fron tor end of the name
                name = name.strip('\'\"') if name else None
                #remove any trailing or leading spaces from the name
                name = name.strip() if name else None
                return (name.strip() if name else None, email)
            elif plain_email:
                # Format: just email@domain.com
                # Check if it's a valid email format
                email_pattern = r'^[^\s<>]+@[^\s<>]+\.[^\s<>]+$'
                if re.match(email_pattern, plain_email.strip()):
                    return (None, plain_email.strip())
                else:
                    # Might be just a name without email
                    return (plain_email.strip(), "")
        
        # Fallback: return the original string as email if it looks like an email
        email_pattern = r'^[^\s<>]+@[^\s<>]+\.[^\s<>]+$'

        if re.match(email_pattern, email_string):
            return (None, email_string)
        
        # If no pattern matches, return as name
        return (email_string, "")

    def create_contacts_from_chat_sessions(self) -> Dict[str, Any]:
        """Create contact entries from distinct combinations of chat_session and service values in the messages table.
        
        This method:
        1. Retrieves all distinct combinations of chat_session and service from the messages table
        2. Creates a contact entry for each chat_session/service combination
        3. Uses the chat_session value as the contact name
        4. Sets service-specific fields based on the service type:
           - iMessage: sets imessageid and numimessages
           - SMS: sets smsid and numsms
           - WhatsApp: sets whatsappid and numwhatsapp
           - Facebook Messenger: sets facebookid and numfacebook
           - Instagram: sets instagramid and numinstagram
        5. Skips sessions with less than 2 messages
        
        Returns:
            Dictionary with statistics:
            - total_sessions: Total number of distinct chat_session/service combinations found
            - contacts_created: Number of new contacts created
            - contacts_existing: Number of contacts that already existed (currently always 0)
            - errors: List of error messages if any
        """
        session = self.db.get_session()
        stats = {
            "total_sessions": 0,
            "contacts_created": 0,
            "contacts_existing": 0,
            "errors": []
        }
        
        try:
            # Get all distinct combinations of chat_session and service (excluding None and empty strings)
            distinct_sessions = session.query(
                IMessage.chat_session,
                IMessage.service
            ).filter(
                IMessage.chat_session.isnot(None),
                IMessage.chat_session != ''
            ).group_by(
                IMessage.chat_session,
                IMessage.service
            ).all()
            
            # Extract session names and services from tuples
            session_data = [(row[0], row[1]) for row in distinct_sessions if row[0]]
            stats["total_sessions"] = len(session_data)
            
            # Create contacts for each session/service combination that doesn't exist
            for session_name, service in session_data:

#remove any emojis like love hearts or other emojis from the session name
                session_name = re.sub(r'[^\w\s]', '', session_name).strip()

                #strip any leading or trailing spaces from the session name
                session_name = session_name.strip()
                #strip any leading or trailing spaces from the session name
                session_name = session_name.strip()
                #strip any leading or trailing spaces from the session name
                try:
                    # Check if contact already exists
                    existing_contact = session.query(Contacts).filter(
                        Contacts.name == session_name
                    ).first()
                    
                    # if existing_contact:
                    #     stats["contacts_existing"] += 1
                    # else:

                        #count the number of messages where the chat_session and service match
                    message_count = session.query(IMessage).filter(
                        IMessage.chat_session == session_name,
                        IMessage.service == service
                    ).count()

                    if message_count < 2:
                        print(f"Skipping contact {session_name} because it has less than 2 messages")
                        continue

                    new_contact = Contacts(
                        name=session_name,
                        description=f"Contact created from chat session: {session_name}"
                    )

                    if service == "iMessage":
                        new_contact.imessageid = session_name
                        new_contact.numimessages = message_count
                    elif service == "SMS":
                        new_contact.smsid = session_name
                        new_contact.numsms = message_count
                    elif service == "WhatsApp":
                        new_contact.whatsappid = session_name
                        new_contact.numwhatsapp = message_count
                    elif service == "Facebook Messenger":
                        new_contact.facebookid = session_name
                        new_contact.numfacebook = message_count
                    elif service == "Instagram":
                        new_contact.instagramid = session_name
                        new_contact.numinstagram = message_count
                    # Create new contact

                    session.add(new_contact)
                    stats["contacts_created"] += 1
                        
                except Exception as e:
                    error_msg = f"Error creating contact for session '{session_name}': {str(e)}"
                    stats["errors"].append(error_msg)
                    continue
            
            # Commit all changes
            session.commit()
            
        except Exception as e:
            session.rollback()
            error_msg = f"Error processing chat sessions: {str(e)}"
            stats["errors"].append(error_msg)
            raise
        finally:
            session.close()
        
        return stats

    def create_contacts_from_emails(self) -> Dict[str, Any]:
        """Create contact entries from distinct email addresses in the emails table.
        
        This method:
        1. Retrieves all distinct from_address values from the emails table
        2. Retrieves all distinct to_addresses values and splits comma-separated addresses
        3. Creates a contact entry for each unique email address that doesn't already exist
        4. Uses the email address as the contact name
        
        Returns:
            Dictionary with statistics:
            - total_addresses: Total number of unique email addresses found
            - contacts_created: Number of new contacts created
            - contacts_existing: Number of contacts that already existed
            - errors: List of error messages if any
        """
        session = self.db.get_session()
        stats = {
            "total_addresses": 0,
            "contacts_created": 0,
            "contacts_existing": 0,
            "errors": []
        }
        
        try:
            # Get all distinct from_address values (excluding None and empty strings)
            distinct_from = session.query(distinct(Email.from_address)).filter(
                Email.from_address.isnot(None),
                Email.from_address != ''
            ).all()
            
            # Get all distinct to_addresses values (excluding None and empty strings)
            distinct_to = session.query(distinct(Email.to_addresses)).filter(
                Email.to_addresses.isnot(None),
                Email.to_addresses != ''
            ).all()
            
            # Collect all unique email addresses
            unique_addresses = set()
            
            # Process from_address values
            for address_tuple in distinct_from:
                if address_tuple[0]:
                    address = address_tuple[0].strip()
                    if address:
                        unique_addresses.add(address)
            
            # Process to_addresses values (may contain comma-separated addresses)
            for addresses_tuple in distinct_to:
                if addresses_tuple[0]:
                    addresses_str = addresses_tuple[0].strip()
                    if addresses_str:
                        # Split by comma and process each address
                        addresses = [addr.strip() for addr in addresses_str.split(',')]
                        for address in addresses:
                            if address:
                                unique_addresses.add(address)
            
            stats["total_addresses"] = len(unique_addresses)
            
            # Create contacts for each address that doesn't exist
            for email_address in unique_addresses:
                # Parse the email address to get the name and email address
                name, parsed_email = self.parse_email_address(email_address)

                if name and parsed_email:                #continue if the email address or name contains no-reply or noreply or no-response or noresponse or no-reply@ or noreply@ or no-response@ or noresponse@
                    if "no-reply" in parsed_email.lower() or "noreply" in parsed_email.lower() or "no-response" in parsed_email.lower() or "noresponse" in parsed_email.lower() or "no-reply@" in parsed_email.lower() or "noreply@" in parsed_email.lower() or "no-response@" in parsed_email.lower() or "noresponse@" in parsed_email.lower():
                        continue
                    if "no-reply" in name.lower() or "noreply" in name.lower() or "no-response" in name.lower() or "noresponse" in name.lower() or "no-reply@" in name.lower() or "noreply@" in name.lower() or "no-response@" in name.lower() or "noresponse@" in name.lower():
                        continue
                    #continue if the name or email address contains @aol
                    if "@aol" in parsed_email.lower() or "@aol" in name.lower():
                        continue
                    if "marketing" in parsed_email.lower():
                        continue
                    if "info@" in parsed_email.lower() or "info@" in name.lower():
                        continue
                    if "-" in parsed_email.lower() or "-" in name.lower():
                        continue
                    if "support@" in parsed_email.lower() or "support@" in name.lower():
                        continue
                    if "help@" in parsed_email.lower() or "help@" in name.lower():
                        continue
                    if "contact@" in parsed_email.lower() or "contact@" in name.lower():
                        continue
                    if "customer-service@" in parsed_email.lower() or "customer-service@" in name.lower():
                        continue
                    if "customer-support@" in parsed_email.lower() or "customer-support@" in name.lower():
                        continue
                    if "billing@" in parsed_email.lower() or "billing@" in name.lower():
                        continue
                    if "accounts@" in parsed_email.lower() or "accounts@" in name.lower():
                        continue
                    if "info@" in parsed_email.lower() or "info@" in name.lower():
                        continue
                    if "hello@" in parsed_email.lower():
                        continue
                    if "undisclosed" in parsed_email.lower() or "undisclosed" in name.lower():
                        continue
                    if "/O=" in parsed_email:
                        continue
                    if "satyam" in parsed_email.lower():
                        continue
                    if "thales" in parsed_email.lower():
                        continue
                else:
                    print (f"Name or email address is not valid: {name},  {parsed_email}, {email_address}")
                    continue



                # Use parsed email if available, otherwise use original
                contact_email = parsed_email if parsed_email else email_address
                # Use parsed name if available, otherwise use email as name
                contact_name = name if name else contact_email
                
                try:
                    # Check if contact already exists (by email address first, then by name)
                    existing_contact = None
                    if contact_email:
                        existing_contact = session.query(Contacts).filter(
                            Contacts.email == contact_email
                        ).first()
                    
                    if not existing_contact and contact_name:
                        existing_contact = session.query(Contacts).filter(
                            Contacts.name == contact_name
                        ).first()

                    #count the number of emails where the email address is in the to_addresses field of the emails table or the from_address field of the emails table
                    email_count = session.query(Email).filter(
                        or_(
                            Email.to_addresses.like(f"%{contact_email}%"),
                            Email.from_address.like(f"%{contact_email}%")
                        )
                    ).count()
                    if email_count < 2:
                        print(f"Skipping contact {contact_name} with email {contact_email} because it has less than 2 emails")
                        #continue if the number of emails where the email address is in the to_addresses field of the emails table or the from_address field of the emails table is less than 5
                        continue

                    if existing_contact:
                        stats["contacts_existing"] += 1
                    else:
                        # Create new contact
                        new_contact = Contacts(
                            name=contact_name,
                            email=contact_email if contact_email else None,
                            description=f"Contact created from email address: {email_address}",
                            numemails=email_count
                        )
                        session.add(new_contact)
                        stats["contacts_created"] += 1
                        
                except Exception as e:
                    error_msg = f"Error creating contact for email '{email_address}': {str(e)}"
                    stats["errors"].append(error_msg)
                    continue
            
            # Commit all changes
            session.commit()
            
        except Exception as e:
            session.rollback()
            error_msg = f"Error processing email addresses: {str(e)}"
            stats["errors"].append(error_msg)
            raise
        finally:
            session.close()
        
        return stats

    def get_relationship(self, relationship_id: int) -> Relationship:
        """Get a relationship by ID.
        
        Args:
            relationship_id: ID of the relationship
            
        Returns:
            Relationship instance
            
        Raises:
            NotFoundError: If relationship not found
        """
        session = self.db.get_session()
        try:
            relationship = session.query(Relationship).filter(
                Relationship.id == relationship_id
            ).first()
            
            if not relationship:
                raise NotFoundError(f"Relationship with ID {relationship_id} not found")
            
            return relationship
        finally:
            session.close()

    def create_relationship(
        self,
        source_id: int,
        target_id: int,
        type: str,
        description: Optional[str] = None,
        ai_description: Optional[str] = None,
        strength: Optional[int] = None,
        is_active: bool = True,
        is_personal: bool = False,
        is_deleted: bool = False
    ) -> Relationship:
        """Create a new relationship.
        
        Args:
            source_id: ID of the source contact
            target_id: ID of the target contact
            type: Type of relationship (e.g., "friend", "family", "colleague")
            description: Manually entered description
            ai_description: AI generated description
            strength: Relationship strength (integer)
            is_active: Whether the relationship is active
            is_personal: Whether it's a personal relationship
            is_deleted: Whether the relationship is deleted
            
        Returns:
            Created Relationship instance
            
        Raises:
            ValidationError: If validation fails
            NotFoundError: If source or target contact not found
        """
        if source_id == target_id:
            raise ValidationError("Source and target contacts cannot be the same")
        
        if not type or not type.strip():
            raise ValidationError("Relationship type is required")
        
        session = self.db.get_session()
        try:
            # Verify contacts exist
            source_contact = session.query(Contacts).filter(Contacts.id == source_id).first()
            if not source_contact:
                raise NotFoundError(f"Source contact with ID {source_id} not found")
            
            target_contact = session.query(Contacts).filter(Contacts.id == target_id).first()
            if not target_contact:
                raise NotFoundError(f"Target contact with ID {target_id} not found")
            
            # Validate strength if provided
            if strength is not None and (strength < 0 or strength > 100):
                raise ValidationError("Strength must be between 0 and 100")
            
            # Create relationship
            relationship = Relationship(
                source_id=source_id,
                target_id=target_id,
                type=type.strip(),
                description=description,
                ai_description=ai_description,
                strength=strength,
                is_active=is_active,
                is_personal=is_personal,
                is_deleted=is_deleted
            )
            
            session.add(relationship)
            session.commit()
            
            return relationship
        except (NotFoundError, ValidationError):
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ValidationError(f"Error creating relationship: {str(e)}")
        finally:
            session.close()

    def get_relationships_by_contact(
        self,
        contact_id: int,
        include_deleted: bool = False
    ) -> List[Relationship]:
        """Get all relationships for a contact (as source or target).
        
        Args:
            contact_id: ID of the contact
            include_deleted: Whether to include deleted relationships
            
        Returns:
            List of Relationship instances
        """
        session = self.db.get_session()
        try:
            query = session.query(Relationship).filter(
                (Relationship.source_id == contact_id) | (Relationship.target_id == contact_id)
            )
            
            if not include_deleted:
                query = query.filter(Relationship.is_deleted == False)
            
            return query.all()
        finally:
            session.close()

    def update_relationship(
        self,
        relationship_id: int,
        type: Optional[str] = None,
        description: Optional[str] = None,
        ai_description: Optional[str] = None,
        strength: Optional[int] = None,
        is_active: Optional[bool] = None,
        is_personal: Optional[bool] = None,
        is_deleted: Optional[bool] = None
    ) -> Relationship:
        """Update an existing relationship.
        
        Args:
            relationship_id: ID of the relationship to update
            type: Relationship type to update
            description: Description to update
            ai_description: AI description to update
            strength: Strength to update
            is_active: Active status to update
            is_personal: Personal status to update
            is_deleted: Deleted status to update
            
        Returns:
            Updated Relationship instance
            
        Raises:
            NotFoundError: If relationship not found
            ValidationError: If validation fails
        """
        session = self.db.get_session()
        try:
            relationship = session.query(Relationship).filter(
                Relationship.id == relationship_id
            ).first()
            
            if not relationship:
                raise NotFoundError(f"Relationship with ID {relationship_id} not found")
            
            # Update fields if provided
            if type is not None:
                if not type.strip():
                    raise ValidationError("Relationship type cannot be empty")
                relationship.type = type.strip()
            
            if description is not None:
                relationship.description = description
            
            if ai_description is not None:
                relationship.ai_description = ai_description
            
            if strength is not None:
                if strength < 0 or strength > 100:
                    raise ValidationError("Strength must be between 0 and 100")
                relationship.strength = strength
            
            if is_active is not None:
                relationship.is_active = is_active
            
            if is_personal is not None:
                relationship.is_personal = is_personal
            
            if is_deleted is not None:
                relationship.is_deleted = is_deleted
            
            session.commit()
            return relationship
        except (NotFoundError, ValidationError):
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ValidationError(f"Error updating relationship: {str(e)}")
        finally:
            session.close()

    def delete_relationship(self, relationship_id: int) -> bool:
        """Delete a relationship (soft delete by setting is_deleted=True).
        
        Args:
            relationship_id: ID of the relationship to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundError: If relationship not found
        """
        session = self.db.get_session()
        try:
            relationship = session.query(Relationship).filter(
                Relationship.id == relationship_id
            ).first()
            
            if not relationship:
                raise NotFoundError(f"Relationship with ID {relationship_id} not found")
            
            relationship.is_deleted = True
            session.commit()
            return True
        except NotFoundError:
            session.rollback()
            raise
        except Exception as e:
            session.rollback()
            raise ValidationError(f"Error deleting relationship: {str(e)}")
        finally:
            session.close()
