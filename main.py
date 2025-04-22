import os
import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError

# 追加：Google Sheets ライブラリ
import gspread
from google.oauth2.service_account import Credentials

# --- Google Sheets 認証設定（ローカルテスト用 credentials.json から） ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
gc = gspread.authorize(creds)
SPREADSHEET_NAME = "LINE通知ログ"
worksheet = gc.open(SPREADSHEET_NAME).sheet1

# --- Flask & LINE Bot 設定 ---
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler     = WebhookHandler(os.getenv("CHANNEL_SECRET"))

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body      = request.get_data(as_text=True)
    print("Received body:", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text    = event.message.text
    user_id = event.source.user_id
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"Received message: {text}")

    # ① スプレッドシートに書き込み
    worksheet.append_row([timestamp, user_id, text])

    # ② LINE 返信
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="スプレッドシートに書き込んだで！")
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
