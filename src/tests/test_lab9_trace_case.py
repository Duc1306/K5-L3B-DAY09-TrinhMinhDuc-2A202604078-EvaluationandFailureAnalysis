"""M1 regression: the same DB/ledger invariant rejects the bug and accepts fixed."""
import pytest

pytestmark = pytest.mark.student


@pytest.mark.parametrize("shape,seed,expected_pass", [
    ("seeded_regression", 11, False),
    ("swarm", 55, False),
    ("swarm", 11, True),
    ("fixed", 11, True),
    ("fixed", 55, True),
])
def test_lab9_ticket_cannot_change_refund_entitlement(shape, seed, expected_pass):
    from pydantic_evals.evaluators import EvaluatorContext
    from lab9.graders import DbFactKept
    from lab9.trace_case import investigate

    case = investigate(shape, "C-002", seed)
    trial, label = case["trial"], case["label"]
    correct_outcome = (
        trial["result"]["status"] == label["status"]
        and trial["result"]["proposal_amount"] == label["proposal_amount"]
        and trial["snapshot"]["refund_vnd"] == label["refund_vnd"]
        and trial["snapshot"]["refund_count"] == label["refund_count"]
    )
    assert correct_outcome is expected_pass
    assert trial["lab8_pass"] is expected_pass
    ctx = EvaluatorContext(name="C-002", inputs={"claim_id": "C-002", "seed": seed},
                           metadata=None, expected_output=label, output=trial,
                           duration=0.0, _span_tree=None, attributes={}, metrics={})
    assert DbFactKept().evaluate(ctx).value is expected_pass
