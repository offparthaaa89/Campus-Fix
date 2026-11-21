"""Create the ReopenRequest table without modifying existing CampusFix data.

Run from the campus_fix project root:
    python -m backend.setup_reopen_requests
"""

from dotenv import load_dotenv
from sqlalchemy import inspect

from backend.models.complaint import Complaint  # Register referenced tables with SQLAlchemy
from backend.models.user import User
from backend.models.reopen_request import ReopenRequest


def main() -> None:
    load_dotenv()
    from backend.main import engine

    with engine.begin() as connection:
        present = set(inspect(connection).get_table_names())
        required = {"users", "complaints", "status_history", "notifications"}
        missing = required - present
        if missing:
            raise RuntimeError(
                "Run earlier CampusFix setup first. Missing: " + ", ".join(sorted(missing))
            )
        ReopenRequest.__table__.create(connection, checkfirst=True)

    print("Reopen requests table ready.")


if __name__ == "__main__":
    main()
