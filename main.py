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

# Google Sheets 認証 (Base64エンコード環境変数から読み込み)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
cred_json = base64.b64decode(cred_b64).decode("utf-8")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_NAME = 'LINE通知ログ'
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# LINE Bot 設定
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# Flaskアプリ
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

    # スプレッドシートにログ追加
    worksheet.append_row([user_message, now, user_id])

    # 簡易的に予約文を認識
    if "月" in user_message and "日" in user_message and "時" in user_message:
        reply_text = "予約を受け付けました。"
    else:
        reply_text = "メッセージを受け取りました：{}".format(user_message)

    # LINE返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# スケジューラー（例：定期実行したいことがあればここに）
def run_scheduler():
    schedule.every(1).minutes.do(lambda: None)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
