"""One-off migration script to populate email_classifications table from email_classifications.json."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.database.connection import Database
from src.database.models import EmailClassifications


CLASSIFICATIONS_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', 'import-processor', 'email_classifications.json'
)


def migrate(db: Database) -> None:
    with open(CLASSIFICATIONS_JSON, 'r') as f:
        data = json.load(f)

    session = db.get_session()
    try:
        inserted = 0
        skipped = 0

        for classification, names in data.items():
            for name in names:
                if not name:
                    continue
                exists = session.query(EmailClassifications).filter_by(
                    name=name, classification=classification
                ).first()
                if not exists:
                    session.add(EmailClassifications(name=name, classification=classification))
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
