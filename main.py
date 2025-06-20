# AXIOLITE v2 - Clean, Prefixed, and Production-Ready Backend
import os, uuid, json, subprocess, requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError
from fastapi.routing import APIRouter

# === CONFIG ===
PREFIX = "/api/v1"
DOWNLOAD_DIR = "downloads/mp3"
QUEUE_FILE = "queue.json"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# === FASTAPI SETUP ===
app = FastAPI(title="Axiolite Backend", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
router = APIRouter(prefix=PREFIX)

# === MODELS ===
class DownloadRequest(BaseModel):
    query: str
    quality: str = "320"

# === UTILS ===
def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return []

def save_queue(data):
    with open(QUEUE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_metadata(query):
    try:
        result = subprocess.run(["yt-dlp", f"ytsearch1:{query}", "--print-json"], capture_output=True, text=True)
        j = json.loads(result.stdout.strip().split("\n")[0])
        return {
            "title": j.get("title"),
            "artist": j.get("artist") or j.get("uploader"),
            "album": j.get("album") or "Single",
            "thumbnail": j.get("thumbnail"),
            "video_url": f"https://www.youtube.com/watch?v={j.get('id')}"
        }
    except Exception as e:
        print("[metadata error]", e)
        return {}

def embed_metadata(file_path, meta):
    try:
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            tags = ID3()

        tags.add(TIT2(encoding=3, text=meta["title"]))
        tags.add(TPE1(encoding=3, text=meta["artist"]))
        tags.add(TALB(encoding=3, text=meta["album"]))

        img = requests.get(meta["thumbnail"], timeout=10).content
        tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=img))
        tags.save(file_path)
    except Exception as e:
        print("[tag error]", e)

def run_download(job_id, url, quality, file_path, meta):
    queue = load_queue()
    item = next((i for i in queue if i["id"] == job_id), None)
    if not item:
        return

    try:
        item["status"] = "downloading"
        save_queue(queue)

        tmp = file_path.replace(".mp3", ".webm")
        subprocess.run([
            "yt-dlp", "-f", "bestaudio", "--extract-audio",
            "--audio-format", "mp3", "--audio-quality", quality,
            "-o", tmp, url
        ], check=True)

        if os.path.exists(tmp):
            os.rename(tmp, file_path)
            embed_metadata(file_path, meta)
            item["status"] = "completed"
        else:
            item["status"] = "failed"
    except Exception as e:
        print("[dl error]", e)
        item["status"] = "failed"
    finally:
        save_queue(queue)

# === ROUTES ===
@router.post("/downloads/audio")
def queue_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    meta = get_metadata(req.query)
    if not meta or not meta.get("video_url"):
        raise HTTPException(404, "Track not found")

    job_id = str(uuid.uuid4())
    file_path = os.path.join(DOWNLOAD_DIR, f"{job_id}.mp3")
    queue = load_queue()
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

@router.get("/downloads/queue")
def get_queue():
    return load_queue()

@router.get("/downloads/file/{item_id}")
def serve_file(item_id: str):
    queue = load_queue()
    item = next((i for i in queue if i["id"] == item_id), None)
    if not item or item["status"] != "completed":
        raise HTTPException(404, "File not found")
    return FileResponse(item["file_path"], filename=f"{item['title']} - {item['artist']}.mp3")

# === REGISTER ROUTER ===
app.include_router(router)
