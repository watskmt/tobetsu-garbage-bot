from __future__ import annotations

from threading import Lock

from jsonfile import load_json, save_json

STORE_FILE = "users.json"
_lock = Lock()


def _load() -> dict:
    return load_json(STORE_FILE, {})


def _save(data: dict):
    save_json(STORE_FILE, data)


def _update(user_id: str, fn) -> None:
    """ユーザーエントリを読み込み → fn で変更 → 保存（ロック内）。"""
    with _lock:
        data = _load()
        entry = data.get(user_id, {})
        fn(entry)
        data[user_id] = entry
        _save(data)


def set_district(user_id: str, district: int):
    def apply(entry):
        entry["district"] = district
    _update(user_id, apply)


def get_district(user_id: str) -> int | None:
    # 通知設定だけ先に行ったユーザーは district キーを持たないので .get で読む
    return _load().get(user_id, {}).get("district")


def set_notify_time(user_id: str, time_str: str | None):
    """通知時刻を設定する。None で通知オフ。time_str は "HH:MM" 形式。"""
    def apply(entry):
        if time_str is None:
            entry.pop("notify_time", None)
        else:
            entry["notify_time"] = time_str
    _update(user_id, apply)


def get_notify_time(user_id: str) -> str | None:
    return _load().get(user_id, {}).get("notify_time")


def set_ads_opt_out(user_id: str, opt_out: bool):
    """広告配信のオプトアウト。True で広告を受け取らない。"""
    def apply(entry):
        if opt_out:
            entry["ads_opt_out"] = True
        else:
            entry.pop("ads_opt_out", None)
    _update(user_id, apply)


def get_ads_opt_out(user_id: str) -> bool:
    return bool(_load().get(user_id, {}).get("ads_opt_out"))


def delete_user(user_id: str) -> bool:
    with _lock:
        data = _load()
        if user_id not in data:
            return False
        del data[user_id]
        _save(data)
    return True


def get_all_users() -> list[dict]:
    """登録済みユーザー一覧を返す（管理画面表示用）。"""
    return [
        {
            "user_id": uid,
            "district": entry.get("district"),
            "notify_time": entry.get("notify_time"),
            "ads_opt_out": bool(entry.get("ads_opt_out")),
        }
        for uid, entry in _load().items()
    ]


def get_broadcast_targets() -> list[str]:
    """広告配信対象のユーザーID一覧（オプトアウト済みを除く）。"""
    return [uid for uid, entry in _load().items() if not entry.get("ads_opt_out")]


def get_users_to_notify(hhmm: str) -> list[dict]:
    """指定の HH:MM に通知が設定されているユーザー一覧を返す。"""
    return [
        {"user_id": uid, "district": entry["district"]}
        for uid, entry in _load().items()
        if entry.get("notify_time") == hhmm and entry.get("district")
    ]
