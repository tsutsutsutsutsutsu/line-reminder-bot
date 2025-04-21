from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import threading
import time
import schedule

# .envから環境変数読み込み
load_dotenv()

# Flask & LINE bot初期設定
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("CHANNEL_SECRET"))

# メモリ上にリマインダー情報を保存
reminders = []

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
            # 日付・時刻の抽出
            month = int(user_msg.split("月")[0])
            day = int(user_msg.split("月")[1].split("日")[0])
            hour = int(user_msg.split("日")[1].split("時")[0])
            now = datetime.now()
            year = now.year
            target_time = datetime(year, month, day, hour, 0)

            # ✅ 通常は「target_time - timedelta(days=1)」
            # ✅ 今はテスト用に「今から1分後」に設定
            remind_time = datetime.now() + timedelta(minutes=1)

            reminders.append({
                "user_id": user_id,
                "message": f"（テスト）予約通知です：{month}月{day}日 {hour}時",
                "remind_time": remind_time.replace(second=0, microsecond=0)
            })

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

# リマインダーを定期的にチェックして通知
def check_reminders():
    now = datetime.now().replace(second=0, microsecond=0)
    for reminder in reminders[:]:
        if reminder["remind_time"] == now:
            line_bot_api.push_message(
                reminder["user_id"],
                TextSendMessage(text=reminder["message"])
            )
            reminders.remove(reminder)

# 定期実行スレッド
def run_scheduler():
    schedule.every(1).minutes.do(check_reminders)
    while True:
        schedule.run_pending()
        time.sleep(1)

# スレッド起動
threading.Thread(target=run_scheduler, daemon=True).start()

# Flask起動
if __name__ == "__main__":
    app.run(port=5000)
