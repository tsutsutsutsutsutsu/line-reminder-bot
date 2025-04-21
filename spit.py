from moviepy.editor import VideoFileClip
import math
import os

def split_video_by_seconds(input_path, output_dir, interval_seconds=7):
    # 動画を読み込む
    video = VideoFileClip(input_path)
    duration = video.duration
    basename = os.path.splitext(os.path.basename(input_path))[0]

    # 出力先フォルダがなければ作成
    os.makedirs(output_dir, exist_ok=True)

    # 7秒ごとに分割
    num_clips = math.ceil(duration / interval_seconds)
    for i in range(num_clips):
        start = i * interval_seconds
        end = min((i + 1) * interval_seconds, duration)
        subclip = video.subclip(start, end)
        output_path = os.path.join(output_dir, f"{basename}_part{i+1}.mp4")
        subclip.write_videofile(output_path, codec="libx264", audio_codec="aac")

    print("✅ 分割完了！")

# 実行例
split_video_by_seconds("input.mp4", "output_clips", interval_seconds=7)
