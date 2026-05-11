# 03 — Probability & Statistics

## Fundamentals

- **P(A)**: probability of event A, P(A) ∈ [0,1]
- **P(A ∪ B)** = P(A) + P(B) − P(A ∩ B)
- **P(A | B)** = P(A ∩ B) / P(B)   (conditional probability)
- **Independence**: P(A ∩ B) = P(A)P(B)

## Bayes' Theorem

```
P(θ | X) = P(X | θ) · P(θ) / P(X)

posterior ∝ likelihood × prior
```

- **P(θ)**: prior — belief about parameters before seeing data
- **P(X | θ)**: likelihood — probability of data given parameters
- **P(θ | X)**: posterior — updated belief after seeing data
- **P(X)**: marginal likelihood (normalizing constant)

**ML connection**: Bayesian inference generalizes point estimates to distributions over model parameters.

## Key Distributions

| Distribution | PMF/PDF | Mean | Variance | Use in ML |
|---|---|---|---|---|
| Bernoulli(p) | pˣ(1-p)¹⁻ˣ | p | p(1-p) | binary classification |
| Binomial(n,p) | C(n,k)pᵏ(1-p)ⁿ⁻ᵏ | np | np(1-p) | count of successes |
| Categorical(π) | πₖ | — | — | multi-class output |
| Gaussian(μ,σ²) | (1/√2πσ²)exp(-(x-μ)²/2σ²) | μ | σ² | continuous data, noise |
| Multivariate Normal | (2π)^(-d/2)|Σ|^(-1/2)exp(-½(x-μ)ᵀΣ⁻¹(x-μ)) | μ | Σ | GMMs, Gaussian processes |
| Exponential(λ) | λe^(-λx) | 1/λ | 1/λ² | time between events |
| Poisson(λ) | λᵏe^(-λ)/k! | λ | λ | event counts |
| Beta(α,β) | xᵅ⁻¹(1-x)^(β-1)/B(α,β) | α/(α+β) | — | prior on probabilities |
| Dirichlet(α) | generalization of Beta | αᵢ/Σαᵢ | — | prior on categoricals |

## Expectation & Variance

```
E[X] = Σ x·P(X=x)           (discrete)
E[X] = ∫ x·f(x)dx           (continuous)
E[aX + b] = aE[X] + b
E[X + Y] = E[X] + E[Y]

Var(X) = E[(X - μ)²] = E[X²] - (E[X])²
Var(aX + b) = a²Var(X)
Var(X + Y) = Var(X) + Var(Y) + 2Cov(X,Y)

Cov(X,Y) = E[(X-μₓ)(Y-μᵧ)]
Corr(X,Y) = Cov(X,Y) / (σₓσᵧ)  ∈ [-1, 1]
```

## Maximum Likelihood Estimation (MLE)

Find parameters θ that maximize the probability of the observed data:

```
θ_MLE = argmax_θ P(X | θ)
       = argmax_θ Σᵢ log P(xᵢ | θ)   (log-likelihood, sum over iid samples)
```

**Example — Gaussian MLE:**
- μ_MLE = (1/n)Σxᵢ  (sample mean)
- σ²_MLE = (1/n)Σ(xᵢ-μ)²  (biased sample variance)

**Connection to loss functions:**
- MLE under Gaussian noise → minimizing MSE
- MLE under Bernoulli → minimizing binary cross-entropy
- MLE under Categorical → minimizing cross-entropy (softmax + NLL)

## Maximum A Posteriori (MAP)

```
θ_MAP = argmax_θ P(θ | X)
       = argmax_θ [log P(X | θ) + log P(θ)]
```

**MAP = MLE + regularization:**
- Gaussian prior on θ → L2 regularization (weight decay)
- Laplace prior on θ → L1 regularization (sparsity)

## Central Limit Theorem

For iid samples x₁,...,xₙ with mean μ and variance σ²:
```
√n (x̄ - μ) / σ  →  N(0, 1)  as n → ∞
```
The sample mean is approximately Gaussian for large n, regardless of the original distribution.

## Hypothesis Testing

1. State H₀ (null) and H₁ (alternative)
2. Compute test statistic
3. Compare p-value to significance level α (typically 0.05)
4. Reject H₀ if p < α

**p-value**: probability of observing data at least as extreme as seen, if H₀ were true.

**Common tests:**
- t-test: compare means (one/two sample)
- chi-squared: test independence of categorical variables
- A/B test in ML: often use t-test or Mann-Whitney U

## Bias-Variance Tradeoff (Statistical View)

For estimator θ̂ of θ:
```
MSE(θ̂) = Var(θ̂) + Bias(θ̂)²
```
- High bias → underfitting (model too simple)
- High variance → overfitting (model too complex)

## Code

See [code/probability_statistics.py](code/probability_statistics.py) for MLE fitting, Bayes update, and distribution sampling.
