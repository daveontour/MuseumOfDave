"""Email client package."""

from .client import GmailClient
from .imap_client import IMAPClient

__all__ = ["GmailClient", "IMAPClient"]
