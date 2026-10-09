"""Deterministic rules done by CODE, never by the model.
OWNER: Person A (feat/model-pipeline).
"""
from copilot.schemas import GradedItem, ItemScores, Rubric, RubricItem, Transcription


def evidence_found(quote: str, text: str) -> bool:
    """True if `quote` appears in `text` (case/space-insensitive, fuzzy).

    TODO (Person A): normalise both (lowercase, collapse spaces), then
    exact substring OR difflib.SequenceMatcher over windows of the same
    length with ratio >= config.EVIDENCE_MATCH_RATIO. Empty quote -> False.
    """
    raise NotImplementedError


def clamp(item: RubricItem, marks: int) -> tuple[int, bool]:
    """Return (allowed_marks_value, was_changed).

    TODO (Person A): if marks not in item.allowed_marks, snap to the nearest
    allowed value <= marks (or the minimum) and return was_changed=True.
    """
    raise NotImplementedError


def apply(rubric: Rubric, scores: ItemScores,
          transcription: Transcription) -> tuple[list[GradedItem], int, list[str]]:
    """Turn raw model scores into GradedItems + total + flags.

    TODO (Person A):
    - match scores to rubric items by item_id (missing item -> 0 + MODEL_ERROR flag)
    - clamp marks (RULE_VIOLATION flag if changed)
    - evidence check (EVIDENCE_NOT_FOUND if marks > 0 and quote not found)
    - LOW_CONFIDENCE if any confidence == "low"
    - total = sum(final_marks)   <- the only place a total is computed
    """
    raise NotImplementedError
