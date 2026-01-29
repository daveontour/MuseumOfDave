"""Facebook Messenger import functionality."""

import json
import mimetypes
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import text
from typing import Dict, Any, Optional, Callable

from sqlalchemy import func

from src.database import IMessage

from ..database.connection import Database
from ..database.storage import IMessageStorage
from .export_root_detector import detect_facebook_export_root


def parse_timestamp_ms(timestamp_ms: Optional[int]) -> Optional[datetime]:
    """Parse Unix timestamp in milliseconds to datetime object."""
    if not timestamp_ms:
        return None
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0)
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not parse timestamp '{timestamp_ms}': {e}")
        return None


def find_attachment_file(base_dir: Path, uri: str, export_root: Optional[Path] = None, auto_detect_root: bool = True) -> Optional[Path]:
    """Find attachment file by URI. URIs are relative to export root or conversation directory.
    
    Args:
        base_dir: Base directory (conversation directory)
        uri: URI from Facebook export (relative path)
        export_root: Optional export root directory for absolute URIs
        auto_detect_root: If True and export_root is None, attempt to auto-detect export root
        
    Returns:
        Path to attachment file if found, None otherwise
    """
    # Try relative to conversation directory first
    relative_path = base_dir / uri
    if relative_path.exists() and relative_path.is_file():
        return relative_path
    
    # Try relative to conversation directory with just filename
    filename = Path(uri).name
    filename_path = base_dir / filename
    if filename_path.exists() and filename_path.is_file():
        return filename_path
    
    # Try in subdirectories (photos/, videos/, files/)
    for subdir_name in ['photos', 'videos', 'files']:
        subdir_path = base_dir / subdir_name / filename
        if subdir_path.exists() and subdir_path.is_file():
            return subdir_path
    
    # Auto-detect export root if not provided
    detected_root = export_root
    if not detected_root and auto_detect_root:
        detected_root = detect_facebook_export_root(base_dir, uri)
        if detected_root:
            print(f"Auto-detected Facebook export root: {detected_root}")
    
    # Try relative to export root if provided or detected
    if detected_root:
        export_path = detected_root / uri
        if export_path.exists() and export_path.is_file():
            return export_path
    
    # Search for files ending with the filename
    for file_path in base_dir.rglob(filename):
        if file_path.is_file():
            return file_path
    
    return None


