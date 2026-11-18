"""M6: combinatorial probabilities, invalid counts, and the derived gate metric."""
import itertools

import pytest

pytestmark = pytest.mark.student


def test_estimators_match_enumerating_every_subset():
    from lab9.stats import pass_at_k, pass_hat_k
    for n in range(1, 7):
        for c in range(n + 1):
            for k in range(1, n + 1):
                subsets = list(itertools.combinations(range(n), k))
                at_least_one = sum(any(index < c for index in group) for group in subsets) / len(subsets)
                every_one = sum(all(index < c for index in group) for group in subsets) / len(subsets)
                assert pass_at_k(n, c, k) == pytest.approx(at_least_one)
                assert pass_hat_k(n, c, k) == pytest.approx(every_one)
                assert pass_hat_k(n, c, k) <= c / n <= pass_at_k(n, c, k)


@pytest.mark.parametrize("counts", [
    (0, 0, 1), (-1, 0, 1), (5, -1, 1), (5, 6, 1),
    (5, 2, 0), (5, 2, 6), (5.0, 2, 1), (5, 2.5, 1),
    (5, 2, 1.0), (True, 1, 1), (5, False, 1), (5, 2, True),
])
def test_estimators_reject_invalid_counts(counts):
    from lab9.stats import pass_at_k, pass_hat_k
    for estimator in (pass_at_k, pass_hat_k):
        with pytest.raises(ValueError):
            estimator(*counts)


def test_rare_success_probability_is_not_rounded_down_to_zero():
    from lab9.stats import pass_at_k, pass_hat_k
    assert pass_at_k(10**18, 1, 1) == 1e-18
    assert pass_hat_k(10**18, 1, 1) == 1e-18


def test_numpy_integer_counts_are_supported():
    import numpy as np
    from lab9.stats import pass_at_k, pass_hat_k
    assert pass_at_k(np.int64(5), np.int64(4), np.int64(5)) == 1.0
    assert pass_hat_k(np.int64(5), np.int64(4), np.int64(5)) == 0.0


def rows_for(pass_counts):
    return [{"item_id": f"E-{item}", "seed": seed, "pass_rate": seed < count, "cost": 0.0, "slices": []}
            for item, count in enumerate(pass_counts) for seed in range(5)]


def test_aggregate_uses_per_item_unbiased_estimates():
    from lab9.eval import aggregate
    metrics = aggregate(rows_for([4, 5]), ["pass_rate"], k_values=[1, 3, 5])
    assert metrics["pass_at_1"] == metrics["pass_hat_1"] == metrics["pass_rate"] == 0.9
    assert metrics["pass_at_3"] == metrics["pass_at_5"] == 1.0
    assert metrics["pass_hat_3"] == 0.7
    assert metrics["pass_hat_5"] == metrics["pass_5"] == 0.5


def test_fewer_than_k_trials_do_not_produce_a_reliability_estimate():
    from lab9.eval import aggregate
    metrics = aggregate(rows_for([5])[:2], ["pass_rate"], k_values=[5])
    assert metrics["pass_at_5"] is None and metrics["pass_hat_5"] is None


def test_pass_hat_blocks_unreliability_that_average_and_ci_allow():
    from lab9.eval import aggregate
    from lab9.gate import check

    def report(counts):
        rows = rows_for(counts)
        return {"manifest": {"eval_set_sha": "same", "items": 3, "seeds": list(range(5))},
                "rows": rows, "metrics": aggregate(rows, ["pass_rate"], k_values=[5]), "evaluator_failures": []}

    baseline, candidate = report([5, 5, 5]), report([4, 4, 5])
    spec = {"metrics": [
        {"id": "pass_rate", "kind": "capability", "blocking": True,
         "threshold": {"min": 0.85, "no_significant_drop": True}},
        {"id": "pass_hat_5", "kind": "capability", "blocking": True, "threshold": {"min": 0.8}},
    ], "bootstrap": {"n_resamples": 1000, "rng": 2027, "confidence": 0.95}}
    assert candidate["metrics"]["pass_rate"] == 0.8667
    assert candidate["metrics"]["pass_hat_5"] == 0.3333
    assert all("pass_hat_5" not in row for row in candidate["rows"])
    assert check(candidate, baseline, spec)[0] == ["pass_hat_5"]
