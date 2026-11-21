"""Create the assignments audit table; safe to run repeatedly.

From campus_fix root: python -m backend.setup_staff_workflow
"""

from dotenv import load_dotenv
from sqlalchemy import inspect

from backend.models.assignment import Assignment
from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.status_history import StatusHistory
from backend.models.user import User


def main():
    load_dotenv()
    from backend.main import engine

    with engine.begin() as connection:
        present = set(inspect(connection).get_table_names())
        necessary = {"users", "categories", "complaints", "status_history"}
        missing = necessary - present
        if missing:
            raise RuntimeError("Run previous setup steps. Missing tables: " + ", ".join(sorted(missing)))
        Assignment.__table__.create(connection, checkfirst=True)
    print("Staff workflow table ready: assignments")


if __name__ == "__main__":
    main()
