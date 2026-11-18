"""M4: hashes must survive Git's Windows-to-Linux newline conversion."""
import hashlib
import json

import pytest

pytestmark = pytest.mark.student


def test_evalset_build_writes_canonical_lf_bytes(tmp_path, monkeypatch):
    from lab9 import evalset
    source = tmp_path / "claims.jsonl"
    source.write_text(json.dumps({"claim_id": "C-001", "matrix_id": "T01",
                                 "expected": {"refund_vnd": 35000}}) + "\n", encoding="utf-8")
    items, labels = tmp_path / "items.jsonl", tmp_path / "labels.json"
    monkeypatch.setattr(evalset, "ITEMS", items)
    monkeypatch.setattr(evalset, "LABELS", labels)
    evalset.build(source)
    for path in (items, labels):
        assert b"\r" not in path.read_bytes()
    portable_digest = hashlib.sha256(items.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]
    assert evalset.sha12(items) == portable_digest


def test_eval_cli_report_uses_lf_bytes(tmp_path, monkeypatch):
    from lab9 import eval
    report = {"run_id": "test", "shape": "swarm",
              "manifest": {"eval_set_sha": "test", "items": 1, "seeds": [11], "llm": "MockLLM"},
              "rows": [{"item_id": "E-001", "seed": 11, "pass_rate": True}],
              "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    monkeypatch.setattr(eval, "run_eval", lambda *args: report)
    output = tmp_path / "report.json"
    assert eval.main(["--shape", "swarm", "--out", str(output)]) == 0
    assert b"\r" not in output.read_bytes()
    assert json.loads(output.read_text(encoding="utf-8")) == report
