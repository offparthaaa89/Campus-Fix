"""Android-only entry point. Mac entry remains python -m frontend.main."""
import os
from app_config import API_BASE_URL

# Must be set BEFORE importing frontend.main, which reads this value at import time.
os.environ["CAMPUSFIX_API_BASE"] = API_BASE_URL
from frontend.main import CampusFixApp

if __name__ == "__main__":
    CampusFixApp().run()
