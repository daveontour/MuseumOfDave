import base64
import json
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GmailClient:

    TRACEON = False


    def set_trace(self, traceon):
        self.TRACEON = traceon

    def __init__(self, credentials_file="credentials.json", token_file="token.json", history_file="history.json"):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.history_file = history_file
        self.scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        self.service = None
        self.history = self._load_history()
        self.label_map_id_to_name = {}  # Cache for ID -> Name
        self.label_map_name_to_id = {}  # Cache for Name -> ID

    def _load_history(self):
        """Loads processed message IDs from the history file."""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                print("Warning: Could not load history file. Starting with empty history.")
                return set()
        return set()

    def save_history(self):
        """Saves processed message IDs to the history file."""
        try:
            with open(self.history_file, "w") as f:
                json.dump(list(self.history), f)
        except IOError as e:
            print(f"Error saving history file: {e}")

    def authenticate(self):
        """Authenticates the user and creates the Gmail service."""
        print(f"Authenticating with credentials file: {self.credentials_file}")
        print(f"Authenticating with token file: {self.token_file}")
        print(f"Authenticating with history file: {self.history_file}")
        print(f"Authenticating with scopes: {self.scopes}")
        creds = None
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError:
                    # Token has been expired or revoked, need to re-authenticate
                    print("Token expired or revoked. Re-authenticating...")
                    # Remove the invalid token file
                    if os.path.exists(self.token_file):
                        os.remove(self.token_file)
                    creds = None
            
            if not creds or not creds.valid:
                # Need to get new credentials via OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, "w") as token:
                token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)

    def _get_header_value(self, headers, name):
        """Utility to get header value by name."""
        if not headers:
            return None
        for header in headers:
            if header["name"].lower() == name.lower():
                return header["value"]
        return None

    def _decode_base64url(self, data):
        """Decodes base64url string."""
        if not data:
            return ""
        # Add padding if needed
        padding = len(data) % 4
        if padding:
            data += "=" * (4 - padding)
        return base64.urlsafe_b64decode(data).decode("utf-8")

    def _get_attachment_data(self, user_id, message_id, attachment_id):
        """Fetches and encodes attachment data."""
        try:
            response = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId=user_id, messageId=message_id, id=attachment_id)
                .execute()
            )
            return response.get("data", "")
        except HttpError as error:
            print(f"An error occurred fetching attachment: {error}")
            return None

    def _parse_message_parts(self, user_id, message_id, parts):
        """Recursively parses message parts for body and attachments."""
        body_text = ""
        body_html = ""
        attachments = []

        if not parts:
            return body_text, body_html, attachments

        for part in parts:
            mime_type = part.get("mimeType", "")
            filename = part.get("filename", "")
            part_body = part.get("body", {})
            data = part_body.get("data", "")
            attachment_id = part_body.get("attachmentId", "")

            # Handle nested parts (multipart)
            if "parts" in part:
                sub_text, sub_html, sub_attachments = self._parse_message_parts(
                    user_id, message_id, part["parts"]
                )
                body_text += sub_text
                body_html += sub_html
                attachments.extend(sub_attachments)

            # Handle text/plain
            elif mime_type == "text/plain" and data:
                body_text += self._decode_base64url(data)

            # Handle text/html
            elif mime_type == "text/html" and data:
                body_html += self._decode_base64url(data)

            # Handle attachments (if filename is present, it's usually an attachment)
            elif filename:
                attachment_data = ""
                file_size = part_body.get("size", 0)

                if attachment_id:
                    # Fetch full attachment data
                    attachment_data = self._get_attachment_data(
                        user_id, message_id, attachment_id
                    )
                elif data:
                    # Attachment data might be inline for small files
                    attachment_data = data

                if attachment_data:
                    # Calculate size if not provided by API
                    if not file_size:
                        try:
                            # attachment_data is base64url encoded
                            # Padding might be needed for strict decoding, but simple length estimation:
                            # bytes = (len(str) * 3) / 4 - padding
                            padding = len(attachment_data) % 4
                            if padding:
                                padded_data = attachment_data + "=" * (4 - padding)
                            else:
                                padded_data = attachment_data
                            file_size = len(base64.urlsafe_b64decode(padded_data))
                        except Exception:
                            file_size = 0

                    attachments.append({
                        "filename": filename,
                        "mimeType": mime_type,
                        "size": file_size,
                        "data": attachment_data,  # This is base64url encoded
                    })

        return body_text, body_html, attachments

    def _retrieve_message_from_server(self, message_id, clean_body_callback=None):
        """Fetches and processes a single message.
        clean_body_callback: Optional function that takes (text, html) and returns (cleaned_text, cleaned_html)
        """
        try:
            # Fetch full message details
            message_full = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            payload = message_full.get("payload", {})
            headers = payload.get("headers", [])
            label_ids = message_full.get("labelIds", [])
            
            # Resolve label IDs to names
            if not self.label_map_id_to_name:
                self.get_labels() # Ensure cache is populated
                
            label_names = [self.label_map_id_to_name.get(lid, lid) for lid in label_ids]

            # Extract metadata
            metadata = {
                "uid": message_id,
                "labels": label_names,
                "subject": self._get_header_value(headers, "Subject"),
                "from": self._get_header_value(headers, "From"),
                "to": self._get_header_value(headers, "To"),
                "cc": self._get_header_value(headers, "Cc"),
                "bcc": self._get_header_value(headers, "Bcc"),
                "date": self._get_header_value(headers, "Date"),
            }

            # Parse body and attachments
            body_text = ""
            body_html = ""
            attachments = []

            # Payload might have parts or just a body
            if "parts" in payload:
                body_text, body_html, attachments = self._parse_message_parts(
                    "me", message_id, payload["parts"]
                )
            else:
                # Single part message (e.g. just text/plain or text/html)
                mime_type = payload.get("mimeType", "")
                data = payload.get("body", {}).get("data", "")
                if mime_type == "text/plain":
                    body_text = self._decode_base64url(data)
                elif mime_type == "text/html":
                    body_html = self._decode_base64url(data)

            # Apply cleansing callback if provided
            if clean_body_callback:
                try:
                    body_text, body_html = clean_body_callback(body_text, body_html)
                except Exception as e:
                    print(f"Error in cleansing callback for message {message_id}: {e}")

            # Construct JSON structure
            message_data = {
                "id": message_id,
                "threadId": message_full.get("threadId"),
                "snippet": message_full.get("snippet"),
                "metadata": metadata,
                "body": {
                    "text": body_text,
                    "html": body_html
                },
                "attachments": attachments
            }
            return message_data

        except HttpError as error:
            print(f"An error occurred processing message {message_id}: {error}")
            return None

    def _get_messages_metadata(self, target_labels, max_results=None, new_only=False, check_history_callback=None):
        """Helper to yield message metadata (IDs) from specified labels.
        If max_results is None, fetches all messages (uses pagination).
        If new_only is True, filters out messages already in history.
        check_history_callback: Optional function(msg_id, label_name) -> bool. 
                                Returns True if message exists (should be skipped).
        Yields message objects as they are found.
        """
        if not self.service:
            raise Exception("Service not authenticated. Call authenticate() first.")

        # Get all labels to create a name->ID map
        if self.TRACEON: 
            print("Fetching labels...")
        # get_labels updates the internal cache
        self.get_labels()
        
        # Use cached map
        label_map = self.label_map_name_to_id
        print(f"[DEBUG] Total labels in map: {len(label_map)}")
        print(f"[DEBUG] Available labels in map (first 10): {list(label_map.keys())[:10]}")
        print(f"[DEBUG] Target labels to process: {target_labels}")

        seen_message_ids = set()
        yield_count = 0

        # Iterate over target labels
        for label_name in target_labels:
            print(f"[DEBUG] Looking up label: '{label_name}'")
            label_id = label_map.get(label_name)

            if not label_id:
                print(f"[WARNING] Label '{label_name}' not found in label map.")
                print(f"[DEBUG] Checking for similar labels...")
                # Check for case-insensitive match
                label_lower = label_name.lower()
                matching_labels = [k for k in label_map.keys() if k.lower() == label_lower]
                if matching_labels:
                    print(f"[DEBUG] Found case-insensitive match: {matching_labels[0]}")
                else:
                    print(f"[DEBUG] No match found. Sample of available labels: {list(label_map.keys())[:20]}")
                continue

            print(f"[DEBUG] Found label '{label_name}' with ID: {label_id}")
            if self.TRACEON:
                print(f"Listing messages for label: {label_name}...")
            
            try:
                page_token = None
                while True:
                    list_kwargs = {
                        "userId": "me",
                        "labelIds": [label_id],
                        "pageToken": page_token
                    }
                    if max_results is not None:
                        remaining = max_results - yield_count
                        if remaining <= 0:
                            return
                        list_kwargs["maxResults"] = min(remaining, 500) if remaining > 500 else remaining
                        
                    results = (
                        self.service.users()
                        .messages()
                        .list(**list_kwargs)
                        .execute()
                    )
                    
                    messages = results.get("messages", [])
                    print(f"Found {len(messages)} messages for label {label_name} (page)")
                    if messages:
                        for msg in messages:
                            msg_id = msg["id"]
                            if msg_id not in seen_message_ids:
                                is_existing = False
                                if new_only:
                                    if check_history_callback:
                                        # Use injected callback
                                        try:
                                            is_existing = check_history_callback(msg_id, label_name)
                                        except Exception as e:
                                            print(f"Error in history callback for {msg_id}: {e}")
                                            # Default to False (process it) or True? False is safer to ensure we get data.
                                            is_existing = False 
                                    else:
                                        # Use internal history
                                        is_existing = msg_id in self.history
                                
                                if is_existing:
                                    continue
                                    
                                yield msg
                                seen_message_ids.add(msg_id)
                                yield_count += 1
                                
                                if max_results is not None and yield_count >= max_results:
                                    return

                    page_token = results.get("nextPageToken")
                    
                    # Stop if no more pages
                    if not page_token:
                        print(f"No more pages for label {label_name}. Total messages processed: {yield_count}")
                        break
                    else:
                        print(f"Continuing to next page for label {label_name}...")
                             
            except HttpError as e:
                print(f"Error listing messages for label {label_name}: {e}")
                import traceback
                traceback.print_exc()

    def get_labels(self):
        """Fetches and returns a list of all labels. Caches the result."""
        if not self.service:
             raise Exception("Service not authenticated. Call authenticate() first.")
        
        try:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])
            
            # Update cache
            self.label_map_id_to_name = {label["id"]: label["name"] for label in labels}
            self.label_map_name_to_id = {label["name"]: label["id"] for label in labels}
            
            return labels
        except HttpError as error:
            print(f"An error occurred fetching labels: {error}")
            return []
            
    def fetch_messages(self, target_labels, max_results=None, new_only=False, clean_body_callback=None, check_history_callback=None):
        """Fetches messages from specified labels. Defaults to all if max_results is None."""
        if self.TRACEON:
            print("Starting message fetch...")
        processed_messages = []
        generator = self._get_messages_metadata(target_labels, max_results, new_only, check_history_callback)

        for msg in generator:
            if self.TRACEON:
                print(f"Processing message ID: {msg['id']}")
            data = self._retrieve_message_from_server(msg['id'], clean_body_callback)
            if data:
                processed_messages.append(data)
                self.history.add(msg['id'])
                self.save_history()
        
        if not processed_messages:
             if self.TRACEON:
                 print("No messages found or processed.")
             
        # self.save_history() # Already saved incrementally
        return processed_messages

    def fetch_and_process_messages(self, target_labels, callback, max_results=None, new_only=False, clean_body_callback=None, check_history_callback=None):
        """Fetches messages and applies a callback function to each processed message.
        Yields processed message objects as they are processed.
        """
        
        print(f"Starting message processing for labels: {target_labels}")
        try:
            generator = self._get_messages_metadata(target_labels, max_results, new_only, check_history_callback)
            count = 0
            for msg in generator:
                count += 1
                #print(f"Found message ID: {msg.get('id', 'unknown')} ")
                # if self.TRACEON:
                #     print(f"Processing message ID: {msg['id']}")
                data = self._retrieve_message_from_server(msg['id'], clean_body_callback)
                if data:
                    try:
                        #check if callback is a function
                        if callable(callback):
                            callback(data)
                        self.history.add(msg['id'])
                        self.save_history()
                        yield data
                    except Exception as e:
                        print(f"Error in callback for message {msg['id']}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"Warning: No data retrieved for message {msg.get('id', 'unknown')}")
            
            print(f"Completed processing. Total messages found: {count}")
            if count == 0:
                print(f"No messages found or processed for labels: {target_labels}")
        except Exception as e:
            print(f"Error in fetch_and_process_messages: {e}")
            import traceback
            traceback.print_exc()


