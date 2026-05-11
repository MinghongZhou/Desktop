"""Linear algebra fundamentals for ML."""
import numpy as np


def dot_product_and_angle(a, b):
    dot = np.dot(a, b)
    angle = np.degrees(np.arccos(dot / (np.linalg.norm(a) * np.linalg.norm(b))))
    return dot, angle


def matrix_operations():
    A = np.array([[4, 2], [1, 3]], dtype=float)

    print("Matrix A:")
    print(A)
    print(f"Transpose:\n{A.T}")
    print(f"Determinant: {np.linalg.det(A):.2f}")
    print(f"Trace: {np.trace(A)}")
    print(f"Inverse:\n{np.linalg.inv(A)}")

    # Verify A @ A^-1 = I
    print(f"A @ A^-1 ≈ I: {np.allclose(A @ np.linalg.inv(A), np.eye(2))}")


def eigendecomposition():
    # Symmetric PSD matrix (like a covariance matrix)
    A = np.array([[3, 1], [1, 3]], dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(A)  # eigh for symmetric matrices

    print(f"\nEigenvalues: {eigenvalues}")
    print(f"Eigenvectors (columns):\n{eigenvectors}")

    # Reconstruct A = Q @ Λ @ Q^T
    A_reconstructed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    print(f"Reconstruction error: {np.max(np.abs(A - A_reconstructed)):.2e}")


def svd_and_low_rank():
    np.random.seed(42)
    A = np.random.randn(5, 4)

    U, s, Vt = np.linalg.svd(A, full_matrices=False)
    print(f"\nSingular values: {s.round(3)}")

    # Rank-2 approximation
    k = 2
    A_k = U[:, :k] @ np.diag(s[:k]) @ Vt[:k, :]
    frobenius_error = np.linalg.norm(A - A_k, 'fro')
    variance_captured = sum(s[:k]**2) / sum(s**2)
    print(f"Rank-{k} approximation: {variance_captured:.1%} variance, error={frobenius_error:.3f}")


def least_squares():
    # Overdetermined system: Ax = b, more equations than unknowns
    np.random.seed(0)
    A = np.random.randn(10, 3)
    true_x = np.array([1.0, -2.0, 0.5])
    b = A @ true_x + 0.1 * np.random.randn(10)

    # Normal equations
    x_hat = np.linalg.solve(A.T @ A, A.T @ b)
    # Or: x_hat = np.linalg.lstsq(A, b, rcond=None)[0]

    print(f"\nTrue x:      {true_x}")
    print(f"Estimated x: {x_hat.round(4)}")


if __name__ == "__main__":
    a = np.array([1.0, 0.0])
    b = np.array([1.0, 1.0]) / np.sqrt(2)
    dot, angle = dot_product_and_angle(a, b)
    print(f"Dot product: {dot:.3f}, angle: {angle:.1f}°\n")

    matrix_operations()
    eigendecomposition()
    svd_and_low_rank()
    least_squares()
