"""Generic IMAP email client using Python stdlib imaplib."""

import base64
import imaplib
import re
import email as email_lib
from email.header import decode_header, make_header
from typing import Callable, Iterator, List, Optional


class IMAPClient:
    """IMAP email client compatible with the GmailClient fetch_and_process_messages interface."""

    def __init__(self, host: str, port: int, username: str, password: str, use_ssl: bool = True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.connection: Optional[imaplib.IMAP4] = None

    def connect(self):
        """Connect and authenticate. Raises on failure."""
        if self.use_ssl:
            self.connection = imaplib.IMAP4_SSL(self.host, self.port)
        else:
            self.connection = imaplib.IMAP4(self.host, self.port)
        self.connection.login(self.username, self.password)
        print(f"Connected to IMAP server {self.host}:{self.port}")

    def disconnect(self):
        """Disconnect from the IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
            except Exception:
                pass
            self.connection = None

    def get_folders(self) -> List[str]:
        """Return a list of folder names available on the server."""
        typ, data = self.connection.list()
        folders = []
        for item in data:
            if item is None:
                continue
            line = item.decode('utf-8', errors='replace') if isinstance(item, bytes) else item
            # Format: (\HasNoChildren) "/" "Folder Name"  or  (\HasNoChildren) "/" FolderName
            # Extract everything after the last delimiter token
            match = re.search(r'"/" (?:"([^"]+)"|(\S+))$', line)
            if match:
                name = match.group(1) or match.group(2)
                if name:
                    folders.append(name)
        return folders

    def fetch_and_process_messages(
        self,
        target_labels: List[str],
        callback: Optional[Callable] = None,
        max_results: Optional[int] = None,
        new_only: bool = False,
        clean_body_callback: Optional[Callable] = None,
        check_history_callback: Optional[Callable] = None,
    ) -> Iterator[dict]:
        """Fetch messages from IMAP folders and yield processed message dicts.

        Mirrors the GmailClient.fetch_and_process_messages generator interface
        so EmailDatabaseLoader.load_emails() works without modification.
        """
        for folder_name in target_labels:
            print(f"Processing IMAP folder: {folder_name}")
            try:
                typ, data = self.connection.select(f'"{folder_name}"', readonly=True)
                if typ != 'OK':
                    print(f"Warning: Could not select folder {folder_name}: {data}")
                    continue
            except Exception as e:
                print(f"Warning: Error selecting folder {folder_name}: {e}")
                continue

            try:
                typ, search_data = self.connection.search(None, 'ALL')
                if typ != 'OK' or not search_data[0]:
                    print(f"No messages found in folder: {folder_name}")
                    continue
            except Exception as e:
                print(f"Warning: Error searching folder {folder_name}: {e}")
                continue

            seq_nums = search_data[0].split()
            print(f"Found {len(seq_nums)} messages in folder: {folder_name}")

            count = 0
            for seq_bytes in seq_nums:
                if max_results is not None and count >= max_results:
                    break

                seq_str = seq_bytes.decode()
                imap_uid = f"imap_{folder_name}_{seq_str}"

                if new_only and check_history_callback:
                    if check_history_callback(imap_uid, folder_name):
                        continue

                try:
                    data = self._retrieve_message_from_server(seq_str, folder_name)
                    if data:
                        if callable(callback):
                            try:
                                callback(data)
                            except Exception as e:
                                print(f"Error in callback for message {imap_uid}: {e}")
                                import traceback
                                traceback.print_exc()
                        count += 1
                        yield data
                    else:
                        print(f"Warning: No data retrieved for message {imap_uid}")
                except Exception as e:
                    print(f"Error retrieving message {imap_uid}: {e}")
                    import traceback
                    traceback.print_exc()

            print(f"Completed folder {folder_name}: {count} messages processed")

    def _retrieve_message_from_server(self, seq_num: str, folder_name: str) -> Optional[dict]:
        """Fetch a single message and return it as the standard message dict."""
        try:
            typ, msg_data = self.connection.fetch(seq_num, '(RFC822)')
            if typ != 'OK' or not msg_data or msg_data[0] is None:
                return None

            raw_bytes = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_bytes)

            imap_uid = f"imap_{folder_name}_{seq_num}"

            subject = self._decode_header_value(msg.get('Subject', ''))
            from_addr = self._decode_header_value(msg.get('From', ''))
            to_addr = self._decode_header_value(msg.get('To', ''))
            cc_addr = self._decode_header_value(msg.get('Cc', ''))
            bcc_addr = self._decode_header_value(msg.get('Bcc', ''))
            date_str = msg.get('Date', '')
            message_id = msg.get('Message-ID', imap_uid)

            body_text, body_html, attachments = self._parse_parts(msg)

            snippet_source = body_text or body_html or ''
            snippet = snippet_source[:200].strip()

            return {
                "id": imap_uid,
                "threadId": message_id,
                "snippet": snippet,
                "metadata": {
                    "uid": imap_uid,
                    "labels": [folder_name],
                    "subject": subject,
                    "from": from_addr,
                    "to": to_addr,
                    "cc": cc_addr,
                    "bcc": bcc_addr,
                    "date": date_str,
                },
                "body": {
                    "text": body_text,
                    "html": body_html,
                },
                "attachments": attachments,
            }
        except Exception as e:
            print(f"Error parsing message {seq_num} in {folder_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _decode_header_value(self, value: Optional[str]) -> Optional[str]:
        """Decode RFC 2047 encoded header values."""
        if not value:
            return None
        try:
            return str(make_header(decode_header(value)))
        except Exception:
            return str(value)

    def _parse_parts(self, msg) -> tuple:
        """Walk the message and extract text body, HTML body, and attachments.

        Returns:
            (body_text, body_html, attachments) where attachments is a list of dicts
            with keys: filename, mimeType, size, data (base64url-encoded string)
        """
        body_text = ""
        body_html = ""
        attachments = []

        for part in msg.walk():
            content_type = part.get_content_type()
            content_maintype = part.get_content_maintype()

            if content_maintype == 'multipart':
                continue

            content_disposition = str(part.get('Content-Disposition', ''))
            filename = part.get_filename()
            if filename:
                filename = self._decode_header_value(filename)

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            is_attachment = filename or 'attachment' in content_disposition.lower()

            if content_type == 'text/plain' and not is_attachment:
                charset = part.get_content_charset() or 'utf-8'
                body_text += payload.decode(charset, errors='replace')
            elif content_type == 'text/html' and not is_attachment:
                charset = part.get_content_charset() or 'utf-8'
                body_html += payload.decode(charset, errors='replace')
            elif is_attachment:
                # Encode as base64url — process_email() will urlsafe_b64decode() it
                encoded_data = base64.urlsafe_b64encode(payload).decode('ascii')
                attachments.append({
                    "filename": filename or "attachment",
                    "mimeType": content_type,
                    "size": len(payload),
                    "data": encoded_data,
                })

        return body_text, body_html, attachments
