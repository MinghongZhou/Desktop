# 01 — Linear Algebra

## Vectors

A vector **x** ∈ ℝⁿ is an ordered list of n real numbers.

- Dot product: **x** · **y** = Σ xᵢyᵢ = ‖x‖‖y‖cos(θ)
- L2 norm: ‖x‖₂ = √(Σ xᵢ²)
- L1 norm: ‖x‖₁ = Σ |xᵢ|

## Matrices

A matrix **A** ∈ ℝᵐˣⁿ has m rows and n columns.

| Operation | Formula |
|---|---|
| Transpose | (Aᵀ)ᵢⱼ = Aⱼᵢ |
| Matrix multiply | (AB)ᵢⱼ = Σₖ AᵢₖBₖⱼ |
| Inverse | AA⁻¹ = I (requires square, full rank) |
| Trace | tr(A) = Σᵢ Aᵢᵢ |
| Determinant | scalar measure of volume scaling |

### Special matrices
- **Symmetric**: A = Aᵀ
- **Orthogonal**: AᵀA = I, columns are orthonormal
- **Positive semi-definite (PSD)**: xᵀAx ≥ 0 for all x

## Eigendecomposition

For square matrix **A**: **Av** = λ**v**

- **v**: eigenvector (direction unchanged by A)
- **λ**: eigenvalue (scaling factor)
- Decomposition: **A** = **QΛQᵀ** (when A is symmetric)
  - **Q**: matrix of eigenvectors (columns)
  - **Λ**: diagonal matrix of eigenvalues

**Why it matters for ML:**
- PCA uses eigenvectors of the covariance matrix
- Eigenvalues describe variance captured per component
- Spectral methods in graph neural networks

## Singular Value Decomposition (SVD)

Any matrix **A** ∈ ℝᵐˣⁿ decomposes as: **A = UΣVᵀ**

- **U** ∈ ℝᵐˣᵐ: left singular vectors (orthogonal)
- **Σ** ∈ ℝᵐˣⁿ: diagonal matrix of singular values σ₁ ≥ σ₂ ≥ ... ≥ 0
- **V** ∈ ℝⁿˣⁿ: right singular vectors (orthogonal)

**Truncated SVD (rank-k approximation):**
Aₖ = UₖΣₖVₖᵀ — best rank-k approximation by Frobenius norm (Eckart-Young theorem)

**Why it matters for ML:**
- Dimensionality reduction (PCA is SVD on centered data)
- Collaborative filtering / matrix factorization for recommenders
- Solving least squares: A⁺ = VΣ⁺Uᵀ (pseudoinverse)
- Measuring rank and condition number of weight matrices

## Systems of Linear Equations

**Ax = b**

- Unique solution if A is square and invertible: x = A⁻¹b
- Least squares solution (overdetermined): x = (AᵀA)⁻¹Aᵀb
- Numerically: prefer SVD or QR decomposition over inverting A directly

## Key Identities to Memorize

```
(AB)ᵀ = BᵀAᵀ
(AB)⁻¹ = B⁻¹A⁻¹
tr(AB) = tr(BA)
det(AB) = det(A)det(B)
∂(xᵀAx)/∂x = (A + Aᵀ)x = 2Ax  (if A symmetric)
∂(aᵀx)/∂x = a
```

## Code

See [code/linear_algebra.py](code/linear_algebra.py) for implementations and visualizations.
