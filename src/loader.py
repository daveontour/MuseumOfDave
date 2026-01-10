"""
Email Database Loader module for loading emails into a database.
"""

import base64
import os
from io import BytesIO
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont

from .database import Attachment, Email
from .config import Config, get_config
from .database.storage import EmailStorage
from .email_client import GmailClient


class EmailDatabaseLoader:
    """
    Main class for loading emails into a database.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the EmailDatabaseLoader."""
        if config is None:
            config = get_config()
        self.config = config

        # Initialize the storage
        self.storage = EmailStorage()
    
    def init_client(self):
        """Initialize the Gmail client."""
        self.client = GmailClient()
        self.client.authenticate()
    
    def _is_image(self, mime_type: Optional[str]) -> bool:
        """Check if a MIME type represents an image.
        
        Args:
            mime_type: The MIME type to check
            
        Returns:
            True if the MIME type is an image, False otherwise
        """
        if not mime_type:
            return False
        return mime_type.lower().startswith("image/")
    
    def _get_file_type(self, mime_type: Optional[str], filename: Optional[str] = None) -> str:
        """Determine file type from MIME type and/or filename.
        
        Args:
            mime_type: The MIME type
            filename: Optional filename
            
        Returns:
            File type: 'image', 'pdf', 'text', 'video', 'audio', or 'unknown'
        """
        if not mime_type:
            mime_type = ""
        mime_lower = mime_type.lower()
        
        if mime_lower.startswith("image/"):
            return "image"
        elif mime_lower == "application/pdf":
            return "pdf"
        elif mime_lower.startswith("text/"):
            return "text"
        elif mime_lower.startswith("video/"):
            return "video"
        elif mime_lower.startswith("audio/"):
            return "audio"
        elif filename:
            # Check file extension as fallback
            _, ext = os.path.splitext(filename)
            ext = ext.lstrip(".").lower()
            if ext == "pdf":
                return "pdf"
            elif ext in ["txt", "md", "csv", "json", "xml", "html", "css", "js"]:
                return "text"
            elif ext in ["mp4", "avi", "mov", "wmv", "flv", "webm", "mkv"]:
                return "video"
            elif ext in ["mp3", "wav", "ogg", "flac", "aac", "m4a"]:
                return "audio"
        
        return "unknown"
    
    def _create_icon_thumbnail(self, file_type: str, max_size: int = 100) -> bytes:
        """Create an icon-based thumbnail for non-image file types.
        
        Args:
            file_type: Type of file ('pdf', 'text', 'video', 'audio', 'unknown')
            max_size: Size of thumbnail (default: 100)
            
        Returns:
            Binary thumbnail data as JPEG
        """
        # Define colors and labels for each file type
        type_configs = {
            "pdf": {"color": (220, 38, 38), "label": "PDF"},  # Red
            "text": {"color": (34, 139, 34), "label": "TEXT"},  # Green
            "video": {"color": (75, 0, 130), "label": "VIDEO"},  # Purple
            "audio": {"color": (255, 140, 0), "label": "AUDIO"},  # Orange
            "unknown": {"color": (128, 128, 128), "label": "FILE"},  # Gray
        }
        
        config = type_configs.get(file_type, type_configs["unknown"])
        bg_color = config["color"]
        label = config["label"]
        
        # Create image with white background
        img = Image.new("RGB", (max_size, max_size), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw colored rectangle (slightly inset)
        margin = 10
        draw.rectangle(
            [margin, margin, max_size - margin, max_size - margin],
            fill=bg_color,
            outline=(200, 200, 200),
            width=2
        )
        
        # Try to use a default font, fallback to basic if not available
        font_size = max_size // 4
        font = None
        
        # Try common font paths
        font_paths = [
            "arial.ttf",
            "Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
        
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        
        # Fallback to default font if no truetype font found
        if font is None:
            font = ImageFont.load_default()
        
        # Calculate text position (centered)
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (max_size - text_width) // 2
        text_y = (max_size - text_height) // 2
        
        # Draw text in white
        draw.text((text_x, text_y), label, fill=(255, 255, 255), font=font)
        
        # Save to bytes as JPEG
        thumbnail_bytes = BytesIO()
        img.save(thumbnail_bytes, format="JPEG", quality=85)
        thumbnail_bytes.seek(0)
        
        return thumbnail_bytes.getvalue()
    
    def _create_thumbnail(self, image_data: bytes, max_size: int = 100) -> Optional[bytes]:
        """Create a thumbnail from image data.
        
        Args:
            image_data: Binary image data
            max_size: Maximum width/height for thumbnail (default: 100)
            
        Returns:
            Binary thumbnail data as JPEG, or None if creation fails
        """
        try:
            # Open image from bytes
            img = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary (handles RGBA, P, etc.)
            if img.mode in ("RGBA", "LA", "P"):
                # Create a white background
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # Calculate thumbnail size maintaining aspect ratio
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save to bytes as JPEG
            thumbnail_bytes = BytesIO()
            img.save(thumbnail_bytes, format="JPEG", quality=85)
            thumbnail_bytes.seek(0)
            
            return thumbnail_bytes.getvalue()
        except Exception as e:
            print(f"Warning: Could not create thumbnail: {e}")
            return None
    
    def _should_save_attachment(self, attachment: Dict[str, Any]) -> bool:
        """Check if an attachment should be saved based on configuration.
        
        Args:
            attachment: Dictionary containing attachment data with keys:
                - filename: Optional filename
                - mimeType: Optional MIME type
                - size: Optional size in bytes
        
        Returns:
            True if attachment should be saved, False otherwise
        """
        attachment_config = self.config.attachments
        
        # If no filtering is configured, save all attachments
        if attachment_config.allowed_types is None and attachment_config.min_size == 0:
            return True
        
        # Check size first (most efficient check)
        size = attachment.get("size", 0)
        if size < attachment_config.min_size:
            return False
        
        # If no type restrictions, only size matters
        if attachment_config.allowed_types is None:
            return True
        
        # Check MIME type
        mime_type = attachment.get("mimeType", "").lower()
        if mime_type and mime_type in attachment_config.allowed_types:
            return True
        
        # Check file extension
        filename = attachment.get("filename", "")
        if filename:
            # Get extension without the dot
            _, ext = os.path.splitext(filename)
            ext = ext.lstrip(".").lower()
            if ext and ext in attachment_config.allowed_types:
                return True
        
        # Attachment doesn't match any allowed type
        return False
    
    def process_email(self, email):
        """Process an email. Saves the retrieved email to the database."""

        uid = email["metadata"]["uid"]
        # Convert labels list to comma-separated string
        labels = email["metadata"]["labels"]
        folder = ",".join(labels) if isinstance(labels, list) else str(labels)
        subject = email["metadata"]["subject"]
        snippet = email["snippet"]
        from_address = email["metadata"]["from"]
        to_addresses = email["metadata"]["to"]
        cc_addresses = email["metadata"]["cc"]
        bcc_addresses = email["metadata"]["bcc"]
        
        # Parse date string to datetime object
        date_str = email["metadata"]["date"]
        date = None
        if date_str:
            try:
                date = parsedate_to_datetime(date_str)
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse date '{date_str}': {e}")
                date = None
        
        raw_message = email["body"]["html"]
        plain_text = email["body"]["text"]
        
        # Filter and process attachments - decode base64url data to bytes
        attachments = email.get("attachments", [])
        processed_attachments = []
        filtered_count = 0
        for att in attachments:
            # Check if attachment should be saved based on configuration
            if not self._should_save_attachment(att):
                filtered_count += 1
                continue
            
            processed_att = att.copy()
            # Decode base64url encoded data to bytes
            if "data" in processed_att and processed_att["data"]:
                try:
                    # Base64url decode
                    data_str = processed_att["data"]
                    # Add padding if needed
                    padding = len(data_str) % 4
                    if padding:
                        data_str += "=" * (4 - padding)
                    processed_att["data"] = base64.urlsafe_b64decode(data_str)
                    
                    # Create thumbnail for all attachment types
                    mime_type = processed_att.get("mimeType", "")
                    filename = processed_att.get("filename", "")
                    file_type = self._get_file_type(mime_type, filename)
                    
                    if file_type == "image" and processed_att["data"]:
                        # Create image thumbnail from actual image data
                        thumbnail = self._create_thumbnail(processed_att["data"])
                        if thumbnail:
                            processed_att["thumbnail"] = thumbnail
                    else:
                        # Create icon-based thumbnail for non-image files
                        thumbnail = self._create_icon_thumbnail(file_type)
                        processed_att["thumbnail"] = thumbnail
                except Exception as e:
                    print(f"Warning: Could not decode attachment data: {e}")
                    processed_att["data"] = None
            else:
                # Even if no data, create thumbnail based on file type
                mime_type = processed_att.get("mimeType", "")
                filename = processed_att.get("filename", "")
                file_type = self._get_file_type(mime_type, filename)
                if file_type != "image":
                    thumbnail = self._create_icon_thumbnail(file_type)
                    processed_att["thumbnail"] = thumbnail
            processed_attachments.append(processed_att)
        
        if filtered_count > 0:
            print(f"Filtered out {filtered_count} attachment(s) based on configuration")
        
        print(f"Saving email: {subject} from folder: {folder}")
        return self.storage.save_email(uid, folder, subject, snippet, from_address, to_addresses, cc_addresses, bcc_addresses, date, raw_message, plain_text, processed_attachments)

    def check_email_exists_callback(self, msg_id: str, label_name: str) -> bool:
        """Callback function to check if an email already exists in the database.
        
        This function checks the database by uid (Gmail message ID) and folder (label)
        to determine if an email has already been processed and saved.
        
        Args:
            msg_id: Gmail message ID (used as uid in database)
            label_name: Current label being processed (checked against folder field)
            
        Returns:
            True if email exists in database with this uid and label (should be skipped), False otherwise
        """
        # The uid in the database is the Gmail message ID
        # The folder field stores comma-separated labels
        # Check if an email exists with this uid where the folder contains the label_name
        session = self.storage.db.get_session()
        print(f"Checking if email exists with uid: {msg_id} and label: {label_name}", end='')
        try:
            from .database import Email
            from sqlalchemy import and_, or_
            
            # Check if email exists with this uid AND folder containing the label
            # Handle comma-separated labels: exact match, at start, in middle, or at end
            count = session.query(Email).filter(
                and_(
                    Email.uid == msg_id,
                    or_(
                        Email.folder == label_name,  # Exact match
                        Email.folder.like(f"{label_name},%"),  # Label at start
                        Email.folder.like(f"%,{label_name},%"),  # Label in middle
                        Email.folder.like(f"%,{label_name}")  # Label at end
                    )
                )
            ).count()
            print(f"...Found: {count} email(s)")
            return count > 0
        finally:
            session.close()
    
    def load_emails(self, label: str, new_only: bool = False) -> int:
        """Load emails from a specific label into the database.
        
        Args:
            label: The Gmail label to process (e.g., "INBOX")
            new_only: If True, only load new emails (uses database check callback)
            
        Returns:
            Number of emails processed
        """
        if not hasattr(self, 'client') or self.client is None:
            self.init_client()
        
        count = 0
        # Use database check callback when new_only is True
        check_callback = self.check_email_exists_callback if new_only else None
        email_generator = self.client.fetch_and_process_messages(
            [label], 
            self.process_email, 
            new_only=new_only,
            check_history_callback=check_callback
        )
        for email in email_generator:
            count += 1
        
        return count

        
