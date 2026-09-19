"""One System One HTTP call. Never prints the API key."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_ENV = Path.home() / "PROJECTS" / "JEV-research" / ".env"
DEFAULT_BASE = "https://api.typesafe.ai"


def load_env_file(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.is_file():
        return vals
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        vals[key.strip()] = value.strip().strip('"').strip("'")
    return vals


def resolve_key() -> tuple[str, str]:
    """Return (api_key, base_url). Key may be empty."""
    env_path = Path(os.environ.get("JEV_ENV_FILE") or DEFAULT_ENV)
    file_vals = load_env_file(env_path)
    key = (
        os.environ.get("TYPESAFE_API_KEY")
        or file_vals.get("TYPESAFE_API_KEY")
        or file_vals.get("JEV_API_KEY")
        or ""
    )
    base = (
        os.environ.get("TYPESAFE_BASE_URL")
        or file_vals.get("TYPESAFE_BASE_URL")
        or DEFAULT_BASE
    ).rstrip("/")
    return key, base


def post_systemone(
    *,
    state: Any,
    questions: dict[str, Any],
    model: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    key, base = resolve_key()
    if not key:
        return {"ok": False, "error": "missing_key"}
    url = f"{base}/v1/systemone"
    body = {"state": state, "model": model, "questions": questions}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return {"ok": False, "error": f"http_{err.code}"}
    except Exception as err:  # noqa: BLE001 — fail closed, do not leak
        return {"ok": False, "error": type(err).__name__}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "bad_payload"}
    payload["ok"] = True
    return payload
