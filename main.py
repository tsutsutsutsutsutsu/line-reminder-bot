import os
import json
import time
import base64
import uuid
import re
import pytz
import datetime
from flask import Flask, request, abort

from google.oauth2.service_account import Credentials
import gspread

from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError

# ─────────────── Google Sheets 認証設定 ───────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

cred_dict = None

# 1) 環境変数 GOOG﻿LE_CREDENTIALS_B64 から読み込む
cred_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
if cred_b64:
    try:
        cred_json = base64.b64decode(cred_b64).decode("utf-8")
        cred_dict = json.loads(cred_json)
    except Exception as e:
        raise RuntimeError(f"GOOGLE_CREDENTIALS_B64 のデコードに失敗しました: {e}")
# 2) ローカルの credentials.json を参照（開発時用フォールバック）
elif os.path.isfile("credentials.json"):
    with open("credentials.json", "r", encoding="utf-8") as f:
        cred_dict = json.load(f)
else:
    raise EnvironmentError(
        "サービスアカウント認証情報が見つかりません。"
        " 環境変数 GOOGLE_CREDENTIALS_B64 を設定するか、"
        "credentials.json をプロジェクトルートに置いてください。"
    )

creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
gc    = gspread.authorize(creds)
sheet = gc.open("LINE通知ログ").sheet1

# ─────────────── LINE Bot 設定 ───────────────
LINE_TOKEN  = os.getenv("CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("CHANNEL_SECRET")

if not LINE_TOKEN or not LINE_SECRET:
    raise EnvironmentError("CHANNEL_ACCESS_TOKEN と CHANNEL_SECRET を環境変数に設定してください。")

line_bot_api = LineBotApi(LINE_TOKEN)
handler      = WebhookHandler(LINE_SECRET)

# ─────────────── Flask アプリ ───────────────
app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    # LINE からの webhook を検証してハンドラに渡す
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # ユーザーからのテキストを受け取ってシートに記録
    text    = event.message.text
    user_id = event.source.user_id
    now_str = datetime.datetime.now(pytz.timezone("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M")

    # 本文中の「YYYY-MM-DD hh:mm」を正規表現で抽出
    m = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", text)
    remind_time = m.group() if m else ""

    # 一意な行IDと状態を生成
    row_id = str(uuid.uuid4())[:8]
    status = "未送信"

    # シートに追加（ID, 本文, リマインド時刻, ユーザーID, 状態）
    sheet.append_row([row_id, text, remind_time, user_id, status])

    # 返信メッセージ
    if remind_time:
        reply = "予約を受け付けました。"
    else:
        reply = f"メッセージを受け取りました：{text}"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

@app.route("/run-reminder")
def run_reminder():
    # 現在時刻を取得
    now_dt = datetime.datetime.now(pytz.timezone("Asia/Tokyo"))

    # シートの全行を取得
    rows    = sheet.get_all_values()
    headers = rows[0]
    data    = rows[1:]

    # 列インデックスを決定
    idx_time   = headers.index("リマインド時刻")
    idx_user   = headers.index("ユーザーID")
    idx_msg    = headers.index("メッセージ")
    idx_status = headers.index("状態")

    # 各行をチェックして、送信すべきなら LINE Push を実行
    for i, row in enumerate(data, start=2):
        try:
            remind_str = row[idx_time]
            user_id    = row[idx_user]
            msg        = row[idx_msg]
            status     = row[idx_status]

            # 既に送信済み／時刻なし はスキップ
            if status == "送信済み" or not remind_str:
                continue

            # 日時比較
            remind_dt = datetime.datetime.strptime(remind_str, "%Y-%m-%d %H:%M")
            remind_dt = pytz.timezone("Asia/Tokyo").localize(remind_dt)

            if remind_dt <= now_dt:
                # プッシュ通知
                line_bot_api.push_message(
                    to=user_id,
                    messages=[TextSendMessage(text=f"⏰ リマインド：{msg}")]
                )
                # 状態を「送信済み」に更新
                sheet.update_cell(i, idx_status + 1, "送信済み")

        except Exception as e:
            print(f"[ERROR] 行 {i}: {e}")

    return "リマインド実行しました"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
