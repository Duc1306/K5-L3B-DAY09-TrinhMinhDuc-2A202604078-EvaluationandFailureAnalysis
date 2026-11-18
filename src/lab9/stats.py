"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math
from numbers import Integral

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must contain the same number of labels")
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for expected, predicted in zip(human, judge):
        if expected not in ("PASS", POS) or predicted not in ("PASS", POS):
            raise ValueError("labels must be PASS or FAIL")
        if expected == POS:
            key = "tp" if predicted == POS else "fn"
        else:
            key = "fp" if predicted == POS else "tn"
        counts[key] += 1
    return counts


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    """Precision and recall for finding FAIL; a zero denominator returns 0.0."""
    cm = confusion(human, judge)
    predicted_fail = cm["tp"] + cm["fp"]
    actual_fail = cm["tp"] + cm["fn"]
    return (cm["tp"] / predicted_fail if predicted_fail else 0.0,
            cm["tp"] / actual_fail if actual_fail else 0.0)


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa is undefined without labels")
    # Keep the expected-agreement numerator integral so p_e == 1 is exact.
    expected = ((cm["tp"] + cm["fn"]) * (cm["tp"] + cm["fp"])
                + (cm["tn"] + cm["fp"]) * (cm["tn"] + cm["fn"]))
    denominator = n * n - expected
    if denominator == 0:
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (n * (cm["tp"] + cm["tn"]) - expected) / denominator


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct failure prevalence; clip to [0, 1], reject undefined correction."""
    for name, value in (("observed_rate", observed_rate), ("sensitivity", sensitivity),
                        ("specificity", specificity)):
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be a finite probability in [0, 1]")
    denominator = sensitivity + specificity - 1.0
    if denominator == 0.0:
        raise ValueError("Rogan-Gladen is undefined when sensitivity + specificity = 1")
    corrected = (observed_rate + specificity - 1.0) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    left, right = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if left.ndim != 1 or right.ndim != 1 or left.shape != right.shape or len(left) < 2:
        raise ValueError("paired bootstrap needs equal one-dimensional samples with at least two items")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("paired bootstrap samples must be finite")
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, int) or n_resamples < 1:
        raise ValueError("n_resamples must be a positive integer")
    if not math.isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if np.array_equal(left, right):
        return 0.0, 0.0, 0.0

    def mean_difference(x, y, axis=-1):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    result = bootstrap((left, right), mean_difference, paired=True, vectorized=True,
                       method="percentile", n_resamples=n_resamples, confidence_level=confidence,
                       rng=np.random.default_rng(rng))
    return (float(np.mean(left) - np.mean(right)),
            float(result.confidence_interval.low), float(result.confidence_interval.high))


def _trial_counts(n: int, c: int, k: int) -> tuple[int, int, int]:
    """Validate counts before computing either without-replacement estimator."""
    if any(isinstance(value, bool) or not isinstance(value, Integral) for value in (n, c, k)):
        raise ValueError("n, c, and k must be integer counts")
    n, c, k = int(n), int(c), int(k)
    if n < 1 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("require n >= 1, 0 <= c <= n, and 1 <= k <= n")
    return n, c, k


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    n, c, k = _trial_counts(n, c, k)
    total = math.comb(n, k)
    # Subtract integers before dividing to avoid cancellation for rare successes.
    return (total - math.comb(n - c, k)) / total


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    n, c, k = _trial_counts(n, c, k)
    return math.comb(c, k) / math.comb(n, k)
