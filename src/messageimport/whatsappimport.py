"""WhatsApp import functionality."""

import csv
import mimetypes
from datetime import datetime
from pathlib import Path
import re
from typing import Dict, Any, Optional, Callable

from src.database import IMessage
from src.services.subject_configuration_service import SubjectConfigurationService

from ..database.connection import Database
from ..database.storage import IMessageStorage


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string from CSV format to datetime object."""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        print(f"Warning: Could not parse date '{date_str}': {e}")
        return None


# Exclusion patterns for non-group-chat notifications
NON_GROUP_CHAT_NOTIFICATION_PATTERNS = (
    "Messages to this chat and calls are now secured with end-to-end encryption",
    "You started a call",
    "You ended a call",
    "You joined a call",
    "You left a call",
    "You missed a call",
    "You rejected a call",
    "You accepted a call",
    "You declined a call",
    "You blocked a call",
    "changed their phone number to a new number",
    "is a contact",
    "This chat is now end-to-end encrypted",
    "Voice call -",
    "Video call -",
    "Missed video",
    "Missed voice",
    "This chat is with a business account",
    "turned on disappearing messages",
    "This business account has now registered as a standard account"
)


def find_attachment_file(base_dir: Path, filename: str) -> Optional[Path]:
    """Helper function to find attachment file by exact match or ending with filename."""
    # First try exact match
    exact_path = base_dir / filename
    if exact_path.exists() and exact_path.is_file():
        return exact_path
    
    # Search for files ending with the filename
    for file_path in base_dir.iterdir():
        if file_path.is_file() and file_path.name.endswith(filename):
            return file_path
    return None


def import_whatsapp_from_directory(
    directory_path: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None
) -> Dict[str, Any]:
    """
    Import WhatsApp messages from a directory structure.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain a CSV file with the messages.
    
    Args:
        directory_path: Path to the top-level directory containing conversation subdirectories
        progress_callback: Optional callback function called after each conversation is processed.
                          Receives a dict with current stats including missing_attachment_filenames.
        cancelled_check: Optional function to check if import should be cancelled.
                        Should return True if cancelled.
        
    Returns:
        dict: Statistics about the import process
    """
    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory does not exist or is not a directory: {directory_path}")
    
    storage = IMessageStorage()
    
    # Count total conversations first
    total_conversations = sum(1 for subdir in directory.iterdir() if subdir.is_dir())
    
    stats = {
        "conversations_processed": 0,
        "total_conversations": total_conversations,
        "messages_imported": 0,
        "messages_updated": 0,
        "messages_created": 0,
        "errors": 0,
        "attachments_found": 0,
        "attachments_missing": 0,
        "missing_attachment_filenames": [],
    }
    
    # Iterate through subdirectories
    for subdir in directory.iterdir():
        if not subdir.is_dir():
            continue
        
        # Check for cancellation
        if cancelled_check and cancelled_check():
            print("WhatsApp import cancelled by user")
            break
        
        conversation_name = subdir.name
        stats["conversations_processed"] += 1
        stats["current_conversation"] = conversation_name
        
        # Find CSV files in the subdirectory
        csv_files = list(subdir.glob("*.csv"))

        config_service = SubjectConfigurationService(db=Database())
        configuration = config_service.get_configuration()

        subject_name = configuration.subject_name if configuration else None
        subject_family_name = configuration.family_name if configuration else None
        subject_full_name = f"{subject_name} {subject_family_name}" if subject_name and subject_family_name else subject_name or subject_family_name or None
        
        if not csv_files:
            print(f"No CSV file found in subdirectory: {conversation_name}")
            # Still call progress callback even if no CSV found
            if progress_callback:
                progress_callback(stats.copy())
            continue
        
        # Process each CSV file (in case there are multiple)
        for csv_file in csv_files:
            print(f"Processing CSV file: {csv_file}")
            try:
                with open(csv_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        try:
                            # Parse dates
                            message_date = parse_date(row.get('Message Date', '').strip())
                            sent_date = parse_date(row.get('Sent Date', '').strip())
                            
                            # Parse attachment information
                            attachment_filename = row.get('Attachment', '').strip() or None
                            attachment_type = row.get('Attachment type', '').strip() or None
                            attachment_data = None
                            
                            # Handle attachments
                            if attachment_filename:
                                attachment_path = find_attachment_file(csv_file.parent, attachment_filename)
                                
                                # If not found and filename has .heic extension, try .jpg instead
                                if not attachment_path and attachment_filename.lower().endswith('.heic'):
                                    jpg_filename = attachment_filename[:-5] + '.jpg'  # Replace .heic with .jpg
                                    attachment_path = find_attachment_file(csv_file.parent, jpg_filename)
                                    if attachment_path:
                                        print(f"Found .jpg version instead of .heic: {attachment_path.name}")
                                        attachment_filename = jpg_filename
                                        attachment_type = "image/jpeg"
                                
                                # If not found and filename has .opus extension, try .mp3 instead
                                if not attachment_path and attachment_filename.lower().endswith('.opus'):
                                    mp3_filename = attachment_filename[:-5] + '.mp3'  # Replace .opus with .mp3
                                    attachment_path = find_attachment_file(csv_file.parent, mp3_filename)
                                    if attachment_path:
                                        print(f"Found .mp3 version instead of .opus: {attachment_path.name}")
                                        attachment_filename = mp3_filename
                                        attachment_type = "audio/mpeg"
                                
                                if attachment_path:
                                    try:
                                        with open(attachment_path, 'rb') as att_file:
                                            attachment_data = att_file.read()
                                        
                                        # If attachment_type is not set, guess it from the filename
                                        if not attachment_type or attachment_type == "Image" or attachment_type == "Video" or attachment_type == "Audio" or attachment_type == "Attachment":
                                            guessed_type, _ = mimetypes.guess_type(attachment_filename)
                                            if guessed_type:
                                                attachment_type = guessed_type
                                            else:
                                                # Fallback: try to determine from actual file path extension
                                                guessed_type, _ = mimetypes.guess_type(str(attachment_path))
                                                if guessed_type:
                                                    attachment_type = guessed_type
                                                else:
                                                    # Default fallback
                                                    attachment_type = "application/octet-stream"
                                        
                                        stats["attachments_found"] += 1
                                    except Exception as e:
                                        missing_filename = f"{conversation_name}/{attachment_filename}"
                                        print(f"Warning: Could not read attachment file {attachment_path}: {e}")
                                        stats["attachments_missing"] += 1
                                        if missing_filename not in stats["missing_attachment_filenames"]:
                                            stats["missing_attachment_filenames"].append(missing_filename)
                                else:
                                    missing_filename = f"{conversation_name}/{attachment_filename}"
                                    print(f"Warning: Attachment file not found: {attachment_filename}")
                                    stats["attachments_missing"] += 1
                                    if missing_filename not in stats["missing_attachment_filenames"]:
                                        stats["missing_attachment_filenames"].append(missing_filename)
                            
                            # Build message data dictionary
                            # Note: attachment_filename and attachment_type are passed separately to save_imessage
                            # and stored in media_items table, not in the message table
                            message_data = {
                                "chat_session": row.get('Chat Session', '').strip() or None,
                                "message_date": message_date,
                                "delivered_date": sent_date,  # WhatsApp Sent Date maps to delivered_date
                                "read_date": None,  # WhatsApp CSV doesn't have read date
                                "edited_date": None,  # WhatsApp CSV doesn't have edited date
                                "service": "WhatsApp",  # Always set to WhatsApp
                                "type": row.get('Type', '').strip() or None,
                                "sender_id": row.get('Sender ID', '').strip() or None,
                                "sender_name": row.get('Sender Name', '').strip() or None,
                                "status": row.get('Status', '').strip() or None,
                                "replying_to": row.get('Replying to', '').strip() or None,
                                "subject": None,  # WhatsApp CSV doesn't have subject
                                "text": row.get('Text', '').strip() or None,
                            }

                            # Check if notification indicates a group chat
                            # Group chat notifications exclude encryption messages, call events, and contact changes
                            if message_data['type'] == "Notification":
                                message_text = message_data.get('text') or ''
                                if not any(pattern in message_text for pattern in NON_GROUP_CHAT_NOTIFICATION_PATTERNS):
                                    message_data['is_group_chat'] = True

                            try:
                                message_data['chat_session'] = re.sub(r'[^\w\s]', '', message_data['chat_session']).strip()
                                if message_data['sender_name'] != None: 
                                    message_data['sender_name'] = re.sub(r'[^\w\s]', '', message_data['sender_name']).strip()
                            except Exception as e:
                                print(f"Skipping message from {message_data['chat_session']}")
                                continue;
                            
                            # Save message to database
                            imessage, is_update = storage.save_imessage(
                                message_data, 
                                attachment_data=attachment_data,
                                attachment_filename=attachment_filename,
                                attachment_type=attachment_type, 
                                source="WhatsApp"
                            )
                            
                            if is_update:
                                stats["messages_updated"] += 1
                            else:
                                stats["messages_created"] += 1
                            
                            stats["messages_imported"] += 1

                            
                            
                        except Exception as e:
                            print(f"Error processing message row: {e}")
                            stats["errors"] += 1
                            continue
                            
            except Exception as e:
                print(f"Error reading CSV file {csv_file}: {e}")
                stats["errors"] += 1
                continue
        
        # Call progress callback after each conversation is processed
        if progress_callback:
            progress_callback(stats.copy())
    
    print("Setting is_group_chat flag")
    set_is_group_chat()
    
    return stats

def set_is_group_chat() -> Dict[str, Any]:
        """Set the is_notification flag for the message data."""
        #for each distinct chat_session, checi his any message is a notification and if so, set the is_notification flag to True for all messages in that chat_session
        try:
            db = Database()
            session = db.get_session()
            distinct_chat_sessions = session.query(IMessage.chat_session).distinct().filter(IMessage.service == 'WhatsApp').all()
            for chat_session_tuple in distinct_chat_sessions:
                chat_session = chat_session_tuple[0]  # Extract the actual value from the tuple
                messages = session.query(IMessage).filter(IMessage.chat_session == chat_session).all()
                # Check if any message in this chat_session has is_notification set
                has_group_chat = any(message.is_group_chat for message in messages)
                # If any message has is_notification set, set all messages to is_notification = True
                if has_group_chat:
                    for message in messages:
                        message.is_group_chat = True
            session.commit()
            session.close()
        except Exception as e:
            print(f"Error setting is_notification flag: {e}")
            return False


def main():
    """Main function for testing the import."""
    # Initialize database connection and create tables
    db = Database()
    db.create_tables()

    #empty the messages table and the media_items table and the message_attachments table and the media_blob table
    db.empty_tables()
    db.commit()
    db.close()
    
    #recreate the tables
    db.create_tables()
    db.commit()
    db.close()
    
    # Test directory path - update this to your actual directory
    test_directory = r"C:\NonOneDrive\iMazingBackup\David's iPhone (4729)\WhatsAppTest"
    
    print(f"Starting WhatsApp import from: {test_directory}")
    print("-" * 60)
    
    try:
        stats = import_whatsapp_from_directory(test_directory)
        
        print("-" * 60)
        print("Import completed!")
        print(f"Conversations processed: {stats['conversations_processed']}")
        print(f"Messages imported: {stats['messages_imported']}")
        print(f"  - New messages created: {stats['messages_created']}")
        print(f"  - Existing messages updated: {stats['messages_updated']}")
        print(f"Attachments found: {stats['attachments_found']}")
        print(f"Attachments missing: {stats['attachments_missing']}")
        print(f"Errors: {stats['errors']}")
        
    except Exception as e:
        print(f"Import failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
