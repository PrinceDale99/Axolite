import requests
import os
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")


def get_access_token():
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
    )
    return r.json()["access_token"]


def get_spotify_playlist(url):
    token = get_access_token()
    playlist_id = url.split("playlist/")[-1].split("?")[0]
    headers = {"Authorization": f"Bearer {token}"}

    items = []
    offset = 0
    while True:
        r = requests.get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers=headers,
            params={"offset": offset, "limit": 100},
        )
        data = r.json()
        for item in data["items"]:
            track = item["track"]
            items.append({
                "title": track["name"],
                "artist": track["artists"][0]["name"],
                "album": track["album"]["name"],
                "album_art": track["album"]["images"][0]["url"]
            })
        if data["next"]:
            offset += 100
        else:
            break
    return items
