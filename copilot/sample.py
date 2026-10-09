"""Sample class for demos (sample mode).

Builds a separate workspace in data/sample/ with a rubric, 3 teacher anchors and
8 handwritten-looking student answers that show every part of the workflow:
clean scripts, an ambiguous answer, two grading runs that disagree, a quote the
model made up, an unreadable photo, and teacher approvals with an edit.

The marks below are PREPARED EXAMPLES, not live model output. Every sample
grade is labelled backend="sample". Totals and flags are still computed by the
real rules code (rules.apply), exactly as for real grades.
"""
import random
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from copilot import audit, config, pipeline, rules, store
from copilot.schemas import (FLAG_RUNS_DISAGREE, FLAG_UNREADABLE, AnchorGrade, AuditEntry,
                             ItemScore, ItemScores, Rubric, RubricItem, ScriptGrade,
                             Transcription)

FONT = config.ROOT / "assets" / "fonts" / "Caveat.ttf"
SAMPLE_BACKEND = "sample"
SAMPLE_MODEL = "sample data (prepared example)"

RUBRIC = Rubric(
    rubric_id="physics-class9-newton2",
    question="State Newton's second law of motion and explain it with one everyday example. (5 marks)",
    items=[
        RubricItem(item_id="1a", description="Correct statement of the law (F = ma, or force is proportional "
                   "to rate of change of momentum)", max_marks=2, allowed_marks=[0, 1, 2],
                   guidance="1 for the formula only, 2 for formula plus a correct statement in words"),
        RubricItem(item_id="1b", description="Explains what F, m and a mean", max_marks=1,
                   allowed_marks=[0, 1], guidance="All three quantities needed"),
        RubricItem(item_id="1c", description="Valid everyday example linked to the law", max_marks=2,
                   allowed_marks=[0, 1, 2], guidance="1 for an example, 2 if it is explained using the law"),
    ])

ANCHORS = [
    AnchorGrade(script_id="A01", marks={"1a": 2, "1b": 1, "1c": 2}, notes={
        "1c": "Example clearly uses a = F/m"},
        transcription="Newton's second law says the force on a body equals its mass times its acceleration, "
                      "F = ma. F is the force in newtons, m is the mass in kg and a is the acceleration in m/s2. "
                      "Example: if I push an empty trolley and a full trolley with the same force, the full one "
                      "speeds up less because it has more mass, so a = F/m is smaller."),
    AnchorGrade(script_id="A02", marks={"1a": 2, "1b": 0, "1c": 1}, notes={
        "1b": "Symbols not explained", "1c": "Example given but not linked to the law"},
        transcription="The second law is F = ma, which means force is equal to mass multiplied by "
                      "acceleration. For example a cricket ball moves when the bat hits it."),
    AnchorGrade(script_id="A03", marks={"1a": 1, "1b": 0, "1c": 0}, notes={
        "1a": "Formula only, no statement", "1c": "No example"},
        transcription="F = ma. Newton gave three laws of motion and this is the second one. It is very "
                      "important in physics."),
]


def _s(item_id, marks, quote, reasoning, confidence="high"):
    return ItemScore(item_id=item_id, marks_awarded=marks, evidence_quote=quote, reasoning=reasoning,
                     confidence=confidence)


