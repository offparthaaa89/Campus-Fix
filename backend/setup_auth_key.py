"""Generate a local token signing key without printing it."""

from pathlib import Path
from secrets import token_urlsafe

from dotenv import dotenv_values


def main() -> None:
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        raise SystemExit("Save the project's existing database configuration in .env first.")

    values = dotenv_values(env_file, interpolate=False)
    key_name = "CAMPUSFIX_AUTH_SECRET"
    if key_name in values:
        if len((values[key_name] or "").encode()) < 32:
            raise SystemExit("Remove the blank or short CAMPUSFIX_AUTH_SECRET line and rerun this command.")
        print("Auth key already set.")
        return

    with env_file.open("a", encoding="utf-8") as config:
        config.write(f"\n{key_name}={token_urlsafe(48)}\n")
    print("Auth key ready.")


if __name__ == "__main__":
    main()
