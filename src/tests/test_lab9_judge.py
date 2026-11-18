"""M2 edge cases and calibration decisions, with FAIL as the positive class."""
import csv
import math
from pathlib import Path

import pytest

pytestmark = pytest.mark.student


def write_labels(path, pairs):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("item_id", "reply", "human", "judge"))
        for n, (human, judge) in enumerate(pairs):
            writer.writerow((f"T-{n}", "test reply", human, judge))
    return path


@pytest.mark.parametrize("human,judge", [
    (["PASS"], []),
    ([], ["PASS"]),
    (["PASS"], ["UNKNOWN"]),
    (["unknown"], ["FAIL"]),
])
def test_invalid_label_pairs_are_rejected(human, judge):
    from lab9.stats import confusion
    with pytest.raises(ValueError):
        confusion(human, judge)


def test_no_labels_have_no_measurable_agreement():
    from lab9 import stats
    assert stats.confusion([], []) == {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    assert stats.precision_recall([], []) == (0.0, 0.0)
    with pytest.raises(ValueError):
        stats.cohen_kappa([], [])


def test_constant_judge_on_mixed_labels_has_zero_recall_and_kappa():
    from lab9 import stats
    human, judge = ["PASS", "FAIL"], ["PASS", "PASS"]
    assert stats.precision_recall(human, judge) == (0.0, 0.0)
    assert stats.cohen_kappa(human, judge) == 0.0


def test_perfect_and_opposite_agreement():
    from lab9 import stats
    human = ["PASS", "FAIL"]
    assert stats.cohen_kappa(human, human) == 1.0
    assert stats.cohen_kappa(human, ["FAIL", "PASS"]) == -1.0


@pytest.mark.parametrize("rates", [
    (-0.1, 0.8, 0.9),
    (0.3, 1.1, 0.9),
    (0.3, 0.8, float("nan")),
    (float("inf"), 0.8, 0.9),
    (0.3, 0.0, 1.0),
])
def test_rogan_gladen_rejects_invalid_or_uninformative_calibration(rates):
    from lab9.stats import rogan_gladen
    with pytest.raises(ValueError):
        rogan_gladen(*rates)


def test_rogan_gladen_clips_above_one():
    from lab9.stats import rogan_gladen
    assert rogan_gladen(0.9, 0.5, 0.9) == 1.0


def test_helpful_judge_misses_most_failures():
    from lab9.judge import calibrate
    result = calibrate(Path("data/eval/judge_helpful_public.csv"))
    assert result["confusion"] == {"tp": 9, "fp": 0, "fn": 21, "tn": 70}
    assert (result["precision"], result["recall"], result["kappa"]) == (1.0, 0.3, 0.375)
    assert result["corrected_fail_rate"] == 0.3
    assert result["passed"] is False


def test_undefined_kappa_fails_calibration_without_crashing(tmp_path, capsys):
    from lab9.judge import calibrate, main
    path = write_labels(tmp_path / "constant.csv", [("PASS", "PASS")] * 5)
    result = calibrate(path)
    assert math.isnan(result["kappa"])
    assert math.isnan(result["corrected_fail_rate"])
    assert result["passed"] is False
    assert main(["--csv", str(path)]) == 1
    assert "FAIL floors" in capsys.readouterr().out


def test_rounding_cannot_promote_a_judge_below_the_precision_floor(tmp_path):
    from lab9.judge import calibrate
    pairs = [("FAIL", "FAIL")] * 1999 + [("PASS", "FAIL")] * 501 + [("PASS", "PASS")] * 2000
    result = calibrate(write_labels(tmp_path / "below_floor.csv", pairs))
    assert result["precision"] == 0.8  # 0.7996 displayed to three decimal places
    assert result["recall"] >= 0.7 and result["kappa"] >= 0.6
    assert result["passed"] is False


def test_empty_csv_is_reported_as_failed_calibration(tmp_path, capsys):
    from lab9.judge import main
    path = write_labels(tmp_path / "empty.csv", [])
    assert main(["--csv", str(path)]) == 1
    assert "no labeled rows" in capsys.readouterr().out
