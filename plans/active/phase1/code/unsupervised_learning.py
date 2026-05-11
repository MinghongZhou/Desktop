"""Unsupervised learning: K-Means, PCA, GMM, simple autoencoder."""
import numpy as np
from sklearn.datasets import make_blobs, load_iris
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score


def kmeans_from_scratch(X, k, n_iter=100, seed=42):
    rng = np.random.default_rng(seed)
    # k-means++ init
    centroids = [X[rng.integers(len(X))]]
    for _ in range(k - 1):
        dists = np.min([np.sum((X - c)**2, axis=1) for c in centroids], axis=0)
        centroids.append(X[rng.choice(len(X), p=dists / dists.sum())])
    centroids = np.array(centroids)

    for _ in range(n_iter):
        dists = np.linalg.norm(X[:, None] - centroids[None], axis=2)
        labels = dists.argmin(axis=1)
        new_centroids = np.array([X[labels == i].mean(axis=0) for i in range(k)])
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids

    inertia = sum(np.sum((X[labels == i] - centroids[i])**2) for i in range(k))
    return labels, centroids, inertia


def pca_from_scratch(X, n_components):
    X_centered = X - X.mean(axis=0)
    cov = (X_centered.T @ X_centered) / (len(X) - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigh returns ascending order; reverse for descending
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]
    components = eigenvectors[:, :n_components]
    X_reduced = X_centered @ components
    explained_variance_ratio = eigenvalues[:n_components] / eigenvalues.sum()
    return X_reduced, explained_variance_ratio


def demo_kmeans():
    print("=== K-Means ===")
    X, true_labels = make_blobs(n_samples=300, centers=4, random_state=42)

    labels_scratch, centroids, inertia = kmeans_from_scratch(X, k=4)
    sil_scratch = silhouette_score(X, labels_scratch)
    print(f"  Scratch  — inertia={inertia:.1f}, silhouette={sil_scratch:.3f}")

    km_sklearn = KMeans(n_clusters=4, random_state=42, n_init=10).fit(X)
    sil_sklearn = silhouette_score(X, km_sklearn.labels_)
    print(f"  sklearn  — inertia={km_sklearn.inertia_:.1f}, silhouette={sil_sklearn:.3f}")

    # Elbow method
    inertias = [KMeans(k, random_state=0, n_init=5).fit(X).inertia_ for k in range(2, 8)]
    print(f"  Elbow (inertia by k): {[f'{v:.0f}' for v in inertias]}")


def demo_pca():
    print("\n=== PCA ===")
    iris = load_iris()
    X = StandardScaler().fit_transform(iris.data)

    X_reduced, evr = pca_from_scratch(X, n_components=2)
    print(f"  Scratch PCA — explained variance: {evr[0]:.3f}, {evr[1]:.3f} (total={evr.sum():.3f})")

    pca_sk = PCA(n_components=2).fit(X)
    print(f"  sklearn PCA — explained variance: {pca_sk.explained_variance_ratio_[0]:.3f}, "
          f"{pca_sk.explained_variance_ratio_[1]:.3f}")

    # Show variance explained per component
    pca_full = PCA().fit(X)
    cumvar = np.cumsum(pca_full.explained_variance_ratio_)
    print(f"  Cumulative variance: {[f'{v:.3f}' for v in cumvar]}")


def demo_gmm():
    print("\n=== Gaussian Mixture Model ===")
    X, _ = make_blobs(n_samples=300, centers=3, cluster_std=1.5, random_state=0)

    for cov_type in ["full", "diag", "spherical"]:
        gmm = GaussianMixture(n_components=3, covariance_type=cov_type, random_state=0).fit(X)
        labels = gmm.predict(X)
        sil = silhouette_score(X, labels)
        print(f"  GMM ({cov_type:10s}): BIC={gmm.bic(X):.1f}, silhouette={sil:.3f}")

    # Select number of components by BIC
    bics = [GaussianMixture(k, random_state=0).fit(X).bic(X) for k in range(2, 7)]
    best_k = np.argmin(bics) + 2
    print(f"  Best k by BIC: {best_k}")


class SimpleAutoencoder:
    """Shallow autoencoder via numpy (linear, for demo purposes)."""

    def __init__(self, input_dim, latent_dim, lr=0.01):
        self.lr = lr
        scale = np.sqrt(2 / (input_dim + latent_dim))
        self.W_enc = np.random.randn(input_dim, latent_dim) * scale
        self.W_dec = np.random.randn(latent_dim, input_dim) * scale

    def encode(self, X):
        return np.tanh(X @ self.W_enc)

    def decode(self, Z):
        return Z @ self.W_dec

    def train_step(self, X):
        Z = self.encode(X)
        X_hat = self.decode(Z)
        loss = np.mean((X - X_hat) ** 2)

        # Backprop
        dX_hat = -2 * (X - X_hat) / len(X)
        dW_dec = Z.T @ dX_hat
        dZ = dX_hat @ self.W_dec.T * (1 - Z**2)  # tanh derivative
        dW_enc = X.T @ dZ

        self.W_enc -= self.lr * dW_enc
        self.W_dec -= self.lr * dW_dec
        return loss


def demo_autoencoder():
    print("\n=== Autoencoder (linear, numpy) ===")
    np.random.seed(42)
    X = StandardScaler().fit_transform(load_iris().data)

    ae = SimpleAutoencoder(input_dim=4, latent_dim=2, lr=0.05)
    for epoch in range(1000):
        loss = ae.train_step(X)

    X_hat = ae.decode(ae.encode(X))
    recon_error = np.mean((X - X_hat)**2)
    print(f"  Final reconstruction MSE: {recon_error:.4f}")

    # Compare latent space to PCA
    Z = ae.encode(X)
    pca = PCA(n_components=2).fit_transform(X)
    print(f"  Latent dim variance (AE): {Z.var(axis=0).round(3)}")
    print(f"  Latent dim variance (PCA): {pca.var(axis=0).round(3)}")


if __name__ == "__main__":
    np.random.seed(0)
    demo_kmeans()
    demo_pca()
    demo_gmm()
    demo_autoencoder()
