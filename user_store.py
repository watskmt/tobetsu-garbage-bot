import json
import os
from threading import Lock

STORE_FILE = "users.json"
_lock = Lock()


def _load() -> dict:
    if os.path.exists(STORE_FILE):
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save(data: dict):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_district(user_id: str, district: int):
    with _lock:
        data = _load()
        data[user_id] = {"district": district}
        _save(data)


def get_district(user_id: str) -> int | None:
    data = _load()
    entry = data.get(user_id)
    return entry["district"] if entry else None
