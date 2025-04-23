import os
import json
import base64
import datetime
import pytz
import re
import uuid

from flask import Flask, request, abort

import gspread
from google.oauth2.service_account import Credentials

from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhooks.models import TextMessage
from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.webhooks import WebhookParser

# Flask アプリ
app = Flask(__name__)

# 環境変数からLINEの設定
channel_secret = os.getenv("CHANNEL_SECRET")
channel_access_token = os.getenv("CHANNEL_ACCESS_TOKEN")

if not channel_secret or not channel_access_token:
    raise ValueError("CHANNEL_SECRETとCHANNEL_ACCESS_TOKENを環境変数に設定してください")

configuration = Configuration(access_token=channel_access_token)
parser = WebhookParser(channel_secret)

# Google Sheets 認証
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
cred_json = base64.b64decode(os.getenv("GOOGLE_CREDENTIALS_B64")).decode("utf-8")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
worksheet = gc.open("LINE通知ログ").sheet1

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    print(f"[INFO] Webhook body: {body}")

    try:
        events = parser.parse(body, signature)
    except Exception as e:
        print(f"[ERROR] Webhook parse error: {e}")
        abort(400)

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_message(event)

    return "OK"

def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text
    now = datetime.datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")

    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", user_message)
    remind_time = match.group() if match else ""
    row_id = str(uuid.uuid4())[:8]
    status = "未送信"

    worksheet.append_row([row_id, user_message, remind_time, user_id, status])

    reply_text = "予約を受け付けました。" if remind_time else f"メッセージを受け取りました：{user_message}"
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )

@app.route("/run-reminder")
def run_reminder():
    now_dt = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))
    rows = worksheet.get_all_values()
    headers = rows[0]
    data = rows[1:]

    remind_col = headers.index("リマインド時刻")
    user_id_col = headers.index("ユーザーID")
    msg_col = headers.index("メッセージ")
    status_col = headers.index("状態")

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)

        for i, row in enumerate(data, start=2):
            try:
                remind_time_str = row[remind_col]
                user_id = row[user_id_col]
                message = row[msg_col]
                status = row[status_col]

                if status == "送信済み":
                    continue

                if remind_time_str:
                    remind_dt = datetime.datetime.strptime(remind_time_str, "%Y-%m-%d %H:%M")
                    remind_dt = pytz.timezone("Asia/Tokyo").localize(remind_dt)

                    if remind_dt <= now_dt:
                        messaging_api.push_message(
                            to=user_id,
                            messages=[TextMessage(text=f"⏰ リマインド：{message}")]
                        )
                        worksheet.update_cell(i, status_col + 1, "送信済み")
            except Exception as e:
                print(f"[ERROR] Row {i}: {e}")

    return "リマインド実行しました"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
