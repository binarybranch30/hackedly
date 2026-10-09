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
