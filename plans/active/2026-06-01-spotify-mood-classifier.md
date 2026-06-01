# Plan: Spotify Mood Classifier

**Date:** 2026-06-01
**Status:** active

## Goal

A web app that pulls your Spotify listening history, extracts audio features,
clusters songs by mood using K-Means + PCA, and displays labeled playlists.

## Stack

- **Backend**: Python + FastAPI
- **ML**: scikit-learn (K-Means, PCA, StandardScaler)
- **Spotify**: Spotipy (official Spotify Web API wrapper)
- **Frontend**: Single HTML page, vanilla JS + Chart.js (PCA scatter plot)

## Steps

- [x] Write plan
- [ ] Set up project structure
- [ ] Spotify OAuth + fetch top tracks with audio features
- [ ] Feature engineering (select + scale audio features)
- [ ] K-Means clustering (elbow method to pick k)
- [ ] PCA to 2D for visualization
- [ ] Auto-label clusters as moods (e.g. Energetic, Chill, Happy, Dark)
- [ ] FastAPI backend exposing /analyze endpoint
- [ ] Frontend: scatter plot + mood playlist cards
- [ ] Test end-to-end with real Spotify account

## Audio Features Used (from Spotify API)

| Feature | Range | What it captures |
|---|---|---|
| energy | 0–1 | intensity and activity |
| valence | 0–1 | musical positiveness |
| danceability | 0–1 | how suitable for dancing |
| acousticness | 0–1 | acoustic vs electric |
| instrumentalness | 0–1 | vocals vs instrumental |
| tempo | BPM | speed |
| loudness | dB | overall volume |

## Mood Label Logic (rule-based on cluster centroids)

| Mood | High | Low |
|---|---|---|
| Energetic | energy, tempo | acousticness |
| Chill | acousticness, instrumentalness | energy |
| Happy | valence, danceability | — |
| Dark/Sad | — | valence, energy |
| Hype | energy, danceability, tempo | valence |

## Notes

- Spotify app credentials needed (Client ID + Secret from developer.spotify.com)
- Store credentials in .env, never commit them
- Use 50 top tracks (medium_term) as default data source
