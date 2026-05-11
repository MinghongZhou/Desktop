# 02 — Calculus for ML

## Derivatives

The derivative f'(x) = df/dx measures the rate of change.

| Function | Derivative |
|---|---|
| xⁿ | nxⁿ⁻¹ |
| eˣ | eˣ |
| ln(x) | 1/x |
| σ(x) = 1/(1+e⁻ˣ) | σ(x)(1 − σ(x)) |
| tanh(x) | 1 − tanh²(x) |
| max(0, x) (ReLU) | 0 if x<0, 1 if x>0 |

## Chain Rule

If y = f(g(x)), then dy/dx = (df/dg)(dg/dx)

This is the heart of **backpropagation**:
```
L = loss(ŷ),  ŷ = f(z),  z = Wx + b
∂L/∂W = (∂L/∂ŷ)(∂ŷ/∂z)(∂z/∂W)
```

## Partial Derivatives & Gradients

For f: ℝⁿ → ℝ, the gradient is:
```
∇f(x) = [∂f/∂x₁, ∂f/∂x₂, ..., ∂f/∂xₙ]ᵀ
```
The gradient points in the direction of steepest ascent.

## Jacobian

For f: ℝⁿ → ℝᵐ, the Jacobian **J** ∈ ℝᵐˣⁿ:
```
Jᵢⱼ = ∂fᵢ/∂xⱼ
```
Used in backprop through vector-valued layers (e.g., softmax).

## Hessian

For f: ℝⁿ → ℝ, the Hessian **H** ∈ ℝⁿˣⁿ:
```
Hᵢⱼ = ∂²f / (∂xᵢ ∂xⱼ)
```
- If H is PSD at a critical point → local minimum
- If H is NSD → local maximum
- Mixed signs → saddle point (common in deep networks)

Second-order methods (Newton's method) use H⁻¹∇f but are expensive for large models.

## Gradient Descent

Update rule: θ ← θ − η∇L(θ)

| Variant | Batch size | Notes |
|---|---|---|
| Batch GD | Full dataset | Stable, slow per update |
| Stochastic GD | 1 sample | Noisy, fast, escapes local minima |
| Mini-batch SGD | 32–512 samples | Standard in practice |

## Taylor Series & Local Approximation

f(x + ε) ≈ f(x) + εf'(x) + ½ε²f''(x) + ...

First-order approximation underlies gradient descent.
Second-order underlies Newton/quasi-Newton methods (Adam uses diagonal approximation of curvature).

## Backpropagation Algorithm

Given a computation graph:

1. **Forward pass**: compute all intermediate values and loss L
2. **Backward pass**: apply chain rule from L back to each parameter
   - Store ∂L/∂output for each node
   - Accumulate gradients: ∂L/∂W = Σ (∂L/∂y)(∂y/∂W)

**Key insight**: gradients flow backwards through the same graph used for forward computation. Each operation needs to implement both forward() and backward().

## Common Gradient Computations in ML

```
MSE loss:    L = (1/n)‖ŷ - y‖²     →  ∂L/∂ŷ = (2/n)(ŷ - y)
CE loss:     L = -Σ yᵢ log(p̂ᵢ)    →  ∂L/∂z = p̂ - y  (with softmax, very clean)
Linear:      ŷ = Wx + b             →  ∂L/∂W = (∂L/∂ŷ)xᵀ,  ∂L/∂b = ∂L/∂ŷ
ReLU:        ŷ = max(0, x)          →  ∂L/∂x = (∂L/∂ŷ) · 𝟙[x > 0]
```

## Code

See [code/calculus.py](code/calculus.py) for numerical gradient checking and backprop from scratch.
