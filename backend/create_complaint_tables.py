"""One-time local schema setup. This does not add test accounts or complaints."""

from dotenv import load_dotenv
from sqlalchemy import Engine, inspect

from backend.models.base import Base
from backend.models.category import Category
from backend.models.complaint import Complaint
from backend.models.user import User


def create_tables(engine: Engine) -> list[str]:
    """Create the two new tables if missing and verify they exist."""
    with engine.begin() as connection:
        if not inspect(connection).has_table(Category.__tablename__):
            raise RuntimeError("Categories table is missing. Run python -m backend.seed_categories first.")

        Base.metadata.create_all(
            bind=connection,
            tables=[User.__table__, Complaint.__table__],
            checkfirst=True,
        )
        inspector = inspect(connection)
        tables = [Category.__tablename__, User.__tablename__, Complaint.__tablename__]
        missing = [name for name in tables if not inspector.has_table(name)]
        if missing:
            raise RuntimeError(f"Expected tables not found: {', '.join(missing)}")

    return tables


def main() -> None:
    load_dotenv()
    # The existing FastAPI module reads the database password when it is imported.
    from backend.main import engine

    print("Tables ready:", ", ".join(create_tables(engine)))


if __name__ == "__main__":
    main()
