import os
import json
import time
import base64
import schedule
import datetime
import uuid
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# Google Sheets 認証 (Base64エンコード環境変数から読み込み)
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

    # 正規表現でリマインド内容と時刻を取得
    import re
    match = re.search(r"(.*?)(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", user_message)
    if match:
        message = match.group(1).strip()
        remind_time = match.group(2).strip()
        row_id = str(uuid.uuid4())[:8]

        # 正しい順で追加 → C列にリマインド時刻
        worksheet.append_row([row_id, message, remind_time, user_id, now])
        reply_text = f"リマインドを登録しました（{remind_time}）"
    else:
        reply_text = "メッセージを受け取りました：{}".format(user_message)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@app.route("/run-reminder")
def run_reminder():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = worksheet.get_all_records()

    for row in rows:
        remind_time = row.get("リマインド時刻")
        user_id = row.get("ユーザーID")
        message = row.get("メッセージ")
        if remind_time == now and user_id and message:
            line_bot_api.push_message(user_id, TextSendMessage(text=f"⏰ リマインド：{message}"))

    return "リマインド実行しました"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
