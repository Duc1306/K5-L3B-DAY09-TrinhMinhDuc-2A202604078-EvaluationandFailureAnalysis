"""Replay the public M1 cases and save their trace/ledger evidence.

Run from src/: python -m lab9.m1_evidence
Local shapes only select existing switches from variant_agent.make_shape;
neither Lab 8 nor the supplied variants/graders are changed.
"""
from __future__ import annotations

import json
from pathlib import Path

from lab8.shapes import SHAPES
from lab9.evalset import FAILURE_MODES_V1, SOURCE, load_jsonl, sha12
from lab9.trace_case import investigate
from lab9.variant_agent import make_shape

OUTPUT = Path("../docs/evidence/m1_traces.json")
LOCAL_BUGS = {
    "m1_leaky_trace": "leaky_trace",
    "m1_round_down": "round_down",
    "m1_stale_clause": "stale_clause",
    "m1_sibling_refund": "sibling_refund",
    "m1_misreport": "misreport",
    "m1_ignore_denied": "ignore_denied",
}
REPLAY_BY_MODE = {
    "FM-01": "m1_leaky_trace",
    "FM-02": "seeded_regression",
    "FM-03": "seeded_regression",
    "FM-04": "m1_round_down",
    "FM-05": "seeded_regression",
    "FM-06": "m1_stale_clause",
    "FM-07": "m1_sibling_refund",
    "FM-08": "m1_misreport",
    # v1 provides a successful boundary control, not an observed FM-09 failure.
    "FM-09": "fixed",
}
ANCHORS = {
    "FM-01": ("m1_leaky_trace", "C-001", 11, "debug_claim_row"),
    "FM-02": ("seeded_regression", "C-007", 11, "reply"),
    "FM-03": ("seeded_regression", "C-002", 11, "model_override"),
    "FM-04": ("slice_regression", "C-014", 11, "proposal"),
    "FM-05": ("seeded_regression", "C-014", 11, "proposal"),
    "FM-06": ("m1_stale_clause", "C-006", 11, "quote"),
    "FM-07": ("m1_sibling_refund", "C-001", 11, "batch_refund"),
    "FM-08": ("m1_misreport", "C-008", 11, "reply"),
}


def build() -> dict:
    for name, bug in LOCAL_BUGS.items():
        SHAPES[name] = make_shape(name, {"no_override", bug})

    trials: dict[str, dict] = {}

    def replay(shape: str, claim_id: str, seed: int = 11) -> str:
        run_id = f"R-{shape}-{claim_id}-s{seed}"
        if run_id not in trials:
            trial = investigate(shape, claim_id, seed)["trial"]
            result = trial["result"]
            if not trial["events"] or "run_id" not in result:
                raise RuntimeError(f"Replay did not produce a trace: {run_id}")
            trials[run_id] = {
                "result": {key: result[key] for key in
                           ("run_id", "shape", "claim_id", "seed", "status", "proposal_amount", "error_reason")},
                "snapshot": trial["snapshot"],
                "unexpected_rows": trial["unexpected_rows"],
                "lab8_pass": trial["lab8_pass"],
                "lab8_reason": trial["lab8_reason"],
                "events": trial["events"],
            }
        return run_id

    coverage, controls = {}, {}
    for claim in load_jsonl(SOURCE):
        claim_id = claim["claim_id"]
        controls[claim_id] = replay("fixed", claim_id)
        if not trials[controls[claim_id]]["lab8_pass"]:
            raise RuntimeError(f"Fixed control failed: {claim_id}")
        coverage[claim_id] = {}
        for mode in FAILURE_MODES_V1[claim_id]:
            shape = REPLAY_BY_MODE[mode]
            if mode == "FM-04" and claim_id == "C-014":
                shape = "slice_regression"
            if mode == "FM-02" and claim_id == "C-013":
                shape = "m1_ignore_denied"
            coverage[claim_id][mode] = replay(shape, claim_id)

    anchors = {}
    for mode, (shape, claim_id, seed, kind) in ANCHORS.items():
        run_id = replay(shape, claim_id, seed)
        step = next(i for i, event in enumerate(trials[run_id]["events"], 1) if event["kind"] == kind)
        anchors[mode] = {"run_id": run_id, "first_wrong_step": step, "kind": kind,
                         "control_run_id": controls[claim_id]}
    reference_miss = replay("swarm", "C-002", 55)
    replay("fixed", "C-002", 55)
    sources = ("data/public_claims.jsonl", "data/public_world_state.json", "lab9/variant_agent.py",
               "lab9/variants.py", "lab8/shapes/swarm_reference.py")
    return {"schema": "m1_trace_evidence.v1", "command": "python -m lab9.m1_evidence",
            "source_sha12": {source: sha12(Path(source)) for source in sources},
            "local_shapes": {name: ["no_override", bug] for name, bug in LOCAL_BUGS.items()},
            "coverage": coverage, "fixed_controls": controls, "anchors": anchors,
            "swarm_reference_miss": reference_miss, "trials": trials}


def main() -> int:
    report = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}: {len(report['trials'])} trials, {len(report['coverage'])} items, "
          f"{len(report['anchors'])} failure-mode anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
