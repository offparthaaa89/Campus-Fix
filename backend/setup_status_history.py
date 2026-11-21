"""Add status_history safely and backfill the original Open event of old tickets.

Run from the project root: python -m backend.setup_status_history
"""

from dotenv import load_dotenv
from sqlalchemy import String, exists, insert, inspect, literal, select

from backend.models.base import Base
from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.status_history import StatusHistory
from backend.models.user import User


def main():
    load_dotenv()
    from backend.main import engine

    with engine.begin() as connection:
        existing_tables = set(inspect(connection).get_table_names())
        required = {"users", "complaints", "categories"}
        if not required.issubset(existing_tables):
            raise RuntimeError(f"Missing tables: {', '.join(sorted(required - existing_tables))}")

        Base.metadata.create_all(
            bind=connection, tables=[StatusHistory.__table__], checkfirst=True
        )
        # Older tickets were created with status Open. Restore only that known event.
        # Never invent intermediate transitions from before tracking was enabled.
        already_recorded = exists(
            select(StatusHistory.id).where(StatusHistory.complaint_id == Complaint.id)
        )
        historical_open = select(
            Complaint.id,
            Complaint.reported_by,
            literal(None, type_=String(20)),
            Complaint.status,
            Complaint.created_at,
        ).where(Complaint.status == "Open", ~already_recorded)
        statement = insert(StatusHistory).from_select(
            ["complaint_id", "changed_by", "old_status", "new_status", "changed_at"],
            historical_open,
        )
        result = connection.execute(statement)
        count = result.rowcount

    print("Status history ready.")
    print(f"Original Open events added for existing complaints: {count}")


if __name__ == "__main__":
    main()
