import os
import json
import subprocess
import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

QUEUE_FILE = "queue.json"
DOWNLOADS_DIR = "downloads"

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def load_queue():
    with open(QUEUE_FILE, "r") as f:
        return json.load(f)

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

def download_audio_task():
    queue = load_queue()
    for item in queue:
        if item["status"] == "pending":
            try:
                item["status"] = "downloading"
                save_queue(queue)

                file_name = f"{item['id']}.{item['format']}"
                file_path = os.path.join(DOWNLOADS_DIR, item['format'], file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                cmd = [
                    "yt-dlp",
                    "-x",
                    f"--audio-format", item['format'],
                    f"--audio-quality", item['quality'],
                    "-o", file_path,
                    item['youtube_url']
                ]
                subprocess.run(cmd, check=True)

                if os.path.exists(file_path):
                    audio = EasyID3(file_path)
                    audio["title"] = item.get("title", "")
                    audio["artist"] = item.get("artist", "")
                    audio["album"] = item.get("album", "")
                    audio.save()

                    if item.get("album_art_url"):
                        art_data = requests.get(item["album_art_url"]).content
                        audio = ID3(file_path)
                        audio["APIC"] = APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,
                            desc=u"Cover",
                            data=art_data
                        )
                        audio.save()

                item["status"] = "completed"
                item["file_path"] = file_path
                save_queue(queue)

            except Exception as e:
                item["status"] = "failed"
                save_queue(queue)