def guess_mime_type(filename: str) -> Optional[str]:
    """Guess MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type


def get_first_attachment(message: Dict[str, Any], conversation_dir: Path, export_root: Optional[Path] = None) -> tuple[Optional[str], Optional[str], Optional[bytes], list[Dict[str, Any]]]:
    """Extract first attachment from message, prioritizing photos > videos > files.
    
    Returns:
        tuple: (filename, mime_type, data, additional_attachments)
        where additional_attachments is a list of dicts with keys: filename, type, data
    """
    attachment_filename = None
    attachment_type = None
    attachment_data = None
    additional_attachments = []
    
    # Priority: photos > videos > files (stickers are ignored)
    photos = message.get('photos', [])
    videos = message.get('videos', [])
    files = message.get('files', [])
    
    # Process photos first
    if photos:
        # Process first photo
        photo = photos[0]
        uri = photo.get('uri', '')
        if uri:
            attachment_path = find_attachment_file(conversation_dir, uri, export_root)
            
            # Try .heic -> .jpg fallback
            if not attachment_path and uri.lower().endswith('.heic'):
                jpg_uri = uri[:-5] + '.jpg'
                attachment_path = find_attachment_file(conversation_dir, jpg_uri, export_root)
                if attachment_path:
                    uri = jpg_uri
            
            if attachment_path and attachment_path.exists():
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment_data = f.read()
                    attachment_filename = Path(uri).name
                    attachment_type = guess_mime_type(attachment_filename) or "image/jpeg"
                except Exception as e:
                    print(f"Warning: Could not read photo file {attachment_path}: {e}")
        
        # Process additional photos
        for photo in photos[1:]:
            uri = photo.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                # Try .heic -> .jpg fallback
                if not attachment_path and uri.lower().endswith('.heic'):
                    jpg_uri = uri[:-5] + '.jpg'
                    attachment_path = find_attachment_file(conversation_dir, jpg_uri, export_root)
                    if attachment_path:
                        uri = jpg_uri
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "image/jpeg"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read additional photo file {attachment_path}: {e}")
    
    # Process videos if no photo found
    if not attachment_data and videos:
        # Process first video
        video = videos[0]
        uri = video.get('uri', '')
        if uri:
            attachment_path = find_attachment_file(conversation_dir, uri, export_root)
            
            if attachment_path and attachment_path.exists():
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment_data = f.read()
                    attachment_filename = Path(uri).name
                    attachment_type = guess_mime_type(attachment_filename) or "video/mp4"
                except Exception as e:
                    print(f"Warning: Could not read video file {attachment_path}: {e}")
        
        # Process additional videos
        for video in videos[1:]:
            uri = video.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "video/mp4"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read additional video file {attachment_path}: {e}")
    
    # Process files if no photo or video found
    if not attachment_data and files:
        # Process first file
        file_obj = files[0]
        uri = file_obj.get('uri', '')
        if uri:
            attachment_path = find_attachment_file(conversation_dir, uri, export_root)
            
            # Try .opus -> .mp3 fallback
            if not attachment_path and uri.lower().endswith('.opus'):
                mp3_uri = uri[:-5] + '.mp3'
                attachment_path = find_attachment_file(conversation_dir, mp3_uri, export_root)
                if attachment_path:
                    uri = mp3_uri
            
            if attachment_path and attachment_path.exists():
                try:
                    with open(attachment_path, 'rb') as f:
                        attachment_data = f.read()
                    attachment_filename = Path(uri).name
                    attachment_type = guess_mime_type(attachment_filename) or "application/octet-stream"
                except Exception as e:
                    print(f"Warning: Could not read file {attachment_path}: {e}")
        
        # Process additional files
        for file_obj in files[1:]:
            uri = file_obj.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                # Try .opus -> .mp3 fallback
                if not attachment_path and uri.lower().endswith('.opus'):
                    mp3_uri = uri[:-5] + '.mp3'
                    attachment_path = find_attachment_file(conversation_dir, mp3_uri, export_root)
                    if attachment_path:
                        uri = mp3_uri
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "application/octet-stream"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read additional file {attachment_path}: {e}")
    
    # If we processed photos first, also process videos and files as additional attachments
    if attachment_data and photos:
        # Process videos as additional attachments
        for video in videos:
            uri = video.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "video/mp4"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read video file {attachment_path}: {e}")
        
        # Process files as additional attachments
        for file_obj in files:
            uri = file_obj.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                # Try .opus -> .mp3 fallback
                if not attachment_path and uri.lower().endswith('.opus'):
                    mp3_uri = uri[:-5] + '.mp3'
                    attachment_path = find_attachment_file(conversation_dir, mp3_uri, export_root)
                    if attachment_path:
                        uri = mp3_uri
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "application/octet-stream"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read file {attachment_path}: {e}")
    
    # If we processed videos first, also process files as additional attachments
    elif attachment_data and videos:
        # Process files as additional attachments
        for file_obj in files:
            uri = file_obj.get('uri', '')
            if uri:
                attachment_path = find_attachment_file(conversation_dir, uri, export_root)
                
                # Try .opus -> .mp3 fallback
                if not attachment_path and uri.lower().endswith('.opus'):
                    mp3_uri = uri[:-5] + '.mp3'
                    attachment_path = find_attachment_file(conversation_dir, mp3_uri, export_root)
                    if attachment_path:
                        uri = mp3_uri
                
                if attachment_path and attachment_path.exists():
                    try:
                        with open(attachment_path, 'rb') as f:
                            att_data = f.read()
                        att_filename = Path(uri).name
                        att_type = guess_mime_type(att_filename) or "application/octet-stream"
                        additional_attachments.append({
                            'filename': att_filename,
                            'type': att_type,
                            'data': att_data
                        })
                    except Exception as e:
                        print(f"Warning: Could not read file {attachment_path}: {e}")
    
    return attachment_filename, attachment_type, attachment_data, additional_attachments


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


def import_facebook_from_directory(
    directory_path: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    cancelled_check: Optional[Callable[[], bool]] = None,
    export_root: Optional[str] = None,
    user_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Import Facebook Messenger messages from a directory structure.
    
    The directory should contain subdirectories, each representing a conversation.
    Each subdirectory should contain JSON files (message_1.json, message_2.json, etc.) with the messages.
    
    Args:
        directory_path: Path to the top-level directory containing conversation subdirectories
        progress_callback: Optional callback function called after each conversation is processed.
                          Receives a dict with current stats including missing_attachment_filenames.
        cancelled_check: Optional function to check if import should be cancelled.
                        Should return True if cancelled.
        export_root: Optional path to Facebook export root directory (for resolving attachment URIs)
        user_name: Optional user's name to determine incoming/outgoing messages
        
    Returns:
        dict: Statistics about the import process
    """
    directory = Path(directory_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"Directory does not exist or is not a directory: {directory_path}")
    
    # Auto-detect export root if not provided
    export_root_path = None
    if export_root:
        export_root_path = Path(export_root)
    else:
        # Try to auto-detect export root from directory structure
        export_root_path = detect_facebook_export_root(directory)
        if export_root_path:
            print(f"Auto-detected Facebook export root: {export_root_path}")
    
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
            print("Facebook Messenger import cancelled by user")
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
                            # Skip messages with only stickers
                            if 'sticker' in msg and not msg.get('content') and not msg.get('photos') and not msg.get('videos') and not msg.get('files'):
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
                            text_content = msg.get('content', '') or None
                            
                            # Extract share information
                            share = msg.get('share')
                            subject = None
                            if share:
                                link = share.get('link', '')
                                share_text = share.get('share_text', '')
                                if link or share_text:
                                    subject = f"{share_text} {link}".strip()
                            
                            # Get first attachment and additional attachments
                            attachment_filename, attachment_type, attachment_data, additional_attachments = get_first_attachment(
                                msg, subdir, export_root_path
                            )
                            
                            # Track attachment statistics
                            if attachment_data:
                                stats["attachments_found"] += 1
                            elif attachment_filename:
                                missing_filename = f"{conversation_name}/{attachment_filename}"
                                stats["attachments_missing"] += 1
                                if missing_filename not in stats["missing_attachment_filenames"]:
                                    stats["missing_attachment_filenames"].append(missing_filename)
                            
                            # Build base message data dictionary (used for main message and additional attachments)
                            base_message_data = {
                                "chat_session": chat_session,
                                "message_date": message_date,
                                "delivered_date": message_date,  # Facebook doesn't provide separate delivered date
                                "read_date": None,  # Facebook doesn't provide read receipts
                                "edited_date": None,  # Facebook doesn't provide edit timestamps
                                "service": "Facebook Messenger",
                                "type": msg_type,
                                "sender_id": sender_name,  # Use sender_name as sender_id
                                "sender_name": sender_name,
                                "status": "Sent" if msg_type == "Outgoing" else "Received",
                                "replying_to": None,  # Facebook doesn't provide reply threading
                                "subject": subject,
                            }
                            
                            # Build main message data dictionary
                            message_data = {
                                **base_message_data,
                                "text": text_content,
                                "attachment_filename": attachment_filename,
                                "attachment_type": attachment_type,
                            }
                            
                            # Save main message to database
                            _, is_update = storage.save_imessage(
                                message_data,
                                attachment_data=attachment_data,
                                attachment_filename=attachment_filename,
                                attachment_type=attachment_type,
                                source="Facebook"
                            )
                            
                            if is_update:
                                stats["messages_updated"] += 1
                            else:
                                stats["messages_created"] += 1
                            
                            stats["messages_imported"] += 1
                            
                            # Create separate database entries for each additional attachment
                            for idx, additional_att in enumerate(additional_attachments, start=1):
                                # Track attachment statistics
                                if additional_att.get('data'):
                                    stats["attachments_found"] += 1
                                else:
                                    missing_filename = f"{conversation_name}/{additional_att.get('filename', 'unknown')}"
                                    stats["attachments_missing"] += 1
                                    if missing_filename not in stats["missing_attachment_filenames"]:
                                        stats["missing_attachment_filenames"].append(missing_filename)
                                
                                # Adjust message_date slightly to make each additional attachment unique
                                # Add milliseconds to keep them in chronological order but make them distinct
                                adjusted_message_date = message_date + timedelta(milliseconds=idx)
                                
                                # Build message data for additional attachment (text is None)
                                additional_message_data = {
                                    **base_message_data,
                                    "message_date": adjusted_message_date,  # Slightly adjusted to make unique
                                    "delivered_date": adjusted_message_date,  # Also adjust delivered_date
                                    "text": None,  # Text is null for additional attachments
                                    "attachment_filename": additional_att.get('filename'),
                                    "attachment_type": additional_att.get('type'),
                                }
                                
                                # Save additional attachment as separate message entry
                                _, is_update_att = storage.save_imessage(
                                    additional_message_data, 
                                    attachment_data=additional_att.get('data'),
                                    attachment_filename=additional_att.get('filename'),
                                    attachment_type=additional_att.get('type'),
                                    source="Facebook"
                                )
                                
                                if is_update_att:
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

    detect_group_chat()
    
    return stats

