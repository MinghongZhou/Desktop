# 08 — Feature Engineering

## Encoding Categorical Variables

### Ordinal Encoding
Map categories to integers: {low, medium, high} → {0, 1, 2}  
Use only when there is a natural order.

### One-Hot Encoding
Create binary column per category. Drop one to avoid multicollinearity (dummy variable trap).
- Risk: high cardinality → very wide feature space

### Target Encoding (Mean Encoding)
Replace category with mean of target within that category.
- Powerful for high-cardinality categoricals (e.g., zip codes)
- **Risk of leakage**: must use out-of-fold estimates during training

### Other Encodings
- **Binary encoding**: encode integer as binary bits — compact
- **Frequency encoding**: replace with count/frequency in dataset
- **Embedding**: learn dense representation (used in deep learning)

## Scaling

| Method | Formula | When to Use |
|---|---|---|
| Standardization (Z-score) | (x - μ) / σ | Most cases; required for PCA, SVM, kNN, linear models |
| Min-Max | (x - min) / (max - min) | When bounded range needed [0,1]; sensitive to outliers |
| Robust Scaler | (x - median) / IQR | When outliers are present |
| Log Transform | log(x + 1) | Right-skewed data, multiplicative relationships |
| Power Transform (Box-Cox) | (xλ - 1) / λ | Make distribution more Gaussian |

**Note:** Tree-based models (RF, XGBoost) do **not** require scaling. Neural networks and distance-based models do.

## Imputation (Missing Values)

**First: understand why data is missing**
- MCAR: Missing Completely At Random — safe to impute
- MAR: Missing At Random — depends on observed data
- MNAR: Missing Not At Random — may be informative (flag it)

| Strategy | Best For |
|---|---|
| Mean/median imputation | Numerical, MCAR, simple baseline |
| Mode imputation | Categorical |
| KNN imputation | When similar samples exist |
| Iterative imputation (MICE) | Best statistical approach |
| Indicator + imputation | MNAR — add binary "was_missing" column |
| Model-based | Use other features to predict missing values |

## Feature Selection

### Filter Methods (model-independent)
- Correlation with target (Pearson, Spearman)
- Mutual information with target
- Chi-squared test (categorical features vs target)
- Variance threshold (remove near-zero variance features)

### Wrapper Methods (model-in-the-loop)
- Forward selection: add features greedily
- Backward elimination: remove features greedily
- Recursive Feature Elimination (RFE): rank by model coefficients/importances

### Embedded Methods (during model training)
- Lasso: drives unimportant feature weights to zero
- Tree feature importance: mean decrease in impurity or permutation importance
- Regularization in neural networks

## Feature Creation

### Numerical Features
- Polynomial features: x₁², x₁x₂ — capture interactions
- Ratio features: revenue/users, click/impression
- Binning/bucketing: convert continuous to categorical
- Log/sqrt transforms to compress scale

### Temporal Features (from datetime)
- Hour of day, day of week, month, quarter
- Days since event, time to event
- Rolling statistics: 7-day average, 30-day max

### Text Features
- Bag of words (CountVectorizer)
- TF-IDF: term frequency × inverse document frequency
- N-grams: bigrams, trigrams capture phrases
- Embeddings: word2vec, GloVe, BERT sentence embeddings

### Interaction Features
- Explicit: feature_A × feature_B
- Tree-based models learn interactions implicitly
- Manual domain-driven interactions (e.g., age × income)

## Feature Engineering Pipeline

```
Raw Data
   ↓
Handle missing values (impute or flag)
   ↓
Encode categoricals
   ↓
Create new features
   ↓
Scale numerical features
   ↓
Select features
   ↓
Model
```

**Always fit transformers on train set only, then apply to val/test.** Fitting on the full dataset leaks information (data leakage).

## Leakage

**Feature leakage**: using information not available at prediction time.
- Future data leaking into past (time series)
- Target included in features
- Post-event features (e.g., "was refunded" in fraud detection)

**Train-test leakage**: fitting preprocessing (scalers, encoders) on the full dataset before splitting.

## Code

See [code/feature_engineering.py](code/feature_engineering.py) for encoding, scaling, imputation, and selection examples.
