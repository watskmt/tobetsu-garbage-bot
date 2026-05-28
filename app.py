import calendar as cal_module
import json
import os
from datetime import date
from pathlib import Path

import jpholiday
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessageAction,
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

import user_store
from calendar_parser import GarbageCalendar, DISTRICT_NAMES

load_dotenv()

LINE_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

app = FastAPI()
config = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
calendar = GarbageCalendar()

MAIN_QUICK_REPLY = QuickReply(items=[
    QuickReplyItem(action=MessageAction(label="今日", text="今日")),
    QuickReplyItem(action=MessageAction(label="明日", text="明日")),
    QuickReplyItem(action=MessageAction(label="１週間", text="１週間")),
    QuickReplyItem(action=MessageAction(label="今月", text="今月")),
])

DISTRICT_QUICK_REPLY = QuickReply(items=[
    QuickReplyItem(action=MessageAction(label="1地区", text="地区1")),
    QuickReplyItem(action=MessageAction(label="2地区", text="地区2")),
    QuickReplyItem(action=MessageAction(label="3地区", text="地区3")),
    QuickReplyItem(action=MessageAction(label="4地区", text="地区4")),
])

DISTRICT_GUIDE = (
    "地区を選択してください。\n\n"
    "1地区: 弥生・園生・青山・弁華別など\n"
    "2地区: 金沢・中小屋・東裏・蕨岱町\n"
    "3地区: 白樺町・下川町・末広・スウェーデンヒルズなど\n"
    "4地区: 春日町・樺岱町・太美・高岡など"
)


@app.post("/webhook")
async def webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode(), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"


def reply(event, text: str, quick_reply: QuickReply | None = MAIN_QUICK_REPLY):
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=text, quick_reply=quick_reply)],
        ))


@handler.add(FollowEvent)
def handle_follow(event):
    reply(
        event,
        "当別町ごみ収集日Botへようこそ！\n\n" + DISTRICT_GUIDE,
        quick_reply=DISTRICT_QUICK_REPLY,
    )


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 地区設定
    district_map = {
        "地区1": 1, "１地区": 1, "1地区": 1, "地区１": 1,
        "地区2": 2, "２地区": 2, "2地区": 2, "地区２": 2,
        "地区3": 3, "３地区": 3, "3地区": 3, "地区３": 3,
        "地区4": 4, "４地区": 4, "4地区": 4, "地区４": 4,
    }
    if text in district_map:
        d = district_map[text]
        user_store.set_district(user_id, d)
        reply(event, f"{DISTRICT_NAMES[d]} に設定しました。\n「今日」「明日」「今週」で収集日を確認できます。")
        return

    if text in ("地区変更", "地区設定", "設定"):
        reply(event, DISTRICT_GUIDE, quick_reply=DISTRICT_QUICK_REPLY)
        return

    district = user_store.get_district(user_id)
    if district is None:
        reply(event, "まず地区を設定してください。\n" + DISTRICT_GUIDE, quick_reply=DISTRICT_QUICK_REPLY)
        return

    if text in ("今日", "きょう", "today"):
        reply(event, calendar.get_today(district))
    elif text in ("明日", "あした", "tomorrow"):
        reply(event, calendar.get_tomorrow(district))
    elif text in ("１週間", "1週間", "今週", "こんしゅう", "週間", "今週のごみ"):
        reply(event, calendar.get_week(district))
    elif text in ("今月", "こんげつ", "一ヶ月", "1ヶ月", "来月まで"):
        reply(event, calendar.get_month(district))
    elif text in ("再読込", "リロード", "更新"):
        calendar.clear_cache()
        calendar.reload()
        reply(event, "カレンダーデータを再取得しました。")
    else:
        reply(
            event,
            "「今日」「明日」「今週」でごみ収集日を確認できます。\n地区変更は「地区変更」と送ってください。",
        )


@app.get("/")
def health():
    status = {str(d): calendar.is_loaded(d) for d in [1, 2, 3, 4]}
    return {"status": "ok", "calendar_loaded": status}


# ------------------------------------------------------------------ #
#  管理ページ                                                          #
# ------------------------------------------------------------------ #

@app.get("/admin")
def admin_page():
    return FileResponse("static/admin.html")


@app.get("/api/schedule")
def api_schedule(district: int, year: int, month: int):
    _, days_in_month = cal_module.monthrange(year, month)
    corrections = _load_corrections_raw()
    district_corrections = corrections.get(str(district), {})
    result = {}
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        key = d.strftime("%Y-%m-%d")
        types = calendar._schedules.get(district, {}).get(key, [])
        holiday_name = jpholiday.is_holiday_name(d) or ""
        result[key] = {
            "types": types,
            "is_exception": key in district_corrections,
            "is_holiday": bool(holiday_name),
            "holiday_name": holiday_name,
        }
    return result


@app.post("/api/correction")
async def api_correction(request: Request):
    body = await request.json()
    district_key = str(body["district"])
    date_key = body["date"]
    types = body.get("types")   # None = ルールに戻す, [] = 収集なし, [...] = 上書き

    corrections = _load_corrections_raw()
    if district_key not in corrections:
        corrections[district_key] = {}

    if types is None:
        corrections[district_key].pop(date_key, None)
    else:
        corrections[district_key][date_key] = types

    Path("corrections.json").write_text(
        json.dumps({"_comment": "手動修正", **corrections}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    calendar.reload()
    return {"status": "ok"}


def _load_corrections_raw() -> dict:
    path = Path("corrections.json")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}
