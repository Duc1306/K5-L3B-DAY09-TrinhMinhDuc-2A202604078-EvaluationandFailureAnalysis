"""M7: enforce complete paired evidence and preserve same-version gate rules."""
import copy

import pytest

from lab9.eval import aggregate
from lab9.gate import check, integrity_check

pytestmark = pytest.mark.student


@pytest.fixture
def evidence():
    spec = {"eval_set_version": "v2", "pass_k": [2], "metrics": [
        {"id": "pass_rate", "kind": "capability", "blocking": True,
         "threshold": {"min": 0.8, "no_significant_drop": True}},
        {"id": "secret_leak", "kind": "safety", "blocking": True, "threshold": {"max": 0}},
        {"id": "pass_hat_2", "blocking": True, "threshold": {"min": 0.8}},
        {"id": "cost_per_success", "blocking": False, "threshold": {"max_increase": 0.1}},
    ], "slices": [{"name": "priority", "metric": "pass_rate", "min": 0.8,
                   "no_significant_drop": True, "blocking": True}]}
    rows = [{"item_id": f"unseen-{item}", "seed": seed, "pass_rate": True,
             "secret_leak": False, "slices": ["priority", "audit"] if item < 2 else [], "cost": 1.0}
            for item in range(3) for seed in (7, 19)]
    base = {"manifest": {"eval_set_sha": "test-sha", "items": 3, "seeds": [7, 19]},
            "rows": rows, "metrics": aggregate(rows, ["pass_rate", "secret_leak"], [2]),
            "evaluator_failures": []}
    return base, spec


def assert_integrity_block(candidate, baseline, spec):
    blocked, lines = check(candidate, baseline, spec)
    assert blocked == ["integrity"]
    assert lines and all("INTEGRITY" in line for line in lines)


def test_complete_reports_and_derived_metrics_are_accepted(evidence):
    base, spec = evidence
    assert all("pass_hat_2" not in row for row in base["rows"])
    assert integrity_check(base, base, spec, spec) == []
    assert check(base, base, spec, spec)[0] == []


def test_ordering_of_rows_seeds_and_slice_tags_is_irrelevant(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["rows"].reverse()
    candidate["manifest"]["seeds"].reverse()
    for row in candidate["rows"]:
        row["slices"].reverse()
    assert integrity_check(candidate, base, spec) == []


def test_duplicate_replacing_a_row_is_blocked_even_with_unchanged_count(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["rows"][-1] = copy.deepcopy(candidate["rows"][0])
    assert len(candidate["rows"]) == len(base["rows"])
    assert_integrity_block(candidate, base, spec)


def test_evaluator_failure_is_blocked_despite_all_green_scores(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["evaluator_failures"] = ["unseen-1@7:Evaluator:crashed"]
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -float("inf"), "1", 2])
def test_bad_case_score_cannot_disappear_from_the_average(evidence, bad):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["rows"][0]["pass_rate"] = bad
    assert_integrity_block(candidate, base, spec)


def test_missing_case_score_is_blocked(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    del candidate["rows"][0]["secret_leak"]
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("mid", ["pass_rate", "pass_hat_2", "cost_per_success"])
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "perfect", 10**400])
def test_invalid_or_undefined_summary_is_blocked(evidence, mid, bad):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["metrics"][mid] = bad
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("mid", ["pass_rate", "pass_hat_2", "secret_leak", "cost_per_success"])
def test_forged_finite_aggregate_is_blocked(evidence, mid):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["metrics"][mid] += 0.01
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("change", ["drop", "duplicate_seed", "wrong_items", "pick_seed", "swap_item", "missing_manifest"])
def test_manifest_and_pair_coverage_cannot_be_gamed(evidence, change):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    if change == "drop":
        candidate["rows"].pop()
    elif change == "duplicate_seed":
        candidate["manifest"]["seeds"] = [7, 7]
    elif change == "wrong_items":
        candidate["manifest"]["items"] = 2
    elif change == "pick_seed":
        candidate["rows"] = [row for row in candidate["rows"] if row["seed"] == 7]
        candidate["manifest"]["seeds"] = [7]
        candidate["metrics"] = aggregate(candidate["rows"], ["pass_rate", "secret_leak"], [2])
    elif change == "swap_item":
        for row in candidate["rows"]:
            if row["item_id"] == "unseen-2":
                row["item_id"] = "replacement"
    else:
        del candidate["manifest"]
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("all_seeds", [False, True])
def test_slice_relabelling_is_blocked(evidence, all_seeds):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    for row in candidate["rows"]:
        if row["item_id"] == "unseen-0" and (all_seeds or row["seed"] == 7):
            row["slices"] = []
    assert_integrity_block(candidate, base, spec)


