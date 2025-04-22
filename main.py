import os
import json
import time
import base64
import schedule
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# 認証
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
cred_json = base64.b64decode(cred_b64).decode("utf-8")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_NAME = 'LINE通知ログ'
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# LINE
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# Flask
app = Flask(__name__)
reminders = []

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row_id = str(int(time.time()))  # UNIX時間をIDに

    # スプレッドシートに記録
    worksheet.append_row([row_id, user_message, "", user_id, now])

    if "月" in user_message and "日" in user_message and "時" in user_message:
        reply_text = "予約を受け付けました。"
    else:
        reply_text = f"メッセージを受け取りました：{user_message}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@app.route("/run-reminder", methods=["GET"])
def run_reminder():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = worksheet.get_all_values()

    for row in rows[1:]:  # ヘッダー除外
        if len(row) < 5:
            continue
        row_id = row[0]
        message = row[1]
        remind_time = row[2]
        user_id = row[3]  # ← ここ修正
        already_sent = row[4] if len(row) > 4 else ""

        if remind_time and now >= remind_time and already_sent != "SENT":
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=f"⏰ リマインド: {message}"))
                row_index = rows.index(row) + 1
                worksheet.update_cell(row_index + 1, 5, "SENT")
            except Exception as e:
                print(f"通知エラー: {e}")

    return "リマインド実行しました"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
