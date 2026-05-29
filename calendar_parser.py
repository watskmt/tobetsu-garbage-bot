"""
当別町ごみ収集カレンダー パーサー（画像PDF対応）

PDF → 画像変換 → Claude Vision API でカレンダーを解析する。
結果はローカルにキャッシュするため、APIコールは初回起動時のみ。
"""
from __future__ import annotations

import base64
import io
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_JST = timezone(timedelta(hours=9))


def _today() -> date:
    """サーバーのシステムタイムゾーンに依存せず JST の今日を返す"""
    return datetime.now(_JST).date()

import anthropic
import requests
from pdf2image import convert_from_bytes

BASE_URL = "https://www.town.tobetsu.hokkaido.jp"
DISTRICT_PDFS = {
    1: "/uploaded/attachment/29812.pdf",
    2: "/uploaded/attachment/29813.pdf",
    3: "/uploaded/attachment/29814.pdf",
    4: "/uploaded/attachment/29815.pdf",
}

DISTRICT_NAMES = {
    1: "1地区（弥生・園生・青山・弁華別など）",
    2: "2地区（金沢・中小屋・東裏・蕨岱町）",
    3: "3地区（白樺町・下川町・末広・スウェーデンヒルズなど）",
    4: "4地区（春日町・樺岱町・太美・高岡など）",
}

WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]
CACHE_DIR = Path("cache")

PROMPT = """\
この画像は北海道当別町のごみ収集カレンダーです。
カレンダー全体を左上から右下まで丁寧に読み取り、
各日付のごみ収集情報をJSON形式のみで返答してください（説明文・```不要）。

出力形式:
{
  "2026-04-07": ["燃やせるごみ"],
  "2026-04-11": ["資源物"],
  "2026-04-03": ["燃えないごみ"],
  ...
}

【ごみ種別の見分け方（これが唯一の判断基準）】
- 赤い丸（○）が付いている日            → 「燃やせるごみ」
- 青い四角の枠線で囲まれている日        → 「資源物」
- 水色・青の斜線網掛けの日             → 「燃えないごみ」
- ピンク・薄赤の斜線網掛けの日         → 「燃やせないごみ」
- スプレー缶マークまたは別記号の日     → 「スプレー缶」
- 日付の文字色（赤・黒など）は無視してよい

【重要ルール】
1. 網掛けは薄くても見落とさないこと。
   うっすら斜線が入っているセルも必ず記録する。

2. ごみ種別は必ず以下の6種類の表記に統一すること:
   - 「燃やせるごみ」  → 赤い○マーク
   - 「燃やせないごみ」→ ピンク・薄赤の斜線網掛け
   - 「燃えないごみ」  → 水色・青の斜線網掛け
   - 「資源物」        → 青い四角枠
   - 「スプレー缶」    → スプレー缶マーク

3. 同じ日に複数の印がある場合はリストに全て含める。

4. 印のない日（完全に空白）は含めない。

5. 年はカレンダーのヘッダーから読み取る。
   「令和8年」=2026年、「令和7年」=2025年。

6. JSONのみ出力（前後に説明文・```・コメント不要）。
"""


