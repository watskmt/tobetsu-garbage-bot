"""テスト共通設定。

app.py は import 時に環境変数を要求し、カレンダーを生成し、スケジューラを起動するため、
ダミーの環境変数を与え、リポジトリの rules.json / corrections.json をコピーした
一時ディレクトリを CWD にしてから import する（リポジトリ内のデータファイルを汚さない）。
"""
import os
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "test-token")
os.environ.setdefault("LINE_CHANNEL_SECRET", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-password")
os.environ.setdefault("ADMIN_SECRET_KEY", "0" * 64)
os.environ.setdefault("BOT_BASE_URL", "https://example.test")


@pytest.fixture(scope="session")
def workdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("work")
    shutil.copy(REPO / "rules.json", d / "rules.json")
    shutil.copy(REPO / "corrections.json", d / "corrections.json")
    (d / "static").mkdir()
    for f in ("admin.html", "privacy.html", "terms.html", "docs.js"):
        shutil.copy(REPO / "static" / f, d / "static" / f)
    return d


@pytest.fixture(autouse=True)
def _chdir(workdir, monkeypatch):
    monkeypatch.chdir(workdir)


@pytest.fixture(scope="session")
def app_module(workdir):
    os.chdir(workdir)
    import app  # noqa: E402  (環境変数・CWD 設定後に import する必要がある)

    yield app
    app._scheduler.shutdown(wait=False)
