"""Offline regression test for the evaluation harness.

Uses a temporary data/results directory and fake grades only. It deliberately
returns one grade with no items to cover unreadable/model-error handling.
"""
import base64
import csv
import io
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from copilot import config, pipeline, store  # noqa: E402
from copilot.fake import fake_script_grade  # noqa: E402
from copilot.schemas import ScriptGrade  # noqa: E402
from eval import run_eval  # noqa: E402

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/" \
    "1Wm+LwAAAABJRU5ErkJggg=="
)


def write_teacher_marks(path: Path, rubric) -> None:
    fields = ["script_id", "role"] + [item.item_id for item in rubric.items] + ["total", "teacher_says_hard"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for script_id in ("T01", "T02", "T03"):
            row = {"script_id": script_id, "role": "heldout", "total": 0, "teacher_says_hard": "no"}
            row.update({item.item_id: 0 for item in rubric.items})
            writer.writerow(row)


def main() -> None:
    if config.MODEL_BACKEND != "fake":
        raise AssertionError("scripts/test_eval.py must run with MODEL_BACKEND=fake")
    rubric = store.load_rubric()
    original_data_dir = config.DATA_DIR
    original_results = run_eval.RESULTS
    original_load_rubric = store.load_rubric
    original_load_anchors = store.load_anchors
    original_grade_script = pipeline.grade_script
    original_argv = sys.argv[:]

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        data_dir = root / "data"
        scripts_dir = data_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        for script_id in ("T01", "T02", "T03"):
            (scripts_dir / f"{script_id}.png").write_bytes(PNG_1X1)
        write_teacher_marks(data_dir / "teacher_marks.csv", rubric)

        def fake_grade(script, used_rubric, anchors=None, calibrated=True):
            if script.script_id == "T02":
                return ScriptGrade(script_id=script.script_id, run_id="empty", backend="fake", model="fake",
                                   calibrated=calibrated, max_total=used_rubric.max_total,
                                   flags=["UNREADABLE"], seconds=0.01, model_calls=0)
            grade = fake_script_grade(script.script_id, used_rubric)
            grade.calibrated = calibrated
            grade.seconds, grade.model_calls = 0.01, 0
            return grade

        try:
            config.DATA_DIR = data_dir
            run_eval.RESULTS = root / "eval-results"
            store.load_rubric = lambda: rubric
            store.load_anchors = lambda: []
            pipeline.grade_script = fake_grade
            sys.argv = ["run_eval.py", "--runs", "2", "--limit", "3"]
            output = io.StringIO()
            with redirect_stdout(output):
                run_eval.main()
            summary = run_eval.RESULTS / "fake" / "summary.csv"
            assert summary.exists(), "fake results were not isolated in eval/results/fake/"
            assert "mean_seconds" in summary.read_text(encoding="utf-8"), "summary is missing mean_seconds"
            assert "FAKE BACKEND, do not report these numbers" in output.getvalue(), "missing fake-backend warning"
        finally:
            config.DATA_DIR = original_data_dir
            run_eval.RESULTS = original_results
            store.load_rubric = original_load_rubric
            store.load_anchors = original_load_anchors
            pipeline.grade_script = original_grade_script
            sys.argv = original_argv

    print("ALL EVAL TESTS PASSED")


if __name__ == "__main__":
    main()
