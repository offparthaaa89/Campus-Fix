"""Create the notifications table without changing existing project data.

Run from campus_fix root: python -m backend.setup_notifications
"""

from dotenv import load_dotenv
from sqlalchemy import inspect

from backend.models.notification import Notification


def main() -> None:
    load_dotenv()
    from backend.main import engine

    with engine.begin() as connection:
        existing_tables = set(inspect(connection).get_table_names())
        required = {"users", "complaints"}
        missing = required - existing_tables
        if missing:
            raise RuntimeError(
                "Run earlier database setup first. Missing: " + ", ".join(sorted(missing))
            )
        Notification.__table__.create(connection, checkfirst=True)
    print("Notifications table ready.")


if __name__ == "__main__":
    main()
