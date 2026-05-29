from __future__ import annotations

import calendar as cal_module
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import jpholiday
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessageAction,
    ImageMessage,
    PushMessageRequest,
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import FollowEvent, MessageEvent, TextMessageContent

import broadcast_store
import user_store
from calendar_parser import GarbageCalendar, DISTRICT_NAMES

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

load_dotenv()

LINE_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]

app = FastAPI()
config = Configuration(access_token=LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
calendar = GarbageCalendar()

# ------------------------------------------------------------------ #
#  Push通知スケジューラ                                                #
# ------------------------------------------------------------------ #

def _push_text(user_id: str, text: str):
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        api.push_message(PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=text)],
        ))


def _send_daily_notifications():
    """毎分呼ばれ、現在時刻(JST)に通知設定のあるユーザーへPush送信する。"""
    now = datetime.now(JST)
    hhmm = now.strftime("%H:%M")
    targets = user_store.get_users_to_notify(hhmm)
    for t in targets:
        try:
            msg = calendar.get_today(t["district"])
            if "収集なし" in msg:
                continue
            _push_text(t["user_id"], f"【本日のごみ収集】\n{msg}")
        except Exception as e:
            logger.error("push failed user=%s: %s", t["user_id"], e)


_scheduler = BackgroundScheduler(timezone="Asia/Tokyo")
_scheduler.add_job(_send_daily_notifications, "cron", minute="*")
_scheduler.start()


