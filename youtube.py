import subprocess
import json

def search_youtube_videos(query):
    cmd = ["yt-dlp", f"ytsearch10:{query}", "--print-json"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = result.stdout.strip().split('\n')
    videos = []
    for line in lines:
        data = json.loads(line)
        videos.append({
            "title": data.get("title"),
            "videoId": data.get("id"),
            "duration": data.get("duration"),
            "channel": data.get("channel"),
            "thumbnail": data.get("thumbnail")
        })
    return videos
