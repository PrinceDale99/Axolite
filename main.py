from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
import subprocess
import threading
import os
import json
import shutil
import requests
from downloader import download_audio_task
from spotify import get_spotify_playlist
from youtube import search_youtube_videos

app = FastAPI()

# CORS setup
FRONTEND_BASE_URL = "https://your-firebase-app.web.app"  # Replace later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", FRONTEND_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QUEUE_FILE = "queue.json"
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, "r") as f:
            return json.load(f)
    return []

def save_queue(queue):
    with open(QUEUE_FILE, "w") as f:
        json.dump(queue, f, indent=2)

class SearchRequest(BaseModel):
    query: str

class DownloadRequest(BaseModel):
    youtube_url: str
    format: str
    quality: str
    title: str = ""
    artist: str = ""
    album: str = ""
    album_art_url: str = ""

class PlaylistImportRequest(BaseModel):
    spotify_playlist_url: str

@app.post("/search-youtube")
async def search_youtube(req: SearchRequest):
    return search_youtube_videos(req.query)

@app.post("/download-audio")
async def download_audio(req: DownloadRequest):
    queue = load_queue()
    job_id = str(uuid4())
    queue.append({
        "id": job_id,
        **req.dict(),
        "status": "pending",
        "progress": 0,
        "file_path": ""
    })
    save_queue(queue)
    return {"id": job_id, "message": "Download queued"}

@app.post("/import-playlist")
async def import_playlist(req: PlaylistImportRequest):
    tracks = get_spotify_playlist(req.spotify_playlist_url)
    imported = 0
    for track in tracks:
        results = search_youtube_videos(f"{track['title']} {track['artist']}")
        if results:
            best = results[0]
            download_req = DownloadRequest(
                youtube_url=f"https://youtube.com/watch?v={best['videoId']}",
                format="mp3",
                quality="320kbps",
                title=track['title'],
                artist=track['artist'],
                album=track['album'],
                album_art_url=track['album_art']
            )
            queue = load_queue()
            queue.append({
                "id": str(uuid4()),
                **download_req.dict(),
                "status": "pending",
                "progress": 0,
                "file_path": ""
            })
            save_queue(queue)
            imported += 1
    return {"imported": imported, "total": len(tracks)}

@app.get("/download-queue")
async def get_queue():
    return load_queue()

@app.delete("/download-queue/{item_id}")
async def delete_queue_item(item_id: str):
    queue = load_queue()
    queue = [item for item in queue if item["id"] != item_id]
    save_queue(queue)
    return {"message": "Item removed"}

@app.post("/download-all")
async def start_downloads():
    threading.Thread(target=download_audio_task, daemon=True).start()
    return {"message": "Download process started"}
