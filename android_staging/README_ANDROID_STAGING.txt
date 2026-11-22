CampusFix Android staging — source-only preparation.

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
