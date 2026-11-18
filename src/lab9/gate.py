"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, aggregate, load_spec, per_item
from lab9.graders import GRADERS


def _finite(value) -> bool:
    try:
        return isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


def _rules(spec: dict, problems: list[str], label: str) -> tuple[dict, dict]:
    """Index rules without silently overwriting duplicate metric/slice definitions."""
    if not isinstance(spec, dict):
        problems.append(f"{label}: spec must be an object")
        return {}, {}
    indexed = []
    for section in ("metrics", "slices"):
        result = {}
        entries = spec.get(section, [])
        if not isinstance(entries, list) or (section == "metrics" and not entries):
            problems.append(f"{label}: invalid {section} list")
            entries = []
        for rule in entries:
            fields = ("id",) if section == "metrics" else ("name", "metric")
            if not isinstance(rule, dict) or any(not isinstance(rule.get(k), str) or not rule[k] for k in fields):
                problems.append(f"{label}: invalid {section} rule")
                continue
            key = rule["id"] if section == "metrics" else (rule["name"], rule["metric"])
            if key in result:
                problems.append(f"{label}: duplicate {section} rule {key}")
            result[key] = rule
            threshold = rule.get("threshold", {}) if section == "metrics" else rule
            if not isinstance(threshold, dict):
                problems.append(f"{label}: invalid threshold for {key}")
                continue
            for bound in ("min", "max", "max_increase"):
                if bound in threshold and (isinstance(threshold[bound], bool) or not _finite(threshold[bound])):
                    problems.append(f"{label}: non-finite/invalid {key}.{bound}")
            if "blocking" in rule and not isinstance(rule["blocking"], bool):
                problems.append(f"{label}: invalid blocking flag for {key}")
            if "no_significant_drop" in threshold and not isinstance(threshold["no_significant_drop"], bool):
                problems.append(f"{label}: invalid paired-CI flag for {key}")
        indexed.append(result)
    return indexed[0], indexed[1]


def _ratchet(current: dict, previous: dict, problems: list[str], section: str) -> None:
    for key, old in previous.items():
        if key not in current:
            problems.append(f"ratchet: removed {section} {key}")
            continue
        new = current[key]
        if old.get("blocking") and not new.get("blocking"):
            problems.append(f"ratchet: disabled blocking for {section} {key}")
        old_th = old.get("threshold", {}) if section == "metric" else old
        new_th = new.get("threshold", {}) if section == "metric" else new
        for bound in ("min", "max", "max_increase"):
            if bound in old_th and (bound not in new_th or
                    (new_th[bound] < old_th[bound] if bound == "min" else new_th[bound] > old_th[bound])):
                problems.append(f"ratchet: loosened {section} {key}.{bound}")
        if old_th.get("no_significant_drop") and not new_th.get("no_significant_drop"):
            problems.append(f"ratchet: removed paired CI for {section} {key}")
        if section == "metric":
            for field in ("kind", "grader", "level"):
                if field in old and old[field] != new.get(field):
                    problems.append(f"ratchet: changed {section} {key}.{field}")


