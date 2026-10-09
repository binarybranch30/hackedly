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
    # Sheet file names carry roll number + student name
    P = store.parse_sheet_filename
    assert P("R07 Asha Rao.pdf") == ("R07", "Asha Rao") and P("r7_bilal khan.jpg") == ("R7", "Bilal Khan")
    assert P("R12.pdf") == ("R12", "") and P("R03 - Chitra Iyer.PDF") == ("R03", "Chitra Iyer")
    assert P("IMG_2034.jpg") is None and P("scan.pdf") is None
    c = assessments.create("Names test")
    assert store.add_students([("R07", "Asha Rao"), ("R08", "")]) == 2
    assert store.add_students([("R08", "Dev Shah"), ("R07", "Other")]) == 1   # fills blanks, keeps names
    assert store.student_names() == {"R07": "Asha Rao", "R08": "Dev Shah"}

    # Class insights: averages by code, insights by model (fake), saved per assessment
    rubric = store.load_rubric()
    from copilot.schemas import Rubric, RubricItem
    rubric = Rubric(rubric_id="t", question="Q", items=[
        RubricItem(item_id="1a", description="law", max_marks=2, allowed_marks=[0, 1, 2]),
        RubricItem(item_id="1b", description="symbols", max_marks=1, allowed_marks=[0, 1])])
    store.save_rubric(rubric)
    try:
        pipeline.class_report(rubric)
        raise AssertionError("needs at least 2 sheets")
    except ValueError:
        pass
    for sid in ("R07", "R08"):
        pipeline.grade_script(Script(script_id=sid, image_path="x.jpg"), rubric, [])
    rep = pipeline.class_report(rubric)
    grades = store.load_grades()
    exp = sum(next(i.final_marks for i in g.items if i.item_id == "1a") for g in grades) / 2
    assert rep.averages["1a"] == round(exp, 2) and rep.n_sheets == 2 and len(rep.insights.reteach_topics) == 2
    assert store.load_class_report().insights.struggled_concept

    # Feedback: only after approval; quotes checked against the answer; teacher approves edits
    try:
        pipeline.draft_feedback("R07", rubric)
        raise AssertionError("feedback before approval must fail")
    except ValueError:
        pass
    pipeline.approve("R07", {})
    g, missing = pipeline.draft_feedback("R07", rubric)
    assert g.feedback_status == "draft" and g.feedback and missing == [], (g.feedback, missing)
    pipeline.approve_feedback("R07", g.feedback + " Well done.")
    out = tmp / "fb.csv"
    pipeline.export_csv(out)
    assert out.read_text().splitlines()[0].endswith(",feedback") and "Well done." in out.read_text()
    print("ALL ASSESSMENT TESTS PASSED")
finally:
    config.DATA_DIR = real