class GarbageCalendar:
    def __init__(self):
        CACHE_DIR.mkdir(exist_ok=True)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else None
        # {district: {"2025-04-01": ["燃やせるごみ"], ...}}
        self._schedules: dict[int, dict[str, list[str]]] = {}
        self.reload()

    def reload(self):
        corrections = self._load_corrections()
        for district in [1, 2, 3, 4]:
            try:
                schedule = self._load_district(district)
                # 手動修正を適用
                overrides = corrections.get(str(district), {})
                for date_key, types in overrides.items():
                    if types:
                        schedule[date_key] = types
                    else:
                        schedule.pop(date_key, None)  # 空リスト → 削除
                self._schedules[district] = schedule
                print(f"地区{district}: {len(schedule)}日分 読み込み完了（修正{len(overrides)}件）")
            except Exception as e:
                print(f"地区{district} エラー: {e}")
                self._schedules[district] = {}

    def _generate_from_rules(self, district: int) -> dict[str, list[str]]:
        """rules.json のルールからスケジュールを生成する（起動時: 現年度＋翌年度）"""
        today = date.today()
        fiscal_start_year = today.year if today.month >= 4 else today.year - 1
        result: dict[str, list[str]] = {}
        for fy in [fiscal_start_year, fiscal_start_year + 1]:
            result.update(self._generate_single_fiscal_year(district, fy))
        return result

    def _generate_single_fiscal_year(self, district: int, fiscal_year: int) -> dict[str, list[str]]:
        """指定年度（4月〜翌3月）の1年分を生成する"""
        rules_path = Path("rules.json")
        if not rules_path.exists():
            return {}
        try:
            all_rules = json.loads(rules_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

        district_rules = all_rules.get(str(district), {}).get("weekday_rules", [])
        if not district_rules:
            return {}

        start = date(fiscal_year, 4, 1)
        end   = date(fiscal_year + 1, 3, 31)

        schedule: dict[str, list[str]] = {}
        current = start
        while current <= end:
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
        """指定年度が未生成なら追加生成して_schedulesに追記する"""
        check_key = date(fiscal_year, 4, 1).strftime("%Y-%m-%d")
        if check_key in self._schedules.get(district, {}):
            return  # 生成済み

        new_data = self._generate_single_fiscal_year(district, fiscal_year)
        if not new_data:
            return

        # corrections.json の上書きを適用
        corrections = self._load_corrections()
        overrides = corrections.get(str(district), {})
        for date_key, types in overrides.items():
            if date_key in new_data:
                if types:
                    new_data[date_key] = types
                else:
                    new_data.pop(date_key, None)

        self._schedules.setdefault(district, {}).update(new_data)
        print(f"地区{district}: {fiscal_year}年度を追加生成（{len(new_data)}日分）")

    def _load_corrections(self) -> dict:
        path = Path("corrections.json")
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception:
            return {}

    # ------------------------------------------------------------------ #
    #  取得・解析                                                         #
    # ------------------------------------------------------------------ #

    def _load_district(self, district: int) -> dict[str, list[str]]:
        # ① ルールベース生成（rules.json に定義があれば優先）
        rule_schedule = self._generate_from_rules(district)
        if rule_schedule:
            print(f"地区{district}: ルールから生成")
            return rule_schedule

        # ② キャッシュ（PDF解析済み）
        cache_file = CACHE_DIR / f"district_{district}.json"
        if cache_file.exists():
            print(f"地区{district}: キャッシュから読み込み")
            return json.loads(cache_file.read_text(encoding="utf-8"))

        # PDFをダウンロードして画像に変換
        print(f"地区{district}: PDFをダウンロード中...")
        pdf_bytes = self._download_pdf(district)
        images = convert_from_bytes(pdf_bytes, dpi=250)
        print(f"地区{district}: {len(images)}ページ → Claude Vision で解析中...")

        schedule: dict[str, list[str]] = {}
        for i, img in enumerate(images):
            print(f"  ページ {i+1}/{len(images)} 解析中...")
            page_data = self._parse_image_with_claude(img)
            schedule.update(page_data)

        # キャッシュに保存
        cache_file.write_text(
            json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"地区{district}: キャッシュ保存 → {cache_file}")
        return schedule

    def _download_pdf(self, district: int) -> bytes:
        url = BASE_URL + DISTRICT_PDFS[district]
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.content

    def _parse_image_with_claude(self, img) -> dict[str, list[str]]:
        # PIL Image → base64 PNG
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()

        response = self._client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )

        raw = response.content[0].text.strip()
        # ```json ... ``` で囲まれている場合に対応
        if "```" in raw:
            raw = raw.split("```")[1].lstrip("json").strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  JSON解析エラー: {e}\n  レスポンス: {raw[:200]}")
            return {}

    # ------------------------------------------------------------------ #
    #  公開インターフェース                                               #
    # ------------------------------------------------------------------ #

    def get_today(self, district: int) -> str:
        return self._format_day(district, _today())

    def get_tomorrow(self, district: int) -> str:
        return self._format_day(district, _today() + timedelta(days=1))

    def get_week(self, district: int) -> str:
        today = _today()
        lines = []
        for i in range(7):
            d = today + timedelta(days=i)
            day_str = self._format_day(district, d)
            if "収集なし" not in day_str:
                lines.append(day_str)
        if not lines:
            return "今週の収集予定はありません。"
        return "\n".join(lines)

    def get_month(self, district: int) -> str:
        today = _today()
        lines = []
        for i in range(30):
            d = today + timedelta(days=i)
            day_str = self._format_day(district, d)
            if "収集なし" not in day_str:
                lines.append(day_str)
        if not lines:
            return "向こう30日間に収集予定はありません。"
        return "\n".join(lines)

    def clear_cache(self, district: int | None = None):
        """キャッシュ削除 → 次回reload()時に再取得"""
        targets = [district] if district else [1, 2, 3, 4]
        for d in targets:
            f = CACHE_DIR / f"district_{d}.json"
            if f.exists():
                f.unlink()
                print(f"地区{d} キャッシュ削除")

    def is_loaded(self, district: int) -> bool:
        return bool(self._schedules.get(district))

    # ------------------------------------------------------------------ #
    #  フォーマット                                                       #
    # ------------------------------------------------------------------ #

    def _format_day(self, district: int, d: date) -> str:
        key = d.strftime("%Y-%m-%d")
        types = self._schedules.get(district, {}).get(key, [])
        weekday = WEEKDAY_JP[d.weekday()]
        date_str = f"{d.month}月{d.day}日({weekday})"
        if not types:
            return f"{date_str}: 収集なし"
        return f"{date_str}: {'・'.join(types)}"
