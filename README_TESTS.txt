CampusFix - Phase 3 / Step 1: automated smoke tests

FILES
- tests/test_smoke.py

INSTALL
1. Copy this ZIP into your existing campus_fix folder (do not replace frontend or backend files).
2. From campus_fix, run:
   unzip -n ./CampusFix_Testing_Step1.zip -d .
   source .venv/bin/activate
   python -m pip install pytest httpx
   python -m pytest tests/test_smoke.py -v

NOTES
- These tests do not register users, create complaints, or change statuses.
- PostgreSQL must be running and .env must have the CampusFix database/auth variables.
- Run them from the root of campus_fix so backend imports resolve correctly.
- Do not share credentials, .env contents, or access tokens when reporting errors.
- If you see an import error or a failed test, share the traceback / assertion lines.
