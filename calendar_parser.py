"""
当別町ごみ収集カレンダー

rules.json の曜日ルールから年度単位でスケジュールを生成し、
corrections.json の手動修正（例外日）を上書き適用する。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jpholiday

_JST = timezone(timedelta(hours=9))

RULES_FILE = "rules.json"
CORRECTIONS_FILE = "corrections.json"

DISTRICT_NAMES = {
    1: "1地区（弥生・園生・青山・弁華別など）",
    2: "2地区（金沢・中小屋・東裏・蕨岱町）",
    3: "3地区（白樺町・下川町・末広・スウェーデンヒルズなど）",
    4: "4地区（春日町・樺戸町・太美・高岡など）",
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]


def _today() -> date:
    """サーバーのシステムタイムゾーンに依存せず JST の今日を返す"""
    return datetime.now(_JST).date()


def fiscal_year_of(d: date) -> int:
    """日付が属する年度（4月始まり）を返す"""
    return d.year if d.month >= 4 else d.year - 1


def _read_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_rules() -> dict:
    return _read_json(RULES_FILE)


def load_corrections() -> dict:
    """corrections.json を読み込む（"_" で始まるメタキーは除く）"""
    return {k: v for k, v in _read_json(CORRECTIONS_FILE).items() if not k.startswith("_")}


def _parse_mmdd(s: str) -> tuple[int, int]:
    m, d = s.split("-")
    return int(m), int(d)


def _in_closed_period(d: date, period: dict) -> bool:
    """"MM-DD" 形式の from/to（年跨ぎ可）に d が含まれるか"""
    fm, fd = _parse_mmdd(period["from"])
    tm, td = _parse_mmdd(period["to"])
    start, end = (fm, fd), (tm, td)
    cur = (d.month, d.day)
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end   # 例: 12-31 〜 01-03


def is_collection_holiday(d: date, holiday_cfg: dict) -> bool:
    """rules.json の holidays 設定に基づき、収集を休止する日か判定する"""
    if not holiday_cfg:
        return False
    if holiday_cfg.get("skip_on_national_holidays") and jpholiday.is_holiday(d):
        return True
    return any(_in_closed_period(d, p) for p in holiday_cfg.get("closed_periods", []))


class GarbageCalendar:
    def __init__(self):
        # {district: {"2025-04-01": ["燃やせるごみ"], ...}}
        self._schedules: dict[int, dict[str, list[str]]] = {}
        # 生成済み年度 {district: {2026, 2027}}（修正だけで日付が存在する年度と区別する）
        self._generated: dict[int, set[int]] = {}
        self.reload()

    # ------------------------------------------------------------------ #
    #  生成                                                               #
    # ------------------------------------------------------------------ #

    def reload(self):
        """rules.json / corrections.json を読み直してスケジュールを再生成する"""
        corrections = load_corrections()
        fy = fiscal_year_of(_today())
        for district in [1, 2, 3, 4]:
            try:
                schedule: dict[str, list[str]] = {}
                for year in (fy, fy + 1):
                    schedule.update(self._generate_single_fiscal_year(district, year))
                overrides = corrections.get(str(district), {})
                self._apply_corrections(schedule, overrides)
                self._schedules[district] = schedule
                self._generated[district] = {fy, fy + 1}
                print(f"地区{district}: {len(schedule)}日分 生成完了（修正{len(overrides)}件）")
            except Exception as e:
                print(f"地区{district} エラー: {e}")
                self._schedules[district] = {}
                self._generated[district] = set()

    @staticmethod
    def _apply_corrections(schedule: dict, overrides: dict,
                           start: date | None = None, end: date | None = None):
        """手動修正を適用する。空リスト → 削除、非空 → 上書き（未生成日への追加も可）。
        start/end を指定するとその範囲の修正だけ適用する。"""
        for date_key, types in overrides.items():
            if start or end:
                try:
                    d = date.fromisoformat(date_key)
                except ValueError:
                    continue
                if (start and d < start) or (end and d > end):
                    continue
            if types:
                schedule[date_key] = types
            else:
                schedule.pop(date_key, None)

    def _generate_single_fiscal_year(self, district: int, fiscal_year: int) -> dict[str, list[str]]:
        """指定年度（4月〜翌3月）の1年分を生成する"""
        all_rules = load_rules()
        district_rules = all_rules.get(str(district), {}).get("weekday_rules", [])
        if not district_rules:
            return {}
        holiday_cfg = all_rules.get("holidays", {})

        start = date(fiscal_year, 4, 1)
        end = date(fiscal_year + 1, 3, 31)

        schedule: dict[str, list[str]] = {}
        current = start
        while current <= end:
            if is_collection_holiday(current, holiday_cfg):
                current += timedelta(days=1)
                continue
            types: list[str] = []
            for rule in district_rules:
                if current.weekday() not in rule["weekday"]:
                    continue
                if "nth" in rule:
                    nth = (current.day - 1) // 7 + 1
                    if nth not in rule["nth"]:
                        continue
                t = rule["type"]
                if t not in types:
                    types.append(t)
            if types:
                schedule[current.strftime("%Y-%m-%d")] = types
            current += timedelta(days=1)

        return schedule

    def ensure_fiscal_year(self, district: int, fiscal_year: int):
        """指定年度が未生成なら追加生成して _schedules に追記する"""
        if fiscal_year in self._generated.get(district, set()):
            return

        new_data = self._generate_single_fiscal_year(district, fiscal_year)
        if not new_data:
            return

        # その年度に属する修正だけを適用（reload() と同じ規則: 追加も削除も効く）
        overrides = load_corrections().get(str(district), {})
        self._apply_corrections(
            new_data, overrides,
            start=date(fiscal_year, 4, 1), end=date(fiscal_year + 1, 3, 31),
        )

        self._schedules.setdefault(district, {}).update(new_data)
        self._generated.setdefault(district, set()).add(fiscal_year)
        print(f"地区{district}: {fiscal_year}年度を追加生成（{len(new_data)}日分）")

    # ------------------------------------------------------------------ #
    #  公開インターフェース                                               #
    # ------------------------------------------------------------------ #

    def get_types(self, district: int, d: date) -> list[str]:
        return self._schedules.get(district, {}).get(d.strftime("%Y-%m-%d"), [])

    def get_today(self, district: int) -> str:
        return self._format_day(district, _today())

    def get_tomorrow(self, district: int) -> str:
        return self._format_day(district, _today() + timedelta(days=1))

    def get_week(self, district: int) -> str:
        return self._format_range(district, 7, "今後7日間に収集予定はありません。")

    def get_month(self, district: int) -> str:
        return self._format_range(district, 30, "今後30日間に収集予定はありません。")

    def is_loaded(self, district: int) -> bool:
        return bool(self._schedules.get(district))

    # ------------------------------------------------------------------ #
    #  フォーマット                                                       #
    # ------------------------------------------------------------------ #

    def _format_range(self, district: int, days: int, empty_msg: str) -> str:
        today = _today()
        lines = [
            self._format_day(district, d)
            for d in (today + timedelta(days=i) for i in range(days))
            if self.get_types(district, d)
        ]
        return "\n".join(lines) if lines else empty_msg

    def _format_day(self, district: int, d: date) -> str:
        types = self.get_types(district, d)
        weekday = WEEKDAY_JP[d.weekday()]
        date_str = f"{d.month}月{d.day}日({weekday})"
        if not types:
            return f"{date_str}: 収集なし"
        return f"{date_str}: {'・'.join(types)}"
