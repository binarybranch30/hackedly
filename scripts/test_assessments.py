"""Offline tests for assessments (workspaces), the class roster and exports with names.
Uses a temporary data folder, so real data is never touched.  python scripts/test_assessments.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import assessments, config, pipeline, sample, store  # noqa: E402
from copilot.schemas import Script  # noqa: E402

real = config.DATA_DIR
tmp = Path(tempfile.mkdtemp())
(tmp / "rubric.example.json").write_text((real / "rubric.example.json").read_text())
config.DATA_DIR = tmp
config.MODEL_BACKEND = "fake"
try:
    assert config.workspace() == tmp and assessments.list_all() == []

    a = assessments.create("Unit Test 1", "9A", "Physics")
    b = assessments.create("Unit Test 1", "9A", "Physics")       # same name -> unique slug
    assert a != b and config.active_assessment() == b and config.workspace() == tmp / "assessments" / b
    assert [m["slug"] for m in assessments.list_all()] == [b, a]

    # Each assessment has its own roster, grades and audit log
    store.save_roster(store.parse_roster_csv(b"Roll No,Student Name\nR01,Asha\nR02,Bilal\n,skip\n"))
    assert store.student_names() == {"R01": "Asha", "R02": "Bilal"}
    g = pipeline.grade_script(Script(script_id="R01", image_path="x.jpg"), store.load_rubric(), [])
    pipeline.approve("R01", {})
    out = tmp / "m.csv"
    pipeline.export_csv(out)
    assert out.read_text().splitlines()[1].startswith("R01,Asha,"), out.read_text()
    assert config.audit_path() == tmp / "assessments" / b / "audit.jsonl" and config.audit_path().exists()

    assessments.activate(a)
    assert store.load_grades() == [] and store.load_roster() == [], "assessments must not share data"

    # Sample mode overrides, and switching it off returns to the active assessment
    sample.enable()
    assert config.workspace() == tmp / "sample" and len(sample.answer_sheets()) == 8
    sample.disable()
    assert config.workspace() == tmp / "assessments" / a

    assessments.delete(a)
    assert config.active_assessment() == "" and config.workspace() == tmp
    try:
        store.parse_roster_csv(b"name\nAsha\n")
        raise AssertionError("roster without roll numbers should fail")
    except ValueError:
        pass
    print("ALL ASSESSMENT TESTS PASSED")
finally:
    config.DATA_DIR = real
