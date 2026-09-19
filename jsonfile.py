"""JSON ファイルのアトミックな読み書き（各 store 共通）。

書き込みは一時ファイルに出力してから os.replace で差し替えるため、
書き込み途中でプロセスが落ちても元のファイルは壊れない。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def load_json(path: str | Path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: str | Path, data) -> None:
    # 本番では /app/users.json → /data/users.json のシンボリックリンクになっている。
    # os.replace はリンクそのものを置き換えてしまうため、実体のパスに解決してから書く。
    p = Path(path).resolve()
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
