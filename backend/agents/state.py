"""Simple in-memory status store for agent runs (dev only)."""
from typing import Dict, Any
import threading

_lock = threading.Lock()
_state: Dict[str, Any] = {
    "last_run": None,
    "status": "idle",
    "detail": None,
}


def set_status(status: str, detail: Any = None):
    with _lock:
        _state["status"] = status
        _state["detail"] = detail
        from datetime import datetime

        _state["last_run"] = datetime.utcnow().isoformat()


def get_status() -> Dict[str, Any]:
    with _lock:
        return dict(_state)
