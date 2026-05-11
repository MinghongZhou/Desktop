"""Model evaluation: metrics, cross-validation, calibration, imbalanced data."""
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix,
    mean_squared_error, mean_absolute_error, r2_score,
)
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.preprocessing import StandardScaler


def compute_classification_metrics(y_true, y_pred, y_prob):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy":   accuracy_score(y_true, y_pred),
        "precision":  precision_score(y_true, y_pred, zero_division=0),
        "recall":     recall_score(y_true, y_pred, zero_division=0),
        "f1":         f1_score(y_true, y_pred, zero_division=0),
        "specificity": tn / (tn + fp) if (tn + fp) > 0 else 0,
        "roc_auc":    roc_auc_score(y_true, y_prob),
        "pr_auc":     average_precision_score(y_true, y_prob),
    }


def demo_classification_metrics():
    print("=== Classification Metrics ===")
    X, y = make_classification(n_samples=500, n_features=10, random_state=42)
    X = StandardScaler().fit_transform(X)

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    model = LogisticRegression().fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    metrics = compute_classification_metrics(y_test, y_pred, y_prob)
    for name, val in metrics.items():
        print(f"  {name:12s}: {val:.4f}")

    print(f"\n  Confusion matrix:\n{confusion_matrix(y_test, y_pred)}")


def demo_cross_validation():
    print("\n=== Stratified K-Fold Cross-Validation ===")
    X, y = make_classification(n_samples=500, n_features=10, random_state=42)
    X = StandardScaler().fit_transform(X)

    models = {
        "Logistic Regression": LogisticRegression(),
        "Random Forest":       RandomForestClassifier(n_estimators=50, random_state=0),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for name, model in models.items():
        scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
        print(f"  {name:25s}: AUC = {scores.mean():.4f} ± {scores.std():.4f}")


def demo_imbalanced():
    print("\n=== Imbalanced Classification ===")
    X, y = make_classification(
        n_samples=1000, n_features=10, weights=[0.95, 0.05], random_state=42
    )
    X = StandardScaler().fit_transform(X)

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2,
                                                          stratify=y, random_state=0)

    for strategy, kwargs in [
        ("No weighting",    {}),
        ("Class weights",   {"class_weight": "balanced"}),
    ]:
        model = LogisticRegression(**kwargs).fit(X_train, y_train)
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1]
        print(f"  {strategy:15s}: acc={accuracy_score(y_test, y_pred):.3f}, "
              f"recall={recall_score(y_test, y_pred, zero_division=0):.3f}, "
              f"pr_auc={average_precision_score(y_test, y_prob):.3f}")


def demo_calibration():
    print("\n=== Calibration ===")
    X, y = make_classification(n_samples=1000, n_features=10, random_state=42)
    X = StandardScaler().fit_transform(X)

    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=0)

    rf = RandomForestClassifier(n_estimators=50, random_state=0).fit(X_train, y_train)
    rf_cal = CalibratedClassifierCV(
        RandomForestClassifier(n_estimators=50, random_state=0), cv=5, method="isotonic"
    ).fit(X_train, y_train)

    for name, model in [("RF uncal", rf), ("RF calibrated", rf_cal)]:
        prob = model.predict_proba(X_test)[:, 1]
        frac_pos, mean_pred = calibration_curve(y_test, prob, n_bins=5)
        max_calib_err = np.max(np.abs(frac_pos - mean_pred))
        print(f"  {name:15s}: max calibration error = {max_calib_err:.4f}")


def demo_regression_metrics():
    print("\n=== Regression Metrics ===")
    np.random.seed(42)
    y_true = np.random.randn(100) * 10 + 50
    y_pred_good = y_true + np.random.randn(100) * 2
    y_pred_bad  = y_true + np.random.randn(100) * 8

    for name, y_pred in [("Good predictions", y_pred_good), ("Bad predictions", y_pred_bad)]:
        mse = mean_squared_error(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)
        print(f"  {name:20s}: RMSE={np.sqrt(mse):.3f}, MAE={mae:.3f}, R²={r2:.3f}")


if __name__ == "__main__":
    demo_classification_metrics()
    demo_cross_validation()
    demo_imbalanced()
    demo_calibration()
    demo_regression_metrics()
