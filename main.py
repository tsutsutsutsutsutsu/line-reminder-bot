import os
import json
import time
import schedule
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets 認証
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_info(
    json.loads(os.getenv("GOOGLE_CREDENTIALS")), scopes=SCOPES
)
gc = gspread.authorize(creds)
SPREADSHEET_NAME = 'LINE通知ログ'
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# LINE Bot
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

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

    # 通知ログをシートに追加
    worksheet.append_row([user_message, now, user_id])

    # 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"メッセージを受け取りました：{user_message}")
    )

# 定期タスク
def run_scheduler():
    schedule.every(1).minutes.do(lambda: None)  # 実際の通知処理がある場合に追加
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
