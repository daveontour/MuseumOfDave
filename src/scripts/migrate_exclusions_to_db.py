"""One-off migration script to populate email_exclusions table from exclusions.json."""

import json
import os
import sys

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.database.connection import Database
from src.database.models import EmailExclusions


EXCLUSIONS_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'import-processor', 'exclusions.json'
)


def migrate(db: Database) -> None:
    with open(EXCLUSIONS_JSON, 'r') as f:
        data = json.load(f)

    session = db.get_session()
    try:
        inserted = 0
        skipped = 0

        for pattern in data.get('email', []):
            exists = session.query(EmailExclusions).filter_by(
                email=pattern, name='', name_email=False
            ).first()
            if not exists:
                session.add(EmailExclusions(email=pattern, name='', name_email=False))
                inserted += 1
            else:
                skipped += 1

        for pattern in data.get('name', []):
            exists = session.query(EmailExclusions).filter_by(
                email='', name=pattern, name_email=False
            ).first()
            if not exists:
                session.add(EmailExclusions(email='', name=pattern, name_email=False))
                inserted += 1
            else:
                skipped += 1

        for pair in data.get('name_email', []):
            name = pair.get('name', '')
            email = pair.get('email', '')
            exists = session.query(EmailExclusions).filter_by(
                email=email, name=name, name_email=True
            ).first()
            if not exists:
                session.add(EmailExclusions(email=email, name=name, name_email=True))
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
