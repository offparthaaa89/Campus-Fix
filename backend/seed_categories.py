from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from backend.models.category import Category


CATEGORY_NAMES = [
    "Wi-Fi/IT",
    "Hostel",
    "Electrical",
    "Cleanliness",
    "Classroom",
    "Other",
]


def main():
    load_dotenv()
    from backend.main import engine

    table = Category.__table__
    seed = insert(table).values([{"name": name} for name in CATEGORY_NAMES])
    seed = seed.on_conflict_do_nothing(index_elements=["name"])

    with engine.begin() as connection:
        table.create(connection, checkfirst=True)
        connection.execute(seed)
        names = connection.scalars(select(table.c.name).order_by(table.c.id)).all()

    print("Categories:", names)


if __name__ == "__main__":
    main()