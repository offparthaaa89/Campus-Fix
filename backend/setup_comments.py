"""Add only the comments table; leave existing project data unchanged.

From the project root: python -m backend.setup_comments
"""

from dotenv import load_dotenv
from sqlalchemy import inspect

from backend.models.comment import Comment


def main() -> None:
    load_dotenv()
    from backend.main import engine

    with engine.begin() as connection:
        tables = set(inspect(connection).get_table_names())
        required = {"users", "complaints", "categories"}
        missing = required - tables
        if missing:
            raise RuntimeError("Missing previous tables: " + ", ".join(sorted(missing)))
        Comment.__table__.create(connection, checkfirst=True)
    print("Comments table ready.")


if __name__ == "__main__":
    main()
