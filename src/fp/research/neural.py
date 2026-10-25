"""N2 (LSTM) and N3 (Transformer) for home, draw, away, written in JAX (Amendment 1).

Both read each club's last matches (fp.research.sequences), turn each club's history into one
vector, join the two vectors with the match features (fp.features.ml_features.FEATURES), and
pass them through one 32-unit layer to the three outcomes.

Training (Amendment 1, items 1 and 2): Adam with decoupled weight decay 0.0001, learning rate
0.001, batches of 256, dropout 0.2, at most 60 passes; the latest 10% of the training matches
(in kickoff order) are held back, and training stops after 5 passes without improvement there,
keeping the best pass. Five seeds (1 to 5) are trained and their probabilities averaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import pandas as pd

LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
BATCH = 256
MAX_PASSES = 60
PATIENCE = 5
DROPOUT = 0.2
DENSE = 32
HEADS = 2
LAYERS = 2
SEEDS = (1, 2, 3, 4, 5)
VALID_SHARE = 0.10

Params = dict[str, Any]


def init_params(kind: str, n_seq: int, n_match: int, size: int, length: int,
                key: Any) -> Params:
    keys = iter(jax.random.split(key, 64))

    def glorot(shape: tuple[int, int]) -> Any:
        lim = float(np.sqrt(6.0 / (shape[0] + shape[1])))
        return jax.random.uniform(next(keys), shape, minval=-lim, maxval=lim)

    p: Params = {}
    if kind == "lstm":
        p["wx"] = glorot((n_seq, 4 * size))
        p["wh"] = glorot((size, 4 * size))
        p["b"] = jnp.zeros(4 * size).at[size:2 * size].set(1.0)  # forget gate starts open
    elif kind == "transformer":
        p["proj"] = glorot((n_seq, size))
        p["pos"] = 0.02 * jax.random.normal(next(keys), (length, size))
        for layer in range(LAYERS):
            for name in ("q", "k", "v", "o"):
                p[f"l{layer}_{name}"] = glorot((size, size))
            p[f"l{layer}_ff1"] = glorot((size, 2 * size))
            p[f"l{layer}_ff1b"] = jnp.zeros(2 * size)
            p[f"l{layer}_ff2"] = glorot((2 * size, size))
            p[f"l{layer}_ff2b"] = jnp.zeros(size)
            for ln in ("ln1", "ln2"):
                p[f"l{layer}_{ln}g"] = jnp.ones(size)
                p[f"l{layer}_{ln}b"] = jnp.zeros(size)
    else:
        raise ValueError(kind)
    p["d1"] = glorot((2 * size + n_match, DENSE))
    p["d1b"] = jnp.zeros(DENSE)
    p["out"] = glorot((DENSE, 3))
    p["outb"] = jnp.zeros(3)
    return p


def _dropout(x: Any, key: Any, train: bool) -> Any:
    if not train:
        return x
    keep = jax.random.bernoulli(key, 1.0 - DROPOUT, x.shape)
    return jnp.where(keep, x / (1.0 - DROPOUT), 0.0)


def _lstm(p: Params, x: Any, m: Any) -> Any:
    """Final hidden state; a masked (empty) step leaves the state unchanged."""
    size = p["wh"].shape[0]
    batch = x.shape[0]

    def step(carry: Any, inputs: Any) -> Any:
        h, c = carry
        xt, mt = inputs
        z = xt @ p["wx"] + h @ p["wh"] + p["b"]
        i, f, g, o = jnp.split(z, 4, axis=-1)
        c_new = jax.nn.sigmoid(f) * c + jax.nn.sigmoid(i) * jnp.tanh(g)
        h_new = jax.nn.sigmoid(o) * jnp.tanh(c_new)
        mt = mt[:, None]
        return (mt * h_new + (1 - mt) * h, mt * c_new + (1 - mt) * c), None

    start = (jnp.zeros((batch, size)), jnp.zeros((batch, size)))
    (h, _), _ = jax.lax.scan(step, start, (jnp.swapaxes(x, 0, 1), jnp.swapaxes(m, 0, 1)))
    return h


def _layer_norm(x: Any, g: Any, b: Any) -> Any:
    mu = x.mean(-1, keepdims=True)
    return g * (x - mu) / jnp.sqrt(x.var(-1, keepdims=True) + 1e-5) + b


def _transformer(p: Params, x: Any, m: Any, key: Any, train: bool) -> Any:
    """Mean of the encoded matches the club actually played (zero if it has none)."""
    batch, length, _ = x.shape
    h = x @ p["proj"] + p["pos"][None, :length]
    size = h.shape[-1]
    d = size // HEADS
    keys = jax.random.split(key, 2 * LAYERS)
    visible = m[:, None, None, :] > 0
    for layer in range(LAYERS):
        def heads(w: Any, h: Any = h) -> Any:
            return (h @ w).reshape(batch, length, HEADS, d).transpose(0, 2, 1, 3)
        q, k, v = (heads(p[f"l{layer}_{n}"]) for n in ("q", "k", "v"))
        scores = jnp.where(visible, q @ k.transpose(0, 1, 3, 2) / np.sqrt(d), -1e9)
        att = jax.nn.softmax(scores, axis=-1) @ v
        att = att.transpose(0, 2, 1, 3).reshape(batch, length, size) @ p[f"l{layer}_o"]
        h = _layer_norm(h + _dropout(att, keys[2 * layer], train),
                        p[f"l{layer}_ln1g"], p[f"l{layer}_ln1b"])
        ff = jax.nn.relu(h @ p[f"l{layer}_ff1"] + p[f"l{layer}_ff1b"])
        ff = ff @ p[f"l{layer}_ff2"] + p[f"l{layer}_ff2b"]
        h = _layer_norm(h + _dropout(ff, keys[2 * layer + 1], train),
                        p[f"l{layer}_ln2g"], p[f"l{layer}_ln2b"])
    count = m.sum(1, keepdims=True)
    return (h * m[..., None]).sum(1) / jnp.maximum(count, 1.0)


def forward(p: Params, kind: str, xs: Any, ms: Any, feats: Any, key: Any, train: bool) -> Any:
    """Logits (batch, 3). xs: (batch, 2 clubs, length, 11); ms: (batch, 2, length)."""
    batch, _, length, n_seq = xs.shape
    x = xs.reshape(batch * 2, length, n_seq)
    m = ms.reshape(batch * 2, length)
    k1, k2, k3 = jax.random.split(key, 3)
    enc = _lstm(p, x, m) if kind == "lstm" else _transformer(p, x, m, k1, train)
    z = jnp.concatenate([enc.reshape(batch, -1), feats], axis=-1)
    z = jax.nn.relu(_dropout(z, k2, train) @ p["d1"] + p["d1b"])
    return _dropout(z, k3, train) @ p["out"] + p["outb"]


def _cross_entropy(logits: Any, y: Any) -> Any:
    logp = jax.nn.log_softmax(logits)
    return -jnp.take_along_axis(logp, y[:, None], axis=1).mean()


@cache
def _compiled(kind: str) -> tuple[Any, Any, Any]:
    """Jitted training step, held-back loss and prediction for one network kind."""

    def loss(p: Params, xs: Any, ms: Any, fs: Any, y: Any, key: Any) -> Any:
        return _cross_entropy(forward(p, kind, xs, ms, fs, key, True), y)

    @jax.jit
    def step(p: Params, mom: Params, vel: Params, t: Any, xs: Any, ms: Any, fs: Any, y: Any,
             key: Any) -> tuple[Params, Params, Params]:
        grads = jax.grad(loss)(p, xs, ms, fs, y, key)
        mom = jax.tree_util.tree_map(lambda a, g: 0.9 * a + 0.1 * g, mom, grads)
        vel = jax.tree_util.tree_map(lambda a, g: 0.999 * a + 0.001 * g * g, vel, grads)
        c1, c2 = 1 - 0.9 ** t, 1 - 0.999 ** t
        p = jax.tree_util.tree_map(
            lambda w, a, b: w - LEARNING_RATE * (a / c1 / (jnp.sqrt(b / c2) + 1e-8)
                                                 + WEIGHT_DECAY * w), p, mom, vel)
        return p, mom, vel

    @jax.jit
    def held_back(p: Params, xs: Any, ms: Any, fs: Any, y: Any) -> Any:
        return _cross_entropy(forward(p, kind, xs, ms, fs, jax.random.PRNGKey(0), False), y)

    @jax.jit
    def predict(p: Params, xs: Any, ms: Any, fs: Any) -> Any:
        return jax.nn.softmax(forward(p, kind, xs, ms, fs, jax.random.PRNGKey(0), False))

    return step, held_back, predict


def train_one(kind: str, size: int, xs: np.ndarray, ms: np.ndarray, fs: np.ndarray,
              y: np.ndarray, seed: int) -> Params:
    """One network on rows already in kickoff order; the last 10% are held back."""
    n = len(y)
    n_valid = max(1, int(round(n * VALID_SHARE)))
    n_train = n - n_valid
    step, held_back, _ = _compiled(kind)
    key = jax.random.PRNGKey(seed)
    key, sub = jax.random.split(key)
    p = init_params(kind, xs.shape[-1], fs.shape[-1], size, xs.shape[2], sub)
    mom = jax.tree_util.tree_map(jnp.zeros_like, p)
    vel = jax.tree_util.tree_map(jnp.zeros_like, p)
    valid = (xs[n_train:], ms[n_train:], fs[n_train:], y[n_train:])
    batch = min(BATCH, n_train)
    rng = np.random.default_rng(seed)
    best, best_p, stale, t = np.inf, p, 0, 0
    for _ in range(MAX_PASSES):
        order = rng.permutation(n_train)
        for b in range(n_train // batch):
            idx = order[b * batch:(b + 1) * batch]
            t += 1
            key, sub = jax.random.split(key)
            p, mom, vel = step(p, mom, vel, jnp.float32(t), xs[idx], ms[idx], fs[idx], y[idx],
                               sub)
        score = float(held_back(p, *valid))
        if score < best - 1e-6:
            best, best_p, stale = score, p, 0
        else:
            stale += 1
            if stale >= PATIENCE:
                break
    return best_p


@dataclass
class SeqNet:
    """A sequence model with its settings: {"size": 16 or 32, "length": 5 or 10}."""

    kind: str
    params: dict[str, int]
    features: list[str]
    nets: list[Params] = field(default_factory=list)
    scale: dict[str, Any] = field(default_factory=dict)

    def _inputs(self, rows: pd.DataFrame, seq: np.ndarray,
                mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        length = self.params["length"]
        xs = seq[:, :, -length:, :]
        ms = mask[:, :, -length:]
        xs = np.where(ms[..., None] > 0, (xs - self.scale["seq_mu"]) / self.scale["seq_sd"], 0.0)
        fs = rows[self.features].to_numpy(dtype=float)
        fs = np.where(np.isnan(fs), self.scale["median"], fs)
        fs = (fs - self.scale["mu"]) / self.scale["sd"]
        return xs.astype(np.float32), ms.astype(np.float32), fs.astype(np.float32)

    def fit(self, rows: pd.DataFrame, seq: np.ndarray, mask: np.ndarray) -> SeqNet:
        order = np.argsort(rows["kickoff_utc"].to_numpy(), kind="stable")
        rows, seq, mask = rows.iloc[order], seq[order], mask[order]
        length = self.params["length"]
        fs = rows[self.features].to_numpy(dtype=float)
        median = np.nanmedian(fs, axis=0)
        filled = np.where(np.isnan(fs), median, fs)
        seen = mask[:, :, -length:].reshape(-1) > 0
        flat = seq[:, :, -length:, :].reshape(-1, seq.shape[-1])[seen]
        self.scale = {"median": median, "mu": filled.mean(0), "sd": filled.std(0) + 1e-6,
                      "seq_mu": flat.mean(0), "seq_sd": flat.std(0) + 1e-6}
        xs, ms, fs_in = self._inputs(rows, seq, mask)
        y = rows["outcome"].to_numpy().astype(np.int32)
        self.nets = [train_one(self.kind, self.params["size"], xs, ms, fs_in, y, s)
                     for s in SEEDS]
        return self

    def predict(self, rows: pd.DataFrame, seq: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Probabilities home, draw, away: the average of the five seeds."""
        _, _, predict = _compiled(self.kind)
        xs, ms, fs = self._inputs(rows, seq, mask)
        return np.mean([np.asarray(predict(net, xs, ms, fs)) for net in self.nets], axis=0)
