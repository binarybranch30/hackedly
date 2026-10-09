"""The grading workflow. The UI and the eval call ONLY functions in this file.

grade_script  -> OWNER: Person A (the AI steps)
approve / export_csv -> plumbing, already written; both may use them.
"""
import csv
from pathlib import Path

from copilot import audit, config, store
from copilot.fake import fake_script_grade
from copilot.schemas import AnchorGrade, AuditEntry, Rubric, Script, ScriptGrade


def grade_script(script: Script, rubric: Rubric,
                 anchors: list[AnchorGrade] | None = None,
                 calibrated: bool = True) -> ScriptGrade:
    """Grade one script. Steps (TODO Person A):

    1. Image check (Pillow can open it? not tiny?) -> else flag UNREADABLE.
    2. models.generate_json(TRANSCRIBE_SYSTEM, ..., image, Transcription)
       -> if legibility == "unreadable": flag UNREADABLE, stop.
    3. Grade TWICE: models.generate_json(GRADE_SYSTEM,
       build_grade_prompt(rubric, t, anchors if calibrated else None), image, ItemScores)
    4. rules.apply(...) on run 1 (and run 2 for its total).
       If |total1 - total2| >= config.DISAGREE_THRESHOLD -> flag RUNS_DISAGREE.
    5. ModelError anywhere -> flag MODEL_ERROR (never crash the batch).
    6. If last_backend_used() != config.MODEL_BACKEND -> flag FALLBACK_USED.
    7. status = "needs_review" if flags else "auto_ok".
    8. audit.log every step; store.save_grade(result).

    Until then this returns FAKE grades so the UI branch can work.
    """
    grade = fake_script_grade(script.script_id, rubric)
    store.save_grade(grade)
    audit.log(AuditEntry(actor="system", action="grade", script_id=script.script_id,
                         after=str(grade.total), reason="FAKE grade (pipeline not built yet)",
                         backend=grade.backend, model=grade.model))
    return grade


def approve(script_id: str, edits: dict[str, int], teacher: str = "teacher") -> ScriptGrade:
    """Teacher approves a script, optionally editing marks {item_id: new_marks}.
    Every edit and the approval go to the audit log. Total is recomputed by code."""
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    for item in grade.items:
        if item.item_id in edits and edits[item.item_id] != item.final_marks:
            audit.log(AuditEntry(actor="teacher", action="edit", script_id=script_id,
                                 item_id=item.item_id, before=str(item.final_marks),
                                 after=str(edits[item.item_id]), reason=teacher))
            item.final_marks = edits[item.item_id]
    grade.total = sum(i.final_marks for i in grade.items)
    grade.status = "approved"
    store.save_grade(grade)
    audit.log(AuditEntry(actor="teacher", action="approve", script_id=script_id,
                         after=str(grade.total), reason=teacher))
    return grade


def export_csv(path: str | Path) -> int:
    """Write APPROVED scripts only to CSV. Returns number of rows written."""
    rubric = store.load_rubric()
    approved = [g for g in store.load_grades() if g.status in ("approved", "released")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["script_id"] + [i.item_id for i in rubric.items] + ["total", "max_total"])
        for g in approved:
            marks = {i.item_id: i.final_marks for i in g.items}
            w.writerow([g.script_id] + [marks.get(i.item_id, "") for i in rubric.items]
                       + [g.total, g.max_total])
    for g in approved:
        if g.status != "released":
            g.status = "released"
            store.save_grade(g)
            audit.log(AuditEntry(actor="teacher", action="release", script_id=g.script_id,
                                 after=str(g.total)))
    return len(approved)
