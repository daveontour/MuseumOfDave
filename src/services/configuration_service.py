"""Application configuration service — database-first with .env fallback."""

import os
from typing import Optional

from ..database import Database
from ..database.models import AppConfiguration

# All known non-DB configuration keys.
# (key, env_default, is_mandatory, description)
KNOWN_KEYS = [
    ("GEMINI_API_KEY",                          None,              True,  "Google Gemini API key"),
    ("GEMINI_MODEL_NAME",                       "gemini-2.5-flash", False, "Gemini model name"),
    ("ANTHROPIC_API_KEY",                       None,              False, "Anthropic Claude API key"),
    ("CLAUDE_MODEL_NAME",                       "claude-sonnet-4-6", False, "Claude model name"),
    ("TAVILY_API_KEY",                          None,              False, "Tavily web search API key"),
    ("DEFAULT_SUBJECT_NAME",                    None,              True,  "Default subject name"),
    ("DEFAULT_SUBJECT_FAMILY_NAME",             None,              False, "Subject family/last name"),
    ("DEFAULT_SUBJECT_GENDER",                  "Male",            False, "Subject gender (Male/Female)"),
    ("PAGE_TITLE",                              "Digital Museum",  False, "Browser page title"),
    ("ATTACHMENT_ALLOWED_TYPES",                "",                False, "Comma-separated allowed attachment MIME/ext types"),
    ("ATTACHMENT_MIN_SIZE",                     "0",               False, "Minimum attachment size in bytes"),
    ("DEFAULT_PROCESS_ALL_FOLDERS",             "false",           False, "Process all email folders by default"),
    ("DEFAULT_NEW_ONLY_OPTION",                 "true",            False, "Import new emails only by default"),
    ("DEFAULT_WHATSAPP_IMPORT_DIRECTORY",       "",                False, "Default WhatsApp import directory"),
    ("DEFAULT_FACEBOOK_IMPORT_DIRECTORY",       "",                False, "Default Facebook Messenger import directory"),
    ("DEFAULT_FACEBOOK_EXPORT_ROOT",            "",                False, "Default Facebook export root directory"),
    ("DEFAULT_FACEBOOK_USER_NAME",              "",                False, "Default Facebook username"),
    ("DEFAULT_INSTAGRAM_IMPORT_DIRECTORY",      "",                False, "Default Instagram import directory"),
    ("DEFAULT_INSTAGRAM_EXPORT_ROOT",           "",                False, "Default Instagram export root directory"),
    ("DEFAULT_INSTAGRAM_USER_NAME",             "",                False, "Default Instagram username"),
    ("DEFAULT_IMESSAGE_DIRECTORY_PATH",         "",                False, "Default iMessage database directory"),
    ("DEFAULT_FACEBOOK_ALBUMS_IMPORT_DIRECTORY","",                False, "Default Facebook Albums import directory"),
    ("DEFAULT_FACEBOOK_ALBUMS_EXPORT_ROOT",     "",                False, "Default Facebook Albums export root"),
    ("DEFAULT_FILESYSTEM_IMPORT_DIRECTORY",     "",                False, "Default filesystem image import directory"),
    ("DEFAULT_FILESYSTEM_IMPORT_MAX_IMAGES",    "",                False, "Max images per filesystem import run"),
    ("DEFAULT_FILESYSTEM_IMPORT_CREATE_THUMBNAIL", "false",        False, "Create thumbnails on filesystem import"),
    ("DEFAULT_IMAGE_EXPORT_DIRECTORY",          "",                False, "Default image export directory"),
    ("DEFAULT_IMAP_HOST",                       "",                False, "Default IMAP server hostname"),
    ("DEFAULT_IMAP_PORT",                       "993",             False, "Default IMAP port"),
    ("DEFAULT_IMAP_USERNAME",                   "",                False, "Default IMAP username"),
    ("FILESYSTEM_IMPORT_EXCLUDE_PATTERNS",      "",                False, "Comma-separated directory exclusion patterns"),
]

# Fast lookup for metadata
_KNOWN_KEYS_META: dict[str, tuple] = {k: (d, m, desc) for k, d, m, desc in KNOWN_KEYS}


class ConfigurationService:
    """Provides configuration values from the database, falling back to the .env file."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Return value for key — DB first, then os.getenv(), then default."""
        try:
            session = self.db.get_session()
            try:
                row = session.query(AppConfiguration).filter_by(key=key).first()
                if row is not None:
                    return row.value
            finally:
                session.close()
        except Exception as e:
            print(f"[ConfigurationService.get] DB error for key '{key}': {e}")
        return os.getenv(key, default)

    def set(self, key: str, value: Optional[str], *,
            is_mandatory: Optional[bool] = None,
            description: Optional[str] = None) -> AppConfiguration:
        """Upsert a configuration key-value pair."""
        session = self.db.get_session()
        try:
            row = session.query(AppConfiguration).filter_by(key=key).first()
            if row:
                row.value = value
                if is_mandatory is not None:
                    row.is_mandatory = is_mandatory
                if description is not None:
                    row.description = description
            else:
                meta = _KNOWN_KEYS_META.get(key, (None, False, None))
                row = AppConfiguration(
                    key=key,
                    value=value,
                    is_mandatory=is_mandatory if is_mandatory is not None else meta[1],
                    description=description if description is not None else meta[2],
                )
                session.add(row)
            session.commit()
            session.refresh(row)
            return row
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete(self, key: str) -> bool:
        """Delete a key from the database. Returns True if it existed."""
        session = self.db.get_session()
        try:
            row = session.query(AppConfiguration).filter_by(key=key).first()
            if row:
                session.delete(row)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_all(self) -> list:
        """Return all configuration rows ordered by key."""
        session = self.db.get_session()
        try:
            return session.query(AppConfiguration).order_by(AppConfiguration.key).all()
        finally:
            session.close()

    def seed_from_env(self) -> int:
        """Seed the database from .env for all KNOWN_KEYS not already present.

        For keys that already exist in the DB, backfills any missing is_mandatory
        or description without changing the stored value.

        Returns the number of new rows inserted.
        """
        session = self.db.get_session()
        try:
            existing = {row.key: row for row in session.query(AppConfiguration).all()}
            inserted = 0

            for key, env_default, is_mandatory, description in KNOWN_KEYS:
                if key in existing:
                    # Backfill metadata if it was never set
                    row = existing[key]
                    changed = False
                    if row.description is None and description:
                        row.description = description
                        changed = True
                    if changed:
                        session.add(row)
                    continue

                env_value = os.getenv(key)
                # Use env value if available; otherwise use the documented default
                value = env_value if env_value is not None else env_default
                row = AppConfiguration(
                    key=key,
                    value=value,
                    is_mandatory=is_mandatory,
                    description=description,
                )
                session.add(row)
                inserted += 1

            session.commit()
            print(f"[ConfigurationService] Seeded {inserted} key(s) from .env into app_configuration table")
            return inserted
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
