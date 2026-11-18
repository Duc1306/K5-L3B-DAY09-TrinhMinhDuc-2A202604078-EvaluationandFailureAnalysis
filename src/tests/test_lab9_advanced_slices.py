"""M5: slice decisions use paired items, configured metrics, and explicit floors."""
import copy

import pytest

pytestmark = pytest.mark.student


def report(values, *, name="priority", metric="quality"):
    return {"rows": [{"item_id": f"E-{i}", "seed": seed, "slices": [name], metric: value}
                     for i, item in enumerate(values) for seed, value in enumerate(item)]}


def spec(*, minimum=0.9, paired=False, blocking=True, confidence=0.95):
    return {"slices": [{"name": "priority", "metric": "quality", "min": minimum,
                        "no_significant_drop": paired, "blocking": blocking}],
            "bootstrap": {"confidence": confidence, "rng": 2027, "n_resamples": 1000}}


def test_slice_floor_uses_per_item_means_instead_of_weighting_longer_seed_lists():
    from lab9.gate import slice_check
    candidate = report([[False], [True, True, True, True]])
    assert slice_check(candidate, candidate, spec(minimum=0.7))[0] == ["slice:priority/quality"]


def test_slice_pairing_blocks_a_drop_even_when_the_absolute_floor_is_met():
    from lab9.gate import slice_check
    assert slice_check(report([[0.8], [0.8], [0.8]]), report([[1], [1], [1]]),
                       spec(minimum=0.5, paired=True))[0] == ["slice:priority/quality"]


def test_slice_comparison_accepts_an_identical_baseline_and_exact_floor():
    from lab9.gate import slice_check
    baseline = report([[0.8], [1.0]])
    assert slice_check(baseline, baseline, spec(paired=True))[0] == []


def test_slice_logic_accepts_arbitrary_names_and_metric_ids():
    from lab9.gate import slice_check
    rule = {"slices": [{"name": "unseen_group", "metric": "refund_quality", "min": 0.8, "blocking": True}]}
    candidate = report([[1], [0]], name="unseen_group", metric="refund_quality")
    assert slice_check(candidate, candidate, rule)[0] == ["slice:unseen_group/refund_quality"]


def test_nonblocking_slice_reports_a_warning_without_blocking():
    from lab9.gate import slice_check
    blocked, lines = slice_check(report([[0], [0]]), report([[1], [1]]), spec(blocking=False))
    assert blocked == [] and any("warn" in line for line in lines)


def test_missing_slice_is_blocked_instead_of_vacuously_passing():
    from lab9.gate import slice_check
    assert slice_check({"rows": []}, report([[1], [1]]), spec())[0] == ["slice:priority/quality"]


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_missing_or_nonfinite_slice_values_are_blocked(bad):
    from lab9.gate import slice_check
    assert slice_check(report([[1], [bad]]), report([[1], [1]]), spec())[0] == ["slice:priority/quality"]


def test_paired_slice_refuses_a_different_item_set():
    from lab9.gate import slice_check
    assert slice_check(report([[1]]), report([[1], [1]]), spec(paired=True))[0] == ["slice:priority/quality"]


def test_paired_slice_requires_a_usable_baseline_metric():
    from lab9.gate import slice_check
    assert slice_check(report([[1], [1]]), report([[1], [None]]), spec(paired=True))[0] == ["slice:priority/quality"]


def test_single_item_cannot_produce_a_paired_confidence_interval():
    from lab9.gate import slice_check
    assert slice_check(report([[1]]), report([[1]]), spec(paired=True))[0] == ["slice:priority/quality"]


def test_slice_bootstrap_respects_the_configured_confidence():
    from lab9.gate import slice_check
    baseline = report([[True]] * 5)
    candidate = report([[False], [False], [True], [True], [True]])
    assert slice_check(candidate, baseline, spec(minimum=0.5, paired=True, confidence=0.5))[0]
    assert slice_check(candidate, baseline, spec(minimum=0.5, paired=True, confidence=0.99))[0] == []


def test_slice_order_does_not_change_pairing():
    from lab9.gate import slice_check
    baseline = report([[1], [1], [1]])
    candidate = report([[0.8], [0.8], [0.8]])
    reversed_rows = copy.deepcopy(candidate)
    reversed_rows["rows"].reverse()
    assert slice_check(candidate, baseline, spec(paired=True)) == slice_check(reversed_rows, baseline, spec(paired=True))
