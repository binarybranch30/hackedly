#!/usr/bin/env python3
"""Test report generation and grading folder logic.

Usage:
    python scripts/test_report.py
"""
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import config, store  # noqa: E402
from copilot.report import write_report  # noqa: E402
from copilot.schemas import GradedItem, ScriptGrade, Transcription  # noqa: E402
from scripts.grade_folder import grade_folder  # noqa: E402

# Ensure fake mode
config.MODEL_BACKEND = "fake"
os.environ["MODEL_BACKEND"] = "fake"


def test_reports_end_to_end():
    rubric = store.load_rubric()

    # 1. Create 4 temporary images with Pillow
    temp_dir = Path(tempfile.mkdtemp(prefix="ag_test_scripts_"))
    img_names = ["script_01.jpg", "script_02.png", "script_03.jpeg", "script_04.jpg"]
    for i, name in enumerate(img_names):
        # Make one image > 900px to test thumbnail resizing
        size = (1100, 750) if i == 0 else (450, 450)
        im = Image.new("RGB", size, color=(230 + i * 5, 230 + i * 5, 230 + i * 5))
        im.save(temp_dir / name)

    # 2. Run grade_folder logic into a temp output directory
    out_dir = Path(tempfile.mkdtemp(prefix="ag_test_report_out_"))
    res = grade_folder(temp_dir, out_dir)
    grades = res["grades"]
    rep = res["report_result"]

    # Assertion 1: All 3 files exist
    report_file = rep["report"]
    flagged_file = rep["flagged"]
    marks_file = rep["marks"]
    assert report_file.is_file(), f"report.html missing: {report_file}"
    assert flagged_file.is_file(), f"flagged.csv missing: {flagged_file}"
    assert marks_file.is_file(), f"marks_all.csv missing: {marks_file}"

    # Read contents
    html_text = report_file.read_text(encoding="utf-8")

    with open(flagged_file, "r", encoding="utf-8") as f:
        flagged_reader = list(csv.DictReader(f))
        flagged_sids_in_csv = {row["script_id"] for row in flagged_reader}

    with open(marks_file, "r", encoding="utf-8") as f:
        marks_reader = list(csv.DictReader(f))
        marks_by_sid = {row["script_id"]: row for row in marks_reader}

    # Assertion 2: Every flagged script appears in flagged.csv and in the HTML "Flagged scripts" section
    flagged_section_idx = html_text.find("<h2>Flagged scripts</h2>")
    assert flagged_section_idx != -1, "Flagged scripts section missing in HTML body"
    # Isolate flagged section up to the closing </div> of flagged-section
    flagged_section_end = html_text.find("</div>\n\n<div class=", flagged_section_idx)
    if flagged_section_end == -1:
        flagged_section_end = html_text.find("</div>\n<div class=", flagged_section_idx)
    flagged_section_html = (
        html_text[flagged_section_idx:flagged_section_end]
        if flagged_section_end != -1
        else html_text[flagged_section_idx:flagged_section_idx + 4000]
    )

    flagged_grades = [g for g in grades if g.flags]
    for fg in flagged_grades:
        assert fg.script_id in flagged_sids_in_csv, f"Flagged script {fg.script_id} missing in flagged.csv"
        assert fg.script_id in flagged_section_html, f"Flagged script {fg.script_id} missing in HTML Flagged scripts section"

    # Assertion 3: The HTML contains <mark>
    assert "<mark>" in html_text, "report.html does not contain <mark>"

    # Assertion 5: Totals in marks_all.csv equal ScriptGrade.total
    assert len(marks_reader) == len(grades)
    for g in grades:
        assert g.script_id in marks_by_sid, f"Script {g.script_id} missing from marks_all.csv"
        csv_total = int(marks_by_sid[g.script_id]["total"])
        assert csv_total == g.total, f"Total mismatch for {g.script_id}: csv={csv_total} != grade={g.total}"

    # Now test with custom ScriptGrade containing <script>alert(1)</script>
    xss_out_dir = Path(tempfile.mkdtemp(prefix="ag_test_xss_out_"))
    xss_transcription_text = (
        "Here is the answer: <script>alert(1)</script> force equals mass times acceleration, F = ma."
    )
    xss_quote = "<script>alert(1)</script>"
    xss_grade = ScriptGrade(
        script_id="XSS_SCRIPT",
        run_id="run_xss",
        backend="fake",
        model="fake",
        calibrated=True,
        transcription=Transcription(
            legibility="good",
            text=xss_transcription_text,
            unclear_spans=[],
        ),
        items=[
            GradedItem(
                item_id="1a",
                marks_awarded=2,
                evidence_quote=xss_quote,
                reasoning="Extracted <script>alert(1)</script> from answer.",
                confidence="low",
                evidence_found=True,
                final_marks=2,
            ),
            GradedItem(
                item_id="1b",
                marks_awarded=1,
                evidence_quote="force equals mass times acceleration",
                reasoning="Reasoning with mass and acceleration",
                confidence="high",
                evidence_found=True,
                final_marks=1,
            ),
            GradedItem(
                item_id="1c",
                marks_awarded=1,
                evidence_quote="F = ma",
                reasoning="Formula reasoning",
                confidence="medium",
                evidence_found=True,
                final_marks=1,
            ),
        ],
        total=4,
        max_total=5,
        flags=["LOW_CONFIDENCE", "RULE_VIOLATION"],
        status="needs_review",
    )

    combined_grades = [xss_grade] + grades
    xss_res = write_report(combined_grades, rubric, xss_out_dir, image_dir=temp_dir)
    xss_html = xss_res["report"].read_text(encoding="utf-8")

    # Assertion 4: The HTML contains no unescaped <script>, even when a fake transcription contains <script>alert(1)</script>
    # Check that no <script> or <script ...> tags exist anywhere in the HTML
    script_tag_match = re.search(r"<\s*script\b", xss_html, re.IGNORECASE)
    assert script_tag_match is None, f"Found unescaped script tag in HTML at position {script_tag_match.start()}"

    # And check that the escaped text is present
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in xss_html, "Escaped script text missing from HTML"

    # And check that <mark> is still present
    assert "<mark>" in xss_html, "Expected <mark> in HTML with custom grade"

    # Also verify that xss_grade appears in flagged.csv and in the Flagged scripts section
    with open(xss_res["flagged"], "r", encoding="utf-8") as f:
        xss_flagged_rows = list(csv.DictReader(f))
        assert any(r["script_id"] == "XSS_SCRIPT" for r in xss_flagged_rows), "XSS_SCRIPT missing from flagged.csv"

    xss_flagged_section_idx = xss_html.find("<h2>Flagged scripts</h2>")
    assert xss_flagged_section_idx != -1, "Flagged scripts section missing in xss_html"
    xss_flagged_section_end = xss_html.find("</div>\n\n<div class=", xss_flagged_section_idx)
    if xss_flagged_section_end == -1:
        xss_flagged_section_end = xss_html.find("</div>\n<div class=", xss_flagged_section_idx)
    xss_flagged_html = (
        xss_html[xss_flagged_section_idx:xss_flagged_section_end]
        if xss_flagged_section_end != -1
        else xss_html[xss_flagged_section_idx:xss_flagged_section_idx + 4000]
    )
    assert "XSS_SCRIPT" in xss_flagged_html, "XSS_SCRIPT missing from Flagged scripts section"

    # Also verify marks_all.csv totals for combined_grades
    with open(xss_res["marks"], "r", encoding="utf-8") as f:
        combined_marks_rows = list(csv.DictReader(f))
        combined_by_sid = {r["script_id"]: r for r in combined_marks_rows}
        for g in combined_grades:
            assert int(combined_by_sid[g.script_id]["total"]) == g.total

    # Also test CLI invocation directly
    cli_out = Path(tempfile.mkdtemp(prefix="ag_test_cli_out_"))
    cli_cmd = [
        sys.executable,
        str(Path(__file__).resolve().parent / "grade_folder.py"),
        str(temp_dir),
        "--out",
        str(cli_out),
    ]
    proc = subprocess.run(cli_cmd, capture_output=True, text=True, check=True)
    assert "Report:" in proc.stdout
    assert "Summary:" in proc.stdout
    assert (cli_out / "report.html").is_file()
    assert (cli_out / "flagged.csv").is_file()
    assert (cli_out / "marks_all.csv").is_file()

    print("ALL REPORT TESTS PASSED")


if __name__ == "__main__":
    test_reports_end_to_end()