# (script_id, legibility, text, unclear_spans, run-1 scores, run-2 total or None, teacher edits or None)
STUDENTS = [
    ("R01", "good",
     "Newton's second law states that the force acting on a body is equal to its mass multiplied by its "
     "acceleration, F = ma. Here F is force in newtons, m is mass in kg and a is acceleration. When we kick a "
     "football and a heavy medicine ball with the same force, the heavy ball moves slower because it has more "
     "mass, so its acceleration a = F/m is smaller.", [],
     [_s("1a", 2, "force acting on a body is equal to its mass multiplied by its acceleration, F = ma",
         "Formula and correct statement."),
      _s("1b", 1, "F is force in newtons, m is mass in kg and a is acceleration", "All three explained."),
      _s("1c", 2, "the heavy ball moves slower because it has more mass, so its acceleration a = F/m is smaller",
         "Example explained with the law.")], None, None),
    ("R02", "good",
     "F = ma. Force equals mass into acceleration. When a car applies brakes it slows down and stops.", [],
     [_s("1a", 2, "F = ma. Force equals mass into acceleration", "Formula with words."),
      _s("1b", 0, "", "Quantities not explained."),
      _s("1c", 1, "When a car applies brakes it slows down", "Example given but not linked to F = ma.",
         "medium")], None, {}),
    ("R03", "good",
     "The law says that things move faster when you push them harder. Like when you push a swing hard "
     "it goes higher.", [],
     [_s("1a", 1, "things move faster when you push them harder",
         "Hints that more force gives more acceleration, but no formula and 'faster' mixes up speed and "
         "acceleration.", "low"),
      _s("1b", 0, "", "No quantities named."),
      _s("1c", 1, "push a swing hard it goes higher", "Example present, link to the law is weak.", "low")],
     None, None),
    ("R04", "good",
     "Force = mass x acceleration (F=ma). A rocket pushes gas down with a big force so it accelerates up. "
     "Bigger rockets need more force.", [],
     [_s("1a", 2, "Force = mass x acceleration (F=ma)", "Formula with words."),
      _s("1b", 0, "", "Symbols not explained individually.", "medium"),
      _s("1c", 2, "Bigger rockets need more force", "Example linked: more mass needs more force.", "medium")],
     3, None),
    ("R05", "good",
     "Newtons 2nd law: F = ma. The force on an object makes it accelerate. For example pushing a bicycle "
     "makes it go.", [],
     [_s("1a", 2, "force is the rate of change of momentum", "Correct statement of the law."),
      _s("1b", 0, "", "Quantities not explained."),
      _s("1c", 1, "pushing a bicycle makes it go", "Example given, not explained.", "medium")], None, None),
    ("R06", "unreadable", "", [], None, None, None),
    ("R07", "partial",
     "Second law: the acceleration of a body is directly proportional to the force [?] and inversely "
     "proportional to its mass, so F = ma. a is acceleration, m is mass, F is the net force. Example: a "
     "[?] truck needs more force than a bike to speed up equally.", ["empty", "loaded"],
     [_s("1a", 2, "acceleration of a body is directly proportional to the force", "Correct statement."),
      _s("1b", 1, "a is acceleration, m is mass, F is the net force", "All three explained."),
      _s("1c", 2, "truck needs more force than a bike to speed up equally", "Example linked to mass.",
         "medium")], None, None),
    ("R08", "good",
     "Newton's second law: F = ma, the net force equals mass times acceleration. F is force, m is mass and a "
     "is acceleration. If two people push a car instead of one, the car accelerates more because the force "
     "is bigger.", [],
     [_s("1a", 2, "F = ma, the net force equals mass times acceleration", "Formula and statement."),
      _s("1b", 1, "F is force, m is mass and a is acceleration", "All three explained."),
      _s("1c", 1, "two people push a car instead of one, the car accelerates more",
         "Example given; the link to the law could be clearer.", "medium")], None, {"1c": 2}),
]


def _handwriting(text: str, out: Path, header: str, messy: bool = False, seed: int = 0) -> None:
    """Render text as a blue-ink handwritten page on lined paper."""
    rng = random.Random(seed)
    W, H = 1100, 1300
    im = Image.new("RGB", (W, H), (251, 249, 242))
    d = ImageDraw.Draw(im)
    for y in range(150, H - 40, 62):  # ruled lines; text sits on them
        d.line([(50, y), (W - 50, y)], fill=(185, 205, 232), width=2)
    d.line([(110, 0), (110, H)], fill=(232, 160, 160), width=2)
    font = ImageFont.truetype(str(FONT), 46)
    small = ImageFont.truetype(str(FONT), 40)
    d.text((130, 70), header, fill=(40, 40, 60), font=small)
    if messy:
        text = ("the law is the force thing when it moves and the mass is not same so it goes "
                "and the example is the car or the ball when we push it hard it")
    y = 166
    for line in textwrap.wrap(text, width=44):
        x = 130 + rng.randint(-6, 6)
        d.text((x, y + rng.randint(-3, 3)), line, fill=(28, 42, 120), font=font)
        y += 62
    if messy:  # smudged, faint, rotated: what an unreadable photo looks like
        for _ in range(40):
            x0, y0 = rng.randint(100, W - 200), rng.randint(150, 700)
            d.line([(x0, y0), (x0 + rng.randint(60, 220), y0 + rng.randint(-30, 30))],
                   fill=(60, 70, 120), width=rng.randint(3, 7))
        im = im.filter(ImageFilter.GaussianBlur(5)).rotate(7, fillcolor=(235, 233, 225))
        im = Image.blend(im, Image.new("RGB", im.size, (225, 222, 214)), 0.45)
    else:
        im = im.rotate(rng.uniform(-1.2, 1.2), fillcolor=(240, 238, 230), resample=Image.BICUBIC)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=88)


