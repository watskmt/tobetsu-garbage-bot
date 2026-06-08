from __future__ import annotations

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
        entry = data.get(user_id, {})
        entry["district"] = district
        data[user_id] = entry
        _save(data)


def get_district(user_id: str) -> int | None:
    data = _load()
    entry = data.get(user_id)
    return entry["district"] if entry else None


def set_notify_time(user_id: str, time_str: str | None):
    """通知時刻を設定する。None で通知オフ。time_str は "HH:MM" 形式。"""
    with _lock:
        data = _load()
        entry = data.get(user_id, {})
        if time_str is None:
            entry.pop("notify_time", None)
        else:
            entry["notify_time"] = time_str
        data[user_id] = entry
        _save(data)


def get_notify_time(user_id: str) -> str | None:
    data = _load()
    entry = data.get(user_id)
    return entry.get("notify_time") if entry else None


def delete_user(user_id: str) -> bool:
    with _lock:
        data = _load()
        if user_id not in data:
            return False
        del data[user_id]
        _save(data)
    return True


def get_users_to_notify(hhmm: str) -> list[dict]:
    """指定の HH:MM に通知が設定されているユーザー一覧を返す。"""
    data = _load()
    result = []
    for uid, entry in data.items():
        if entry.get("notify_time") == hhmm and entry.get("district"):
            result.append({"user_id": uid, "district": entry["district"]})
    return result
