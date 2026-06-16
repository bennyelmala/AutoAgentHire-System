"""Quick smoke check for AutoAgentHire services.

This script is intentionally tiny and dependency-free beyond requests.
It verifies that the backend health endpoint responds and that the frontend serves HTML.

Exit codes:
- 0: all checks passed
- 1: one or more checks failed
"""

from __future__ import annotations

import sys
from typing import Tuple

import requests


def check_backend(base_url: str) -> Tuple[bool, str]:
    try:
        r = requests.get(f"{base_url}/api/health", timeout=5)
        r.raise_for_status()
        return True, r.text
    except Exception as e:
        return False, f"backend failed: {e}"


def check_frontend(url: str) -> Tuple[bool, str]:
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "text/html" not in ct:
            return False, f"frontend unexpected content-type: {ct}"
        return True, ct
    except Exception as e:
        return False, f"frontend failed: {e}"


def main() -> int:
    backend_ok, backend_msg = check_backend("http://127.0.0.1:8000")
    frontend_ok, frontend_msg = check_frontend("http://127.0.0.1:8080/")

    print(f"backend:  {'OK' if backend_ok else 'FAIL'}  ({backend_msg})")
    print(f"frontend: {'OK' if frontend_ok else 'FAIL'}  ({frontend_msg})")

    return 0 if backend_ok and frontend_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
