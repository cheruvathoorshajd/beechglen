"""Filesystem layout.

Every path used by the backend is derived here so that no module hard-codes a
relative path and the app behaves the same whichever directory it starts from.
"""

from __future__ import annotations

from pathlib import Path

#: ``backend/app/paths.py`` -> app -> backend -> repository root
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

BACKEND_DIR: Path = REPO_ROOT / "backend"
DATA_DIR: Path = REPO_ROOT / "data"
MA_DATA_DIR: Path = DATA_DIR / "ma"
SCENARIO_DIR: Path = DATA_DIR / "scenarios"
CACHE_DIR: Path = DATA_DIR / "cache"
EXTRACTION_CACHE_DIR: Path = CACHE_DIR / "extractions"
DISPATCH_RULES_FILE: Path = DATA_DIR / "dispatch_rules.json"
FRONTEND_DIST_DIR: Path = REPO_ROOT / "frontend" / "dist"

GAZETTEER_FILE: Path = MA_DATA_DIR / "gazetteer.json"
HIGHWAYS_FILE: Path = MA_DATA_DIR / "highways.json"
LANDMARKS_FILE: Path = MA_DATA_DIR / "landmarks.json"
AGENCIES_FILE: Path = MA_DATA_DIR / "agencies.json"


def ensure_cache_dir() -> Path:
    """Create the extraction cache directory if it does not exist yet."""
    EXTRACTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return EXTRACTION_CACHE_DIR
