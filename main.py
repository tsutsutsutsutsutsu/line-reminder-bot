import os
import json
import time
import base64
import schedule
import datetime
import threading
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets 認証 (Base64エンコード環境変数から読み込み)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
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

    # リマインド時刻を仮に10分後に設定（本番では解析や入力を促す）
    reminder_time = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")

    # スプレッドシートにログ追加
    worksheet.append_row([user_message, now, user_id, reminder_time])

    reply_text = "メッセージを受け取りました：{}".format(user_message)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

# リマインド送信処理
def check_reminders():
    while True:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        records = worksheet.get_all_records()
        for i, row in enumerate(records):
            reminder_time = row.get("リマインド時刻")
            user_id = row.get("ユーザーID")
            message = row.get("メッセージ")
            if reminder_time == now:
                try:
                    line_bot_api.push_message(user_id, TextSendMessage(text=f"⏰ リマインド：{message}"))
                    worksheet.update_cell(i+2, 4, "")  # D列 (リマインド時刻) を空にして再送防止
                except Exception as e:
                    print("送信エラー:", e)
        time.sleep(60)  # 1分おきにチェック

if __name__ == "__main__":
    # スレッドでリマインド処理を開始
    reminder_thread = threading.Thread(target=check_reminders, daemon=True)
    reminder_thread.start()

    # Flask起動
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
