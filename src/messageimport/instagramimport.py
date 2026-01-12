"""Instagram Messages import functionality."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from ..database.connection import Database
from ..database.storage import IMessageStorage


def parse_timestamp_ms(timestamp_ms: Optional[int]) -> Optional[datetime]:
    """Parse Unix timestamp in milliseconds to datetime object."""
    if not timestamp_ms:
        return None
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0)
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not parse timestamp '{timestamp_ms}': {e}")
        return None


def determine_message_type(sender_name: str, user_name: Optional[str], participants: list[Dict[str, Any]]) -> str:
    """Determine if message is Incoming or Outgoing.
    
    Args:
        sender_name: Name of the message sender
        user_name: User's name (if known)
        participants: List of participant dictionaries with 'name' field
        
    Returns:
        "Incoming" or "Outgoing"
    """
    # If user_name is provided, use it
    if user_name:
        return "Outgoing" if sender_name == user_name else "Incoming"
    
    # Otherwise, use first participant as default user
    if participants and len(participants) > 0:
        first_participant_name = participants[0].get('name', '')
        return "Outgoing" if sender_name == first_participant_name else "Incoming"
    
    # Default to Incoming if we can't determine
    return "Incoming"


def import_instagram_from_directory(
    directory_path: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
    export_root: Optional[str] = None,
    user_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import Instagram messages from a directory structure.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain JSON files (message_1.json, message_2.json, etc.) with the messages.
    
    Args:
        directory_path: Path to the top-level directory containing conversation subdirectories
        progress_callback: Optional callback function called after each conversation is processed.
                          Receives a dict with current stats.
        cancelled_check: Optional function to check if import should be cancelled.
                        Should return True if cancelled.
        export_root: Optional path to Instagram export root directory (for consistency, not used for attachments)
        user_name: Optional user's name to determine incoming/outgoing messages
        
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
    }
    
    # Iterate through subdirectories
    for subdir in directory.iterdir():
        if not subdir.is_dir():
            continue
        
        # Check for cancellation
        if cancelled_check and cancelled_check():
            print("Instagram import cancelled by user")
            break
        
        conversation_name = subdir.name
        stats["conversations_processed"] += 1
        stats["current_conversation"] = conversation_name
        
        # Find JSON files in the subdirectory (message_1.json, message_2.json, etc.)
        json_files = sorted(subdir.glob("message_*.json"), key=lambda p: int(p.stem.split('_')[1]) if p.stem.split('_')[1].isdigit() else 0)
        
        if not json_files:
            print(f"No message JSON file found in subdirectory: {conversation_name}")
            # Still call progress callback even if no JSON found
            if progress_callback:
                progress_callback(stats.copy())
            continue
        
        # Process each JSON file
        for json_file in json_files:
            print(f"Processing JSON file: {json_file}")
            try:
                with open(json_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    
                    # Extract title (chat_session) from top-level JSON
                    chat_session = data.get('title', conversation_name)
                    participants = data.get('participants', [])
                    messages = data.get('messages', [])
                    
                    # Process each message
                    for msg in messages:
                        try:
                            # Skip messages with only reactions or shares (no content)
                            # But process messages that have content even if they also have reactions/shares
                            content = msg.get('content', '')
                            if not content:
                                # Skip messages with no content (reactions and shares are ignored)
                                continue
                            
                            # Parse timestamp
                            timestamp_ms = msg.get('timestamp_ms')
                            message_date = parse_timestamp_ms(timestamp_ms)
                            
                            if not message_date:
                                print(f"Warning: Skipping message with invalid timestamp")
                                continue
                            
                            # Extract sender information
                            sender_name = msg.get('sender_name', '')
                            
                            # Determine message type
                            msg_type = determine_message_type(sender_name, user_name, participants)
                            
                            # Extract text content
                            text_content = content or None
                            
                            # Build message data dictionary
                            message_data = {
                                "chat_session": chat_session,
                                "message_date": message_date,
                                "delivered_date": message_date,  # Instagram doesn't provide separate delivered date
                                "read_date": None,  # Instagram doesn't provide read receipts
                                "edited_date": None,  # Instagram doesn't provide edit timestamps
                                "service": "Instagram",
                                "type": msg_type,
                                "sender_id": sender_name,  # Use sender_name as sender_id
                                "sender_name": sender_name,
                                "status": "Sent" if msg_type == "Outgoing" else "Received",
                                "replying_to": None,  # Instagram doesn't provide reply threading
                                "subject": None,  # Instagram doesn't have subject field
                                "text": text_content,
                                "attachment_filename": None,  # Instagram messages don't have attachments
                                "attachment_type": None,
                            }
                            
                            # Save message to database (no attachment data)
                            _, is_update = storage.save_imessage(message_data, None)
                            
                            if is_update:
                                stats["messages_updated"] += 1
                            else:
                                stats["messages_created"] += 1
                            
                            stats["messages_imported"] += 1
                            
                        except Exception as e:
                            print(f"Error processing message: {e}")
                            import traceback
                            traceback.print_exc()
                            stats["errors"] += 1
                            continue
                            
            except Exception as e:
                print(f"Error reading JSON file {json_file}: {e}")
                import traceback
                traceback.print_exc()
                stats["errors"] += 1
                continue
        
        # Call progress callback after each conversation is processed
        if progress_callback:
            progress_callback(stats.copy())
    
    return stats


def main():
    """Main function for testing the import."""
    # Initialize database connection and create tables
    db = Database()
    db.create_tables()
    
    # Test directory path - update this to your actual directory
    test_directory = r"G:\My Drive\meta-2026-Jan-11-23-24-13\instagram-dave.on.tour-2026-01-11-6UHErqvT\your_instagram_activity\messages\inbox"
    
    print(f"Starting Instagram import from: {test_directory}")
    print("-" * 60)
    
    try:
        stats = import_instagram_from_directory(test_directory)
        
        print("-" * 60)
        print("Import completed!")
        print(f"Conversations processed: {stats['conversations_processed']}")
        print(f"Messages imported: {stats['messages_imported']}")
        print(f"  - New messages created: {stats['messages_created']}")
        print(f"  - Existing messages updated: {stats['messages_updated']}")
        print(f"Errors: {stats['errors']}")
        
    except Exception as e:
        print(f"Import failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
