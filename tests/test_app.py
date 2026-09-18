import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


@pytest.mark.parametrize("text,expected", [
    ("通知7時", "07:00"),
    ("7時通知", "07:00"),
    ("毎朝8時", "08:00"),
    ("毎日６時", "06:00"),
    ("7時に通知", "07:00"),
    ("通知 9 時", "09:00"),
    ("通知25時", None),
    # 文章中の「N時」で誤って通知設定されない
    ("今日は7時に出せばいい？", None),
    ("9時間かかった", None),
    ("ごみは8時までに", None),
    ("7時", None),
    ("明日", None),
])
def test_parse_notify_time(app_module, text, expected):
    assert app_module._parse_notify_time(text) == expected


def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_docs_pages_have_csp(client):
    for path in ("/privacy", "/terms"):
        r = client.get(path)
        assert r.status_code == 200
        assert "script-src 'self'" in r.headers["content-security-policy"]
        assert "<script>" not in r.text          # インラインスクリプトは外部化済み
        assert 'src="/static/docs.js"' in r.text


def test_webhook_rejects_bad_signature(client):
    r = client.post("/webhook", content=b"{}", headers={"X-Line-Signature": "bad"})
    assert r.status_code == 400


def test_admin_login_and_rate_limit_per_client_ip(client, app_module):
    app_module._login_attempts.clear()
    # 別 IP（Fly-Client-IP）の失敗はカウントを共有しない
    for _ in range(30):
        r = client.post("/admin/login", json={"password": "wrong"}, headers={"Fly-Client-IP": "10.0.0.1"})
        assert r.status_code == 401
    r = client.post("/admin/login", json={"password": "wrong"}, headers={"Fly-Client-IP": "10.0.0.1"})
    assert r.status_code == 429
    r = client.post("/admin/login", json={"password": "test-password"}, headers={"Fly-Client-IP": "10.0.0.2"})
    assert r.status_code == 200
    token = r.json()["token"]
    r = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_admin_token_is_jst_date_based(app_module, monkeypatch):
    from datetime import datetime, timedelta, timezone

    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            # UTC 2026-09-17 23:30 = JST 2026-09-18 08:30
            return datetime(2026, 9, 17, 23, 30, tzinfo=timezone.utc).astimezone(tz or timezone.utc)

    monkeypatch.setattr(app_module, "datetime", FakeDT)
    t1 = app_module._admin_token()
    # JST では同じ日（09:00 前）なのでトークンは変わらない
    class FakeDT2(FakeDT):
        @classmethod
        def now(cls, tz=None):
            return (datetime(2026, 9, 17, 23, 30, tzinfo=timezone.utc) + timedelta(minutes=20)).astimezone(tz or timezone.utc)

    monkeypatch.setattr(app_module, "datetime", FakeDT2)
    assert app_module._admin_token() == t1
