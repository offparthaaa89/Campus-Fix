"""Stage CampusFix's existing Kivy app for Android without touching backend or Mac app.

Run from project root: python scripts/prepare_android.py
Later, with an HTTPS backend: python scripts/prepare_android.py --set-api-url https://api.your-domain.example
Validation: python scripts/prepare_android.py --check [--require-api]
"""
from __future__ import annotations

import argparse
import ast
import configparser
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "android_staging"
MARKER = STAGE / ".campusfix_staging_marker"
PLACEHOLDER = "https://campusfix-api.invalid"
ALLOWED = {
    "main.py", "app_config.py", "buildozer.spec", "frontend/__init__.py",
    "frontend/main.py", ".campusfix_staging_marker", "README_ANDROID_STAGING.txt",
}

LAUNCHER = '''"""Android-only entry point. Mac entry remains python -m frontend.main."""
import os
from app_config import API_BASE_URL

# Must be set BEFORE importing frontend.main, which reads this value at import time.
os.environ["CAMPUSFIX_API_BASE"] = API_BASE_URL
from frontend.main import CampusFixApp

if __name__ == "__main__":
    CampusFixApp().run()
'''

SPEC = '''# CampusFix Android DEBUG prototype. Build from this folder, not project root.
# Change package.domain to a domain you control before any release.
[app]
title = CampusFix
package.name = campusfix
package.domain = org.campusfix.prototype
source.dir = .
source.include_exts = py
version = 0.1.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.api = 36
android.minapi = 24
android.archs = arm64-v8a
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1
'''

README = '''CampusFix Android staging — source-only preparation.

This folder is generated from the working frontend. It is NOT a built APK.
The backend and PostgreSQL remain separate and must be reachable through HTTPS.
Do not build while app_config.py has https://campusfix-api.invalid.

Files copied from the project: ONLY frontend/main.py, plus a package initializer.
Launcher: main.py sets CAMPUSFIX_API_BASE before importing frontend.main.
Buildozer requirements: python3,kivy,requests. No backend dependencies.

When a reachable HTTPS API is available, run FROM PROJECT ROOT:
  python scripts/prepare_android.py --set-api-url https://your-real-api.example
  python scripts/prepare_android.py --check --require-api

Do not copy .env, credentials, backend, tests, virtualenv, or PostgreSQL data.
Do not commit this generated folder until configuration and staging review.
Java 26 is installed on the Mac; Android tooling may require JDK 17.
Buildozer and Android device tests are a separate next step.
'''


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def validate_https(url: str) -> str:
    """Accept only non-secret, absolute HTTPS URLs pointing away from loopback."""
    url = url.strip().rstrip("/")
    if not url or len(url) > 240 or any(x.isspace() for x in url):
        raise ValueError("API URL must be a non-empty HTTPS URL without spaces")
    try:
        result = urlsplit(url)
        port = result.port  # access validates port
    except ValueError as error:
        raise ValueError("Invalid HTTPS API URL") from error
    host = (result.hostname or "").lower()
    if (result.scheme != "https" or not host or result.username or result.password
            or result.query or result.fragment or port == 0):
        raise ValueError("Use an HTTPS URL without credentials, query, or fragment")
    if (host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "example.com"}
            or host.endswith((".invalid", ".local", ".localhost"))):
        raise ValueError("API must be a reachable HTTPS host, not localhost or a placeholder")
    if not re.fullmatch(r"[A-Za-z0-9._:\[\]-]+", result.netloc):
        raise ValueError("API host contains unsupported characters")
    return url


def safe_stage() -> bool:
    return (STAGE.is_dir() and not STAGE.is_symlink() and MARKER.is_file()
            and not MARKER.is_symlink() and
            MARKER.read_text(encoding="utf-8").startswith("CampusFix Android staging v1\n"))


