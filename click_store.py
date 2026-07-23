from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from threading import Lock

STORE_FILE = "clicks.json"
_lock = Lock()
JST = timezone(timedelta(hours=9))


def _default() -> dict:
    return {"impressions": 0, "clicks": 0, "calls": 0, "last_click": None}


def _load() -> dict:
    p = Path(STORE_FILE)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict):
    Path(STORE_FILE).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _entry(data: dict, bid: str) -> dict:
    return data.setdefault(bid, _default())


def record_impressions(bid: str, n: int):
    """広告を送信した人数を累積する。"""
    if not bid or n <= 0:
        return
    with _lock:
        data = _load()
        _entry(data, bid)["impressions"] += n
        _save(data)


def record_click(bid: str):
    """バナーのタップ（サイト訪問・中間ページ表示）を1件記録する。"""
    with _lock:
        data = _load()
        e = _entry(data, bid)
        e["clicks"] += 1
        e["last_click"] = datetime.now(JST).isoformat()
        _save(data)


def record_call(bid: str):
    """中間ページの「電話する」タップ（発信意図）を1件記録する。"""
    with _lock:
        data = _load()
        _entry(data, bid)["calls"] += 1
        _save(data)


def get_stats(bid: str) -> dict:
    return _load().get(bid, _default())


def all_stats() -> dict:
    return _load()
