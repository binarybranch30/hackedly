"""The grading workflow. The UI and the eval call ONLY functions in this file.

Functions for the UI / eval:
  grade_script(script, rubric, anchors, calibrated) -> ScriptGrade   one script
  grade_batch(scripts, rubric, anchors, on_progress) -> (grades, drift_results)
  transcribe_image(image_path) -> Transcription      pre-fill the Anchors form
  drift_check(rubric, anchors, index) -> dict         re-grade one anchor
  extract_rubric(image_path) -> (Rubric, problems)    draft rubric from a question-paper photo
  approve(script_id, edits) / export_csv(path)        teacher approval + release
"""
import csv
import time
import uuid
from pathlib import Path

from PIL import Image

from copilot import audit, config, models, prompts, rules, store
from copilot.fake import fake_script_grade
from copilot.schemas import (FLAG_FALLBACK_USED, FLAG_MODEL_ERROR, FLAG_RUNS_DISAGREE,
                             FLAG_UNREADABLE, AnchorGrade, AuditEntry, ItemScores, Rubric,
                             Script, ScriptGrade, Transcription)

DRIFT_EVERY = 5        # run a drift check after every N scripts in a batch
DRIFT_TOLERANCE = 1    # warn if a re-graded anchor is more than this many marks off


def grade_script(script: Script, rubric: Rubric,
                 anchors: list[AnchorGrade] | None = None,
                 calibrated: bool = True) -> ScriptGrade:
    """Grade one script: image check -> transcribe -> grade x2 -> rules -> route.

    Never raises for model problems: they become flags so a batch never crashes.
    With MODEL_BACKEND=fake it returns a varied fake grade (for UI work).
    """
    start, calls0 = time.perf_counter(), models.call_count()
    if config.MODEL_BACKEND == "fake":
        grade = fake_script_grade(script.script_id, rubric)
        grade.calibrated = calibrated
        _finish(grade, "FAKE grade (MODEL_BACKEND=fake)", start, calls0)
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
        _finish(grade, f"image check failed: {problem}", start, calls0)
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
            _finish(grade, "model could not read the handwriting", start, calls0)
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
        _finish(grade, f"model error: {type(e).__name__}", start, calls0)
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
    _finish(grade, f"run totals {total} and {total2}", start, calls0)
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


def _finish(grade: ScriptGrade, reason: str, start: float, calls0: int) -> None:
    """Set status + timing, save, and log the grade and any flags."""
    grade.status = "needs_review" if grade.flags else "auto_ok"
    grade.seconds = round(time.perf_counter() - start, 2)
    grade.model_calls = models.call_count() - calls0
    store.save_grade(grade)
    audit.log(AuditEntry(actor="system", action="grade", script_id=grade.script_id,
                         after=f"{grade.total}/{grade.max_total}",
                         reason=f"{reason} ({grade.seconds}s, {grade.model_calls} model calls)",
                         backend=grade.backend, model=grade.model))
    if grade.flags:
        audit.log(AuditEntry(actor="system", action="flag", script_id=grade.script_id,
                             after=",".join(grade.flags), reason="sent to teacher review"))