def _next_occurrence(day_of_week: int, hour: int) -> datetime:
    """次の指定曜日・時刻を返す。APScheduler/Python 規約: 0=月曜〜6=日曜"""
    now = datetime.now(JST)
    days_ahead = (day_of_week - now.weekday()) % 7
    if days_ahead == 0 and now.hour >= hour:
        days_ahead = 7
    return (now + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def _push_broadcast_to_all(broadcast: dict):
    if broadcast["type"] == "text":
        msg = TextMessage(text=broadcast["text"])
    elif broadcast["type"] == "image":
        msg = ImageMessage(
            original_content_url=broadcast["image_url"],
            preview_image_url=broadcast.get("preview_url") or broadcast["image_url"],
        )
    else:
        return

    users = user_store._load()
    with ApiClient(config) as api_client:
        api = MessagingApi(api_client)
        for uid in users:
            try:
                api.push_message(PushMessageRequest(to=uid, messages=[msg]))
            except Exception as e:
                logger.error("broadcast push failed user=%s: %s", uid, e)


def _add_broadcast_job(broadcast: dict):
    bid = broadcast["id"]
    schedule = broadcast.get("schedule", "weekly")
    hour = int(broadcast.get("hour", 9))

    def execute():
        b = broadcast_store.get_broadcast(bid)
        if b and b.get("enabled"):
            _push_broadcast_to_all(b)

    if schedule == "weekly":
        _scheduler.add_job(
            execute, "cron", id=f"bcast_{bid}",
            day_of_week=int(broadcast.get("day_of_week", 0)),
            hour=hour, minute=0, replace_existing=True,
        )
    elif schedule == "biweekly":
        _scheduler.add_job(
            execute, "interval", id=f"bcast_{bid}",
            weeks=2, start_date=broadcast.get("start_date"),
            replace_existing=True,
        )
    elif schedule == "monthly":
        _scheduler.add_job(
            execute, "cron", id=f"bcast_{bid}",
            day=int(broadcast.get("day_of_month", 1)),
            hour=hour, minute=0, replace_existing=True,
        )


def _remove_broadcast_job(bid: str):
    try:
        _scheduler.remove_job(f"bcast_{bid}")
    except Exception:
        pass


for _b in broadcast_store.list_broadcasts():
    if _b.get("enabled"):
        try:
            _add_broadcast_job(_b)
        except Exception as _e:
            logger.error("broadcast job load failed id=%s: %s", _b.get("id"), _e)

# ------------------------------------------------------------------ #
#  管理画面認証                                                        #
# ------------------------------------------------------------------ #
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
_ADMIN_SECRET  = os.environ.get("ADMIN_SECRET_KEY") or secrets.token_hex(32)


def _admin_token() -> str:
    """サーバー秘密鍵から管理者トークンを生成（決定論的HMAC）"""
    return hmac.new(_ADMIN_SECRET.encode(), b"admin-session", hashlib.sha256).hexdigest()


def require_admin(authorization: Optional[str] = Header(None)):
    """管理API用認証依存関係"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="認証が必要です")
    if not hmac.compare_digest(authorization[7:], _admin_token()):
        raise HTTPException(status_code=401, detail="トークンが無効です")


@app.get("/admin/check")
def admin_check(authorization: Optional[str] = Header(None)):
    """トークン検証"""
    if not authorization or not authorization.startswith("Bearer "):
        return {"valid": False, "auth_required": True}
    return {"valid": hmac.compare_digest(authorization[7:], _admin_token()), "auth_required": True}


@app.post("/admin/login")
async def admin_login(request: Request):
    """パスワード検証 → トークン発行"""
    body = await request.json()
    password = body.get("password", "")
    if not hmac.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="パスワードが違います")
    return {"token": _admin_token()}


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
    "1地区: 弥生・園生(旭町・万代町)・青山・弁華別・茂平沢・みどり野\n"
    "2地区: 金沢・中小屋・東裏・蕨岱町\n"
    "3地区: 白白樺町・下川町・末広・西町・錦町・北栄町・美里・六軒町・若葉・上当別・スウェーデンヒルズ\n"
    "4地区: 春日町・樺戸町・幸町・栄町・対雁・東町・緑町・元町・太美(東・西・南・北・中央・寿・スターライト)・高岡・獅子内・ビトエ・当別太・川下(右岸・左岸)"
)

NOTIFY_QUICK_REPLY = QuickReply(items=[
    QuickReplyItem(action=MessageAction(label="6時", text="通知6時")),
    QuickReplyItem(action=MessageAction(label="7時", text="通知7時")),
    QuickReplyItem(action=MessageAction(label="8時", text="通知8時")),
    QuickReplyItem(action=MessageAction(label="通知オフ", text="通知オフ")),
])

# "通知7時" "7時通知" "毎朝7時" 等を HH:00 に変換（正時のみ受付）
_TIME_PATTERN = re.compile(
    r"(?:通知|毎朝|毎日)?([０-９0-9]{1,2})時(?:通知|に通知)?"
)

def _parse_notify_time(text: str) -> str | None:
    """テキストから正時を解析して "HH:00" 形式で返す。解析失敗時は None。"""
    t = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    m = _TIME_PATTERN.search(t)
    if not m:
        return None
    hour = int(m.group(1))
    if not (0 <= hour <= 23):
        return None
    return f"{hour:02d}:00"


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

    # 通知設定
    if text in ("通知設定", "通知", "通知する", "毎日通知"):
        current = user_store.get_notify_time(user_id)
        status = f"現在の設定: {current}" if current else "現在: 通知オフ"
        reply(
            event,
            f"毎朝の通知時刻を選択してください。\n{status}",
            quick_reply=NOTIFY_QUICK_REPLY,
        )
        return

    if text in ("通知オフ", "通知OFF", "通知なし", "通知停止", "通知解除"):
        user_store.set_notify_time(user_id, None)
        reply(event, "毎日の通知をオフにしました。")
        return

    if text in ("通知確認",):
        current = user_store.get_notify_time(user_id)
        if current:
            reply(event, f"毎日 {current} に通知します。\n変更は「通知設定」、停止は「通知オフ」と送ってください。")
        else:
            reply(event, "現在、通知は設定されていません。\n「通知設定」と送ると設定できます。")
        return

    notify_time = _parse_notify_time(text)
    if notify_time:
        user_store.set_notify_time(user_id, notify_time)
        reply(event, f"毎日 {notify_time} にごみ収集情報を通知します。\n停止するには「通知オフ」と送ってください。")
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
            "「今日」「明日」「今週」でごみ収集日を確認できます。\n地区変更は「地区変更」、通知設定は「通知設定」と送ってください。",
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
def api_schedule(district: int, year: int, month: int, _=Depends(require_admin)):
    # リクエストされた年度が未生成なら自動補完
    fy = year if month >= 4 else year - 1
    calendar.ensure_fiscal_year(district, fy)

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
async def api_correction(request: Request, _=Depends(require_admin)):
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


# ------------------------------------------------------------------ #
#  ブロードキャスト管理 API                                             #
# ------------------------------------------------------------------ #

@app.get("/api/broadcasts")
def api_list_broadcasts(_=Depends(require_admin)):
    return broadcast_store.list_broadcasts()


@app.post("/api/broadcasts")
async def api_create_broadcast(request: Request, _=Depends(require_admin)):
    body = await request.json()
    if body.get("schedule") == "biweekly":
        dow = int(body.get("day_of_week", 0))
        hour = int(body.get("hour", 9))
        body["start_date"] = _next_occurrence(dow, hour).isoformat()
    b = broadcast_store.create_broadcast(body)
    if b.get("enabled"):
        _add_broadcast_job(b)
    return b


@app.delete("/api/broadcasts/{bid}")
def api_delete_broadcast(bid: str, _=Depends(require_admin)):
    _remove_broadcast_job(bid)
    if not broadcast_store.delete_broadcast(bid):
        raise HTTPException(status_code=404, detail="not found")
    return {"status": "ok"}


@app.post("/api/broadcasts/{bid}/send")
def api_send_broadcast_now(bid: str, _=Depends(require_admin)):
    b = broadcast_store.get_broadcast(bid)
    if not b:
        raise HTTPException(status_code=404, detail="not found")
    _push_broadcast_to_all(b)
    return {"status": "ok"}


@app.patch("/api/broadcasts/{bid}")
async def api_patch_broadcast(bid: str, request: Request, _=Depends(require_admin)):
    body = await request.json()
    b = broadcast_store.update_broadcast(bid, body)
    if not b:
        raise HTTPException(status_code=404, detail="not found")
    if b.get("enabled"):
        _add_broadcast_job(b)
    else:
        _remove_broadcast_job(bid)
    return b
