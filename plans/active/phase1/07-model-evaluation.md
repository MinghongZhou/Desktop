# 07 — Model Evaluation

## Train / Validation / Test Split

| Split | Purpose | Typical Size |
|---|---|---|
| Train | Fit model parameters | 60–80% |
| Validation | Tune hyperparameters | 10–20% |
| Test | Final unbiased evaluation | 10–20% |

**Rule:** never look at test set until final evaluation. Repeated peeking leaks information.

## Cross-Validation

### K-Fold CV
1. Split data into k equal folds
2. Train on k-1 folds, evaluate on held-out fold
3. Repeat k times, report mean ± std of metric

- k=5 or k=10 is standard
- Reduces variance of evaluation estimate
- More expensive (k× training runs)

### Stratified K-Fold
Preserves class distribution in each fold. Use for imbalanced classification.

### Time Series CV (Walk-Forward)
Train on past, validate on future — never use future data to predict past.

## Classification Metrics

**Confusion matrix:**
```
               Predicted
               Pos    Neg
Actual  Pos  [ TP  |  FN ]
        Neg  [ FP  |  TN ]
```

| Metric | Formula | When to Use |
|---|---|---|
| Accuracy | (TP+TN)/(TP+TN+FP+FN) | Balanced classes |
| Precision | TP/(TP+FP) | Cost of false positives is high |
| Recall (Sensitivity) | TP/(TP+FN) | Cost of false negatives is high |
| F1 Score | 2·P·R/(P+R) | Imbalanced classes, balance P/R |
| F-beta | (1+β²)·P·R / (β²·P+R) | β<1 favors precision, β>1 favors recall |
| Specificity | TN/(TN+FP) | Medical/screening |
| AUC-ROC | Area under ROC curve | Threshold-independent, balanced |
| AUC-PR | Area under PR curve | Imbalanced data (rare positives) |

**ROC Curve:** TPR vs FPR at varying thresholds.  
**PR Curve:** Precision vs Recall at varying thresholds.

**Key insight:** AUC-ROC can be misleading when classes are very imbalanced — prefer AUC-PR.

## Regression Metrics

| Metric | Formula | Notes |
|---|---|---|
| MSE | (1/n)Σ(y-ŷ)² | Penalizes large errors heavily |
| RMSE | √MSE | Same units as y, interpretable |
| MAE | (1/n)Σ|y-ŷ| | Robust to outliers |
| MAPE | (1/n)Σ|y-ŷ|/|y| × 100% | Percentage error, fails when y≈0 |
| R² | 1 - SS_res/SS_tot | Fraction of variance explained ∈ (-∞,1] |

## Bias-Variance Tradeoff

```
Expected Test Error = Bias² + Variance + Irreducible Noise

Bias: error from wrong assumptions (underfitting)
Variance: sensitivity to training data (overfitting)
```

**Diagnosing:**
- High train error + high val error → underfitting (high bias): use more complex model
- Low train error + high val error → overfitting (high variance): regularize, get more data
- Both low → good fit

## Calibration

A model is **calibrated** if predicted probabilities match empirical frequencies:
P(y=1 | ŷ=0.7) ≈ 0.7

**Reliability diagram (calibration curve):** plot mean predicted probability vs fraction of positives in each bin.

**Calibration methods:**
- Platt scaling: sigmoid fit on predicted scores
- Isotonic regression: non-parametric monotone fit

**Why it matters:** in medical/financial applications, the probability value itself (not just the rank) matters.

## Handling Imbalanced Data

| Strategy | When | Notes |
|---|---|---|
| Oversample minority (SMOTE) | Training only | Synthetic minority samples |
| Undersample majority | Large datasets | Loses data |
| Class weights | Always | Easiest, built into sklearn |
| Threshold adjustment | Post-training | Move decision threshold from 0.5 |
| Collect more data | Always preferred | If feasible |

## Statistical Significance

When comparing two models A and B:
- Use paired t-test on per-fold CV scores
- McNemar's test for classification (comparing error patterns)
- Report confidence intervals, not just point estimates

**A/B test sample size:** n ≈ 16σ²/δ² for detecting effect size δ at 80% power, α=0.05.

## Code

See [code/model_evaluation.py](code/model_evaluation.py) for confusion matrices, ROC/PR curves, calibration plots, and CV.
