"""Prompt text. OWNER: Person A (feat/model-pipeline)."""
from copilot.schemas import AnchorGrade, Rubric, Transcription

# TODO (Person A): tune these during the go/no-go test.
TRANSCRIBE_SYSTEM = (
    "You transcribe handwritten exam answers exactly as written. "
    "Do not correct spelling or fill in missing words. "
    "List any words you cannot read in unclear_spans. "
    "If the page cannot be read at all, set legibility to 'unreadable'."
)

GRADE_SYSTEM = (
    "You are a careful examiner. Score each rubric item using ONLY the allowed marks. "
    "For every mark, copy the exact words from the answer that earned it into "
    "evidence_quote. If nothing earns marks, use an empty quote and 0. "
    "Do NOT add up totals. If you are unsure, set confidence to 'low' instead of guessing."
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
