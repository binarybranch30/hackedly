"""Prompt text. OWNER: Person A (feat/model-pipeline)."""
from copilot.schemas import AnchorGrade, Rubric, Transcription

# Tune these after the go/no-go test on real handwriting.
TRANSCRIBE_SYSTEM = (
    "You transcribe handwritten exam answers exactly as written. "
    "Keep the student's spelling, grammar and line breaks; do not correct or complete anything. "
    "Skip words that are crossed out. Write formulas as plain text (e.g. F = ma). "
    "Describe any diagram briefly in square brackets, e.g. [diagram: force arrow on a box]. "
    "Put every word you cannot read with certainty in unclear_spans and write it as [?] in the text. "
    "legibility: 'good' if almost everything is readable, 'partial' if some words are not, "
    "'unreadable' if you cannot follow the answer at all."
)

GRADE_SYSTEM = (
    "You are a careful examiner. Score each rubric item separately using ONLY its allowed marks. "
    "For each item, evidence_quote must be copied word for word from the student answer "
    "(the shortest phrase that earns the marks, at most 25 words). "
    "If nothing in the answer earns marks, give 0 and an empty evidence_quote. "
    "Never award marks for content that is not in the answer. Do NOT add up totals. "
    "confidence: 'high' if the answer clearly meets or clearly misses the item, 'medium' if it is a "
    "judgement call, 'low' if the handwriting or meaning is unclear. Prefer 'low' over guessing."
)

RUBRIC_SYSTEM = (
    "You read exam question papers and marking schemes. Draft a marking rubric: split the "
    "question into separately markable items (item_id like 1a, 1b), each with a clear "
    "description of what earns marks, max_marks, and allowed_marks from 0 up to max_marks. "
    "Use the marks printed on the paper; never invent a different total. Copy any marking "
    "notes into guidance."
)


INSIGHTS_SYSTEM = (
    "You help a teacher understand how a class did on one assessment. You get the rubric, the class "
    "average for each rubric item, and every student's answer with the marks given. Base everything ONLY "
    "on these answers: describe mistakes you can actually see in them, not general ones. For each rubric "
    "item give the most common mistake in one plain sentence (empty if most got it right). Name the one "
    "concept the class struggled with most, and exactly two short topics to re-teach."
)

FEEDBACK_SYSTEM = (
    "You write a short note from the teacher to one student about their answer. 2-3 sentences, kind, "
    "specific and honest. Quote the student's own words in double quotes at least once, copied exactly "
    "from their answer. Say one thing they did well and one thing to improve, based on the marks. "
    "Address the student as 'you'. Do not mention the total mark. List every phrase you quoted in quotes."
)


def build_insights_prompt(rubric: Rubric, sheets: list, averages: dict[str, float]) -> str:
    """sheets: graded ScriptGrades that have a transcription and item marks."""
    lines = [f"Question: {rubric.question}", "", "Rubric and class average:"]
    for it in rubric.items:
        lines.append(f"[item_id={it.item_id}] {it.description} — average {averages.get(it.item_id, 0):.1f}"
                     f"/{it.max_marks}")
    lines += ["", f"Answers from {len(sheets)} students:"]
    for g in sheets:
        marks = ", ".join(f"{i.item_id}={i.final_marks}" for i in g.items)
        text = g.transcription.text.replace("\n", " ")[:700]
        lines += [f"--- {g.script_id} ({marks}) ---", text]
    return "\n".join(lines)


def build_feedback_prompt(rubric: Rubric, grade) -> str:
    lines = [f"Question: {rubric.question}", "", "Marks for this student:"]
    marks = {i.item_id: i for i in grade.items}
    for it in rubric.items:
        m = marks.get(it.item_id)
        lines.append(f"- {it.item_id} {it.description}: {m.final_marks if m else 0}/{it.max_marks}"
                     + (f" ({m.reasoning})" if m and m.reasoning else ""))
    lines += ["", "The student's answer:", grade.transcription.text if grade.transcription else ""]
    return "\n".join(lines)


def build_grade_prompt(rubric: Rubric, transcription: Transcription,
                       anchors: list[AnchorGrade] | None) -> str:
    """Build the grading prompt.

    Keep the `[item_id=...]` markers: the fake backend reads them.
    anchors=None or [] means UNCALIBRATED (used by the eval).

    Each anchor becomes a worked example of how THIS teacher marks.
    """
    lines = [f"Question: {rubric.question}", "", "Rubric:"]
    for it in rubric.items:
        lines.append(f"[item_id={it.item_id}] {it.description} "
                     f"(allowed marks: {it.allowed_marks}) {it.guidance}")
    if anchors:
        lines += ["", "Examples graded by this teacher. Match their strictness exactly:"]
        for n, a in enumerate(anchors, 1):
            lines += ["", f"--- Example {n} answer ---", a.transcription, "Teacher's marks:"]
            for it in rubric.items:
                note = a.notes.get(it.item_id, "")
                lines.append(f"  {it.item_id}: {a.marks.get(it.item_id, 0)}/{it.max_marks}"
                             + (f" ({note})" if note else ""))
        lines += ["", "--- End of examples ---"]
    lines += ["", "Now grade this student answer:", transcription.text]
    if transcription.unclear_spans:
        lines.append(f"(Words the reader could not read clearly: {transcription.unclear_spans})")
    return "\n".join(lines)
