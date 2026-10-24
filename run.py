"""Start Nexus911: the API, the WebSocket and (when built) the frontend.

    python run.py          # http://localhost:8080, docs at /docs

The port comes from PORT (default 8080). Binds 0.0.0.0 so the same entry point
works locally and on Cloud Run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"


def main() -> None:
    sys.path.insert(0, str(BACKEND))
    from app.config import get_settings

    uvicorn.run("app.main:app", host="0.0.0.0", port=get_settings().port, app_dir=str(BACKEND))


if __name__ == "__main__":
    main()
