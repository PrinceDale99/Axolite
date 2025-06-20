import subprocess
import json

def search_youtube_videos(query):
    cmd = ["yt-dlp", f"ytsearch10:{query}", "--print-json"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    raw_output = result.stdout.strip()
    print("yt-dlp raw output:", raw_output)  # Debug: show raw yt-dlp output

    videos = []
    for line in raw_output.split('\n'):
        line = line.strip()
        if not line or not line.startswith('{'):
            continue  # Skip empty lines or non-JSON lines
        try:
            data = json.loads(line)
            videos.append({
                "title": data.get("title"),
                "videoId": data.get("id"),
                "duration": data.get("duration"),
                "channel": data.get("channel"),
                "thumbnail": data.get("thumbnail")
            })
        except json.JSONDecodeError:
            print("⚠️ Failed to decode line:", line)
            continue  # Skip lines that fail to parse

    return videos