def _report_integrity(report: dict, metric_rules: dict, slice_rules: dict,
                      label: str, problems: list[str]) -> dict:
    """Return pair -> slice tags after validating coverage and recomputing summaries."""
    start = len(problems)
    if not isinstance(report, dict):
        problems.append(f"{label}: report must be an object")
        return {}
    manifest, rows, metrics = report.get("manifest"), report.get("rows"), report.get("metrics")
    if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(metrics, dict):
        problems.append(f"{label}: missing/invalid manifest, rows or metrics")
        return {}
    if any(not isinstance(mid, str) for mid in metrics):
        problems.append(f"{label}: metric names must be strings")
        return {}
    if not isinstance(report.get("evaluator_failures"), list) or report["evaluator_failures"]:
        problems.append(f"{label}: evaluator_failures must be an empty list")
    if not isinstance(manifest.get("eval_set_sha"), str) or not manifest["eval_set_sha"]:
        problems.append(f"{label}: missing eval_set_sha")
    seeds, count = manifest.get("seeds"), manifest.get("items")
    if (not isinstance(seeds, list) or not seeds or
            any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds)):
        problems.append(f"{label}: manifest seeds must be distinct integers")
        seeds = []
    if type(count) is not int or count < 1:
        problems.append(f"{label}: manifest items must be a positive integer")
    elif len(rows) != count * len(seeds):
        problems.append(f"{label}: row count {len(rows)} != items x seeds ({count * len(seeds)})")
    for mid, value in metrics.items():
        if value is not None and not _finite(value):
            problems.append(f"{label}: metric {mid} is non-finite or not numeric")
    for mid in metric_rules:
        if mid not in metrics:
            problems.append(f"{label}: missing aggregate metric {mid}")

    def derived(mid):
        return mid in ("pass_5", "cost_per_success") or re.fullmatch(r"pass_(?:at|hat)_[1-9][0-9]*", mid)

    graded = {mid for mid in metric_rules if not derived(mid)}
    required = graded | {metric for _, metric in slice_rules}
    derived_ids = {mid for mid in metrics.keys() | metric_rules.keys() if derived(mid)}
    if derived_ids:
        required.add("pass_rate")
    pairs, item_slices = {}, {}
    for index, row in enumerate(rows):
        if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str) or
                not row["item_id"] or type(row.get("seed")) is not int):
            problems.append(f"{label}: invalid item/seed at row {index}")
            continue
        item, seed = row["item_id"], row["seed"]
        pair = (item, seed)
        if pair in pairs:
            problems.append(f"{label}: duplicate (item_id, seed) {pair}")
        tags = row.get("slices", [])
        if (not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags) or
                len(set(tags)) != len(tags)):
            problems.append(f"{label}: invalid slice tags at {pair}")
            tags = []
        tags = frozenset(tags)
        if item in item_slices and item_slices[item] != tags:
            problems.append(f"{label}: inconsistent slice tags across seeds for {item}")
        item_slices[item] = tags
        pairs[pair] = tags
        for mid in required:
            value = row.get(mid)
            if not _finite(value) or (mid in GRADERS and value not in (0, 1)):
                problems.append(f"{label}: missing/invalid grader {mid} at {pair}")
        if "cost_per_success" in derived_ids and (not _finite(row.get("cost")) or row["cost"] < 0):
            problems.append(f"{label}: missing/invalid cost at {pair}")
    if len(item_slices) != count:
        problems.append(f"{label}: unique item count differs from manifest")
    needs_pairs = any(rule.get("threshold", {}).get("no_significant_drop") for rule in metric_rules.values())
    if len(item_slices) < 2 and needs_pairs:
        problems.append(f"{label}: paired CI needs at least two items")
    if seeds and pairs.keys() != {(item, seed) for item in item_slices for seed in seeds}:
        problems.append(f"{label}: rows do not cover every item x manifest seed exactly once")

    if len(problems) == start:
        # Use the harness's aggregation (including safety counts and macro pass^k),
        # never a mean that silently omits failed grader results. Costs are only
        # needed for cost_per_success; minimal case-only reports need not have them.
        k_values = {int(mid.rsplit("_", 1)[1]) for mid in derived_ids if mid.startswith(("pass_at_", "pass_hat_"))}
        recomputed = aggregate([dict(row, cost=row.get("cost", 0)) for row in rows],
                               sorted(required), k_values=sorted(k_values))
        for mid in (graded | derived_ids) & metrics.keys():
            expected, actual = recomputed[mid], metrics[mid]
            if (expected is None) != (actual is None) or (expected is not None and
                    not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9)):
                problems.append(f"{label}: aggregate {mid} does not match rows")
    return pairs


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    metrics, slices = _rules(spec, problems, "spec")
    if base_spec is not None:
        old_metrics, old_slices = _rules(base_spec, problems, "base spec")
        if not problems and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            _ratchet(metrics, old_metrics, problems, "metric")
            _ratchet(slices, old_slices, problems, "slice")
    if problems:
        return problems
    candidate = _report_integrity(pr, metrics, slices, "PR", problems)
    baseline = _report_integrity(base, metrics, slices, "baseline", problems)
    if candidate.keys() != baseline.keys():
        problems.append("PR (item_id, seed) set differs from baseline (cherry-picked items/seeds)")
    if any(candidate[pair] != baseline[pair] for pair in candidate.keys() & baseline.keys()):
        problems.append("PR slice tags differ from baseline")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for rule in spec.get("slices", []):
        name, metric = rule["name"], rule["metric"]
        identifier = f"slice:{name}/{metric}"

        def values(report):
            rows = [r for r in report["rows"] if name in (r.get("slices") or [])]
            if not rows:
                return {}, "no rows in slice"
            if any(not isinstance(r.get(metric), (int, float)) or not math.isfinite(r[metric]) for r in rows):
                return {}, "missing or non-finite slice metric"
            return per_item(report, metric, slice_name=name), None

        candidate, error = values(pr)
        value = sum(candidate.values()) / len(candidate) if candidate else None
        verdict = "missing" if error else "ok"
        notes = [error] if error else []
        if value is not None and "min" in rule and value < rule["min"]:
            verdict = "fail"
        if rule.get("no_significant_drop") and candidate:
            baseline, error = values(base)
            if error or candidate.keys() != baseline.keys():
                verdict = "missing"
                notes.append(error or "slice item set differs from baseline")
            elif len(candidate) < 2:
                verdict = "missing"
                notes.append("paired CI needs at least two slice items")
            else:
                keys = sorted(candidate)
                difference, low, high = stats.paired_bootstrap(
                    [candidate[key] for key in keys], [baseline[key] for key in keys],
                    n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                    confidence=bs.get("confidence", 0.95))
                notes.append(f"Δ {difference:+.3f} CI [{low:+.3f}, {high:+.3f}]")
                if high < 0:
                    verdict = "fail"
        if verdict != "ok" and rule.get("blocking"):
            blocked.append(identifier)
        label = "ok" if verdict == "ok" else ("BLOCK" if rule.get("blocking") else "warn")
        if verdict == "missing":
            notes.append("MISSING")
        lines.append(f"  {identifier:<32} {value!s:<8} min={rule.get('min', '-')!s:<5} "
                     f"{' ; '.join(notes):<35} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                               confidence=bs.get("confidence", 0.95))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    pr_id = pr.get("run_id", "?") if isinstance(pr, dict) else "?"
    base_id = base.get("run_id", "?") if isinstance(base, dict) else "?"
    manifest = pr.get("manifest") if isinstance(pr, dict) else None
    eval_sha = manifest.get("eval_set_sha", "?") if isinstance(manifest, dict) else "?"
    print(f"gate: PR {pr_id} vs main {base_id} · eval set {eval_sha}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
