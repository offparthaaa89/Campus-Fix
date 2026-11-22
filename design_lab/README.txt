CAMPUSFIX — COMPACT BRAND DESIGN LAB
===============================
This is an isolated Kivy design prototype. It does not replace or import
frontend/main.py, connect to FastAPI, or modify PostgreSQL.

HOW TO TRY IT
1. Extract the ZIP into the root of your existing campus_fix folder.
2. Open Cursor, activate your existing virtual environment:
   source .venv/bin/activate
3. Run:
   python design_lab/fixline_preview.py
4. Click through the Student issue-signs, report preview, and tracking flow.
5. Try the Staff and Admin role previews with the role selector.
6. Resize the desktop window to a phone-like width to see the layout adapt.

The design is intentionally offline and uses sample data. In particular,
"Review report", "Start working", and "Assign request" do not write to the
real CampusFix database. The production version must preserve all current
backend authorization, status transition, comment, and notification rules.

NEXT AFTER REVIEW
Integrate the approved Fixline design system incrementally into the existing
Kivy frontend, screen by screen, testing Student, Staff and Admin flows after
each change. Do not replace backend endpoints or recreate your database.

BRANDING UPDATE
The app window and visible header now show only the CampusFix name beside a
custom vector mark. The internal Fixline progress component remains in ticket
tracking, but Fixline is no longer shown as a product name. The mobile header
is compact and uses a role preview dropdown so issue signs appear sooner.
The Student home page no longer shows a mock ticket-progress indicator.

SAFETY
This is a standalone offline preview. It never modifies frontend/main.py,
backend endpoints, PostgreSQL records, or your existing Git checkpoint.
