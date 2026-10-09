"""Evaluation harness. See EVAL.md.

Run: python eval/run_eval.py --runs 5
Raw model outputs are retained beneath eval/results/raw/ for traceability.
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import config, pipeline, store  # noqa: E402
from copilot.schemas import Script, ScriptGrade  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"


def load_teacher_marks(path: Path) -> dict[str, dict]:
    """Read teacher marks CSV, preserving marks per rubric item and hard tag."""
    if not path.exists():
        raise FileNotFoundError(f"Teacher marks file not found: {path}")
    records = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"script_id", "role", "total", "teacher_says_hard"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must include: {', '.join(sorted(required))}")
        item_fields = [name for name in reader.fieldnames if name not in required]
        for line, row in enumerate(reader, start=2):
            script_id = (row.get("script_id") or "").strip()
            if not script_id:
                raise ValueError(f"Row {line} has no script_id.")
            try:
                marks = {item_id: int(row[item_id]) for item_id in item_fields if row.get(item_id, "").strip()}
                total = int(row["total"])
            except ValueError as exc:
                raise ValueError(f"Row {line} has a non-integer mark or total.") from exc
            hard_value = (row["teacher_says_hard"] or "").strip().lower()
            if hard_value not in {"yes", "no", "true", "false", "1", "0"}:
                raise ValueError(f"Row {line} teacher_says_hard must be yes or no.")
            records[script_id] = {"role": (row["role"] or "").strip(), "items": marks,
                                  "total": total, "hard": hard_value in {"yes", "true", "1"}}
    return records


def mean_abs_error(system: dict[str, int], teacher: dict[str, int]) -> float:
    """Metric 1: average absolute total error over held-out scripts."""
    return statistics.mean(abs(system[script_id] - teacher[script_id]) for script_id in system)


def consistency(totals_per_script: dict[str, list[int]]) -> dict:
    """Metric 2: per-script range/stdev and aggregate consistency."""
    per_script = {}
    for script_id, totals in totals_per_script.items():
        if not totals:
            raise ValueError(f"No runs recorded for {script_id}.")
        per_script[script_id] = {
            "range": max(totals) - min(totals),
            "stdev": statistics.pstdev(totals),
            "identical": len(set(totals)) == 1,
        }
    return {
        "per_script": per_script,
        "mean_range": statistics.mean(row["range"] for row in per_script.values()),
        "mean_stdev": statistics.mean(row["stdev"] for row in per_script.values()),
        "percent_identical": 100 * statistics.mean(row["identical"] for row in per_script.values()),
    }


def flag_quality(flagged: dict[str, bool], hard: dict[str, bool]) -> dict:
    """Metric 3: 2x2 table of system flags against calibrated-error hardness."""
    if set(flagged) != set(hard):
        raise ValueError("Flag and hard script IDs must match.")
    return {
        "flagged_hard": sum(flagged[s] and hard[s] for s in flagged),
        "flagged_not_hard": sum(flagged[s] and not hard[s] for s in flagged),
        "unflagged_hard": sum(not flagged[s] and hard[s] for s in flagged),
        "unflagged_not_hard": sum(not flagged[s] and not hard[s] for s in flagged),
    }


def save_raw(results_root: Path, setting: str, script_id: str, run: int, grade: ScriptGrade) -> None:
    path = results_root / "raw" / setting / f"{script_id}_run{run}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(grade.model_dump_json(indent=2), encoding="utf-8")


def grade_once(script_id: str, rubric, anchors, calibrated: bool) -> ScriptGrade:
    image_path = next((str(path) for ext in ("jpg", "jpeg", "png")
                       if (path := config.DATA_DIR / "scripts" / f"{script_id}.{ext}").exists()),
                      str(config.DATA_DIR / "scripts" / f"{script_id}.jpg"))
    return pipeline.grade_script(Script(script_id=script_id, image_path=image_path, role="heldout"),
                                 rubric, anchors=anchors, calibrated=calibrated)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5, help="Calibrated runs per held-out script (default: 5)")
    parser.add_argument("--limit", type=int, help="Limit held-out scripts for a quick run")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")

    rubric = store.load_rubric()
    teacher = load_teacher_marks(config.DATA_DIR / "teacher_marks.csv")
    heldout_ids = [script_id for script_id, record in teacher.items() if record["role"] == "heldout"]
    if args.limit:
        heldout_ids = heldout_ids[:args.limit]
    if not heldout_ids:
        raise ValueError("No heldout scripts found in data/teacher_marks.csv.")
    missing = [script_id for script_id in heldout_ids if any(item.item_id not in teacher[script_id]["items"] for item in rubric.items)]
    if missing:
        raise ValueError(f"Teacher marks are missing rubric items for: {', '.join(missing)}")

    uncalibrated, calibrated = {}, {}
    anchors = store.load_anchors()
    for script_id in heldout_ids:
        grade = grade_once(script_id, rubric, anchors=None, calibrated=False)
        uncalibrated[script_id] = grade
        calibrated[script_id] = []
        for run in range(1, args.runs + 1):
            grade = grade_once(script_id, rubric, anchors=anchors, calibrated=True)
            calibrated[script_id].append(grade)

    all_grades = list(uncalibrated.values()) + [grade for grades in calibrated.values() for grade in grades]
    fake_backend = any(grade.backend == "fake" for grade in all_grades)
    results_root = RESULTS / "fake" if fake_backend else RESULTS
    for script_id, grade in uncalibrated.items():
        save_raw(results_root, "uncalibrated", script_id, 1, grade)
    for script_id, grades in calibrated.items():
        for run, grade in enumerate(grades, start=1):
            save_raw(results_root, "calibrated", script_id, run, grade)

    teacher_totals = {script_id: teacher[script_id]["total"] for script_id in heldout_ids}
    uncal_totals = {script_id: grade.total for script_id, grade in uncalibrated.items()}
    cal_reference = {script_id: grades[0] for script_id, grades in calibrated.items()}
    cal_totals = {script_id: grade.total for script_id, grade in cal_reference.items()}
    item_mae = lambda grades: {item.item_id: statistics.mean(abs(
        next((graded.final_marks for graded in grades[script_id].items
              if graded.item_id == item.item_id), 0)
        - teacher[script_id]["items"][item.item_id]) for script_id in heldout_ids) for item in rubric.items}
    uncal_item_mae, cal_item_mae = item_mae(uncalibrated), item_mae(cal_reference)
    consistency_data = consistency({script_id: [grade.total for grade in grades] for script_id, grades in calibrated.items()})
    errors = {script_id: abs(cal_totals[script_id] - teacher_totals[script_id]) for script_id in heldout_ids}
    flagged = {script_id: bool(cal_reference[script_id].flags) for script_id in heldout_ids}
    hard = {script_id: errors[script_id] >= 1 for script_id in heldout_ids}
    flags = flag_quality(flagged, hard)
    flagged_errors = [errors[s] for s in heldout_ids if flagged[s]]
    unflagged_errors = [errors[s] for s in heldout_ids if not flagged[s]]
    teacher_hard = {script_id: teacher[script_id]["hard"] for script_id in heldout_ids}
    hard_agreement = sum(flagged[s] == teacher_hard[s] for s in heldout_ids)
    uncal_seconds = statistics.mean(grade.seconds for grade in uncalibrated.values())
    uncal_model_calls = statistics.mean(grade.model_calls for grade in uncalibrated.values())
    calibrated_runs = [grade for grades in calibrated.values() for grade in grades]
    cal_seconds = statistics.mean(grade.seconds for grade in calibrated_runs)
    cal_model_calls = statistics.mean(grade.model_calls for grade in calibrated_runs)

    summary_rows = [
        {"setting": "uncalibrated", "model": uncalibrated[heldout_ids[0]].model, "n": len(heldout_ids),
         "mae_total": mean_abs_error(uncal_totals, teacher_totals), "mae_per_item": json.dumps(uncal_item_mae, sort_keys=True),
         "mean_range": "n/a", "mean_stdev": "n/a", "percent_identical": "n/a",
         "mean_seconds": uncal_seconds, "mean_model_calls": uncal_model_calls},
        {"setting": "calibrated", "model": cal_reference[heldout_ids[0]].model, "n": len(heldout_ids),
         "mae_total": mean_abs_error(cal_totals, teacher_totals), "mae_per_item": json.dumps(cal_item_mae, sort_keys=True),
         "mean_range": consistency_data["mean_range"], "mean_stdev": consistency_data["mean_stdev"],
         "percent_identical": consistency_data["percent_identical"],
         "mean_seconds": cal_seconds, "mean_model_calls": cal_model_calls},
    ]
    write_csv(results_root / "summary.csv", summary_rows)
    write_csv(results_root / "consistency.csv", [dict(script_id=script_id, **row) for script_id, row in consistency_data["per_script"].items()])
    write_csv(results_root / "flagging.csv", [{**flags, "mean_error_flagged": statistics.mean(flagged_errors) if flagged_errors else "n/a",
                                            "mean_error_unflagged": statistics.mean(unflagged_errors) if unflagged_errors else "n/a",
                                            "teacher_hard_agreement": hard_agreement, "n": len(heldout_ids)}])

    print("| Setting | Model | n | MAE total (marks) | MAE per item | Mean range over runs | Mean stdev | % identical | Mean seconds | Mean model calls |")
    print("|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for row in summary_rows:
        print(f"| {row['setting'].title()} | {row['model']} | {row['n']} | {row['mae_total']:.3f} | {row['mae_per_item']} | {row['mean_range']} | {row['mean_stdev']} | {row['percent_identical']} | {row['mean_seconds']:.2f} | {row['mean_model_calls']:.2f} |")
    print("\n| | Hard (error ≥1) | Not hard |\n|---|---:|---:|")
    print(f"| Flagged | {flags['flagged_hard']} | {flags['flagged_not_hard']} |")
    print(f"| Not flagged | {flags['unflagged_hard']} | {flags['unflagged_not_hard']} |")
    print(f"\nMean error of flagged scripts: {statistics.mean(flagged_errors) if flagged_errors else 'n/a'} · "
          f"unflagged scripts: {statistics.mean(unflagged_errors) if unflagged_errors else 'n/a'} · "
          f"Flags vs teacher's hard tags agree on {hard_agreement}/{len(heldout_ids)}.")
    print(f"Settings used: temperature {config.TEMPERATURE}, backend {config.MODEL_BACKEND}, "
          f"date/time {datetime.now(timezone.utc).isoformat()}.")
    if fake_backend:
        print("\n" + "!" * 68)
        print("FAKE BACKEND, do not report these numbers")
        print(f"Results were isolated in {results_root.relative_to(ROOT)}/")
        print("!" * 68)


if __name__ == "__main__":
    main()
