"""Probability and statistics for ML: MLE, MAP, Bayes, distributions."""
import numpy as np
from scipy import stats


def mle_gaussian(data):
    """MLE estimates for Gaussian: mean and (biased) variance."""
    mu = np.mean(data)
    sigma2 = np.mean((data - mu) ** 2)
    return mu, sigma2


def map_gaussian(data, prior_mu=0, prior_kappa=1):
    """MAP estimate of mean with Gaussian prior (conjugate)."""
    n = len(data)
    x_bar = np.mean(data)
    # Posterior mean: weighted combination of prior and data
    mu_map = (prior_kappa * prior_mu + n * x_bar) / (prior_kappa + n)
    return mu_map


def bayes_update_bernoulli(prior_alpha, prior_beta, successes, failures):
    """
    Bayesian update for Bernoulli with Beta prior.
    Beta(α, β) + data → Beta(α + successes, β + failures)
    """
    post_alpha = prior_alpha + successes
    post_beta = prior_beta + failures
    post_mean = post_alpha / (post_alpha + post_beta)
    return post_alpha, post_beta, post_mean


def demonstrate_mle():
    np.random.seed(42)
    true_mu, true_sigma = 5.0, 2.0
    data = np.random.normal(true_mu, true_sigma, size=200)

    mu_hat, var_hat = mle_gaussian(data)
    print("MLE for Gaussian:")
    print(f"  True:      μ={true_mu}, σ²={true_sigma**2}")
    print(f"  Estimated: μ={mu_hat:.3f}, σ²={var_hat:.3f}")


def demonstrate_map():
    np.random.seed(0)
    data = np.random.normal(3.0, 1.0, size=5)  # small sample, prior matters more

    mle_mu = np.mean(data)
    map_mu = map_gaussian(data, prior_mu=0, prior_kappa=5)

    print(f"\nMAP vs MLE (n=5, prior mean=0):")
    print(f"  MLE: {mle_mu:.3f}")
    print(f"  MAP: {map_mu:.3f}  (pulled toward prior)")
    print(f"  True data mean: 3.0")


def demonstrate_bayes_update():
    print("\nBayesian coin flip (Beta-Bernoulli):")
    alpha, beta = 1, 1  # uniform prior
    print(f"  Prior: Beta({alpha},{beta}), mean={alpha/(alpha+beta):.2f}")

    for successes, failures in [(3, 2), (7, 3), (20, 10)]:
        a, b, mean = bayes_update_bernoulli(alpha, beta, successes, failures)
        alpha, beta = a, b
        print(f"  After {successes}H {failures}T: Beta({a},{b}), posterior mean={mean:.3f}")


def demonstrate_distributions():
    print("\nSampling from key distributions:")
    np.random.seed(42)

    distributions = {
        "Gaussian(0,1)": np.random.normal(0, 1, 1000),
        "Bernoulli(0.3)": np.random.binomial(1, 0.3, 1000).astype(float),
        "Poisson(5)": np.random.poisson(5, 1000).astype(float),
        "Exponential(2)": np.random.exponential(2, 1000),
    }

    for name, samples in distributions.items():
        print(f"  {name}: mean={samples.mean():.3f}, std={samples.std():.3f}")


def central_limit_theorem():
    print("\nCentral Limit Theorem demo (Poisson samples):")
    np.random.seed(1)
    pop = np.random.poisson(lam=3, size=10000)

    for n in [1, 5, 30, 100]:
        sample_means = [np.mean(np.random.choice(pop, n)) for _ in range(2000)]
        _, p_value = stats.normaltest(sample_means)
        print(f"  n={n:3d}: mean={np.mean(sample_means):.3f}, "
              f"std={np.std(sample_means):.3f}, normality p={p_value:.3f}")


if __name__ == "__main__":
    demonstrate_mle()
    demonstrate_map()
    demonstrate_bayes_update()
    demonstrate_distributions()
    central_limit_theorem()