def test_invalid_baseline_is_blocked_too(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    base["metrics"]["pass_rate"] = float("nan")
    assert_integrity_block(candidate, base, spec)


@pytest.mark.parametrize("index,bound,looser", [(0, "min", 0.5), (1, "max", 1), (3, "max_increase", 0.5)])
@pytest.mark.parametrize("remove", [False, True])
def test_numeric_ratchet_rejects_lowering_or_removing_a_bound(evidence, index, bound, looser, remove):
    base, spec = evidence
    changed = copy.deepcopy(spec)
    if remove:
        del changed["metrics"][index]["threshold"][bound]
    else:
        changed["metrics"][index]["threshold"][bound] = looser
    problems = integrity_check(base, base, changed, spec)
    assert any("ratchet" in problem for problem in problems)


@pytest.mark.parametrize("change", ["metric", "blocking", "paired_ci", "slice", "slice_min", "slice_blocking", "slice_ci", "slice_metric", "grader"])
def test_ratchet_preserves_metric_and_slice_rules(evidence, change):
    base, spec = evidence
    changed = copy.deepcopy(spec)
    if change == "metric":
        changed["metrics"].pop(0)
    elif change == "blocking":
        changed["metrics"][0]["blocking"] = False
    elif change == "paired_ci":
        changed["metrics"][0]["threshold"].pop("no_significant_drop")
    elif change == "slice":
        changed["slices"] = []
    elif change == "slice_min":
        changed["slices"][0]["min"] = 0.5
    elif change == "slice_blocking":
        changed["slices"][0].pop("blocking")
    elif change == "slice_ci":
        changed["slices"][0]["no_significant_drop"] = False
    elif change == "slice_metric":
        changed["slices"][0]["metric"] = "secret_leak"
    else:
        spec["metrics"][0]["grader"] = "original"
        changed["metrics"][0]["grader"] = "always_pass"
    assert any("ratchet" in problem for problem in integrity_check(base, base, changed, spec))


def test_stricter_rules_and_reordering_are_allowed(evidence):
    base, spec = evidence
    changed = copy.deepcopy(spec)
    changed["metrics"][0]["threshold"]["min"] = 0.9
    changed["metrics"][3]["threshold"]["max_increase"] = 0.05
    changed["slices"][0]["min"] = 0.9
    changed["metrics"].reverse()
    assert integrity_check(base, base, changed, spec) == []


def test_ratchet_is_scoped_to_eval_set_version(evidence):
    base, spec = evidence
    changed = copy.deepcopy(spec)
    changed["eval_set_version"] = "v3"
    changed["metrics"][0]["threshold"]["min"] = 0.5
    assert integrity_check(base, base, changed, spec) == []


@pytest.mark.parametrize("change", ["nan_threshold", "duplicate_metric", "duplicate_slice"])
def test_invalid_spec_is_blocked_explicitly(evidence, change):
    base, spec = evidence
    if change == "nan_threshold":
        spec["metrics"][0]["threshold"]["min"] = float("nan")
    elif change == "duplicate_metric":
        spec["metrics"].append(copy.deepcopy(spec["metrics"][0]))
    else:
        spec["slices"].append(copy.deepcopy(spec["slices"][0]))
    assert_integrity_block(base, base, spec)


def test_missing_aggregate_does_not_pass_as_a_nonblocking_warning(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    del candidate["metrics"]["cost_per_success"]
    assert_integrity_block(candidate, base, spec)


def test_single_item_paired_ci_is_an_explicit_integrity_failure(evidence):
    base, spec = evidence
    candidate = copy.deepcopy(base)
    candidate["rows"] = candidate["rows"][:2]
    candidate["manifest"]["items"] = 1
    candidate["metrics"] = aggregate(candidate["rows"], ["pass_rate", "secret_leak"], [2])
    assert_integrity_block(candidate, candidate, spec)
