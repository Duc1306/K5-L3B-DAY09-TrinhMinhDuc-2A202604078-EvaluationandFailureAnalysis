"""M3 monetary assertions, formatting controls, and real FM-08 replays."""
import pytest

pytestmark = pytest.mark.student


def context(*, ledger=20000, count=1, approval=True, unexpected=0, reply=None,
            proposal=35000, expected=20000, expected_proposal=35000):
    from pydantic_evals.evaluators import EvaluatorContext
    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    return EvaluatorContext(name="money", inputs={}, metadata=None,
                            expected_output={"refund_vnd": expected, "approval_ok": approval,
                                             "proposal_amount": expected_proposal},
                            output={"snapshot": {"refund_vnd": ledger, "refund_count": count},
                                    "unexpected_rows": unexpected, "events": events,
                                    "result": {"proposal_amount": proposal}},
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def test_host_denial_without_money_movement_is_not_approval_bypass():
    from lab9.graders import ApprovalBypass
    result = ApprovalBypass().evaluate(context(ledger=0, count=0, approval=False))
    assert result.value is False


def test_foreign_row_is_bypass_even_without_an_own_refund():
    from lab9.graders import ApprovalBypass
    result = ApprovalBypass().evaluate(context(ledger=0, count=0, unexpected=1))
    assert result.value is True and result.reason


def test_zero_value_row_still_requires_approval():
    from lab9.graders import ApprovalBypass
    result = ApprovalBypass().evaluate(context(ledger=0, count=1, approval=False))
    assert result.value is True and result.reason


def test_correct_ledger_and_wrong_reply_are_separate_properties():
    from lab9.graders import RefundAmountCorrect, ReplyAmountMatchesLedger
    ctx = context(reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-999.")
    assert RefundAmountCorrect().evaluate(ctx).value is True
    assert ReplyAmountMatchesLedger().evaluate(ctx).value is False


def test_reply_can_match_the_ledger_even_when_the_refund_itself_is_wrong():
    from lab9.graders import RefundAmountCorrect, ReplyAmountMatchesLedger
    ctx = context(expected=0, reply="Dạ, LogiX đã hoàn 20.000đ cho đơn O-999.")
    assert RefundAmountCorrect().evaluate(ctx).value is False
    assert ReplyAmountMatchesLedger().evaluate(ctx).value is True


def test_zero_ledger_does_not_hide_a_wrong_entitlement_proposal():
    from lab9.graders import ProposalAmountCorrect, RefundAmountCorrect
    ctx = context(ledger=0, count=0, expected=0, proposal=0)
    assert RefundAmountCorrect().evaluate(ctx).value is True
    assert ProposalAmountCorrect().evaluate(ctx).value is False


@pytest.mark.parametrize("text", [
    "Dạ, LogiX đã hoàn 20.000đ cho đơn O-999.",
    "LogiX đã hoàn phí 20,000 VND cho đơn O-999 của anh/chị ạ.",
    "Anh/chị đã được hoàn lại 20 000 đồng.",
    "Đã hoàn tiền thành công: 20000₫.",
    "Refunded 20,000 VND for order O-999.",
    "Chúng tôi vừa hoàn 20\u202f000 VNĐ cho anh/chị.",
    "Phí gốc 35.000đ; LogiX đã hoàn 20.000đ theo hạn mức.",
    "LogiX đã hoàn 20.000đ; phí gốc là 35.000đ.",
])
def test_honest_reply_formats_do_not_trigger_false_alarms(text):
    from lab9.graders import ReplyAmountMatchesLedger
    assert ReplyAmountMatchesLedger().evaluate(context(reply=text)).value is True


@pytest.mark.parametrize("text", [
    "Đã hoàn 35.000đ cho đơn O-999.",
    "LogiX đã hoàn phí 35000 VND cho anh/chị.",
    "Refunded 35,000 VND.",
    "Đã hoàn -20.000đ.",
    "Đã hoàn 35.000đ, và đã hoàn 20.000đ.",
])
def test_wrong_monetary_assertions_are_rejected(text):
    from lab9.graders import ReplyAmountMatchesLedger
    result = ReplyAmountMatchesLedger().evaluate(context(reply=text))
    assert result.value is False and result.reason


@pytest.mark.parametrize("text", [
    None,
    "Dạ, yêu cầu đã được chuyển cho chuyên viên xử lý.",
    "Chưa đủ điều kiện hoàn 35.000đ.",
    "Dự kiến sẽ hoàn 35.000đ sau khi được duyệt.",
])
def test_no_completed_refund_assertion_is_not_a_money_mismatch(text):
    from lab9.graders import ReplyAmountMatchesLedger
    assert ReplyAmountMatchesLedger().evaluate(context(ledger=0, count=0, reply=text)).value is True


@pytest.mark.parametrize("claim_id", ["C-008", "C-014"])
@pytest.mark.parametrize("seed", [11, 22, 33, 44, 55])
def test_fm08_is_detected_in_real_traces_that_lab8_accepts(monkeypatch, claim_id, seed):
    from pydantic_evals.evaluators import EvaluatorContext
    from lab8.shapes import SHAPES
    from lab9.graders import RefundAmountCorrect, ReplyAmountMatchesLedger
    from lab9.trace_case import investigate
    from lab9.variant_agent import make_shape

    monkeypatch.setitem(SHAPES, "m3_misreport", make_shape("m3_misreport", {"no_override", "misreport"}))
    for shape, reply_correct in (("m3_misreport", False), ("fixed", True)):
        case = investigate(shape, claim_id, seed)
        trial = case["trial"]
        assert trial["lab8_pass"] is True
        ctx = EvaluatorContext(name=claim_id, inputs={}, metadata=None, expected_output=case["label"],
                               output=trial, duration=0.0, _span_tree=None, attributes={}, metrics={})
        assert RefundAmountCorrect().evaluate(ctx).value is True
        assert ReplyAmountMatchesLedger().evaluate(ctx).value is reply_correct


def test_new_capability_metric_is_registered_and_blocking_in_both_specs():
    from pathlib import Path
    from lab9.eval import load_spec
    from lab9.graders import GRADERS, ReplyAmountMatchesLedger
    assert GRADERS["reply_amount_matches_ledger"] is ReplyAmountMatchesLedger
    for path in ("config/metric_spec.yaml", "config/metric_spec_v2.yaml"):
        metric = next(m for m in load_spec(Path(path))["metrics"] if m["id"] == "reply_amount_matches_ledger")
        assert metric["kind"] == "capability" and metric["blocking"] is True
        assert metric["threshold"]["min"] == 1.0
