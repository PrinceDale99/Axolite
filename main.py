# AXIOLITE: Fast, Private Music Downloader Backend v2
import os, uuid, json, subprocess, threading, requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mutagen.id3 import ID3, APIC, TIT2, TALB, TPE1, ID3NoHeaderError
from mutagen.mp3 import MP3

# === CONFIG ===
DOWNLOAD_DIR = "downloads/mp3"
QUEUE_FILE = "queue.json"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# === INIT ===
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === HELPERS ===
def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []

def save_queue(data):
    with open(QUEUE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# === MODELS ===
class DownloadRequest(BaseModel):
    query: str
    quality: str = "320"

# === ROUTES ===
@app.post("/download-audio")
async def download_audio(req: DownloadRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    queue = load_queue()

    # Fetch metadata & yt URL
    meta = get_metadata(req.query)
    if not meta or not meta.get("video_url"):
        raise HTTPException(404, "No track found")

    file_name = f"{job_id}.mp3"
    file_path = os.path.join(DOWNLOAD_DIR, file_name)

    # Append to queue
    queue.append({
        "id": job_id,
        "status": "queued",
        "title": meta["title"],
        "artist": meta["artist"],
        "album": meta["album"],
        "thumbnail": meta["thumbnail"],
        "file_path": file_path
    })
    save_queue(queue)

    background_tasks.add_task(run_download, job_id, meta["video_url"], req.quality, file_path, meta)
    return {"id": job_id}

@app.get("/download-queue")
async def get_queue():
    return load_queue()

@app.get("/download-file/{item_id}")
async def download_file(item_id: str):
    queue = load_queue()
    for item in queue:
        if item["id"] == item_id and item["status"] == "completed":
            return FileResponse(item["file_path"], filename=f"{item['title']} - {item['artist']}.mp3")
    raise HTTPException(404, "Not ready yet")

# === CORE: Metadata Search ===
def get_metadata(query):
    try:
        cmd = ["yt-dlp", f"ytsearch1:{query}", "--print-json"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        j = json.loads(res.stdout.strip().split('\n')[0])
        return {
            "title": j.get("title"),
            "artist": j.get("artist") or j.get("uploader"),
            "album": j.get("album") or "Single",
            "thumbnail": j.get("thumbnail"),
            "video_url": f"https://www.youtube.com/watch?v={j.get('id')}"
        }
    except Exception as e:
        print("Metadata error:", e)
        return {}

# === CORE: Download + Tag ===
def run_download(job_id, url, quality, file_path, meta):
    queue = load_queue()
    item = next((x for x in queue if x["id"] == job_id), None)
    if not item:
        return

    try:
        item["status"] = "downloading"
        save_queue(queue)

        # temp path
        tmp = file_path.replace(".mp3", ".webm")

        cmd = [
            "yt-dlp",
            "-f", "bestaudio",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", quality,
            "-o", tmp,
            url
        ]
        subprocess.run(cmd, check=True)

        if os.path.exists(tmp):
            os.rename(tmp, file_path)

        embed_tags(file_path, meta)
        item["status"] = "completed"
    except Exception as e:
        print("DL error:", e)
        item["status"] = "failed"
    finally:
        save_queue(queue)

# === TAGGING ===
def embed_tags(mp3_file, meta):
    try:
        audio = ID3(mp3_file)
    except ID3NoHeaderError:
        audio = ID3()

    audio.add(TIT2(encoding=3, text=meta["title"]))
    audio.add(TPE1(encoding=3, text=meta["artist"]))
    audio.add(TALB(encoding=3, text=meta["album"]))

    # Album Art
    try:
        img_data = requests.get(meta["thumbnail"], timeout=10).content
        audio.add(APIC(
            encoding=3,
            mime="image/jpeg",
            type=3,
            desc=u"Cover",
            data=img_data
        ))
    except Exception as e:
        print("Art error:", e)

    audio.save(mp3_file)
