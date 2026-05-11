# 06 — Unsupervised Learning

## K-Means Clustering

**Objective:** minimize within-cluster sum of squares (WCSS / inertia):
```
J = Σₖ Σᵢ∈Cₖ ‖xᵢ - μₖ‖²
```

**Algorithm (Lloyd's):**
1. Initialize k centroids (random or k-means++)
2. **E-step**: assign each point to nearest centroid
3. **M-step**: recompute centroids as cluster means
4. Repeat until convergence

**k-means++ initialization:** choose centroids with probability ∝ distance to nearest existing centroid — avoids bad initializations.

**Choosing k:**
- Elbow method: plot WCSS vs k, find the "elbow"
- Silhouette score: measures cohesion vs separation ∈ [-1, 1]

**Limitations:** assumes spherical clusters, sensitive to outliers, must specify k.

## Principal Component Analysis (PCA)

**Goal:** find directions of maximum variance in the data.

**Algorithm:**
1. Center the data: X̃ = X - μ
2. Compute covariance matrix: C = (1/n)X̃ᵀX̃
3. Eigendecompose: C = QΛQᵀ
4. Project: Z = X̃Q_k  (keep top k eigenvectors)

**Equivalently via SVD:** X̃ = UΣVᵀ → principal components = columns of V

**Variance explained by component i:** λᵢ / Σⱼλⱼ  
**Choose k:** retain enough components to explain 95% of variance.

**When to use PCA:**
- Dimensionality reduction before distance-based models
- Visualization (k=2 or k=3)
- Decorrelating features
- Compression

**PCA is NOT:**
- Supervised (no labels used)
- Invariant to feature scaling (always standardize first!)

## Gaussian Mixture Models (GMMs)

**Model:** p(x) = Σₖ πₖ N(x | μₖ, Σₖ)
- πₖ: mixing weights (Σπₖ = 1)
- μₖ, Σₖ: mean and covariance of component k

**Learning via EM:**
- **E-step:** compute responsibilities rᵢₖ = P(z=k | xᵢ)
- **M-step:** update πₖ, μₖ, Σₖ using weighted MLEs
- Guaranteed to increase log-likelihood each iteration

**vs K-Means:**
- GMM: soft assignments, learns cluster shape (full covariance)
- K-Means: hard assignments, assumes spherical clusters
- GMM reduces to K-Means with diagonal, equal covariances

**Selecting k:** BIC or AIC (penalize model complexity)

## Autoencoders

**Architecture:** Encoder → Bottleneck (latent z) → Decoder

**Loss:** L = ‖x - x̂‖²  (reconstruction)

**Variants:**
| Type | Key Idea | Use Case |
|---|---|---|
| Vanilla | just reconstruction | compression, denoising |
| Denoising | input corrupted, reconstruct clean | robust representations |
| Sparse | penalize ‖z‖₁ | interpretable features |
| Variational (VAE) | z ~ N(μ, σ²), ELBO loss | generative model, smooth latent space |

**VAE loss:**
```
L = E[‖x - x̂‖²] + KL(q(z|x) ‖ p(z))
reconstruction    regularization (keep z near N(0,I))
```

**Reparameterization trick:** z = μ + σ ⊙ ε, ε ~ N(0,I) — allows backprop through sampling.

## Dimensionality Reduction Comparison

| Method | Linear | Preserves | Scalable | Notes |
|---|---|---|---|---|
| PCA | Yes | Global variance | Yes | Go-to first choice |
| t-SNE | No | Local structure | No (O(n²)) | Visualization only, not deterministic |
| UMAP | No | Local + global | Better | Faster than t-SNE, better for large data |
| Autoencoder | No | Learned | Yes | Most flexible, needs training |

## Code

See [code/unsupervised_learning.py](code/unsupervised_learning.py) for K-Means, PCA, GMM, and autoencoder from scratch.
