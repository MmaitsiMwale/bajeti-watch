"""
conftest.py — pytest configuration at project root.

Adds all ingestion module folders to sys.path so test files can import
md_cleaner, md_tagger, supabase_uploader etc. directly without worrying
about relative paths.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent  # bajeti-watch/

# Add each ingestion subfolder so imports work directly
sys.path.insert(0, str(ROOT / "ingestion" / "cleaner"))
sys.path.insert(0, str(ROOT / "ingestion" / "tagger"))
sys.path.insert(0, str(ROOT / "ingestion" / "uploader"))
sys.path.insert(0, str(ROOT / "ingestion" / "convertor"))
sys.path.insert(0, str(ROOT / "ingestion"))