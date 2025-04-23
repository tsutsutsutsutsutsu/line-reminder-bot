import os
import json
import time
import base64
import uuid
import re
import pytz
import datetime
from flask import Flask, request, abort
import gspread
from google.oauth2.service_account import Credentials

# LINE Bot v3 SDK
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhook.models import MessageEvent, TextMessageContent
from linebot.v3.messaging import MessagingApi, TextMessage
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.configuration import Configuration

# 認証
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
cred_json = base64.b64decode(cred_b64).decode("utf-8")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
worksheet = gc.open("LINE通知ログ").sheet1

# LINE設定
configuration = Configuration(access_token=os.getenv("CHANNEL_ACCESS_TOKEN"))
line_bot_api = MessagingApi(configuration)
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# Flaskアプリ
app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent)
def handle_message(event):
    if not isinstance(event.message, TextMessageContent):
        return
    user_message = event.message.text
    user_id = event.source.user_id
    now = datetime.datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")

    # メッセージからリマインド時刻抽出
    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", user_message)
    remind_time = match.group() if match else ""
    row_id = str(uuid.uuid4())[:8]

    # 行追加: ID | メッセージ | リマインド時刻 | ユーザーID | 状態
    worksheet.append_row([row_id, user_message, remind_time, user_id, "未送信"])

    reply_text = "予約を受け付けました。" if remind_time else f"メッセージを受け取りました：{user_message}"
    line_bot_api.reply_message(
        event.reply_token,
        [TextMessage(text=reply_text)]
    )

@app.route("/run-reminder")
def run_reminder():
    now = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))
    rows = worksheet.get_all_values()
    headers = rows[0]
    data = rows[1:]

    for i, row in enumerate(data, start=2):
        try:
            row_id = row[0]
            message = row[1]
            remind_time_str = row[2]
            user_id = row[3]
            status = row[4] if len(row) > 4 else ""

            if status != "未送信":
                continue

            if remind_time_str:
                remind_time = datetime.datetime.strptime(remind_time_str, "%Y-%m-%d %H:%M")
                remind_time = pytz.timezone("Asia/Tokyo").localize(remind_time)

                if remind_time <= now:
                    line_bot_api.push_message(user_id, [TextMessage(text=f"⏰ リマインド：{message}")])
                    worksheet.update_cell(i, 5, "送信済み")
        except Exception as e:
            print(f"[ERROR] Row {i}: {e}")

    return "リマインド実行しました"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
