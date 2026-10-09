"""Deterministic rules done by CODE, never by the model.
OWNER: Person A (feat/model-pipeline).
"""
import re
from difflib import SequenceMatcher

from copilot import config
from copilot.schemas import (FLAG_EVIDENCE_NOT_FOUND, FLAG_LOW_CONFIDENCE,
                             FLAG_MODEL_ERROR, FLAG_RULE_VIOLATION, GradedItem,
                             ItemScores, Rubric, RubricItem, Transcription)


def _norm(s: str) -> str:
    """Lowercase, drop punctuation except = + - * /, collapse spaces."""
    s = s.lower()
    s = re.sub(r"[^\w\s=+\-*/]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def evidence_found(quote: str, text: str) -> bool:
    """True if `quote` appears in `text` (case/space-insensitive, fuzzy)."""
    q, t = _norm(quote), _norm(text)
    if not q:
        return False
    if q in t:
        return True
    # Fuzzy: slide a window of the quote's word length over the text.
    qw, tw = q.split(), t.split()
    n = len(qw)
    for i in range(max(1, len(tw) - n + 1)):
        window = " ".join(tw[i:i + n])
        if SequenceMatcher(None, q, window).ratio() >= config.EVIDENCE_MATCH_RATIO:
            return True
    return False


def clamp(item: RubricItem, marks: int) -> tuple[int, bool]:
    """Return (allowed value, was_changed). Snaps to the largest allowed value
    <= marks, or the smallest allowed value if marks is below all of them."""
    allowed = sorted(item.allowed_marks)
    if marks in allowed:
        return marks, False
    lower = [a for a in allowed if a <= marks]
    return (lower[-1] if lower else allowed[0]), True


def apply(rubric: Rubric, scores: ItemScores,
          transcription: Transcription) -> tuple[list[GradedItem], int, list[str]]:
    """Turn raw model scores into GradedItems + total + flags."""
    by_id = {s.item_id: s for s in scores.items}
    items: list[GradedItem] = []
    flags: set[str] = set()
    for r in rubric.items:
        s = by_id.get(r.item_id)
        if s is None:  # model skipped this item
            flags.add(FLAG_MODEL_ERROR)
            items.append(GradedItem(item_id=r.item_id, marks_awarded=0, evidence_quote="",
                                    reasoning="Model returned no score for this item.",
                                    confidence="low", evidence_found=False, final_marks=0))
            continue
        final, changed = clamp(r, s.marks_awarded)
        if changed:
            flags.add(FLAG_RULE_VIOLATION)
        found = evidence_found(s.evidence_quote, transcription.text)
        if final > 0 and not found:
            flags.add(FLAG_EVIDENCE_NOT_FOUND)
        if s.confidence == "low":
            flags.add(FLAG_LOW_CONFIDENCE)
        items.append(GradedItem(**s.model_dump(), evidence_found=found, final_marks=final))
    total = sum(i.final_marks for i in items)  # the ONLY place a total is computed
    return items, total, sorted(flags)
