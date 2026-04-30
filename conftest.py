"""
conftest.py — pytest configuration at project root.

Adds all ingestion module folders to sys.path so test files can import
md_cleaner, md_tagger, supabase_uploader etc. directly without worrying
about relative paths.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent  # bajeti-watch/

# Load the root .env before test modules are imported. Several integration
# tests decide whether to skip at import time based on these variables.
# override=True prevents stale exported values in a long-lived terminal from
# taking precedence over the current .env.
load_dotenv(ROOT / ".env", override=True)

# Add each ingestion subfolder so imports work directly
sys.path.insert(0, str(ROOT / "ingestion" / "cleaner"))
sys.path.insert(0, str(ROOT / "ingestion" / "tagger"))
sys.path.insert(0, str(ROOT / "ingestion" / "uploader"))
sys.path.insert(0, str(ROOT / "ingestion" / "convertor"))
sys.path.insert(0, str(ROOT / "ingestion"))