def detect_group_chat():
    """Detect if a chat is a group chat based on the participants."""
    try:
        db = Database()
        session = db.get_session()

        try:
            distinct_senders = session.query( IMessage.chat_session, func.count(func.distinct(IMessage.sender_id)).label('sender_count')).filter(IMessage.service == 'Facebook Messenger').group_by(IMessage.chat_session).all()
            for sender in distinct_senders:
                if sender.sender_count < 3:
                    continue;
                messages = session.query(IMessage).filter(IMessage.chat_session == sender.chat_session).filter(IMessage.service == 'Facebook Messenger').all()
                for message in messages:
                    message.is_group_chat = True
                session.commit()
        except Exception as e:
            print(f"Error detecting group chat: {e}")
            return False
        finally:
            session.close()

        session = db.get_session()
        try:
            #delete all the messages with is_group_chat = True, service = 'Facebook Messenger' and the number of messages is less than 3
            sql = """DELETE from messages where service = 'Facebook Messenger' AND chat_session IN (
                        SELECT chat_session
                        FROM messages
                        GROUP BY chat_session
                        HAVING COUNT(*) < 2 
                        )
        """
            session.execute(text(sql))
            session.commit()
        except Exception as e:
            print(f"Error deleting group chat messages: {e}")
            return False
        finally:
            session.close()
        

    except Exception as e:
            print(f"Error detecting group chat: {e}")
            return False

def main():
    """Main function for testing the import."""
    # Initialize database connection and create tables
    db = Database()
    db.create_tables()
    
    # Test directory path - update this to your actual directory
    test_directory = r"G:\My Drive\meta-2026-Jan-11-23-20-25\facebook-daveontour-2026-01-11-MnAtpBDv\your_facebook_activity\messages\e2ee_cutover"
    
    print(f"Starting Facebook Messenger import from: {test_directory}")
    print("-" * 60)
    
    try:
        stats = import_facebook_from_directory(test_directory)
        
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
