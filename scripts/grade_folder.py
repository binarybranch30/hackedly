#!/usr/bin/env python3
"""Grade a folder of handwritten script images and generate HTML and CSV reports.

Usage:
    python scripts/grade_folder.py data/scripts --out reports/<name> [--uncalibrated] [--from-saved]
"""
import argparse
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import pipeline, store  # noqa: E402
from copilot.report import write_report  # noqa: E402
from copilot.schemas import Script  # noqa: E402


def grade_folder(folder: Path | str, out: Path | str, uncalibrated: bool = False,
                 from_saved: bool = False, on_progress=None) -> dict:
    """Grade images in folder (or load from saved) and write report to out."""
    out_dir = Path(out)
    folder_path = Path(folder) if folder else None

    if from_saved:
        grades = store.load_grades()
        rubric = store.load_rubric()
        result = write_report(grades, rubric, out_dir, image_dir=folder_path)
        return {"grades": grades, "drift": [], "report_result": result}

    if folder_path is None or not folder_path.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    image_files = sorted([
        p for p in folder_path.iterdir()
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])

    scripts = [Script(script_id=p.stem, image_path=str(p)) for p in image_files]
    rubric = store.load_rubric()
    anchors = store.load_anchors()

    def default_progress(done: int, total: int, grade):
        flag_info = f" flags={grade.flags}" if grade.flags else ""
        print(f"[{done}/{total}] {grade.script_id}: total={grade.total}/{grade.max_total} status={grade.status}{flag_info}")

    progress_cb = on_progress or default_progress

    grades, drift = pipeline.grade_batch(
        scripts,
        rubric,
        anchors,
        calibrated=not uncalibrated,
        on_progress=progress_cb,
    )

    for d in drift:
        if d.get("drifted"):
            print(f"DRIFT WARNING: Anchor {d.get('anchor_id')} drifted! Teacher: {d.get('teacher_total')}, System: {d.get('system_total')}, Diff: {d.get('diff')}")
        elif d.get("error"):
            print(f"Drift check error for anchor {d.get('anchor_id')}: {d.get('error')}")

    result = write_report(grades, rubric, out_dir, image_dir=folder_path)
    return {"grades": grades, "drift": drift, "report_result": result}


def main():
    parser = argparse.ArgumentParser(description="Grade handwritten scripts in a folder and generate reports.")
    parser.add_argument("folder", nargs="?", default="data/scripts", help="Path to folder containing script images")
    parser.add_argument("--out", "-o", required=True, help="Output directory for reports")
    parser.add_argument("--uncalibrated", action="store_true", help="Disable calibration with anchors")
    parser.add_argument("--from-saved", action="store_true", help="Skip grading and build report from saved grades")

    args = parser.parse_args()

    res = grade_folder(
        folder=args.folder,
        out=args.out,
        uncalibrated=args.uncalibrated,
        from_saved=args.from_saved,
    )

    rep = res["report_result"]
    grades = res["grades"]
    print(f"Report: {rep['report']}")
    print(f"Flagged CSV: {rep['flagged']}")
    print(f"Marks CSV: {rep['marks']}")
    print(f"Summary: {len(grades)} scripts processed, {rep['n_flagged']} flagged for review -> {rep['report']}")


if __name__ == "__main__":
    main()
