"""Evaluation on the sample class with the REAL model (no teacher marks needed for most metrics).

    python eval/sample_eval.py [--runs 3]

What is measured, and against what:
- Reading accuracy: Gemma 4's transcription vs the exact text printed on each sheet (we generated
  the sheets, so the true text is known). Word accuracy = 1 - word error rate.
- Consistency: the same sheet graded --runs times; how often the total is identical.
- Unreadable detection: the smudged sheet (R06) must be flagged UNREADABLE, never guessed.
- Evidence: share of awarded marks whose quote is really in the answer (checked by code).
- Marks vs REFERENCE KEY: the key below was written together with the sample answers by the team.
  It is NOT a teacher's marking. Reported with and without the 3 anchor scripts.
- Speed: seconds and model calls per sheet.

Runs in a temporary data folder, so real and live data are never touched.
Results: eval/results/sample_eval.json and a printed table.
"""
import argparse
import json
import re
import shutil
import statistics
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import config, pipeline, sample, store  # noqa: E402
from copilot.schemas import Script  # noqa: E402

# Reference key (written with the sample answers; NOT a teacher). item marks 1a, 1b, 1c.
KEY = {"R01": (2, 1, 2), "R02": (2, 0, 1), "R03": (1, 0, 1), "R04": (2, 0, 2),
       "R05": (2, 0, 1), "R07": (2, 1, 2), "R08": (2, 1, 2)}
ITEMS = ("1a", "1b", "1c")


def words(t: str) -> list[str]:
    t = re.sub(r"^\s*roll no\.?\s*\w+\s*[·.]\s*q1\s*", "", t.lower())  # header line printed on the sheet
    return re.findall(r"[a-z0-9]+", t)


def word_accuracy(truth: str, read: str) -> float:
    a, b = words(truth), words(read)
    sm = SequenceMatcher(None, a, b, autojunk=False)
    errors = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
    return max(0.0, 1 - errors / max(len(a), 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    real = config.DATA_DIR
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(real / "rubric.example.json", tmp / "rubric.example.json")
    config.DATA_DIR = tmp
    try:
        sample.enable()
        rubric, anchors = store.load_rubric(), store.load_anchors()
        texts = {sid: t for sid, t, _ in sample.STUDENTS}
        sheets = [Script(script_id=p.stem, image_path=str(p)) for p in sample.answer_sheets()]
        runs = {"calibrated": [], "uncalibrated": []}
        for n in range(args.runs):
            for g in pipeline.grade_batch(sheets, rubric, anchors, calibrated=True)[0]:
                runs["calibrated"].append((n, g))
            for f in store.grades_dir().glob("*.json"):
                f.unlink()
            print(f"calibrated run {n + 1}/{args.runs} done", flush=True)
        for g in pipeline.grade_batch(sheets, rubric, anchors, calibrated=False)[0]:
            runs["uncalibrated"].append((0, g))
        print("uncalibrated run done", flush=True)
    finally:
        config.DATA_DIR = real

    cal = runs["calibrated"]
    readable = [g for _, g in cal if g.script_id in KEY]
    acc = [word_accuracy(texts[g.script_id], g.transcription.text) for g in readable if g.transcription]
    r06 = [g for _, g in cal if g.script_id == "R06"]
    awarded = [i for g in readable for i in g.items if i.final_marks > 0]
    by_sheet: dict[str, list[int]] = {}
    for _, g in cal:
        if g.script_id in KEY:
            by_sheet.setdefault(g.script_id, []).append(g.total)

    def mark_stats(gs):
        gs = [g for g in gs if g.script_id in KEY and g.items]
        err = [abs(g.total - sum(KEY[g.script_id])) for g in gs]
        item_ok = [next((i.final_marks for i in g.items if i.item_id == it), 0) == KEY[g.script_id][k]
                   for g in gs for k, it in enumerate(ITEMS)]
        return {"n": len(gs), "mae_total": round(statistics.mean(err), 2),
                "exact_total_pct": round(100 * sum(e == 0 for e in err) / len(err)),
                "within_1_pct": round(100 * sum(e <= 1 for e in err) / len(err)),
                "item_agreement_pct": round(100 * sum(item_ok) / len(item_ok))}

    res = {
        "model": sorted({g.model for _, g in cal}),
        "sheets": len(sheets), "runs_calibrated": args.runs,
        "reading_word_accuracy_pct": round(100 * statistics.mean(acc), 1),
        "reading_word_accuracy_min_pct": round(100 * min(acc), 1),
        "unreadable_flagged": f"{sum('UNREADABLE' in g.flags for g in r06)}/{len(r06)}",
        "evidence_found_pct": round(100 * sum(i.evidence_found for i in awarded) / max(len(awarded), 1)),
        "consistency_identical_pct": round(100 * sum(len(set(v)) == 1 for v in by_sheet.values()) / len(by_sheet)),
        "consistency_mean_range": round(statistics.mean(max(v) - min(v) for v in by_sheet.values()), 2),
        "marks_vs_reference_key": {"calibrated": mark_stats(g for _, g in cal),
                                   "uncalibrated": mark_stats(g for _, g in runs["uncalibrated"])},
        "flagged_for_review_pct": round(100 * sum(bool(g.flags) for _, g in cal) / len(cal)),
        "fallback_used": sum("FALLBACK_USED" in g.flags for _, g in cal + runs["uncalibrated"]),
        "seconds_per_sheet": round(statistics.mean(g.seconds for _, g in cal if g.seconds), 1),
        "model_calls_per_sheet": round(statistics.mean(g.model_calls for _, g in cal), 1),
        "per_sheet_totals": {k: v for k, v in sorted(by_sheet.items())},
        "reference_totals": {k: sum(v) for k, v in KEY.items()},
        "caveat": "8 synthetic sheets in a handwriting font, 1 question; reference key written by the team, "
                  "not a teacher. Indicative only.",
    }
    out = config.ROOT / "eval" / "results" / "sample_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
