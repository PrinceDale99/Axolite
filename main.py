# Axiolite: Optimized Music Downloader Backend (v2)
# ---------------------------
# Structure:
# - main.py            (FastAPI entrypoint)
# - downloader.py      (Handles download + metadata)
# - spotify.py         (Fetches album/track info)
# - utils.py           (Helpers for metadata + fallback)

# Starting with main.py...

# main.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from uuid import uuid4
from downloader import queue_download_job, get_queue, remove_item, trigger_downloads
from spotify import enrich_with_spotify
import os, json

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

QUEUE_FILE = "queue.json"

class DownloadRequest(BaseModel):
    query: str
    format: str = "mp3"
    quality: str = "320"

@app.post("/download-audio")
async def download_audio(req: DownloadRequest, bg: BackgroundTasks):
    metadata = enrich_with_spotify(req.query)
    job_id = str(uuid4())
    job = {"id": job_id, **metadata, "format": req.format, "quality": req.quality, "status": "pending"}
    queue_download_job(job)
    bg.add_task(trigger_downloads)
    return {"id": job_id, **metadata}

@app.get("/download-file/{item_id}")
async def get_file(item_id: str):
    queue = get_queue()
    for item in queue:
        if item['id'] == item_id and item['status'] == "completed":
            return FileResponse(item['file_path'], filename=os.path.basename(item['file_path']))
    raise HTTPException(404, "File not ready")

@app.get("/download-queue")
async def get_download_queue():
    return get_queue()

@app.delete("/download-queue/{item_id}")
async def delete_item(item_id: str):
    return remove_item(item_id)

@app.post("/download-all")
async def manual_start(bg: BackgroundTasks):
    bg.add_task(trigger_downloads)
    return {"message": "Started"}
