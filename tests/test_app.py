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


@pytest.mark.parametrize("raw,expected", [
    # ヘルプの行をそのままコピーして送るケース
    ("・プライバシーポリシー ", "プライバシーポリシー"),
    ("・利用規約", "利用規約"),
    ("・今日 → 今日の収集ごみ", "今日"),
    ("・地区変更 → 地区を変更する", "地区変更"),
    ("・広告オフ / 広告オン → お知らせ配信の受信設定", "広告オフ"),
    ("・このBotについて → 運営情報", "このBotについて"),
    ("【利用規約】", "利用規約"),
    ("  ・  プライバシーポリシー  ", "プライバシーポリシー"),
    ("- 今日", "今日"),
    ("● 明日", "明日"),
    ("＞ ヘルプ", "ヘルプ"),
    ("利用規約。", "利用規約"),
    # 全角・半角の揺れ（NFKC）
    ("１地区", "1地区"),
    ("地区１", "地区1"),
    ("１週間", "1週間"),
    ("？", "?"),
    ("ﾍﾙﾌﾟ", "ヘルプ"),
    # 装飾のみ・空文字
    ("・", ""),
    ("   ", ""),
])
def test_normalize(app_module, raw, expected):
    assert app_module._normalize(raw) == expected


@pytest.mark.parametrize("command", [
    "地区1", "地区変更", "通知設定", "通知オフ", "通知確認", "広告オフ", "広告オン",
    "今日", "明日", "1週間", "今月", "ヘルプ", "help", "?", "使い方", "メニュー",
    "このBotについて", "運営情報", "プライバシーポリシー", "プライバシー",
    "利用規約", "再読込", "通知7時",
])
def test_normalize_keeps_existing_commands_intact(app_module, command):
    """既存コマンドは正規化で変化しない（"プライバシーポリシー" の語末の長音符など）"""
    assert app_module._normalize(command) == command


def _fake_event(text, user_id="Utest"):
    from types import SimpleNamespace
    return SimpleNamespace(
        source=SimpleNamespace(user_id=user_id),
        message=SimpleNamespace(text=text),
        reply_token="test-token",
    )


@pytest.fixture
def captured_replies(app_module, monkeypatch):
    """reply() を差し替えて、LINE API を呼ばずに応答文を捕捉する"""
    sent = []
    monkeypatch.setattr(app_module, "reply",
                        lambda event, text, **kw: sent.append(text))
    return sent


@pytest.mark.parametrize("raw,expected_fragment", [
    ("・プライバシーポリシー ", "/privacy"),
    ("プライバシーポリシー", "/privacy"),
    ("・利用規約", "/terms"),
    ("【利用規約】", "/terms"),
    ("・今日 → 今日の収集ごみ", "月"),          # 日付入りの収集情報
    ("・このBotについて → 運営情報", "運営者"),
    ("・ヘルプ", "使い方ガイド"),
])
def test_decorated_commands_are_answered(app_module, captured_replies, raw, expected_fragment):
    import user_store

    user_store.set_district("Utest", 3)
    app_module.handle_message(_fake_event(raw))
    assert len(captured_replies) == 1
    assert expected_fragment in captured_replies[0]


def test_decorated_district_and_ads_commands(app_module, captured_replies):
    import user_store

    app_module.handle_message(_fake_event("・1地区", "Udeco"))
    assert "1地区" in captured_replies[-1]
    assert user_store.get_district("Udeco") == 1

    app_module.handle_message(_fake_event("・広告オフ / 広告オン → お知らせ配信の受信設定", "Udeco"))
    assert "オフにしました" in captured_replies[-1]
    assert user_store.get_ads_opt_out("Udeco") is True

    app_module.handle_message(_fake_event("・通知7時", "Udeco"))
    assert "07:00" in captured_replies[-1]
    assert user_store.get_notify_time("Udeco") == "07:00"


def test_unknown_decorated_text_falls_back_to_help(app_module, captured_replies):
    import user_store

    user_store.set_district("Utest", 3)
    app_module.handle_message(_fake_event("・"))
    assert "使い方ガイド" in captured_replies[-1]
