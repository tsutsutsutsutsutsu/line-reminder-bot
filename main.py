import os
import json
import base64
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from google.oauth2.service_account import Credentials
import gspread

# --- Google Sheets 認証 ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
cred_json = base64.b64decode(cred_b64).decode("utf-8")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_NAME = 'LINE通知ログ'
sheet = gc.open(SPREADSHEET_NAME).sheet1

# --- LINE Bot 設定 ---
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# --- Flask アプリ ---
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

    # スプレッドシートにメッセージ保存
    sheet.append_row([str(datetime.datetime.now()), user_message, '', user_id])
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="メッセージ受け取りました"))

# --- 確認用：手動でリマインド実行 ---
@app.route("/run-reminder", methods=["GET"])
def run_reminder():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = sheet.get_all_records()
    count = 0

    for row in rows:
        if row.get("リマインド時刻") == now:
            user_id = row.get("ユーザーID")
            message = row.get("メッセージ")
            if user_id and message:
                line_bot_api.push_message(user_id, TextSendMessage(text=message))
                count += 1

    return f"{count} 件のリマインドを送信しました", 200

# --- アプリ起動 ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
