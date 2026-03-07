"""One-off migration script to populate email_matches table from email_matches.json."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.database.connection import Database
from src.database.models import EmailMatches


MATCHES_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'import-processor', 'email_matches.json'
)


def migrate(db: Database) -> None:
    with open(MATCHES_JSON, 'r') as f:
        data = json.load(f)

    session = db.get_session()
    try:
        inserted = 0
        skipped = 0

        for entry in data:
            primary_name = entry.get('primary_name', '')
            if not primary_name:
                continue
            for email in entry.get('emails', []):
                if not email:
                    continue
                exists = session.query(EmailMatches).filter_by(
                    primary_name=primary_name, email=email
                ).first()
                if not exists:
                    session.add(EmailMatches(primary_name=primary_name, email=email))
                    inserted += 1
                else:
                    skipped += 1

        session.commit()
        print(f"Migration complete: {inserted} inserted, {skipped} already existed.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    db = Database()
    migrate(db)