def _log(action, script_id, reason, **kw):
    audit.log(AuditEntry(actor=kw.pop("actor", "system"), action=action, script_id=script_id,
                         reason=f"[sample] {reason}", backend=SAMPLE_BACKEND, model=SAMPLE_MODEL, **kw))


def build() -> None:
    """(Re)create the sample workspace in data/sample/. Requires sample mode to be on."""
    if not config.sample_mode():
        raise RuntimeError("turn sample mode on first")
    shutil.rmtree(config.SAMPLE_DIR, ignore_errors=True)
    ws = config.SAMPLE_DIR
    store.save_rubric(RUBRIC)
    _log("edit", "rubric", "rubric saved", actor="teacher", after="3 items, 5 marks")
    store.save_anchors(ANCHORS)
    for n, a in enumerate(ANCHORS):
        _handwriting(a.transcription, ws / "anchors" / f"{a.script_id}.jpg", f"Anchor {a.script_id} · Q1", seed=n)
    _log("edit", "anchors", "3 anchors graded by the teacher", actor="teacher",
         after=", ".join(f"{a.script_id}={sum(a.marks.values())}" for a in ANCHORS))

    for n, (sid, leg, text, unclear, scores, run2_total, edits) in enumerate(STUDENTS):
        _handwriting(text, ws / "scripts" / f"{sid}.jpg", f"Roll no. {sid} · Q1", messy=leg == "unreadable",
                     seed=100 + n)
        t = Transcription(legibility=leg, text=text, unclear_spans=unclear)
        g = ScriptGrade(script_id=sid, run_id=f"sample-{sid}", backend=SAMPLE_BACKEND, model=SAMPLE_MODEL,
                        calibrated=True, transcription=t, max_total=RUBRIC.max_total)
        _log("transcribe", sid, "photo read", after=leg)
        if leg == "unreadable":
            g.flags = [FLAG_UNREADABLE]
        else:
            if sid == "R05":
                _log("retry", sid, "attempt 1: invalid ItemScores (missing field 'confidence'); asked again")
            items, total, flags = rules.apply(RUBRIC, ItemScores(items=scores), t)
            if run2_total is not None and abs(run2_total - total) >= config.DISAGREE_THRESHOLD:
                flags = sorted(set(flags) | {FLAG_RUNS_DISAGREE})
            g.items, g.total, g.flags = items, total, flags
        g.status = "needs_review" if g.flags else "auto_ok"
        store.save_grade(g)
        _log("grade", sid, "graded (run totals "
             + (f"{g.total} and {run2_total})" if run2_total is not None else f"{g.total} and {g.total})"),
             after=f"{g.total}/{g.max_total}")
        if g.flags:
            _log("flag", sid, "sent to teacher review", after=",".join(g.flags))
        if sid == "R05":
            a = ANCHORS[1]
            _log("drift_check", a.script_id, "ok", before=str(sum(a.marks.values())),
                 after=str(sum(a.marks.values())))
        if edits is not None:
            pipeline.approve(sid, edits, teacher="[sample] teacher")


def enable() -> None:
    """Switch to the sample workspace, building it the first time."""
    config.SAMPLE_FLAG.touch()
    if not (config.SAMPLE_DIR / "grades").exists():
        build()


def disable() -> None:
    config.SAMPLE_FLAG.unlink(missing_ok=True)
