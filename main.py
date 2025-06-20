# Complete and enhanced version of Axiolite backend - Single File (main.py)

import os
import uuid
import json
import subprocess
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
from fastapi.routing import APIRouter
from typing import Optional

# ==== CONFIG ====
BASE_DIR = "downloads/mp3"
QUEUE_FILE = "queue.json"
os.makedirs(BASE_DIR, exist_ok=True)

app = FastAPI(title="Axiolite Enhanced Backend", version="v1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter(prefix="/api/v1")

# ==== MODELS ====
class DownloadRequest(BaseModel):
    query: str
    quality: str = "320"  # 128, 192, 320, best
    source: Optional[str] = "auto"  # youtube, deezer, soundcloud, or auto


# ==== UTILS ====
def load_queue():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r") as f:
        return json.load(f)

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

def embed_metadata(mp3_path, metadata):
    try:
        try:
            tags = ID3(mp3_path)
        except ID3NoHeaderError:
            tags = ID3()

        tags.add(TIT2(encoding=3, text=metadata.get("title", "Unknown")))
        tags.add(TPE1(encoding=3, text=metadata.get("artist", "Unknown")))
        tags.add(TALB(encoding=3, text=metadata.get("album", "Unknown")))

        img_url = metadata.get("thumbnail")
        if img_url:
            img = requests.get(img_url, timeout=10).content
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img))
        tags.save(mp3_path)
    except Exception as e:
        print("[Metadata Embed Error]", e)

def fetch_metadata_from_yt(query: str):
    try:
        cmd = ["yt-dlp", f"ytsearch1:{query}", "--print-json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        line = result.stdout.strip().split('\n')[0]
        data = json.loads(line)
        return {
            "title": data.get("title"),
            "artist": data.get("artist") or data.get("uploader") or "Unknown",
            "album": data.get("album") or "Single",
            "thumbnail": data.get("thumbnail"),
            "video_url": f"https://www.youtube.com/watch?v={data.get('id')}"
        }
    except Exception as e:
        print("[YT Metadata Fetch Error]", e)
        return {}

def fetch_metadata_from_deezer(query: str):
    try:
        url = f"https://api.deezer.com/search?q={query}"
        res = requests.get(url, timeout=10)
        track = res.json()["data"][0]
        return {
            "title": track["title"],
            "artist": track["artist"]["name"],
            "album": track["album"]["title"],
            "thumbnail": track["album"]["cover_big"],
            "video_url": f"{track['link']}"
        }
    except Exception as e:
        print("[Deezer Metadata Error]", e)
        return {}

def fetch_metadata(query: str, source: str = "auto"):
    if source == "youtube":
        return fetch_metadata_from_yt(query)
    elif source == "deezer":
        return fetch_metadata_from_deezer(query)
    elif source == "soundcloud":
        return {"title": query, "artist": "Unknown", "album": "SoundCloud", "thumbnail": "", "video_url": query}
    else:  # auto
        metadata = fetch_metadata_from_deezer(query)
        if metadata:
            return metadata
        return fetch_metadata_from_yt(query)

def run_download(job_id, url, quality, file_path, metadata):
    queue = load_queue()
    item = next((x for x in queue if x["id"] == job_id), None)
    if not item:
        return

    try:
        item["status"] = "downloading"
        save_queue(queue)

        temp_path = file_path.replace(".mp3", ".webm")

        subprocess.run([
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", quality,
            "-o", temp_path,
            url
        ], check=True)

        if os.path.exists(temp_path):
            os.rename(temp_path, file_path)
            embed_metadata(file_path, metadata)
            item["status"] = "completed"
        else:
            item["status"] = "failed"
    except Exception as e:
        print("[Download Error]", e)
        item["status"] = "failed"
    finally:
        save_queue(queue)


# ==== ROUTES ====

@router.post("/downloads/audio")
def queue_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    metadata = fetch_metadata(request.query, request.source)
    if not metadata.get("video_url"):
        raise HTTPException(status_code=404, detail="Track not found.")

    job_id = str(uuid.uuid4())
    mp3_path = os.path.join(BASE_DIR, f"{job_id}.mp3")

    queue = load_queue()
    queue.append({
        "id": job_id,
        "title": metadata["title"],
        "artist": metadata["artist"],
        "album": metadata["album"],
        "thumbnail": metadata["thumbnail"],
        "status": "queued",
        "file_path": mp3_path
    })
    save_queue(queue)

    background_tasks.add_task(run_download, job_id, metadata["video_url"], request.quality, mp3_path, metadata)

    return {"id": job_id, "status": "queued"}

@router.get("/downloads/queue")
def get_download_queue():
    return load_queue()

@router.get("/downloads/file/{item_id}")
def serve_mp3(item_id: str):
    queue = load_queue()
    item = next((x for x in queue if x["id"] == item_id and x["status"] == "completed"), None)
    if not item:
        raise HTTPException(status_code=404, detail="File not ready.")
    return FileResponse(path=item["file_path"], filename=f"{item['title']} - {item['artist']}.mp3", media_type="audio/mpeg")

@router.post("/search/youtube")
def search_youtube(query: str = Query(...)):
    try:
        cmd = ["yt-dlp", f"ytsearch10:{query}", "--print-json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        lines = result.stdout.strip().split("\n")
        results = []
        for line in lines:
            if line.strip():
                data = json.loads(line)
                results.append({
                    "title": data.get("title"),
                    "videoId": data.get("id"),
                    "duration": data.get("duration"),
                    "channel": data.get("channel"),
                    "thumbnail": data.get("thumbnail")
                })
        return {"results": results}
    except Exception as e:
        print("[Search Error]", e)
        raise HTTPException(status_code=500, detail="Search failed")


# === Register ===
app.include_router(router)

