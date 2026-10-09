"""Evaluation harness. OWNER: Person B (feat/ui-eval). See EVAL.md.

Run:  python eval/run_eval.py
Uses whatever MODEL_BACKEND is set in .env. Write every raw result to
eval/results/raw/ so each number in EVAL.md can be traced to a file.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import store  # noqa: E402
from copilot.schemas import Script  # noqa: E402


def load_teacher_marks(path: Path) -> dict[str, dict]:
    """TODO: read data/teacher_marks.csv -> {script_id: {"role":..., "total": int, "hard": bool}}"""
    raise NotImplementedError


def mean_abs_error(system: dict[str, int], teacher: dict[str, int]) -> float:
    """Metric 1: average |system total - teacher total| over held-out scripts."""
    return statistics.mean(abs(system[s] - teacher[s]) for s in system)


def consistency(totals_per_script: dict[str, list[int]]) -> dict:
    """Metric 2: grade each script N times. TODO: per-script range and stdev,
    mean range, % of scripts with all N totals identical."""
    raise NotImplementedError


def flag_quality(flagged: dict[str, bool], hard: dict[str, bool]) -> dict:
    """Metric 3: 2x2 table flagged/not x hard/not. 'hard' = calibrated error
    >= 1 mark (decided BEFORE running). TODO."""
    raise NotImplementedError


def main() -> None:
    """TODO (Person B):
    1. heldout = scripts with role 'heldout' in teacher_marks.csv
    2. uncalibrated: pipeline.grade_script(s, rubric, anchors=None, calibrated=False)
    3. calibrated:   pipeline.grade_script(s, rubric, store.load_anchors(), calibrated=True) x5
    4. compute the 3 metrics, print a markdown table, save CSVs to eval/results/
    """
    rubric = store.load_rubric()
    print(f"Loaded rubric {rubric.rubric_id}; eval not implemented yet.")


if __name__ == "__main__":
    main()
