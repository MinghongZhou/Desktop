"""Spotify API: OAuth flow and audio feature fetching."""
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

SCOPE = "user-top-read"
FEATURES = ["energy", "valence", "danceability", "acousticness",
            "instrumentalness", "tempo", "loudness"]


def get_auth_manager():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI", "http://localhost:8000/callback"),
        scope=SCOPE,
        cache_path=".spotify_cache",
        show_dialog=True,
    )


def get_auth_url() -> str:
    return get_auth_manager().get_authorize_url()


def exchange_code(code: str) -> dict:
    auth = get_auth_manager()
    token_info = auth.get_access_token(code, as_dict=True)
    return token_info


def fetch_tracks(access_token: str, limit: int = 50, time_range: str = "medium_term") -> list[dict]:
    """Fetch top tracks and their audio features for a user."""
    sp = spotipy.Spotify(auth=access_token)

    top = sp.current_user_top_tracks(limit=limit, time_range=time_range)
    track_ids = [t["id"] for t in top["items"]]
    track_meta = {t["id"]: t for t in top["items"]}

    # Fetch audio features in batches of 100
    features_raw = []
    for i in range(0, len(track_ids), 100):
        batch = sp.audio_features(track_ids[i:i + 100])
        features_raw.extend([f for f in batch if f is not None])

    tracks = []
    for f in features_raw:
        tid = f["id"]
        meta = track_meta.get(tid, {})
        track = {feat: f.get(feat, 0.0) for feat in FEATURES}
        track["id"] = tid
        track["name"] = meta.get("name", "Unknown")
        track["artist"] = ", ".join(a["name"] for a in meta.get("artists", []))
        tracks.append(track)

    return tracks
