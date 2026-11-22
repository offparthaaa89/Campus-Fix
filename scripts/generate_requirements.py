"""Generate CampusFix local-development dependency pins from this virtualenv.

Safe to run: reads installed distribution metadata, writes only requirements files.
It never runs pip or modifies installed packages.
"""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "backend.txt": [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("SQLAlchemy", "SQLAlchemy"),
        ("psycopg", "psycopg"),
        ("PyJWT", "PyJWT"),
        ("pwdlib", "pwdlib[argon2]"),
        ("email-validator", "email-validator"),
        ("python-dotenv", "python-dotenv"),
        ("pydantic", "pydantic"),
    ],
    "client.txt": [
        ("Kivy", "Kivy"),
        ("requests", "requests"),
    ],
    "dev.txt": [
        ("pytest", "pytest"),
        ("httpx", "httpx"),
    ],
}

HEADERS = {
    "backend.txt": "# FastAPI + PostgreSQL backend. Not part of the Kivy mobile/desktop client.",
    "client.txt": "# Kivy UI client. API server is deployed/running separately.",
    "dev.txt": "# Automated tests; install for local development, not end-user apps.",
}


def build_files() -> dict[Path, str]:
    missing = []
    out = {}
    for filename, deps in GROUPS.items():
        lines = [HEADERS[filename], "# Exact versions detected in the active Python environment."]
        for distribution, requirement_name in deps:
            try:
                current = version(distribution)
            except PackageNotFoundError:
                missing.append(distribution)
                continue
            lines.append(f"{requirement_name}=={current}")
        out[ROOT / "requirements" / filename] = "\n".join(lines) + "\n"
    if missing:
        raise SystemExit("Missing installed packages: " + ", ".join(sorted(set(missing))) +
                         "\nNothing written. Verify that you activated the CampusFix .venv.")
    out[ROOT / "requirements.txt"] = (
        "# Local Mac development environment: backend + client + tests.\n"
        "# For Android/Windows client packaging, use requirements/client.txt only\n"
        "# and validate platform compatibility separately.\n"
        "-r requirements/backend.txt\n"
        "-r requirements/client.txt\n"
        "-r requirements/dev.txt\n"
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite existing requirements files")
    args = parser.parse_args()
    planned = build_files()
    existing = [p for p in planned if p.exists()]
    if existing and not args.force:
        raise SystemExit("Files already exist; no changes made:\n" +
                         "\n".join(f"- {p.relative_to(ROOT)}" for p in existing) +
                         "\nInspect first. Use --force only if replacement is intentional.")
    for dest, contents in planned.items():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(contents, encoding="utf-8")
        print("Created", dest.relative_to(ROOT))
    print("\nReady. No dependencies were installed or modified.")
    print("Next: python -m pip check && python -m pytest tests/ -q")


if __name__ == "__main__":
    main()
