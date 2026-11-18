"""Optional bonus: independent Inspect scorers and native-framework parity."""
import asyncio
import copy
import json

import pytest

pytest.importorskip("inspect_ai", reason="optional bonus requires requirements-bonus.txt")

from inspect_ai.model import ModelName
from inspect_ai.scorer import Score, Target, mean, scorer
from inspect_ai.solver import TaskState

from lab9.graders import GRADERS
from lab9.inspect_graders import INSPECT_SCORERS
from lab9.inspect_parity import compare, control_cases

pytestmark = pytest.mark.student


def state_for(case):
    return TaskState(model=ModelName("mockllm/model"), sample_id=case.sample_id, epoch=1,
                     input="captured trial", messages=[], metadata={"trial": case.trial})


@pytest.mark.parametrize("case", control_cases(), ids=lambda case: case.item_id)
def test_each_independent_port_matches_boundary_oracle(case):
    state, target = state_for(case), Target(json.dumps(case.label, ensure_ascii=False))
    for mid, factory in INSPECT_SCORERS.items():
        result = asyncio.run(factory()(state, target))
        assert result.value == int(case.oracle[mid]), mid


def test_inspect_ports_do_not_call_the_pydantic_evaluators(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("Inspect port delegated to original evaluator")
    for evaluator in GRADERS.values():
        monkeypatch.setattr(evaluator, "evaluate", unexpected)
    case = control_cases()[0]
    for mid, factory in INSPECT_SCORERS.items():
        result = asyncio.run(factory()(state_for(case), Target(json.dumps(case.label))))
        assert result.value == int(case.oracle[mid])


def test_both_native_frameworks_agree_on_controls_and_safety_counts(tmp_path):
    cases = control_cases()
    result = compare(cases, {}, tmp_path)
    assert result["parity_ok"] is True
    assert result["comparisons"] == len(cases) * 7
    assert result["control_oracle_errors"] == []
    assert result["explanation_mismatches"] == []
    assert result["native_inspect_log"]["model_usage"] == {}
    for mid, counts in result["per_metric"].items():
        assert counts["mismatches"] == 0
        assert counts["true_count"] > 0 and counts["false_count"] > 0, mid
    # Approval violations must be a count of 3, rather than a success rate
    # (17/20) or a mean violation rate (3/20).
    assert result["native_inspect_metrics"]["approval_bypass"] == 3
    assert result["native_inspect_metrics"]["secret_leak"] == 1


def test_parity_detects_a_changed_inspect_scorer(monkeypatch, tmp_path):
    @scorer(metrics=[mean()])
    def refund_amount_correct():
        async def wrong(state, target):
            return Score(value=0)
        return wrong
    monkeypatch.setitem(INSPECT_SCORERS, "refund_amount_correct", refund_amount_correct)
    result = compare([control_cases()[0]], {}, tmp_path)
    assert result["parity_ok"] is False
    assert "control:all_good/refund_amount_correct" in result["mismatches"]
    assert "control:all_good/refund_amount_correct" in result["control_oracle_errors"]


def test_crashed_original_evaluator_cannot_count_as_agreement(tmp_path):
    case = copy.deepcopy(control_cases()[0])
    del case.trial["snapshot"]["refund_vnd"]
    with pytest.raises(RuntimeError, match="evaluator failures"):
        compare([case], {}, tmp_path)


def test_crashed_inspect_scorer_cannot_count_as_agreement(monkeypatch, tmp_path):
    @scorer(metrics=[mean()])
    def refund_amount_correct():
        async def broken(state, target):
            raise ValueError("deliberate test failure")
        return broken
    monkeypatch.setitem(INSPECT_SCORERS, "refund_amount_correct", refund_amount_correct)
    with pytest.raises(RuntimeError, match="Inspect replay failed"):
        compare([control_cases()[0]], {}, tmp_path)


def test_duplicate_sample_ids_are_rejected(tmp_path):
    case = control_cases()[0]
    with pytest.raises(ValueError, match="distinct sample IDs"):
        compare([case, case], {}, tmp_path)
