"""The grading workflow. The UI and the eval call ONLY functions in this file.

Functions for the UI / eval:
  grade_script(script, rubric, anchors, calibrated) -> ScriptGrade   one script
  grade_batch(scripts, rubric, anchors, on_progress) -> (grades, drift_results)
  transcribe_image(image_path) -> Transcription      pre-fill the Anchors form
  drift_check(rubric, anchors, index) -> dict         re-grade one anchor
  extract_rubric(image_path) -> (Rubric, problems)    draft rubric from a question-paper photo
  approve(script_id, edits) / export_csv(path)        teacher approval + release
  mark_unreadable / undo_unreadable / reopen_for_new_scan   "cannot mark, needs rescan"
  class_report(rubric) -> ClassReport                 class insights (model) + averages (code)
  draft_feedback / approve_feedback                   per-student feedback, teacher-approved
"""
import csv
import queue
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path


from copilot import audit, config, models, prompts, rules, store
from copilot.fake import fake_script_grade
from copilot.schemas import (ClassInsights, ClassReport, FeedbackDraft, FLAG_FALLBACK_USED, FLAG_MODEL_ERROR, FLAG_RUNS_DISAGREE,
                             FLAG_UNREADABLE, AnchorGrade, AuditEntry, GradedItem, ItemScores, Rubric,
                             Script, ScriptGrade, Transcription)

DRIFT_EVERY = 5        # run a drift check after every N scripts in a batch
DRIFT_TOLERANCE = 1    # warn if a re-graded anchor is more than this many marks off


# Live progress events (for the website's pipeline view).
# on_event(script_id, step, status, detail): step is one of STEPS,
# status is "running" | "ok" | "warn" | "fail".
STEPS = ("check", "read", "grade", "verify")


def grade_script(script: Script, rubric: Rubric,
                 anchors: list[AnchorGrade] | None = None,
                 calibrated: bool = True, on_event=None) -> ScriptGrade:
    """Grade one script: image check -> transcribe -> grade x2 -> rules -> route.

    Never raises for model problems: they become flags so a batch never crashes.
    With MODEL_BACKEND=fake it returns a varied fake grade (for UI work).
    """
    sid = script.script_id
    emit = (lambda step, status, detail="": on_event(sid, step, status, detail)) if on_event else \
        (lambda *a, **k: None)
    start, calls0 = time.perf_counter(), models.call_count()
    if config.MODEL_BACKEND == "fake":
        for step in STEPS:
            emit(step, "ok", "fake")
        grade = fake_script_grade(sid, rubric)
        grade.calibrated = calibrated
        _finish(grade, "FAKE grade (MODEL_BACKEND=fake)", start, calls0)
        return grade

    grade = ScriptGrade(script_id=sid, run_id=uuid.uuid4().hex[:8], backend=config.MODEL_BACKEND,
                        model=models.model_name(config.MODEL_BACKEND), calibrated=calibrated,
                        max_total=rubric.max_total)
    backends_used: set[str] = set()

    # 1. Image check (code)
    emit("check", "running")
    problem = _image_problem(script.image_path)
    if problem:
        emit("check", "fail", problem)
        grade.flags = [FLAG_UNREADABLE]
        _finish(grade, f"image check failed: {problem}", start, calls0)
        return grade
    emit("check", "ok")

    step = "read"
    try:
        # 2. Transcribe (Gemma vision)
        emit("read", "running")
        t = models.generate_json(prompts.TRANSCRIBE_SYSTEM,
                                 "Transcribe this handwritten answer.",
                                 script.image_path, Transcription, script_id=sid)
        backends_used.add(models.last_backend_used())
        grade.transcription = t
        audit.log(AuditEntry(actor="system", action="transcribe", script_id=sid,
                             after=t.legibility, backend=models.last_backend_used(),
                             model=models.model_name(models.last_backend_used())))
        if t.legibility == "unreadable":
            emit("read", "fail", "handwriting unreadable")
            grade.flags = [FLAG_UNREADABLE]
            _finish(grade, "model could not read the handwriting", start, calls0)
            return grade
        emit("read", "warn" if t.legibility == "partial" else "ok", f"{len(t.text.split())} words")

        # 3. Grade twice (self-consistency)
        step = "grade"
        emit("grade", "running", "run 1 of 2")
        prompt = prompts.build_grade_prompt(rubric, t, anchors if calibrated else None)
        runs = []
        for n in range(2):
            scores = models.generate_json(prompts.GRADE_SYSTEM, prompt, script.image_path,
                                          ItemScores, script_id=sid)
            backends_used.add(models.last_backend_used())
            runs.append(rules.apply(rubric, scores, t))
            if n == 0:
                emit("grade", "running", "run 2 of 2")
    except Exception as e:  # ModelError, network errors, ... -> flag, never crash the batch
        emit(step, "fail", type(e).__name__)
        grade.flags = sorted(set(grade.flags) | {FLAG_MODEL_ERROR})
        audit.log(AuditEntry(actor="system", action="error", script_id=sid, reason=str(e)[:300]))
        _finish(grade, f"model error: {type(e).__name__}", start, calls0)
        return grade
    (items, total, flags), (_, total2, flags2) = runs
    emit("grade", "ok" if total == total2 else "warn", f"runs: {total} and {total2}")

    # 4. Rules + routing (code)
    emit("verify", "running")
    flags = set(flags) | set(flags2)
    if abs(total - total2) >= config.DISAGREE_THRESHOLD:
        flags.add(FLAG_RUNS_DISAGREE)
    if backends_used - {config.MODEL_BACKEND}:
        flags.add(FLAG_FALLBACK_USED)
        grade.backend = ",".join(sorted(backends_used))
        grade.model = ", ".join(models.model_name(b) for b in sorted(backends_used))
    grade.items, grade.total, grade.flags = items, total, sorted(flags)
    found = sum(i.evidence_found for i in items if i.final_marks > 0)
    marked = sum(1 for i in items if i.final_marks > 0)
    emit("verify", "warn" if grade.flags else "ok", f"evidence {found}/{marked} found")
    _finish(grade, f"run totals {total} and {total2}", start, calls0)
    return grade


