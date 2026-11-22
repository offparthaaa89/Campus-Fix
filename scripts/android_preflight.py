"""CampusFix Android packaging preflight — read-only; no install, writes, or network."""
from __future__ import annotations

import ast
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def show(kind: str, message: str):
    print(f"[{kind}] {message}")


def top_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def main():
    print("CampusFix — Step 47: Android preflight (READ ONLY)")
    print("Project:", ROOT)
    print("Host:", platform.system(), platform.machine(), "Python", platform.python_version())
    print("=" * 64)
    source = ROOT / "frontend" / "main.py"
    if not source.is_file():
        show("FAIL", "frontend/main.py not found. Run from your campus_fix project.")
        return 2
    try:
        content = source.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(source))
    except (OSError, UnicodeError, SyntaxError) as exc:
        show("FAIL", "Cannot parse frontend/main.py: " + str(exc))
        return 2
    show("PASS", "Frontend Python syntax parsed")
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    if "CampusFixApp" not in classes:
        show("FAIL", "Expected CampusFixApp class not found")
        return 2
    show("PASS", "CampusFixApp entry class found")
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    disallowed = [name for name in imports if name.split(".")[0] in
                  {"backend", "sqlalchemy", "psycopg", "fastapi", "uvicorn"}]
    if disallowed:
        show("FAIL", "Server-only dependencies imported into client: " + ", ".join(disallowed))
        return 2
    show("PASS", "No FastAPI/PostgreSQL server imports in frontend/main.py")

    manifest = ROOT / "requirements" / "client.txt"
    if not manifest.exists():
        show("FAIL", "requirements/client.txt missing")
        return 2
    raw = manifest.read_text(encoding="utf-8").splitlines()
    lines = [x.split("#",1)[0].strip() for x in raw if x.strip() and not x.lstrip().startswith("#")]
    names = [re.split(r"[<=>!~\[; ]", entry, maxsplit=1)[0].lower().replace("_","-") for entry in lines]
    for package in ("kivy", "requests"):
        if package in names:
            show("PASS", "Client manifest includes " + package)
        else:
            show("FAIL", "Client manifest missing " + package)
            return 2
    server_only = set(names) & {"fastapi", "sqlalchemy", "psycopg", "uvicorn", "pytest"}
    if server_only:
        show("FAIL", "Client manifest contains server/test packages: " + ", ".join(sorted(server_only)))
        return 2
    show("PASS", "Client manifest excludes backend/test packages")
    for package in ("Kivy", "requests"):
        v = top_version(package)
        show("INFO", f"Installed {package}: {v or 'missing in current virtualenv'}")

    if "CAMPUSFIX_API_BASE" in content:
        show("PASS", "Frontend reads CAMPUSFIX_API_BASE")
    else:
        show("WARN", "No configurable CAMPUSFIX_API_BASE found")
    configured = os.getenv("CAMPUSFIX_API_BASE", "").strip()
    if configured:
        uri = urlsplit(configured)
        show("INFO", "CAMPUSFIX_API_BASE: " + (uri.scheme + "://" + (uri.hostname or "(invalid host)")))
        if uri.scheme != "https":
            show("WARN", "Use HTTPS for a deployed API; HTTP is for controlled local development")
        if uri.hostname in {"localhost", "127.0.0.1", "::1"}:
            show("WARN", "Loopback points to the Android device itself, not your Mac")
    else:
        show("WARN", "No API URL configured for Android; default local URL will not reach the Mac from the phone")
    show("INFO", "Build packaging will require an explicit API URL inside the Android package or app settings")

    if (ROOT / "main.py").exists():
        show("INFO", "Root main.py exists; packaging needs to inspect it before use")
    else:
        show("INFO", "No root main.py; Android staging will create a minimal entry point")
    if platform.system() != "Darwin" and platform.system() != "Linux":
        show("WARN", "Buildozer needs macOS/Linux (or Linux via WSL)")
    for command in ("buildozer", "java", "javac", "adb", "git"):
        location = shutil.which(command)
        show("INFO", f"{command}: {location if location else 'not installed / not on PATH'}")
    if shutil.which("java"):
        try:
            completed = subprocess.run(["java", "-version"], capture_output=True,
                                       text=True, timeout=6, check=False)
            version_line = (completed.stderr or completed.stdout).splitlines()
            if version_line:
                show("INFO", "Java: " + version_line[0].strip()[:150])
        except (OSError, subprocess.TimeoutExpired):
            show("WARN", "Java executable found but version check unavailable")
    print("=" * 64)
    show("NEXT", "Prepare an isolated Android staging folder; do NOT include backend, .env or PostgreSQL credentials")
    show("NEXT", "Then configure Buildozer and run first debug APK build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