def read_stage_url() -> str:
    tree = ast.parse((STAGE / "app_config.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "API_BASE_URL":
                value = ast.literal_eval(node.value)
                if isinstance(value, str):
                    return value
    raise ValueError("API_BASE_URL declaration missing or malformed")


def write_url(url: str) -> None:
    (STAGE / "app_config.py").write_text(
        '# Android API address; this is not a password or secret.\n'
        f'API_BASE_URL = {url!r}\n', encoding="utf-8"
    )


def create_stage() -> int:
    source = ROOT / "frontend" / "main.py"
    manifest = ROOT / "requirements" / "client.txt"
    if not source.is_file() or not manifest.is_file():
        raise ValueError("Missing frontend/main.py or requirements/client.txt; run from the CampusFix project")
    source_data = source.read_bytes()
    parsed = ast.parse(source_data, filename=str(source))
    if "CampusFixApp" not in {n.name for n in parsed.body if isinstance(n, ast.ClassDef)}:
        raise ValueError("CampusFixApp not found in source")
    imports = []
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    if any(name.split(".")[0] in {"backend", "fastapi", "sqlalchemy", "psycopg", "uvicorn"}
           for name in imports):
        raise ValueError("Frontend imports server-only dependencies")
    if "CAMPUSFIX_API_BASE" not in source_data.decode("utf-8"):
        raise ValueError("Frontend needs CAMPUSFIX_API_BASE configuration")
    dependencies = manifest.read_text(encoding="utf-8").lower()
    if not all(re.search(rf"(?m)^{name}(?:[=<>!~]|$)", dependencies) for name in ("kivy", "requests")):
        raise ValueError("Client requirements must contain Kivy and requests")
    if STAGE.exists() or STAGE.is_symlink():
        raise ValueError("android_staging already exists. Refusing to overwrite it. Use --check or --set-api-url.")
    STAGE.mkdir()
    (STAGE / "frontend").mkdir()
    (STAGE / "frontend" / "main.py").write_bytes(source_data)
    (STAGE / "frontend" / "__init__.py").write_text("", encoding="utf-8")
    (STAGE / "main.py").write_text(LAUNCHER, encoding="utf-8")
    (STAGE / "buildozer.spec").write_text(SPEC, encoding="utf-8")
    (STAGE / "README_ANDROID_STAGING.txt").write_text(README, encoding="utf-8")
    (STAGE / "app_config.py").write_text(f'API_BASE_URL = {PLACEHOLDER!r}\n', encoding="utf-8")
    MARKER.write_text("CampusFix Android staging v1\n" + digest(source_data) + "\n", encoding="utf-8")
    print("[PASS] Android staging created:", STAGE)
    print("[PASS] Copied ONLY frontend/main.py; excluded backend, .env, database, tests, and virtualenv")
    print("[PASS] Android launcher and Buildozer specification created")
    print("[ACTION] API URL not set; staging is NOT ready for an APK build")
    print("[NEXT] python scripts/prepare_android.py --check")
    return 0


def check_stage(require_api: bool) -> int:
    if not safe_stage():
        print("[FAIL] Missing or invalid staging marker; create with python scripts/prepare_android.py")
        return 2
    paths = {p.relative_to(STAGE).as_posix() for p in STAGE.rglob("*") if p.is_file()}
    extras = paths - ALLOWED
    if extras:
        print("[FAIL] Unexpected files in staging:", ", ".join(sorted(extras)))
        return 2
    missing = ALLOWED - paths
    if missing:
        print("[FAIL] Staging files missing:", ", ".join(sorted(missing)))
        return 2
    if any(p.is_symlink() for p in STAGE.rglob("*")):
        print("[FAIL] Symlinks are not allowed in staging")
        return 2
    original = ROOT / "frontend" / "main.py"
    if not original.is_file() or digest(original.read_bytes()) != digest((STAGE / "frontend/main.py").read_bytes()):
        print("[FAIL] Staged frontend differs from current working frontend")
        return 2
    marker_sha = MARKER.read_text(encoding="utf-8").splitlines()[1]
    if marker_sha != digest(original.read_bytes()):
        print("[FAIL] Source signature mismatch")
        return 2
    for part in ("main.py", "frontend/main.py", "app_config.py"):
        ast.parse((STAGE / part).read_text(encoding="utf-8"))
    spec = configparser.ConfigParser(interpolation=None)
    spec.read(STAGE / "buildozer.spec", encoding="utf-8")
    if (spec.get("app", "source.dir") != "."
            or spec.get("app", "requirements") != "python3,kivy,requests"
            or spec.get("app", "android.permissions") != "INTERNET"):
        print("[FAIL] Android spec changed unexpectedly")
        return 2
    if spec.getboolean("app", "android.allow_backup"):
        print("[FAIL] Android app backup should be disabled for this prototype")
        return 2
    print("[PASS] Android staging contains only the approved files")
    print("[PASS] Staged frontend matches the current CampusFix app")
    print("[PASS] Android main.py and Buildozer settings pass static checks")
    url = read_stage_url()
    if url == PLACEHOLDER:
        print("[ACTION] API URL is still a placeholder; do NOT build or distribute an APK")
        return 2 if require_api else 0
    try:
        validate_https(url)
    except ValueError as error:
        print("[FAIL] Invalid API URL:", error)
        return 2
    host = urlsplit(url).hostname
    print("[PASS] Configured HTTPS API host:", host)
    print("[NOTE] Network reachability, Android build, and actual login are NOT tested yet")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Check staging folder, without changing files")
    group.add_argument("--set-api-url", metavar="HTTPS_URL", help="Update ONLY staging API config")
    parser.add_argument("--require-api", action="store_true", help="When checking, fail if API URL is not configured")
    args = parser.parse_args()
    try:
        if args.set_api_url is not None:
            if not safe_stage():
                raise ValueError("No valid staging folder; run script without options first")
            url = validate_https(args.set_api_url)
            write_url(url)
            print("[PASS] Updated Android-only API address:", urlsplit(url).hostname)
            return check_stage(require_api=True)
        if args.check:
            return check_stage(require_api=args.require_api)
        if args.require_api:
            parser.error("--require-api can only be used with --check")
        return create_stage()
    except (ValueError, OSError, SyntaxError, IndexError) as error:
        print("[FAIL]", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
