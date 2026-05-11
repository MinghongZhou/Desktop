"""Feature engineering: encoding, scaling, imputation, selection, leakage."""
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler, LabelEncoder
from sklearn.impute import SimpleImputer, KNNImputer
from sklearn.feature_selection import (
    SelectKBest, mutual_info_classif, f_classif, RFE
)
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


def demo_encoding():
    print("=== Categorical Encoding ===")
    df = pd.DataFrame({
        "color":  ["red", "blue", "green", "blue", "red", "green"],
        "size":   ["small", "medium", "large", "small", "large", "medium"],
        "target": [1, 0, 1, 0, 1, 0],
    })

    # One-hot encoding (drop_first avoids dummy variable trap)
    ohe = pd.get_dummies(df["color"], prefix="color", drop_first=True)
    print(f"  One-hot (color):\n{ohe.to_string()}\n")

    # Ordinal encoding
    size_map = {"small": 0, "medium": 1, "large": 2}
    df["size_ordinal"] = df["size"].map(size_map)
    print(f"  Ordinal (size): {df['size_ordinal'].tolist()}")

    # Target encoding (use out-of-fold to avoid leakage)
    from sklearn.model_selection import KFold
    df["color_target_enc"] = 0.0
    kf = KFold(n_splits=3, shuffle=True, random_state=0)
    for train_idx, val_idx in kf.split(df):
        means = df.iloc[train_idx].groupby("color")["target"].mean()
        df.iloc[val_idx, df.columns.get_loc("color_target_enc")] = \
            df.iloc[val_idx]["color"].map(means).fillna(df["target"].mean())
    print(f"  Target enc (color): {df['color_target_enc'].round(3).tolist()}")


def demo_scaling():
    print("\n=== Scaling ===")
    np.random.seed(42)
    X = np.array([[100, 0.01], [200, 0.02], [150, 0.015], [10000, 0.001]])

    scalers = {
        "Standard":  StandardScaler(),
        "MinMax":    MinMaxScaler(),
        "Robust":    RobustScaler(),
    }
    for name, scaler in scalers.items():
        X_scaled = scaler.fit_transform(X)
        print(f"  {name:10s}: col0={X_scaled[:,0].round(2)}, col1={X_scaled[:,1].round(2)}")

    # Log transform for skewed data
    X_skewed = np.array([1, 2, 5, 100, 10000, 50000])
    X_log = np.log1p(X_skewed)
    print(f"\n  Log1p transform: {X_log.round(2)}")


def demo_imputation():
    print("\n=== Missing Value Imputation ===")
    np.random.seed(0)
    X = np.random.randn(20, 4)
    mask = np.random.rand(*X.shape) < 0.2
    X_missing = X.copy()
    X_missing[mask] = np.nan

    print(f"  Missing values per feature: {np.isnan(X_missing).sum(axis=0)}")

    for name, imputer in [
        ("Mean",     SimpleImputer(strategy="mean")),
        ("Median",   SimpleImputer(strategy="median")),
        ("KNN (k=3)", KNNImputer(n_neighbors=3)),
    ]:
        X_imp = imputer.fit_transform(X_missing)
        mae = np.mean(np.abs(X[mask] - X_imp[mask]))
        print(f"  {name:12s}: MAE vs true = {mae:.4f}")

    # Add missingness indicator
    X_with_flag = np.column_stack([
        SimpleImputer().fit_transform(X_missing),
        np.isnan(X_missing).astype(float)
    ])
    print(f"  With missing flags: shape {X_with_flag.shape} (4 imputed + 4 flags)")


def demo_feature_selection():
    print("\n=== Feature Selection ===")
    X, y = make_classification(
        n_samples=400, n_features=20, n_informative=5, n_redundant=5, random_state=42
    )
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=0)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(max_iter=500)
    base_score = cross_val_score(model, X_train_s, y_train, cv=5, scoring="roc_auc").mean()

    # Filter: mutual information
    mi_selector = SelectKBest(mutual_info_classif, k=8).fit(X_train_s, y_train)
    X_mi = mi_selector.transform(X_train_s)
    mi_score = cross_val_score(model, X_mi, y_train, cv=5, scoring="roc_auc").mean()

    # Filter: ANOVA F-test
    f_selector = SelectKBest(f_classif, k=8).fit(X_train_s, y_train)
    X_f = f_selector.transform(X_train_s)
    f_score = cross_val_score(model, X_f, y_train, cv=5, scoring="roc_auc").mean()

    # Wrapper: RFE
    rfe = RFE(LogisticRegression(max_iter=500), n_features_to_select=8).fit(X_train_s, y_train)
    X_rfe = rfe.transform(X_train_s)
    rfe_score = cross_val_score(model, X_rfe, y_train, cv=5, scoring="roc_auc").mean()

    print(f"  All 20 features:     AUC = {base_score:.4f}")
    print(f"  Mutual Info (k=8):   AUC = {mi_score:.4f}")
    print(f"  ANOVA F-test (k=8):  AUC = {f_score:.4f}")
    print(f"  RFE (k=8):           AUC = {rfe_score:.4f}")


def demo_pipeline_no_leakage():
    print("\n=== Correct Pipeline (no leakage) ===")
    X, y = make_classification(n_samples=300, n_features=10, random_state=0)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    # WRONG: fit scaler on all data before split
    scaler_wrong = StandardScaler().fit(np.vstack([X_train, X_test]))
    model_wrong = LogisticRegression().fit(scaler_wrong.transform(X_train), y_train)
    score_wrong = model_wrong.score(scaler_wrong.transform(X_test), y_test)

    # CORRECT: fit scaler only on train, apply to test
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  LogisticRegression()),
    ])
    pipeline.fit(X_train, y_train)
    score_correct = pipeline.score(X_test, y_test)

    print(f"  Wrong (leakage):  {score_wrong:.4f}")
    print(f"  Correct (no leak):{score_correct:.4f}")
    print("  (Difference is usually small on this toy data but matters on real data)")


if __name__ == "__main__":
    demo_encoding()
    demo_scaling()
    demo_imputation()
    demo_feature_selection()
    demo_pipeline_no_leakage()
