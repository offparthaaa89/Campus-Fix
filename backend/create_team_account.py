"""Create a local development Staff or Admin login securely.

Run from project root with: python -m backend.create_team_account staff
Or: python -m backend.create_team_account admin

This is intentionally a local CLI, not a public API endpoint. Existing users
are NOT promoted. Do not commit credentials or use real personal passwords.
"""

import argparse
from getpass import getpass

from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from pwdlib import PasswordHash
from sqlalchemy.dialects.postgresql import insert

from backend.models.user import User


def main():
    parser = argparse.ArgumentParser(description="Create a Staff or Admin demo account")
    parser.add_argument("role", choices=["staff", "admin"])
    args = parser.parse_args()
    role = args.role.capitalize()

    name = input(f"{role} name: ").strip()
    raw_email = input(f"{role} email: ").strip()
    if not 1 <= len(name) <= 120:
        raise SystemExit("Name must be between 1 and 120 characters.")
    try:
        email = validate_email(raw_email, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise SystemExit(f"Invalid email: {exc}") from None
    if len(email) > 254:
        raise SystemExit("Email is too long.")

    password = getpass("Password (8 to 128 characters): ")
    repeated = getpass("Confirm password: ")
    if not 8 <= len(password) <= 128:
        raise SystemExit("Password length must be 8–128 characters.")
    if password != repeated:
        raise SystemExit("Passwords did not match.")

    load_dotenv()
    from backend.main import engine

    hashed = PasswordHash.recommended().hash(password)
    stmt = (
        insert(User)
        .values(name=name, email=email, password_hash=hashed, role=role)
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User.id)
    )
    with engine.begin() as connection:
        new_id = connection.scalar(stmt)

    if new_id is None:
        raise SystemExit("Account already exists. Nothing changed; choose a different email.")
    print(f"{role} demo account created (ID {new_id}).")


if __name__ == "__main__":
    main()
