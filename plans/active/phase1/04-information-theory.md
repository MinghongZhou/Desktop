# 04 — Information Theory

## Entropy

Shannon entropy measures the average uncertainty (information content) of a distribution:

```
H(X) = -Σₓ P(x) log₂ P(x)   (bits, when using log₂)
H(X) = -Σₓ P(x) ln P(x)     (nats, when using ln)
```

- H(X) ≥ 0 always
- H(X) = 0 when outcome is certain (one P=1, rest P=0)
- H(X) is maximized by the uniform distribution: H = log₂(n) for n outcomes

**Example:** Fair coin: H = -0.5·log₂(0.5) - 0.5·log₂(0.5) = 1 bit

## Cross-Entropy

```
H(p, q) = -Σₓ p(x) log q(x)
```

Measures the average bits needed to encode samples from p using a code optimized for q.

**In ML:** p = true labels, q = model predictions
```
CE loss = -(1/n) Σᵢ Σₖ yᵢₖ log(p̂ᵢₖ)
```
Minimizing cross-entropy is equivalent to maximizing log-likelihood.

## KL Divergence

```
KL(p ‖ q) = Σₓ p(x) log(p(x)/q(x))
           = H(p, q) - H(p)
```

- KL ≥ 0 always (Gibbs' inequality)
- KL(p ‖ q) = 0 iff p = q
- **Not symmetric**: KL(p ‖ q) ≠ KL(q ‖ p)
- "Extra bits" needed when using q to encode p

**Forward vs Reverse KL:**
- KL(p ‖ q): zero-forcing — q avoids putting mass where p has none
- KL(q ‖ p): mean-seeking — q spreads to cover all of p's mass
- Variational inference minimizes KL(q ‖ p) (ELBO)
- VAE loss = reconstruction loss + KL(q(z|x) ‖ p(z))

## Mutual Information

```
I(X; Y) = KL(p(x,y) ‖ p(x)p(y))
         = H(X) - H(X | Y)
         = H(Y) - H(Y | X)
         = H(X) + H(Y) - H(X, Y)
```

Measures how much knowing Y reduces uncertainty about X (and vice versa).

- I(X;Y) = 0 iff X and Y are independent
- I(X;Y) = H(X) iff Y fully determines X

**In ML:**
- Feature selection: select features with high MI to the target
- Representation learning: InfoNCE loss (contrastive learning) maximizes a lower bound on MI
- ICA and independent component analysis

## Jensen's Inequality

For convex function f:
```
f(E[X]) ≤ E[f(X)]
```

Used to prove KL ≥ 0 and to derive the ELBO (Evidence Lower BOund) in variational inference.

## ELBO (Evidence Lower Bound)

In variational inference, we approximate posterior p(z|x) with q(z):
```
log p(x) = ELBO + KL(q(z) ‖ p(z|x))
ELBO = E_q[log p(x|z)] - KL(q(z) ‖ p(z))
```
Since KL ≥ 0, ELBO ≤ log p(x). Maximizing ELBO tightens the bound.

## Connections to ML Loss Functions

| Loss Function | Information Theory Interpretation |
|---|---|
| Binary cross-entropy | CE between Bernoulli(y) and Bernoulli(ŷ) |
| Categorical cross-entropy | CE between true and predicted categorical |
| MSE | Negative log-likelihood under Gaussian |
| KL divergence term in VAE | KL between approximate and prior posterior |
| Contrastive (InfoNCE) | Lower bound on mutual information |

## Code

See [code/information_theory.py](code/information_theory.py) for entropy, KL, and MI computations.
