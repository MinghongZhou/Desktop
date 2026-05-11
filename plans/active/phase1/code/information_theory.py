"""Information theory: entropy, cross-entropy, KL divergence, mutual information."""
import numpy as np


def entropy(p, base=2):
    """Shannon entropy H(p) in bits (base=2) or nats (base=e)."""
    p = np.asarray(p, dtype=float)
    p = p[p > 0]  # remove zeros (0 log 0 = 0)
    if base == 2:
        return -np.sum(p * np.log2(p))
    return -np.sum(p * np.log(p))


def cross_entropy(p, q, eps=1e-12):
    """H(p, q) = -sum p log q. p=true, q=predicted."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    return -np.sum(p * np.log(np.clip(q, eps, 1)))


def kl_divergence(p, q, eps=1e-12):
    """KL(p || q) = sum p log(p/q). Always >= 0."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    mask = p > 0
    return np.sum(p[mask] * np.log(p[mask] / np.clip(q[mask], eps, 1)))


def mutual_information(joint_pxy):
    """I(X;Y) = H(X) + H(Y) - H(X,Y) from joint distribution table."""
    pxy = np.asarray(joint_pxy, float)
    pxy /= pxy.sum()
    px = pxy.sum(axis=1)
    py = pxy.sum(axis=0)
    return entropy(px) + entropy(py) - entropy(pxy.ravel())


def demonstrate_entropy():
    print("Entropy examples:")
    print(f"  Certain coin (p=[1,0]):    H = {entropy([1, 0]):.3f} bits")
    print(f"  Fair coin (p=[0.5,0.5]):   H = {entropy([0.5, 0.5]):.3f} bits")
    print(f"  Biased coin (p=[0.9,0.1]): H = {entropy([0.9, 0.1]):.3f} bits")
    print(f"  Uniform 4-class:           H = {entropy([0.25]*4):.3f} bits")
    print(f"  Uniform 8-class:           H = {entropy([0.125]*8):.3f} bits")


def demonstrate_cross_entropy_and_kl():
    print("\nCross-entropy vs KL divergence:")
    true_p = np.array([0.1, 0.4, 0.5])  # true labels (one-hot or soft)

    predictions = {
        "Perfect": np.array([0.1, 0.4, 0.5]),
        "Good":    np.array([0.15, 0.35, 0.5]),
        "Bad":     np.array([0.5, 0.4, 0.1]),
    }

    for name, q in predictions.items():
        h_p = entropy(true_p)
        h_pq = cross_entropy(true_p, q)
        kl = kl_divergence(true_p, q)
        print(f"  {name:8s}: CE={h_pq:.4f}, KL={kl:.4f}  (H(p)={h_p:.4f})")

    print("  → CE = H(p) + KL(p||q), so KL=0 iff predictions match truth")


def demonstrate_kl_asymmetry():
    print("\nKL asymmetry demo:")
    p = np.array([0.7, 0.2, 0.1])
    q = np.array([0.1, 0.4, 0.5])
    print(f"  KL(p||q) = {kl_divergence(p, q):.4f}")
    print(f"  KL(q||p) = {kl_divergence(q, p):.4f}  (different!)")


def demonstrate_mutual_information():
    print("\nMutual information:")

    # Independent: joint = marginal product
    joint_indep = np.array([[0.1, 0.2], [0.15, 0.3], [0.1, 0.15]])
    joint_indep = np.outer([0.35, 0.45, 0.2], [0.4, 0.6])
    print(f"  Independent variables: I(X;Y) = {mutual_information(joint_indep):.4f} bits")

    # Dependent: knowing Y tells us a lot about X
    joint_dep = np.array([[0.4, 0.05], [0.05, 0.5]])
    print(f"  Dependent variables:   I(X;Y) = {mutual_information(joint_dep):.4f} bits")


def ce_loss_as_mle():
    print("\nCross-entropy loss = negative log-likelihood:")
    np.random.seed(42)
    y_true = np.array([0, 1, 1, 0, 1])
    y_pred = np.array([0.1, 0.9, 0.8, 0.2, 0.7])

    bce = -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))
    print(f"  Binary cross-entropy: {bce:.4f}")
    print(f"  = negative log-likelihood of Bernoulli model")


if __name__ == "__main__":
    demonstrate_entropy()
    demonstrate_cross_entropy_and_kl()
    demonstrate_kl_asymmetry()
    demonstrate_mutual_information()
    ce_loss_as_mle()