def grade_batch(scripts: list[Script], rubric: Rubric, anchors: list[AnchorGrade] | None = None,
                calibrated: bool = True, on_progress=None) -> tuple[list[ScriptGrade], list[dict]]:
    """Grade many scripts. Every DRIFT_EVERY scripts, re-grade one anchor (rotating)
    to check the system still marks like the teacher.

    on_progress(done, total, grade) is called after each script (e.g. a progress bar).
    Returns (grades, drift_results); see drift_check for the dict format.
    """
    grades, drift = [], []
    for n, script in enumerate(scripts, 1):
        g = grade_script(script, rubric, anchors, calibrated)
        grades.append(g)
        if on_progress:
            on_progress(n, len(scripts), g)
        if calibrated and anchors and len(anchors) >= 2 and n % DRIFT_EVERY == 0:
            drift.append(drift_check(rubric, anchors, index=(n // DRIFT_EVERY - 1) % len(anchors)))
    return grades, drift


def transcribe_image(image_path: str) -> Transcription:
    """Transcribe one image (used to pre-fill the anchor form; the teacher corrects it).
    Raises ValueError for unusable images and ModelError if the model fails."""
    problem = _image_problem(image_path)
    if problem:
        raise ValueError(problem)
    return models.generate_json(prompts.TRANSCRIBE_SYSTEM, "Transcribe this handwritten answer.",
                                image_path, Transcription)


def drift_check(rubric: Rubric, anchors: list[AnchorGrade], index: int = 0) -> dict:
    """Re-grade anchor `index` from its text, using the OTHER anchors as examples
    (leave-one-out, so the model can't just copy the answer). Compares with the
    teacher's marks.

    Returns {"anchor_id", "teacher_total", "system_total", "diff", "drifted", "error"}.
    """
    a = anchors[index]
    others = [x for i, x in enumerate(anchors) if i != index]
    teacher_total = sum(a.marks.get(it.item_id, 0) for it in rubric.items)
    result = {"anchor_id": a.script_id, "teacher_total": teacher_total, "system_total": None,
              "diff": None, "drifted": False, "error": None}
    t = Transcription(legibility="good", text=a.transcription)
    try:
        scores = models.generate_json(prompts.GRADE_SYSTEM, prompts.build_grade_prompt(rubric, t, others),
                                      None, ItemScores, script_id=a.script_id)
        _, total, _ = rules.apply(rubric, scores, t)
        result.update(system_total=total, diff=total - teacher_total,
                      drifted=abs(total - teacher_total) > DRIFT_TOLERANCE)
    except Exception as e:  # never crash the batch
        result["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    audit.log(AuditEntry(actor="system", action="drift_check", script_id=a.script_id,
                         before=str(teacher_total), after=str(result["system_total"]),
                         reason="DRIFT WARNING" if result["drifted"] else (result["error"] or "ok"),
                         backend=models.last_backend_used(),
                         model=models.model_name(models.last_backend_used())))
    return result


def extract_rubric(image_path: str) -> tuple[Rubric, list[str]]:
    """Draft a rubric from a photo of the question paper / marking scheme.

    Returns (draft, problems). `problems` are code-checked issues the teacher
    must fix. The draft is NEVER saved here: the teacher edits it and the UI
    saves it with store.save_rubric (human approval).
    Raises ValueError for unusable images and ModelError if the model fails.
    """
    problem = _image_problem(image_path)
    if problem:
        raise ValueError(problem)
    draft = models.generate_json(prompts.RUBRIC_SYSTEM,
                                 "Draft a marking rubric for this question paper.",
                                 image_path, Rubric)
    problems = check_rubric(draft)
    audit.log(AuditEntry(actor="system", action="transcribe", script_id="rubric",
                         after=f"{len(draft.items)} items, {draft.max_total} marks",
                         reason=f"rubric draft; problems: {problems or 'none'}",
                         backend=models.last_backend_used(),
                         model=models.model_name(models.last_backend_used())))
    return draft, problems


def check_rubric(rubric: Rubric) -> list[str]:
    """Code checks on a rubric (model-drafted or teacher-typed). Empty list = OK."""
    problems = []
    if not rubric.items:
        problems.append("rubric has no items")
    ids = [i.item_id for i in rubric.items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate item ids")
    for i in rubric.items:
        if i.max_marks <= 0:
            problems.append(f"{i.item_id}: max_marks must be positive")
        if not i.allowed_marks or 0 not in i.allowed_marks:
            problems.append(f"{i.item_id}: allowed marks should include 0")
        if max(i.allowed_marks, default=-1) != i.max_marks:
            problems.append(f"{i.item_id}: highest allowed mark should equal max_marks ({i.max_marks})")
        if any(m < 0 or m > i.max_marks for m in i.allowed_marks):
            problems.append(f"{i.item_id}: allowed marks must be between 0 and {i.max_marks}")
        if not i.description.strip():
            problems.append(f"{i.item_id}: missing description")
    return problems


def approve(script_id: str, edits: dict[str, int], teacher: str = "teacher") -> ScriptGrade:
    """Teacher approves a script, optionally editing marks {item_id: new_marks}.
    Every edit and the approval go to the audit log. Total is recomputed by code."""
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    allowed = {it.item_id: it.allowed_marks for it in store.load_rubric().items}
    for item_id, m in edits.items():
        if item_id in allowed and m not in allowed[item_id]:
            raise ValueError(f"{item_id}: {m} is not an allowed mark {allowed[item_id]}")
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
