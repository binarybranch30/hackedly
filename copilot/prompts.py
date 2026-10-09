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


def build_grade_prompt(rubric: Rubric, transcription: Transcription,
                       anchors: list[AnchorGrade] | None) -> str:
    """Build the grading prompt.

    Keep the `[item_id=...]` markers: the fake backend reads them.
    anchors=None or [] means UNCALIBRATED (used by the eval).

    TODO (Person A): add the anchors as worked examples ("This teacher gave
    these marks to this answer, because ...").
    """
    lines = [f"Question: {rubric.question}", "", "Rubric:"]
    for it in rubric.items:
        lines.append(f"[item_id={it.item_id}] {it.description} "
                     f"(allowed marks: {it.allowed_marks}) {it.guidance}")
    if anchors:
        lines += ["", "TODO: anchor examples go here"]
    lines += ["", "Student answer:", transcription.text]
    return "\n".join(lines)
