"""M4: preserve pairs, reject undefined comparisons, and respect the CI confidence."""
import copy

import pytest

pytestmark = pytest.mark.student


def test_resampling_preserves_pairing_under_a_constant_shift():
    from lab9.stats import paired_bootstrap
    difference, low, high = paired_bootstrap([10, 100, 1000, 10000], [13, 103, 1003, 10003])
    assert (difference, low, high) == pytest.approx((-3.0, -3.0, -3.0))


def test_paired_bootstrap_is_reproducible_with_a_fixed_rng():
    from lab9.stats import paired_bootstrap
    args = ([1, 0.5, 0, 0.8], [0.5, 1, 0.5, 0.2])
    assert paired_bootstrap(*args, rng=42) == paired_bootstrap(*args, rng=42)


@pytest.mark.parametrize("left,right", [
    ([], []),
    ([1], [1]),
    ([1, 0], [1]),
    ([[1, 0]], [[1, 0]]),
    ([1, float("nan")], [1, 0]),
    ([1, 0], [1, float("inf")]),
])
def test_invalid_pairs_cannot_silently_become_a_zero_difference(left, right):
    from lab9.stats import paired_bootstrap
    with pytest.raises(ValueError):
        paired_bootstrap(left, right)


@pytest.mark.parametrize("options", [
    {"n_resamples": 0},
    {"n_resamples": True},
    {"confidence": 0.0},
    {"confidence": 1.0},
    {"confidence": float("nan")},
])
def test_invalid_bootstrap_options_are_rejected_even_for_identical_samples(options):
    from lab9.stats import paired_bootstrap
    with pytest.raises(ValueError):
        paired_bootstrap([1, 0], [1, 0], **options)


def test_gate_decision_uses_the_confidence_selected_in_the_spec():
    from lab9.gate import check
    base = {"manifest": {"eval_set_sha": "same"}, "metrics": {"quality": 1.0},
            "rows": [{"item_id": f"E-{i}", "seed": 11, "quality": True} for i in range(5)]}
    pr = copy.deepcopy(base)
    pr["metrics"]["quality"] = 0.6
    for row in pr["rows"][:2]:
        row["quality"] = False
    spec = {"metrics": [{"id": "quality", "kind": "capability", "blocking": True,
                         "threshold": {"no_significant_drop": True}}],
            "bootstrap": {"confidence": 0.5, "rng": 2027, "n_resamples": 1000}}
    assert check(pr, base, spec)[0] == ["quality"]
    spec["bootstrap"]["confidence"] = 0.99
    assert check(pr, base, spec)[0] == []
