CampusFix — Step 45: Reproducible Local Dependency Manifests
===============================================================

WHY THIS STEP
The working campus_fix project has no requirements.txt, but its .venv has the
necessary packages. This script records exact versions of the *direct* dependencies
installed on your Mac, grouped by backend, Kivy client, and development tests.

INSTALL (run from your campus_fix folder in Cursor's terminal)
1. unzip -n ./CampusFix_Step45_Dependency_Manifests.zip -d .
2. source .venv/bin/activate
3. python scripts/generate_requirements.py
4. python -m pip check
5. python -m pytest tests/ -q
6. cat requirements.txt && cat requirements/backend.txt && cat requirements/client.txt && cat requirements/dev.txt

WHAT THE SCRIPT CREATES
requirements.txt              Local development convenience requirements
requirements/backend.txt      FastAPI / PostgreSQL service
requirements/client.txt       Kivy / requests UI client
requirements/dev.txt          pytest / httpx test dependencies

SAFETY
- Reads Python installed-package metadata only; does not install/upgrade anything.
- Refuses to overwrite existing dependency manifests unless --force is supplied.
- Does not read .env, private keys, passwords, or your database.
- Leave requirements-macos.snapshot.txt in place as your full environment backup.

IMPORTANT
These exact pins reflect the Mac virtual environment, not a verified Android
or Windows build. Android/Windows need separate, native packaging tests.
The single Starlette warning is non-fatal; do not upgrade dependencies just to
make the warning disappear before platform validation.
