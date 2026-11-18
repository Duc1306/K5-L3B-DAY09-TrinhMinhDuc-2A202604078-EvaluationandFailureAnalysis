"""M5: preserve v1, map every attack, keep labels separate, and enforce coverage."""
from collections import Counter
import json
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.student


@pytest.fixture
def built_v2(tmp_path, monkeypatch):
    from lab9 import evalset
    items, labels = tmp_path / "items_v2.jsonl", tmp_path / "labels_v2.json"
    monkeypatch.setattr(evalset, "ITEMS_V2", items)
    monkeypatch.setattr(evalset, "LABELS_V2", labels)
    evalset.build_v2()
    return evalset, items, labels


def test_v2_preserves_public_items_and_labels_and_maps_every_attack(built_v2):
    evalset, path, labels_path = built_v2
    items = evalset.load_jsonl(path)
    public = evalset.load_jsonl(evalset.ITEMS)
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    public_labels = json.loads(evalset.LABELS.read_text(encoding="utf-8"))
    pack = json.loads(evalset.PACK.read_text(encoding="utf-8"))
    mapping = yaml.safe_load(evalset.FM_MAP.read_text(encoding="utf-8"))
    assert len(items) == len(public) + len(pack["claims"]) == len(labels) == 28
    assert evalset.check(path, labels_path) == []
    for original, rebuilt in zip(public, items):
        assert rebuilt == {**original, "eval_set_version": "v2",
                           "slices": evalset.slices_for(public_labels[original["claim_id"]], False)}
        assert labels[original["claim_id"]] == public_labels[original["claim_id"]]
    adversarial = {item["claim_id"]: item for item in items if item["split"] == "adversarial"}
    attacked = set()
    for claim in pack["claims"]:
        item = adversarial[claim["claim_id"]]
        assert item["failure_modes"] == [mapping[mechanism] for mechanism in claim["mechanisms"]]
        assert item["slices"] == evalset.slices_for(claim["expected"], True)
        assert labels[claim["claim_id"]] == claim["expected"]
        attacked.update(item["failure_modes"])
    counts = Counter(mode for item in items for mode in item["failure_modes"])
    assert all(counts[mode] >= 3 for mode in attacked)
    assert all("expected" not in item and "label" not in item for item in items)
    assert b"\r" not in path.read_bytes() and b"\r" not in labels_path.read_bytes()


@pytest.mark.parametrize("claim_id", ["C-001", "C-105"])
def test_v2_checker_rejects_dropping_public_or_adversarial_claims(built_v2, claim_id):
    evalset, path, labels = built_v2
    items = [item for item in evalset.load_jsonl(path) if item["claim_id"] != claim_id]
    path.write_text("".join(json.dumps(item) + "\n" for item in items), encoding="utf-8", newline="\n")
    assert any(claim_id in problem and "missing from v2" in problem for problem in evalset.check(path, labels))


def test_v2_checker_rejects_an_underrepresented_attacked_mode(built_v2):
    evalset, path, labels = built_v2
    items = evalset.load_jsonl(path)
    for item in items:
        if item["claim_id"] != "C-101":
            item["failure_modes"] = [mode for mode in item["failure_modes"] if mode != "FM-03"] or ["FM-01"]
    path.write_text("".join(json.dumps(item) + "\n" for item in items), encoding="utf-8", newline="\n")
    assert any("FM-03" in problem and "need >= 3" in problem for problem in evalset.check(path, labels))


def test_v2_build_is_reproducible(built_v2):
    evalset, path, labels = built_v2
    before = path.read_bytes(), labels.read_bytes()
    evalset.build_v2()
    assert (path.read_bytes(), labels.read_bytes()) == before


def test_v2_trace_utility_reads_the_adversarial_world():
    from lab9.trace_case import investigate
    case = investigate("fixed", "C-113", 11, Path("config/metric_spec_v2.yaml"))
    assert case["trial"]["lab8_pass"] is True
    assert case["trial"]["result"]["status"] == "escalated"
    assert case["trial"]["snapshot"]["refund_vnd"] == 0
    lookup = next(event["payload"]["lookup_order"] for event in case["trial"]["events"] if event["kind"] == "investigator")
    assert lookup["visible"] is False and lookup["reason"] == "outside_principal_scope"
