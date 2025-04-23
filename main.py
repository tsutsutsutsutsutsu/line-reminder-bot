import os
import json
import re
import uuid
import pytz
import datetime
from flask import Flask, request

from google.oauth2.service_account import Credentials
import gspread

from linebot.v3.webhooks.models import CallbackRequest, MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.messaging.models import TextMessage

# Google Sheets setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
cred_dict = json.loads(cred_json)
creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc = gspread.authorize(creds)
worksheet = gc.open("LINE通知ログ").sheet1

# LINE bot setup
configuration = Configuration(access_token=os.getenv("CHANNEL_ACCESS_TOKEN"))

app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    body = request.get_json()
    events = CallbackRequest(**body).events

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            handle_message(event)

    return "OK"

def handle_message(event):
    user_message = event.message.text
    user_id = event.source.user_id
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
