"""FastAPI backend for Spotify mood classifier."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import pathlib

from spotify_client import get_auth_url, exchange_code, fetch_tracks
from classifier import cluster_tracks

app = FastAPI(title="Spotify Mood Classifier")

# Serve the single-page frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return pathlib.Path("static/index.html").read_text()


@app.get("/login")
async def login():
    return RedirectResponse(get_auth_url())


@app.get("/callback")
async def callback(code: str = Query(...)):
    try:
        token_info = exchange_code(code)
        access_token = token_info["access_token"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")
    return RedirectResponse(f"/?token={access_token}")


@app.get("/analyze")
async def analyze(
    token: str = Query(..., description="Spotify access token"),
    time_range: str = Query("medium_term", description="short_term | medium_term | long_term"),
    limit: int = Query(50, ge=10, le=50),
):
    try:
        tracks = fetch_tracks(token, limit=limit, time_range=time_range)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Spotify error: {e}")

    if len(tracks) < 4:
        raise HTTPException(status_code=400, detail="Not enough tracks to cluster (need ≥ 4).")

    result = cluster_tracks(tracks)
    result["track_count"] = len(tracks)
    return result
