"""WhatsApp import functionality."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Callable

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
                                "attachment_filename": attachment_filename,
                                "attachment_type": attachment_type,
                            }
                            
                            # Save message to database
                            imessage, is_update = storage.save_imessage(message_data, attachment_data)
                            
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
    
    return stats


def main():
    """Main function for testing the import."""
    # Initialize database connection and create tables
    db = Database()
    db.create_tables()
    
    # Test directory path - update this to your actual directory
    test_directory = r"C:\NonOneDrive\iMazingBackup\David's iPhone (4729)\WhatsApp"
    
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
