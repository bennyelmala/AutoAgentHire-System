"""Simple JSON file storage for application results (dev only)."""
import json
from pathlib import Path
from typing import Any, Dict

STORAGE_PATH = Path("data") / "applications.json"


def save_application_result(result: Dict[str, Any]):
    STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = []
    if STORAGE_PATH.exists():
        try:
            data = json.loads(STORAGE_PATH.read_text())
        except Exception:
            data = []
    data.append(result)
    STORAGE_PATH.write_text(json.dumps(data, indent=2))
