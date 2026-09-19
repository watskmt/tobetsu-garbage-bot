import json
from datetime import date
from pathlib import Path

import calendar_parser as cp
from calendar_parser import GarbageCalendar, fiscal_year_of, is_collection_holiday


def _write_rules(extra=None):
    rules = {
        "1": {"weekday_rules": [
            {"weekday": [0, 3], "type": "燃やせるごみ"},
            {"weekday": [1], "nth": [1], "type": "燃えないごみ"},
        ]},
        "2": {"weekday_rules": []}, "3": {"weekday_rules": []}, "4": {"weekday_rules": []},
    }
    rules.update(extra or {})
    Path("rules.json").write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")


def _write_corrections(data):
    Path("corrections.json").write_text(json.dumps({"_comment": "x", **data}, ensure_ascii=False), encoding="utf-8")


def test_fiscal_year_of():
    assert fiscal_year_of(date(2026, 3, 31)) == 2025
    assert fiscal_year_of(date(2026, 4, 1)) == 2026


def test_nth_weekday_rule(monkeypatch):
    _write_rules()
    _write_corrections({})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 6, 1))
    cal = GarbageCalendar()
    # 2026-06-02 は第1火曜、06-09 は第2火曜
    assert cal.get_types(1, date(2026, 6, 2)) == ["燃えないごみ"]
    assert cal.get_types(1, date(2026, 6, 9)) == []
    assert cal.get_types(1, date(2026, 6, 1)) == ["燃やせるごみ"]   # 月曜
    assert cal.is_loaded(1) and not cal.is_loaded(2)


def test_corrections_add_and_remove(monkeypatch):
    _write_rules()
    _write_corrections({"1": {"2026-06-01": [], "2026-06-06": ["資源物"]}})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 6, 1))
    cal = GarbageCalendar()
    assert cal.get_types(1, date(2026, 6, 1)) == []              # 削除
    assert cal.get_types(1, date(2026, 6, 6)) == ["資源物"]       # 土曜に追加
    assert "6月6日(土): 資源物" in cal.get_week(1)
    assert cal.get_today(1) == "6月1日(月): 収集なし"


def test_ensure_fiscal_year_applies_additions(monkeypatch):
    """未生成の将来年度に「収集日を追加する」修正も効く（旧実装では既存キーのみ上書き）"""
    _write_rules()
    _write_corrections({"1": {"2029-06-02": ["スプレー缶"], "2029-06-04": []}})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 6, 1))
    cal = GarbageCalendar()
    assert cal.get_types(1, date(2029, 6, 7)) == []              # 2029年度はまだ未生成
    cal.ensure_fiscal_year(1, 2029)
    assert cal.get_types(1, date(2029, 6, 7)) == ["燃やせるごみ"]  # 生成された
    assert cal.get_types(1, date(2029, 6, 2)) == ["スプレー缶"]   # 土曜への追加が残る
    assert cal.get_types(1, date(2029, 6, 4)) == []              # 月曜の削除も反映される
    # 再呼び出しは no-op
    cal.ensure_fiscal_year(1, 2029)
    assert cal.get_types(1, date(2029, 6, 4)) == []


def test_ensure_fiscal_year_fresh_instance_applies_corrections(monkeypatch):
    """reload() を経ずに ensure_fiscal_year だけで年度を足しても修正が対称に効く"""
    _write_rules()
    _write_corrections({})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 6, 1))
    cal = GarbageCalendar()
    _write_corrections({"1": {"2029-06-02": ["スプレー缶"], "2029-06-04": []}})
    cal.ensure_fiscal_year(1, 2029)
    assert cal.get_types(1, date(2029, 6, 2)) == ["スプレー缶"]   # 旧実装では無視されていた
    assert cal.get_types(1, date(2029, 6, 4)) == []


def test_holiday_config_off_by_default(monkeypatch):
    _write_rules()
    _write_corrections({})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 4, 1))
    cal = GarbageCalendar()
    # 2026-05-04 みどりの日（月曜）: 設定オフなら通常どおり収集
    assert cal.get_types(1, date(2026, 5, 4)) == ["燃やせるごみ"]


def test_holiday_config_skips(monkeypatch):
    _write_rules({"holidays": {
        "skip_on_national_holidays": True,
        "closed_periods": [{"from": "12-31", "to": "01-03"}],
    }})
    _write_corrections({})
    monkeypatch.setattr(cp, "_today", lambda: date(2026, 4, 1))
    cal = GarbageCalendar()
    assert cal.get_types(1, date(2026, 5, 4)) == []               # 祝日
    assert cal.get_types(1, date(2026, 5, 11)) == ["燃やせるごみ"]  # 平日の月曜
    assert cal.get_types(1, date(2026, 12, 31)) == []             # 年末（木曜）
    assert cal.get_types(1, date(2027, 1, 1)) == []               # 年始
    assert cal.get_types(1, date(2027, 1, 4)) == ["燃やせるごみ"]   # 休止期間明けの月曜


def test_is_collection_holiday_period_wrap():
    cfg = {"closed_periods": [{"from": "12-30", "to": "01-03"}]}
    assert is_collection_holiday(date(2026, 12, 30), cfg)
    assert is_collection_holiday(date(2027, 1, 3), cfg)
    assert not is_collection_holiday(date(2027, 1, 4), cfg)
    assert not is_collection_holiday(date(2026, 12, 29), cfg)
    assert not is_collection_holiday(date(2026, 6, 1), {})
