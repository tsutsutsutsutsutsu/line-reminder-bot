import os
import json
import time
import base64
import uuid
import re
import pytz
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets 認証（Base64エンコードされた環境変数）
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

# LINE Bot 設定
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# Flask アプリ
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    now = datetime.datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")

    # メッセージからリマインド時刻を抽出
    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", user_message)
    remind_time = match.group() if match else ""

    row_id = str(uuid.uuid4())[:8]

    worksheet.append_row([row_id, user_message, remind_time, user_id])
    reply_text = "予約を受け付けました。" if remind_time else f"メッセージを受け取りました：{user_message}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@app.route("/run-reminder")
def run_reminder():
    now = datetime.datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")

    rows = worksheet.get_all_values()
    headers = rows[0]
    data = rows[1:]

    for i, row in enumerate(data, start=2):
        try:
            row_id = row[0]
            message = row[1]
            remind_time = row[2]
            user_id = row[3]

            if remind_time and remind_time <= now:
                line_bot_api.push_message(user_id, TextSendMessage(text=f"⏰ リマインド：{message}"))
                worksheet.update_cell(i, 3, "")  # C列を空にする
        except Exception as e:
            print(f"[ERROR] Row {i}: {e}")

    return "リマインド実行しました"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
