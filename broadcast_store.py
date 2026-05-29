from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock

STORE_FILE = "broadcasts.json"
_lock = Lock()
JST = timezone(timedelta(hours=9))


def _load() -> list:
    p = Path(STORE_FILE)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(broadcasts: list):
    Path(STORE_FILE).write_text(
        json.dumps(broadcasts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_broadcasts() -> list:
    return _load()


def create_broadcast(data: dict) -> dict:
    with _lock:
        broadcasts = _load()
        data["id"] = uuid.uuid4().hex[:8]
        data["created_at"] = datetime.now(JST).isoformat()
        data.setdefault("enabled", True)
        broadcasts.append(data)
        _save(broadcasts)
    return data


def get_broadcast(bid: str) -> dict | None:
    for b in _load():
        if b["id"] == bid:
            return b
    return None


def update_broadcast(bid: str, updates: dict) -> dict | None:
    with _lock:
        broadcasts = _load()
        for b in broadcasts:
            if b["id"] == bid:
                b.update(updates)
                _save(broadcasts)
                return b
    return None


def delete_broadcast(bid: str) -> bool:
    with _lock:
        broadcasts = _load()
        new_list = [b for b in broadcasts if b["id"] != bid]
        if len(new_list) == len(broadcasts):
            return False
        _save(new_list)
    return True
