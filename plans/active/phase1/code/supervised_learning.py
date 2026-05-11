"""Supervised learning algorithms from scratch + sklearn comparison."""
import numpy as np
from sklearn.datasets import make_classification, make_regression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, mean_squared_error


class LinearRegressionScratch:
    def fit(self, X, y):
        # Add bias column
        X_b = np.column_stack([np.ones(len(X)), X])
        # Normal equations: w = (X^T X)^{-1} X^T y
        self.w = np.linalg.solve(X_b.T @ X_b, X_b.T @ y)
        return self

    def predict(self, X):
        X_b = np.column_stack([np.ones(len(X)), X])
        return X_b @ self.w


class LogisticRegressionScratch:
    def __init__(self, lr=0.1, n_iter=200):
        self.lr = lr
        self.n_iter = n_iter

    def sigmoid(self, z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))

    def fit(self, X, y):
        n, d = X.shape
        self.w = np.zeros(d)
        self.b = 0.0
        for _ in range(self.n_iter):
            z = X @ self.w + self.b
            p = self.sigmoid(z)
            dw = (X.T @ (p - y)) / n
            db = np.mean(p - y)
            self.w -= self.lr * dw
            self.b -= self.lr * db
        return self

    def predict_proba(self, X):
        return self.sigmoid(X @ self.w + self.b)

    def predict(self, X):
        return (self.predict_proba(X) >= 0.5).astype(int)


class KMeansInit:
    """K-Means++ initialization."""
    def __init__(self, k, n_iter=100):
        self.k = k
        self.n_iter = n_iter

    def fit(self, X):
        n = len(X)
        # k-means++ init
        idx = np.random.randint(n)
        centroids = [X[idx]]
        for _ in range(self.k - 1):
            dists = np.min([np.sum((X - c)**2, axis=1) for c in centroids], axis=0)
            probs = dists / dists.sum()
            centroids.append(X[np.random.choice(n, p=probs)])
        self.centroids = np.array(centroids)

        for _ in range(self.n_iter):
            # Assign
            dists = np.array([np.sum((X - c)**2, axis=1) for c in self.centroids])
            labels = np.argmin(dists, axis=0)
            # Update
            new_centroids = np.array([X[labels == k].mean(axis=0) for k in range(self.k)])
            if np.allclose(self.centroids, new_centroids):
                break
            self.centroids = new_centroids
        self.labels_ = labels
        return self


def demo_regression():
    print("=== Linear Regression ===")
    X, y = make_regression(n_samples=200, n_features=5, noise=10, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    model = LinearRegressionScratch().fit(X_train, y_train)
    rmse = np.sqrt(mean_squared_error(y_test, model.predict(X_test)))
    print(f"  Scratch RMSE: {rmse:.3f}")

    ridge = Ridge().fit(X_train, y_train)
    rmse_sklearn = np.sqrt(mean_squared_error(y_test, ridge.predict(X_test)))
    print(f"  sklearn RMSE: {rmse_sklearn:.3f}")


def demo_classification():
    print("\n=== Classification ===")
    X, y = make_classification(n_samples=500, n_features=10, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # Logistic Regression from scratch
    lr_scratch = LogisticRegressionScratch(lr=0.5, n_iter=300).fit(X_train_s, y_train)
    acc_scratch = accuracy_score(y_test, lr_scratch.predict(X_test_s))

    # sklearn models
    models = {
        "Logistic Regression": LogisticRegression(max_iter=500),
        "Random Forest":       RandomForestClassifier(n_estimators=100, random_state=42),
        "Gradient Boosting":   GradientBoostingClassifier(n_estimators=100, random_state=42),
    }

    print(f"  Scratch LR accuracy:       {acc_scratch:.3f}")
    for name, model in models.items():
        model.fit(X_train_s, y_train)
        acc = accuracy_score(y_test, model.predict(X_test_s))
        print(f"  {name:25s}: {acc:.3f}")


def demo_feature_importance():
    print("\n=== Feature Importance (Random Forest) ===")
    X, y = make_classification(n_samples=500, n_features=8, n_informative=4, random_state=0)
    rf = RandomForestClassifier(n_estimators=100, random_state=0).fit(X, y)
    importances = rf.feature_importances_

    print("  Feature importances (sorted):")
    for rank, (idx, imp) in enumerate(sorted(enumerate(importances), key=lambda x: -x[1])):
        print(f"    {rank+1}. feature_{idx}: {imp:.4f}")


if __name__ == "__main__":
    np.random.seed(42)
    demo_regression()
    demo_classification()
    demo_feature_importance()
