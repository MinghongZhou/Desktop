"""K-Means mood clustering on Spotify audio features."""
import warnings
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

FEATURES = ["energy", "valence", "danceability", "acousticness",
            "instrumentalness", "tempo", "loudness"]

MOOD_RULES = [
    ("Energetic", {"energy": 1, "tempo": 1, "acousticness": -1}),
    ("Happy",     {"valence": 1, "danceability": 1}),
    ("Chill",     {"acousticness": 1, "instrumentalness": 1, "energy": -1}),
    ("Hype",      {"energy": 1, "danceability": 1, "tempo": 1}),
    ("Dark",      {"valence": -1, "energy": -1}),
]

MOOD_EMOJI = {
    "Energetic": "⚡",
    "Happy": "😊",
    "Chill": "🌊",
    "Hype": "🔥",
    "Dark": "🌑",
}


def _label_cluster(centroid_scaled, scaler):
    """Pick a mood label for a cluster based on its centroid."""
    centroid = dict(zip(FEATURES, scaler.inverse_transform([centroid_scaled])[0]))
    # Normalize features to [0,1] range for fair comparison
    ranges = {
        "energy": (0, 1), "valence": (0, 1), "danceability": (0, 1),
        "acousticness": (0, 1), "instrumentalness": (0, 1),
        "tempo": (60, 200), "loudness": (-30, 0),
    }
    norm = {}
    for f, (lo, hi) in ranges.items():
        norm[f] = (centroid[f] - lo) / (hi - lo)

    best_mood, best_score = "Chill", -999
    for mood, weights in MOOD_RULES:
        score = sum(w * norm.get(f, 0.5) for f, w in weights.items())
        if score > best_score:
            best_score = score
            best_mood = mood
    return best_mood


def _pick_k(X_scaled, max_k=8):
    """Pick k via elbow: largest drop in inertia improvement rate."""
    inertias = []
    for k in range(2, min(max_k + 1, len(X_scaled))):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            km.fit(X_scaled)
        inertias.append(km.inertia_)

    if len(inertias) < 2:
        return 2

    drops = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    best = int(np.argmax(drops)) + 2  # +2 because we started at k=2
    return max(2, min(best, 5))  # cap at 5 moods


def cluster_tracks(tracks: list[dict]) -> dict:
    """
    Input:  list of track dicts with keys from FEATURES + 'name', 'artist', 'id'
    Output: dict with clusters, pca_points, mood_labels, explained_variance
    """
    X = np.array([[t[f] for f in FEATURES] for t in tracks])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    k = _pick_k(X_scaled)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)

    # Label each cluster with a mood
    mood_labels = {}
    used_moods = set()
    for cluster_id in range(k):
        centroid = km.cluster_centers_[cluster_id]
        mood = _label_cluster(centroid, scaler)
        # Avoid duplicate mood labels
        if mood in used_moods:
            for m, _ in MOOD_RULES:
                if m not in used_moods:
                    mood = m
                    break
        used_moods.add(mood)
        mood_labels[cluster_id] = mood

    # PCA to 2D for scatter plot
    pca = PCA(n_components=2, random_state=42)
    X_2d = pca.fit_transform(X_scaled)

    clusters = {}
    for cluster_id in range(k):
        mask = labels == cluster_id
        mood = mood_labels[cluster_id]
        clusters[mood] = {
            "tracks": [
                {
                    "name": tracks[i]["name"],
                    "artist": tracks[i]["artist"],
                    "id": tracks[i]["id"],
                    "x": float(X_2d[i, 0]),
                    "y": float(X_2d[i, 1]),
                }
                for i in np.where(mask)[0]
            ],
            "emoji": MOOD_EMOJI.get(mood, "🎵"),
            "size": int(mask.sum()),
        }

    return {
        "clusters": clusters,
        "explained_variance": float(pca.explained_variance_ratio_.sum()),
        "k": k,
    }
