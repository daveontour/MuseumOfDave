"""Relationship service for managing relationships between contacts."""

import json
from operator import or_
import re
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import distinct, text
import json
import re
from difflib import SequenceMatcher
from collections import defaultdict, Counter
from pathlib import Path

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
        self.FUZZY_MERGE_THRESHOLD = 0.78

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
            - name: Extracted name (returns email_address if name is None/Empty)
            - email_address: Extracted email address
        """
        if not email_string or not email_string.strip():
            return None, ""
        
        email_string = email_string.strip()
        
        # Pattern to match: "Name" <email@domain.com> or Name <email@domain.com>
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
                
                # Clean up the name if it exists
                if name:
                    # Remove any single or double quotes from the front or end
                    name = name.strip('\'"')
                    # Remove any trailing or leading spaces
                    name = name.strip()
                
                # UPDATE: If name is None or empty after cleaning, use email as the name
                final_name = name if name else email
                
                return (final_name, email)

            elif plain_email:
                # Format: just email@domain.com
                email_pattern = r'^[^\s<>]+@[^\s<>]+\.[^\s<>]+$'
                if re.match(email_pattern, plain_email.strip()):
                    return (plain_email.strip(), plain_email.strip())
                else:
                    # Might be just a name without email
                    return (plain_email.strip(), "")
        
        # Fallback: return the original string as email if it looks like an email
        email_pattern = r'^[^\s<>]+@[^\s<>]+\.[^\s<>]+$'
        if re.match(email_pattern, email_string):
            return (email_string, email_string)
        
        # If no pattern matches
        return ("", "")

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

            sql = """SELECT 
                    chat_session as name,
                    is_group_chat as is_group,
                    COUNT(CASE WHEN service = 'WhatsApp' THEN 1 END) AS numwhatsapp,
                    COUNT(CASE WHEN service = 'iMessage' THEN 1 END) AS numimessages,
                    COUNT(CASE WHEN service = 'Facebook Messenger' THEN 1 END) AS numfacebook,
                    COUNT(CASE WHEN service = 'SMS' THEN 1 END) AS numsms,
                    COUNT(CASE WHEN service = 'Instagram' THEN 1 END) AS numinstagram,
                    COUNT(CASE WHEN service ilike  '%' THEN 1 END) AS total
                FROM 
                    messages
                GROUP BY 
                    is_group,name
                ORDER BY 
                    is_group, name, total DESC;
                            """
            results = session.execute(text(sql)).fetchall()

            #create a contact entry for each result
            for result in results:
                try:
                    contact = Contacts(
                        name=result[0],
                        is_group=result[1],
                        numwhatsapp=result[2],
                        numimessages=result[3],
                        numfacebook=result[4],
                        numsms=result[5],
                        numinstagram=result[6],
                        total=result[7]
                    )
                    session.add(contact)
                    session.commit()
                    stats["contacts_created"] += 1
                except Exception as e:
                    error_msg = f"Error creating contact for {result[0]}: {str(e)}"
                    stats["errors"].append(error_msg)
                    continue

                

            return stats

            

            
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

    def get_from_addresses(self) -> List[str]:
        """Get all distinct from_addresses from the emails table.
        
        Returns:
            List of distinct from_addresses
        """
        session = self.db.get_session()
        try:
            from_addresses = session.query(Email.from_address).distinct().filter(
                Email.from_address.isnot(None),
                Email.from_address != ''
            ).all()
            #strip out any " from the from_addresses
            from_addresses = [address[0].strip().replace('"', '') for address in from_addresses if address[0]]
            parsed = [self.parse_email_address(address) for address in from_addresses]
            parsed = [value for value in parsed if value[1] is not None and value[1] != '']
            return parsed
        except Exception as e:
            raise ValidationError(f"Error getting from addresses: {str(e)}")
        finally:
            session.close()

    def get_to_addresses(self) -> List[str]:
        """Get all distinct to_addresses from the emails table.
        
        Returns:
            List of distinct to_addresses
        """
        session = self.db.get_session()
        try:
            to_addresses = session.query(Email.to_addresses).distinct().filter(
                Email.to_addresses.isnot(None),
                Email.to_addresses != ''
            ).all()

            #for each entry split the to_addresses by comma and add each address to the to_addresses list
            addresses = []
            for address in to_addresses:
                addresses.extend(address[0].split(','))
            addresses = [address.strip() for address in addresses]

            addresses = [address.strip().replace('"', '') for address in addresses if address]
            parsed = [self.parse_email_address(address) for address in addresses]
            parsed = [value for value in parsed if value[1] is not None and value[1] != '']

            return parsed





        except Exception as e:
            raise ValidationError(f"Error getting to addresses: {str(e)}")
        finally:
            session.close()

    def get_all_email_contacts(self) -> List[str]:
        """Get all email contacts from the emails table.
        
        Returns:
            List of email contacts
        """
        to_addresses = self.get_to_addresses()
        from_addresses = self.get_from_addresses()
        all_addresses = to_addresses + from_addresses

        #normalise the addresses to lowercase
        all_addresses = [(address[0], address[1].lower()) for address in all_addresses]

        #remove any duplicates from the all_addresses list
        all_addresses = list(set(all_addresses))    
        #remove any addresses where the email address is None or empty
        all_addresses = [address for address in all_addresses if address[1] is not None and address[1] != '']
        #remove any addresses where the name is None or empty
        all_addresses = [address for address in all_addresses if address[0] is not None and address[0] != '']
        #remove any addresses where the name is the same as the email address
        all_addresses = [address for address in all_addresses if address[0] != address[1]]
        #remove any addresses where the name is a number
        all_addresses = [address for address in all_addresses if not address[0].isdigit()]
        #remove any addresses where the name is a special character
        all_addresses = [address for address in all_addresses if not re.match(r'^[a-zA-Z0-9]+$', address[0])]
        #sort the all_addresses list by the name
        all_addresses.sort(key=lambda x: x[0])

        # Define exclusion patterns for email addresses and names
        email_exclusions = {
            "no-reply", "noreply", "no-response", "noresponse",
            "no-reply@", "noreply@", "no-response@", "noresponse@",
            "/O=", "satyam", "thales", "marketing", "info@","news@","mail@",
            "help@","contact@","customer-service@",
            "customer-support@","billing@","accounts@","hello@","undisclosed@",
            "customer-service@", "notification@", "contact@", "ticket@", "tickets@","ticketing@","ticketing-system@","ticketing-system-email@","ticketing-system-email-address@"
        }
        
        name_exclusions = {
            "news@", "mail@", "help@", "contact@", "customer-service@",
            "customer-support@", "billing@", "accounts@", "info@", "hello@",
            "undisclosed", "/O=", "satyam", "thales", "marketing"
        }
        
        def should_exclude_address(address: Tuple[str, str]) -> bool:
            """Check if an address should be excluded based on filtering rules."""
            name, email = address[0].lower(), address[1].lower()
            
            # Exclude if email is just a number
            if address[1].isdigit():
                return True
            
            # Exclude if email doesn't contain @ (not a valid email format)
            if "@" not in address[1]:
                return True
            
            # Exclude based on email patterns
            if any(pattern in email for pattern in email_exclusions):
                return True
            
            # Exclude based on name patterns
            if any(pattern in name for pattern in name_exclusions):
                return True
            
            return False
        
        # Apply all email-specific filters
        all_addresses = [address for address in all_addresses if not should_exclude_address(address)]

        

        return all_addresses

    def merge_duplicate_email_contacts(self) -> List[str]:
        """Merge duplicate email contacts from the emails table.
        
        Returns:
            List of email contacts
        """
        data_list = self.get_all_email_contacts()

        # Dictionary to group data by email
        email_map = {}

        for entry in data_list:
            # Unpack the tuple (Name is index 0, Email is index 1)
            name = entry[0]
            raw_email = entry[1]
            
            # Use lowercase email as the key to ensure case-insensitive matching
            # e.g. "User@Mail.com" matches "user@mail.com"
            email_key = raw_email.strip().lower()
            
            if email_key in email_map:
                # If email exists, check if this specific name is already in the list to avoid duplicates
                if name not in email_map[email_key]['names']:
                    email_map[email_key]['names'].append(name)
            else:
                # If email is new, create a new entry
                email_map[email_key] = {
                    'email': raw_email, # Preserves the casing of the first instance found
                    'names': [name]
                }

        # Convert the dictionary values back to a list
    
        cleaned_list = list(email_map.values())
        print("Number of cleaned list: ", len(cleaned_list))

        #combine the records by name using the fuzzy name similarity algorithm
        groups = self.combine_records(cleaned_list)
        print("Number of groups: ", len(groups))
        #build the output from the groups
        output = self.build_output(groups)
        print("Number of output: ", len(output))
        #output the output to a file
        with open('C:\\Users\\dave_\\OneDrive\Desktop\\combined_by_name_fuzzy.json', 'w') as f:
            json.dump(output, f, indent=2)
     


    def normalize_name(self, name: str) -> str:
        name = name.lower()
        name = re.sub(r"\(.*?\)", "", name)
        name = re.sub(r"[^a-z\s]", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name


    def tokenize(self, name: str):
        return set(name.split())


    def sequence_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


    def token_similarity(self, a: str, b: str) -> float:
        ta, tb = self.tokenize(a), self.tokenize(b)
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)


    def initial_similarity(self, a: str, b: str) -> float:
        a_tokens = a.split()
        b_tokens = b.split()
        if len(a_tokens) >= 2 and len(b_tokens) >= 2:
            return 1.0 if (
                a_tokens[0][0] == b_tokens[0][0]
                and a_tokens[-1] == b_tokens[-1]
            ) else 0.0
        return 0.0


    def fuzzy_name_similarity(self, a: str, b: str) -> float:
        return (
            0.45 * self.sequence_similarity(a, b) +
            0.45 * self.token_similarity(a, b) +
            0.10 * self.initial_similarity(a, b)
        )


    def confidence_bucket(self, score: float) -> str:
        if score >= 0.92:
            return "high"
        if score >= 0.85:
            return "medium"
        return "low"


    def load_data(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


    def combine_records(self, records):
        groups = []

        def new_group():
            groups.append({
                "names": set(),
                "emails": set(),
                "normalized": set(),
                "name_frequency": Counter(),
                "merge_scores": []
            })
            return len(groups) - 1

        for record in records:
            email = record["email"]
            print("Processing Email: ", email)
            raw_names = record.get("names", [])
            normalized_names = {self.normalize_name(n) for n in raw_names if n.strip()}

            best_group = None
            best_score = 0.0

            for gid, group in enumerate(groups):
                for n1 in normalized_names:
                    for n2 in group["normalized"]:
                        score = self.fuzzy_name_similarity(n1, n2)
                        if score > best_score:
                            best_score = score
                            best_group = gid

            if best_score >= self.FUZZY_MERGE_THRESHOLD:
                group_id = best_group
            else:
                group_id = new_group()

            group = groups[group_id]
            group["emails"].add(email)

            for raw in raw_names:
                norm = self.normalize_name(raw)
                if norm:
                    group["names"].add(raw)
                    group["normalized"].add(norm)
                    group["name_frequency"][raw] += 1

            if best_score > 0:
                group["merge_scores"].append(best_score)

        return groups


    def choose_primary_name(self, freq: Counter) -> Optional[str]:
        """Choose the primary name from frequency counter.
        
        Returns the most frequent name, or None if counter is empty.
        """
        if not freq:
            return None
        return sorted(
            freq.items(),
            key=lambda x: (-x[1], len(x[0]))
        )[0][0]


    def build_output(self, groups):
        output = []

        for g in groups:
            primary_name = self.choose_primary_name(g["name_frequency"])
            # Fallback to first email if no names available
            if not primary_name:
                primary_name = sorted(g["emails"])[0] if g["emails"] else "Unknown"

            max_score = max(g["merge_scores"], default=1.0)
            avg_score = (
                sum(g["merge_scores"]) / len(g["merge_scores"])
                if g["merge_scores"] else 1.0
            )

            output.append({
                "primary_name": primary_name,
                "primary_emails": sorted(g["emails"]),
                "alternative_names": sorted(
                    n for n in g["names"] if n != primary_name
                ),
                "alternative_emails": sorted(g["emails"]),
                "merge_confidence": self.confidence_bucket(avg_score),
                "merge_score_max": round(max_score, 3),
                "merge_score_avg": round(avg_score, 3)
            })

        return sorted(output, key=lambda x: x["primary_name"].lower())


# def main():
#     records = load_data(INPUT_FILE)
#     groups = combine_records(records)
#     output = build_output(groups)

#     Path(OUTPUT_FILE).write_text(
#         json.dumps(output, indent=2, ensure_ascii=False),
#         encoding="utf-8"
#     )


# if __name__ == "__main__":
#     main()
