"""The grading workflow. The UI and the eval call ONLY functions in this file.

grade_script  -> OWNER: Person A (the AI steps)

approve / export_csv -> plumbing, already written; both may use them.
"""
import csv
import uuid
from pathlib import Path

from PIL import Image

from copilot import audit, config, models, prompts, rules, store
from copilot.fake import fake_script_grade
from copilot.schemas import (FLAG_FALLBACK_USED, FLAG_MODEL_ERROR, FLAG_RUNS_DISAGREE,
                             FLAG_UNREADABLE, AnchorGrade, AuditEntry, ItemScores, Rubric,
                             Script, ScriptGrade, Transcription)


def grade_script(script: Script, rubric: Rubric,
                 anchors: list[AnchorGrade] | None = None,
                 calibrated: bool = True) -> ScriptGrade:
    """Grade one script: image check -> transcribe -> grade x2 -> rules -> route.

    Never raises for model problems: they become flags so a batch never crashes.
    With MODEL_BACKEND=fake it returns a varied fake grade (for UI work).
    """
    if config.MODEL_BACKEND == "fake":
        grade = fake_script_grade(script.script_id, rubric)
        grade.calibrated = calibrated
        _finish(grade, "FAKE grade (MODEL_BACKEND=fake)")
        return grade

    sid = script.script_id
    grade = ScriptGrade(script_id=sid, run_id=uuid.uuid4().hex[:8], backend=config.MODEL_BACKEND,
                        model=models.model_name(config.MODEL_BACKEND), calibrated=calibrated,
                        max_total=rubric.max_total)
    backends_used: set[str] = set()

    # 1. Image check (code)
    problem = _image_problem(script.image_path)
    if problem:
        grade.flags = [FLAG_UNREADABLE]
        _finish(grade, f"image check failed: {problem}")
        return grade

    try:
        # 2. Transcribe (Gemma vision)
        t = models.generate_json(prompts.TRANSCRIBE_SYSTEM,
                                 "Transcribe this handwritten answer.",
                                 script.image_path, Transcription, script_id=sid)
        backends_used.add(models.last_backend_used())
        grade.transcription = t
        audit.log(AuditEntry(actor="system", action="transcribe", script_id=sid,
                             after=t.legibility, backend=models.last_backend_used(),
                             model=models.model_name(models.last_backend_used())))
        if t.legibility == "unreadable":
            grade.flags = [FLAG_UNREADABLE]
            _finish(grade, "model could not read the handwriting")
            return grade

        # 3. Grade twice (self-consistency)
        prompt = prompts.build_grade_prompt(rubric, t, anchors if calibrated else None)
        runs = []
        for _ in range(2):
            scores = models.generate_json(prompts.GRADE_SYSTEM, prompt, script.image_path,
                                          ItemScores, script_id=sid)
            backends_used.add(models.last_backend_used())
            runs.append(rules.apply(rubric, scores, t))
    except Exception as e:  # ModelError, network errors, ... -> flag, never crash the batch
        grade.flags = sorted(set(grade.flags) | {FLAG_MODEL_ERROR})
        audit.log(AuditEntry(actor="system", action="error", script_id=sid, reason=str(e)[:300]))
        _finish(grade, f"model error: {type(e).__name__}")
        return grade

    # 4. Rules + routing (code)
    (items, total, flags), (_, total2, flags2) = runs
    flags = set(flags) | set(flags2)
    if abs(total - total2) >= config.DISAGREE_THRESHOLD:
        flags.add(FLAG_RUNS_DISAGREE)
    if backends_used - {config.MODEL_BACKEND}:
        flags.add(FLAG_FALLBACK_USED)
        grade.backend = ",".join(sorted(backends_used))
    grade.items, grade.total, grade.flags = items, total, sorted(flags)
    _finish(grade, f"run totals {total} and {total2}")
    return grade


def _image_problem(path: str) -> str | None:
    """Return a reason if the image can't be used, else None."""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            w, h = im.size
    except Exception as e:
        return f"cannot open image ({type(e).__name__})"
    if min(w, h) < 300:
        return f"image too small ({w}x{h})"
    return None


def _finish(grade: ScriptGrade, reason: str) -> None:
    """Set status, save, and log the grade and any flags."""
    grade.status = "needs_review" if grade.flags else "auto_ok"
    store.save_grade(grade)
    audit.log(AuditEntry(actor="system", action="grade", script_id=grade.script_id,
                         after=f"{grade.total}/{grade.max_total}", reason=reason,
                         backend=grade.backend, model=grade.model))
    if grade.flags:
        audit.log(AuditEntry(actor="system", action="flag", script_id=grade.script_id,
                             after=",".join(grade.flags), reason="sent to teacher review"))


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
