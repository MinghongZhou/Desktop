# 05 — Supervised Learning

## Linear Regression

**Model:** ŷ = Xw + b  
**Loss (MSE):** L = (1/n)‖y - ŷ‖²  
**Closed-form solution:** w = (XᵀX)⁻¹Xᵀy  
**Gradient:** ∂L/∂w = -(2/n)Xᵀ(y - ŷ)

**Assumptions:**
1. Linearity: E[y|x] = xᵀw
2. Homoscedasticity: constant variance of residuals
3. Independence of errors
4. No multicollinearity

**Regularization:**
- Ridge (L2): L + λ‖w‖²  →  w = (XᵀX + λI)⁻¹Xᵀy
- Lasso (L1): L + λ‖w‖₁  →  no closed form, use coordinate descent
- Elastic Net: L + λ₁‖w‖₁ + λ₂‖w‖²

## Logistic Regression

**Model:** P(y=1|x) = σ(xᵀw + b)  where σ(z) = 1/(1+e⁻ᶻ)  
**Loss (BCE):** L = -(1/n)Σ[y log ŷ + (1-y) log(1-ŷ)]  
**Gradient:** ∂L/∂w = (1/n)Xᵀ(ŷ - y)  — same form as linear regression!

**Multi-class:** softmax + cross-entropy  
P(y=k|x) = exp(xᵀwₖ) / Σⱼ exp(xᵀwⱼ)

## Support Vector Machines (SVM)

**Hard-margin SVM (linearly separable):**
Maximize margin 2/‖w‖ subject to yᵢ(wᵀxᵢ + b) ≥ 1

**Soft-margin SVM (hinge loss):**
```
L = (1/n)Σ max(0, 1 - yᵢ(wᵀxᵢ + b)) + λ‖w‖²
```

**Kernel trick:** replace xᵢᵀxⱼ with K(xᵢ, xⱼ) to work in high-dim space implicitly
- RBF kernel: K(x,z) = exp(-‖x-z‖²/2σ²)
- Polynomial: K(x,z) = (xᵀz + c)ᵈ

**When to use SVM:** small/medium datasets, high-dimensional sparse features (text), clear margin structure.

## Decision Trees

**Split criterion:**
- Classification: Gini impurity = 1 - Σ pₖ²
- Classification: Information gain = H(parent) - Σ wₗH(leaf l)
- Regression: variance reduction = Var(parent) - Σ wₗVar(leaf l)

**Hyperparameters:** max_depth, min_samples_split, min_samples_leaf

**Pros:** interpretable, handles mixed types, no scaling needed  
**Cons:** high variance (overfit easily), not smooth boundaries

## Ensemble Methods

### Bagging (Bootstrap Aggregating)
Train B trees on bootstrap samples, aggregate predictions.
- Classification: majority vote
- Regression: mean
- Reduces variance without increasing bias

**Random Forest:** Bagging + random feature subsets at each split
- Feature importance via mean decrease in impurity

### Boosting
Train models sequentially, each focusing on previous errors.

**AdaBoost:**
- Reweight misclassified samples higher each round
- Final prediction: weighted vote of weak learners

**Gradient Boosting:**
```
F_m(x) = F_{m-1}(x) + η · h_m(x)
where h_m fits the negative gradient (residuals) of L
```
- XGBoost, LightGBM, CatBoost are optimized implementations
- Key hyperparameters: n_estimators, learning_rate, max_depth, subsample

**When to use:**
- Random Forest: good default, robust, less tuning
- XGBoost/LightGBM: tabular data competitions, high-accuracy baseline

## Algorithm Comparison

| Algorithm | Interpretable | Handles Nonlinearity | Scalable | Key Strength |
|---|---|---|---|---|
| Linear Regression | Yes | No | Yes | fast, baseline |
| Logistic Regression | Yes | No | Yes | probability outputs |
| SVM | Partially | Yes (kernel) | No (large n) | max margin |
| Decision Tree | Yes | Yes | Yes | interpretable |
| Random Forest | No | Yes | Yes | robust, low tuning |
| XGBoost | No | Yes | Yes | state-of-art on tabular |

## Code

See [code/supervised_learning.py](code/supervised_learning.py) for implementations from scratch and sklearn comparison.
