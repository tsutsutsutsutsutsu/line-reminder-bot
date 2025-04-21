from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
from datetime import datetime, timedelta
import os
import threading
import time
import schedule
import json

# .envから環境変数を読み込む
load_dotenv()

# FlaskとLINE bot設定
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# リマインダー情報の初期化
reminders = []

# ✅ メッセージ生成用の関数
def create_message(month, day, hour):
    return f"（テスト）予約通知です：{month}月{day}日 {hour}時"

# JSONファイルからリマインダーを読み込み（あれば）
if os.path.exists("reminders.json"):
    with open("reminders.json", "r") as f:
        raw_data = json.load(f)
        for r in raw_data:
            r["remind_time"] = datetime.strptime(r["remind_time"], "%Y-%m-%d %H:%M:%S")
            reminders.append(r)
    print("🔁 保存されたリマインダーを復元しました")

# reminder保存関数
def save_reminders():
    save_data = []
    for r in reminders:
        save_data.append({
            "user_id": r["user_id"],
            "message": r["message"],
            "remind_time": r["remind_time"].strftime("%Y-%m-%d %H:%M:%S")
        })
    with open("reminders.json", "w") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print("💾 reminders.json を保存しました")

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
    user_msg = event.message.text
    user_id = event.source.user_id

    try:
        if "月" in user_msg and "日" in user_msg and "時" in user_msg:
            month = int(user_msg.split("月")[0])
            day = int(user_msg.split("月")[1].split("日")[0])
            hour = int(user_msg.split("日")[1].split("時")[0])
            now = datetime.now()
            year = now.year
            target_time = datetime(year, month, day, hour, 0)

            remind_time = datetime.now() + timedelta(minutes=1)

            reminder = {
                "user_id": user_id,
                "message": create_message(month, day, hour),
                "remind_time": remind_time.replace(second=0, microsecond=0)
            }

            reminders.append(reminder)
            save_reminders()

            print("✅ 新規リマインダー登録：", reminder)

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="予約を受け付けました。1分後に通知します。")
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="形式が正しくありません（例: 4月20日14時に予約）")
            )
    except Exception as e:
        print("エラー:", e)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="エラーが発生しました。もう一度試してください。")
        )

def check_reminders():
    now = datetime.now().replace(second=0, microsecond=0)
    for reminder in reminders[:]:
        if reminder["remind_time"] == now:
            line_bot_api.push_message(
                reminder["user_id"],
                TextSendMessage(text=reminder["message"])
            )
            print(f"📤 通知送信：{reminder['message']} → ユーザーID: {reminder['user_id']}")
            reminders.remove(reminder)
            save_reminders()

def run_scheduler():
    schedule.every(1).minutes.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_scheduler, daemon=True).start()

# ✅ Railwayで動くようにポートは環境変数から取得！
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