def _image_problem(path: str) -> str | None:
    """Return a reason if the image/PDF can't be used, else None."""
    try:
        im = models.load_image(path)
        w, h = im.size
    except Exception as e:
        return f"cannot open file ({type(e).__name__})"
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
                calibrated: bool = True, on_progress=None,
                on_event=None) -> tuple[list[ScriptGrade], list[dict]]:
    """Grade many scripts in parallel. Every DRIFT_EVERY scripts, re-grade one anchor
    (rotating) to check the system still marks like the teacher.

    on_progress(done, total, grade) is called after each script; on_event(script_id,
    step, status, detail) for every step. Both run on the CALLER's thread (safe for
    Streamlit). Returns (grades, drift_results); see drift_check for the dict format.
    """
    events: queue.Queue = queue.Queue()
    worker_event = (lambda *a: events.put(a)) if on_event else None

    def drain():
        while on_event and not events.empty():
            on_event(*events.get_nowait())

    grades, drift = [], []
    workers = max(1, min(config.PARALLEL_SCRIPTS, len(scripts)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(grade_script, s, rubric, anchors, calibrated, worker_event)
                   for s in scripts}
        while pending:
            done, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
            drain()
            for fut in done:
                g = fut.result()
                grades.append(g)
                if on_progress:
                    on_progress(len(grades), len(scripts), g)
                n = len(grades)
                if calibrated and anchors and len(anchors) >= 2 and n % DRIFT_EVERY == 0:
                    drift.append(drift_check(rubric, anchors, index=(n // DRIFT_EVERY - 1) % len(anchors)))
        drain()
    order = {s.script_id: i for i, s in enumerate(scripts)}
    return sorted(grades, key=lambda g: order.get(g.script_id, 0)), drift


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
    # Unreadable / failed scripts have no model items: the teacher marks them by hand.
    have = {i.item_id for i in grade.items}
    for item_id in edits:
        if item_id in allowed and item_id not in have:
            grade.items.append(GradedItem(item_id=item_id, marks_awarded=0, evidence_quote="",
                                          reasoning="Marked by teacher (no model score).",
                                          confidence="low", evidence_found=False, final_marks=0))
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


RESCAN_REASONS = ["Too blurry to read", "Page cut off or missing", "Handwriting illegible",
                  "Wrong sheet or not an answer"]


def mark_unreadable(script_id: str, reason: str, teacher: str = "teacher") -> ScriptGrade:
    """Teacher says this sheet cannot be marked as scanned. It goes to the rescan
    list and is never released until a new scan is graded."""
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    before = grade.status
    grade.status, grade.teacher_note = "rescan", reason.strip() or "Cannot be marked"
    store.save_grade(grade)
    audit.log(AuditEntry(actor="teacher", action="flag", script_id=script_id, before=before,
                         after="rescan", reason=f"{teacher}: {grade.teacher_note}"))
    return grade


def undo_unreadable(script_id: str, teacher: str = "teacher") -> ScriptGrade:
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    grade.status, grade.teacher_note = "needs_review", ""
    store.save_grade(grade)
    audit.log(AuditEntry(actor="teacher", action="edit", script_id=script_id, before="rescan",
                         after="needs_review", reason=f"{teacher}: undo 'cannot mark'"))
    return grade


def reopen_for_new_scan(script_id: str) -> bool:
    """A new scan was uploaded for a sheet marked 'rescan': drop the old result so
    the new file is graded. Returns True if something was reopened."""
    old = next((g for g in store.load_grades() if g.script_id == script_id), None)
    if old is None or old.status != "rescan":
        return False
    (store.grades_dir() / f"{script_id}.json").unlink(missing_ok=True)
    audit.log(AuditEntry(actor="teacher", action="edit", script_id=script_id, before="rescan",
                         after="queued", reason="new scan uploaded"))
    return True


def class_averages(rubric: Rubric, grades: list[ScriptGrade]) -> dict[str, float]:
    """Average final mark per rubric item over sheets that were actually marked (code, not model)."""
    marked = [g for g in grades if g.items and g.status != "rescan"]
    out = {}
    for it in rubric.items:
        vals = [next((i.final_marks for i in g.items if i.item_id == it.item_id), 0) for g in marked]
        out[it.item_id] = round(sum(vals) / len(vals), 2) if vals else 0.0
    return out


def class_report(rubric: Rubric) -> ClassReport:
    """Gemma 4 reads every marked sheet and writes class insights; code computes the averages.
    Raises ValueError if there is nothing to analyse, ModelError if the model fails."""
    sheets = [g for g in store.load_grades()
              if g.items and g.transcription and g.transcription.text and g.status != "rescan"]
    if len(sheets) < 2:
        raise ValueError("Grade at least 2 readable sheets first.")
    avgs = class_averages(rubric, sheets)
    insights = models.generate_json(prompts.INSIGHTS_SYSTEM, prompts.build_insights_prompt(rubric, sheets, avgs),
                                     None, ClassInsights, script_id="class")
    known = {it.item_id for it in rubric.items}  # code check: drop items the rubric does not have
    insights.items = [i for i in insights.items if i.item_id in known]
    report = ClassReport(created=datetime.now(timezone.utc).isoformat(),
                         model=models.model_name(models.last_backend_used()), n_sheets=len(sheets),
                         sheet_ids=[g.script_id for g in sheets], averages=avgs,
                         max_marks={it.item_id: it.max_marks for it in rubric.items}, insights=insights)
    store.save_class_report(report)
    audit.log(AuditEntry(actor="system", action="grade", script_id="class",
                         after=f"class report on {len(sheets)} sheets", reason=insights.struggled_concept[:200],
                         backend=models.last_backend_used(), model=report.model))
    return report


def draft_feedback(script_id: str, rubric: Rubric) -> tuple[ScriptGrade, list[str]]:
    """Gemma 4 drafts 2-3 lines of feedback quoting the student. Only for approved sheets.
    Returns (grade, quotes_not_found): code checks every quote is in the student's answer."""
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    if grade.status not in ("approved", "released"):
        raise ValueError("Approve the marks before drafting feedback.")
    if not (grade.transcription and grade.transcription.text):
        raise ValueError("There is no readable answer to quote.")
    d = models.generate_json(prompts.FEEDBACK_SYSTEM, prompts.build_feedback_prompt(rubric, grade), None,
                             FeedbackDraft, script_id=script_id)
    missing = [q for q in d.quotes if q.strip() and not rules.evidence_found(q, grade.transcription.text)]
    grade.feedback, grade.feedback_status = d.feedback.strip(), "draft"
    store.save_grade(grade)
    audit.log(AuditEntry(actor="system", action="grade", script_id=script_id, after="feedback draft",
                         reason=("quotes not found: " + "; ".join(missing)) if missing else "quotes verified",
                         backend=models.last_backend_used(), model=models.model_name(models.last_backend_used())))
    return grade, missing


def approve_feedback(script_id: str, text: str, teacher: str = "teacher") -> ScriptGrade:
    grade = next(g for g in store.load_grades() if g.script_id == script_id)
    if not text.strip():
        raise ValueError("Feedback is empty.")
    edited = text.strip() != grade.feedback
    grade.feedback, grade.feedback_status = text.strip(), "approved"
    store.save_grade(grade)
    audit.log(AuditEntry(actor="teacher", action="approve", script_id=script_id, after="feedback approved",
                         reason=f"{teacher}{' (edited)' if edited else ''}"))
    return grade


def export_csv(path: str | Path) -> int:
    """Write APPROVED scripts only to CSV. Returns number of rows written."""
    rubric = store.load_rubric()
    names = store.student_names()
    approved = [g for g in store.load_grades() if g.status in ("approved", "released")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["script_id", "name"] + [i.item_id for i in rubric.items] + ["total", "max_total", "feedback"])
        for g in approved:
            marks = {i.item_id: i.final_marks for i in g.items}
            w.writerow([g.script_id, names.get(g.script_id, "")] + [marks.get(i.item_id, "") for i in rubric.items]
                       + [g.total, g.max_total, g.feedback if g.feedback_status == "approved" else ""])
    for g in approved:
        if g.status != "released":
            g.status = "released"
            store.save_grade(g)
            audit.log(AuditEntry(actor="teacher", action="release", script_id=g.script_id,
                                 after=str(g.total)))
    return len(approved)
