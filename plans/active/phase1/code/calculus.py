"""Calculus concepts for ML: gradients, backprop, gradient descent."""
import numpy as np


def numerical_gradient(f, x, eps=1e-5):
    grad = np.zeros_like(x, dtype=float)
    for i in range(len(x)):
        x_plus = x.copy().astype(float); x_plus[i] += eps
        x_minus = x.copy().astype(float); x_minus[i] -= eps
        grad[i] = (f(x_plus) - f(x_minus)) / (2 * eps)
    return grad


def gradient_check():
    """Verify analytical gradient against numerical gradient."""
    def f(x):
        return x[0]**2 + 3*x[1]**2 - x[0]*x[1]

    def analytical_grad(x):
        return np.array([2*x[0] - x[1], 6*x[1] - x[0]])

    x = np.array([2.0, -1.0])
    num_grad = numerical_gradient(f, x)
    ana_grad = analytical_grad(x)

    print("Gradient check:")
    print(f"  Numerical:  {num_grad}")
    print(f"  Analytical: {ana_grad}")
    print(f"  Max diff:   {np.max(np.abs(num_grad - ana_grad)):.2e}")


class SimpleNeuralNet:
    """Single hidden layer net with sigmoid activation — backprop from scratch."""

    def __init__(self, n_in, n_hidden, n_out):
        np.random.seed(42)
        self.W1 = np.random.randn(n_in, n_hidden) * 0.1
        self.b1 = np.zeros(n_hidden)
        self.W2 = np.random.randn(n_hidden, n_out) * 0.1
        self.b2 = np.zeros(n_out)

    def sigmoid(self, z):
        return 1 / (1 + np.exp(-np.clip(z, -500, 500)))

    def forward(self, X):
        self.X = X
        self.z1 = X @ self.W1 + self.b1
        self.a1 = self.sigmoid(self.z1)
        self.z2 = self.a1 @ self.W2 + self.b2
        self.a2 = self.sigmoid(self.z2)
        return self.a2

    def loss(self, y_pred, y_true):
        eps = 1e-8
        return -np.mean(y_true * np.log(y_pred + eps) + (1 - y_true) * np.log(1 - y_pred + eps))

    def backward(self, y_true):
        n = len(y_true)
        # Output layer
        dL_da2 = (self.a2 - y_true) / n
        dL_dz2 = dL_da2 * self.a2 * (1 - self.a2)  # sigmoid derivative
        dL_dW2 = self.a1.T @ dL_dz2
        dL_db2 = dL_dz2.sum(axis=0)
        # Hidden layer
        dL_da1 = dL_dz2 @ self.W2.T
        dL_dz1 = dL_da1 * self.a1 * (1 - self.a1)
        dL_dW1 = self.X.T @ dL_dz1
        dL_db1 = dL_dz1.sum(axis=0)
        return dL_dW1, dL_db1, dL_dW2, dL_db2

    def train_step(self, X, y, lr=0.1):
        y_pred = self.forward(X)
        loss = self.loss(y_pred, y)
        grads = self.backward(y)
        self.W1 -= lr * grads[0]
        self.b1 -= lr * grads[1]
        self.W2 -= lr * grads[2]
        self.b2 -= lr * grads[3]
        return loss


def gradient_descent_demo():
    """Minimize f(x,y) = x² + y² (trivial, answer is (0,0))."""
    f = lambda x: x[0]**2 + x[1]**2
    grad_f = lambda x: np.array([2*x[0], 2*x[1]])

    x = np.array([3.0, -2.0])
    lr = 0.1

    print("\nGradient descent on f(x,y) = x² + y²:")
    for step in range(20):
        if step % 5 == 0:
            print(f"  Step {step:2d}: x={x}, f(x)={f(x):.4f}")
        x = x - lr * grad_f(x)
    print(f"  Final:   x={x.round(6)}, f(x)={f(x):.2e}")


def backprop_demo():
    np.random.seed(0)
    X = np.random.randn(100, 3)
    y = (X[:, 0] + X[:, 1] > 0).astype(float).reshape(-1, 1)

    net = SimpleNeuralNet(3, 8, 1)
    print("\nTraining neural net (backprop from scratch):")
    for epoch in range(0, 201, 50):
        loss = net.train_step(X, y)
        if epoch % 50 == 0:
            acc = ((net.forward(X) > 0.5) == y).mean()
            print(f"  Epoch {epoch:3d}: loss={loss:.4f}, acc={acc:.2%}")


if __name__ == "__main__":
    gradient_check()
    gradient_descent_demo()
    backprop_demo()
