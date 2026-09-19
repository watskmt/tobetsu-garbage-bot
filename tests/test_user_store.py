import pytest

import user_store


@pytest.fixture(autouse=True)
def _store(tmp_path, monkeypatch):
    monkeypatch.setattr(user_store, "STORE_FILE", str(tmp_path / "users.json"))


def test_notify_before_district_does_not_crash():
    # 地区設定前に通知だけ設定したユーザー（旧実装では KeyError → 500）
    user_store.set_notify_time("U1", "07:00")
    assert user_store.get_district("U1") is None
    assert user_store.get_notify_time("U1") == "07:00"
    assert user_store.get_all_users() == [
        {"user_id": "U1", "district": None, "notify_time": "07:00", "ads_opt_out": False}
    ]
    # 地区が無いユーザーには通知しない
    assert user_store.get_users_to_notify("07:00") == []


def test_district_then_notify():
    user_store.set_district("U1", 3)
    user_store.set_notify_time("U1", "08:00")
    assert user_store.get_district("U1") == 3
    assert user_store.get_users_to_notify("08:00") == [{"user_id": "U1", "district": 3}]
    user_store.set_notify_time("U1", None)
    assert user_store.get_notify_time("U1") is None
    assert user_store.get_district("U1") == 3


def test_ads_opt_out():
    user_store.set_district("U1", 1)
    user_store.set_district("U2", 2)
    assert sorted(user_store.get_broadcast_targets()) == ["U1", "U2"]
    user_store.set_ads_opt_out("U2", True)
    assert user_store.get_ads_opt_out("U2") is True
    assert user_store.get_broadcast_targets() == ["U1"]
    user_store.set_ads_opt_out("U2", False)
    assert sorted(user_store.get_broadcast_targets()) == ["U1", "U2"]


def test_delete_user():
    user_store.set_district("U1", 1)
    assert user_store.delete_user("U1") is True
    assert user_store.delete_user("U1") is False
    assert user_store.get_district("U1") is None
