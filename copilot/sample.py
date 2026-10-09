"""Sample class for demos (sample mode).

Builds a separate workspace in data/sample/ with what a teacher would have
prepared BEFORE grading: a rubric, 3 anchor scripts the teacher graded by hand,
and 8 handwritten answer sheets as PDFs. The answer sheets are NOT graded in
advance: press "Grade" in the website and Gemma 4 reads and grades them live.

The sheets cover the interesting cases: strong, average, vague and partly
legible answers, and one smudged, unreadable page.
"""
import random
import shutil
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from copilot import audit, config, store
from copilot.schemas import AnchorGrade, AuditEntry, Rubric, RubricItem

FONT = config.ROOT / "assets" / "fonts" / "Caveat.ttf"

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


# (script_id, answer text, messy?) -- rendered as handwritten PDF answer sheets
STUDENTS = [
    ("R01", "Newton's second law states that the force acting on a body is equal to its mass multiplied by its "
            "acceleration, F = ma. Here F is force in newtons, m is mass in kg and a is acceleration. When we "
            "kick a football and a heavy medicine ball with the same force, the heavy ball moves slower because "
            "it has more mass, so its acceleration a = F/m is smaller.", False),
    ("R02", "F = ma. Force equals mass into acceleration. When a car applies brakes it slows down and stops.", False),
    ("R03", "The law says that things move faster when you push them harder. Like when you push a swing hard "
            "it goes higher.", False),
    ("R04", "Force = mass x acceleration (F=ma). A rocket pushes gas down with a big force so it accelerates up. "
            "Bigger rockets need more force.", False),
    ("R05", "Newtons 2nd law: F = ma. The force on an object makes it accelerate. For example pushing a bicycle "
            "makes it go.", False),
    ("R06", "", True),
    ("R07", "Second law: the acceleration of a body is directly proportional to the force and inversely "
            "proportional to its mass, so F = ma. a is acceleration, m is mass, F is the net force. Example: "
            "a loaded truck needs more force than a bike to speed up equally.", False),
    ("R08", "Newton's second law: F = ma, the net force equals mass times acceleration. F is force, m is mass "
            "and a is acceleration. If two people push a car instead of one, the car accelerates more because "
            "the force is bigger.", False),
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
    if out.suffix == ".pdf":
        im.save(out, "PDF", resolution=100)  # like a scanned answer sheet
    else:
        im.save(out, quality=88)


def build() -> None:
    """(Re)create the sample workspace in data/sample/. Requires sample mode to be on.
    Prepares rubric + teacher-graded anchors + UNGRADED answer-sheet PDFs."""
    if not config.sample_mode():
        raise RuntimeError("turn sample mode on first")
    shutil.rmtree(config.sample_dir(), ignore_errors=True)
    ws = config.sample_dir()
    store.save_rubric(RUBRIC)
    store.save_anchors(ANCHORS)
    for n, a in enumerate(ANCHORS):
        _handwriting(a.transcription, ws / "anchors" / f"{a.script_id}.jpg", f"Anchor {a.script_id} · Q1", seed=n)
    for n, (sid, text, messy) in enumerate(STUDENTS):
        _handwriting(text, ws / "scripts" / f"{sid}.pdf", f"Roll no. {sid} · Q1", messy=messy, seed=100 + n)
    audit.log(AuditEntry(actor="teacher", action="edit", script_id="setup",
                         after=f"rubric {RUBRIC.rubric_id}; anchors " +
                               ", ".join(f"{a.script_id}={sum(a.marks.values())}" for a in ANCHORS),
                         reason="[sample] rubric and 3 anchor scripts prepared by the teacher"))


def answer_sheets() -> list[Path]:
    """The sample answer-sheet PDFs waiting to be graded."""
    return sorted((config.sample_dir() / "scripts").glob("*.pdf"))


def enable() -> None:
    """Switch to the sample workspace, building it the first time."""
    config.sample_flag().touch()
    if not store.rubric_path().exists():
        build()


def disable() -> None:
    config.sample_flag().unlink(missing_ok=True)
