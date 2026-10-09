"""Made-up but realistic outputs so the UI and eval can be built before the
real model is wired up. Used when MODEL_BACKEND=fake. Delete nothing here;
it is also handy for demos without internet.
"""
import random
import re

from copilot.schemas import (FLAG_EVIDENCE_NOT_FOUND, FLAG_LOW_CONFIDENCE,
                             GradedItem, ItemScore, ItemScores, Rubric, RubricItem,
                             ScriptGrade, Transcription)

FAKE_TEXT = ("Newton's second law says force equals mass times acceleration, F = ma. "
             "So if you push a heavier trolley with the same force it speeds up less.")


def fake_transcription(seed: str = "") -> Transcription:
    rng = random.Random(seed)
    legibility = rng.choice(["good", "good", "good", "partial"])
    return Transcription(legibility=legibility, text=FAKE_TEXT,
                         unclear_spans=["trolley"] if legibility == "partial" else [])


def fake_item_scores(item_ids: list[str], seed: str = "") -> ItemScores:
    rng = random.Random(seed)
    items = []
    for item_id in item_ids:
        items.append(ItemScore(
            item_id=item_id,
            marks_awarded=rng.choice([0, 1, 2]),
            evidence_quote=rng.choice(["F = ma", "force equals mass times acceleration",
                                       "a made-up quote not in the answer", ""]),
            reasoning="Fake reasoning for UI testing.",
            confidence=rng.choice(["high", "high", "medium", "low"]),
        ))
    return ItemScores(items=items)


def fake_for_schema(schema, prompt: str):
    """Fake backend for models.generate_json. For ItemScores it reads item ids
    from markers like [item_id=1a] in the prompt."""
    if schema is Transcription:
        return fake_transcription(prompt[:50])
    if schema is Rubric:
        return Rubric(rubric_id="draft", question="Explain photosynthesis. (4 marks)", items=[
            RubricItem(item_id="1a", description="Defines photosynthesis", max_marks=2,
                       allowed_marks=[0, 1, 2], guidance=""),
            RubricItem(item_id="1b", description="Gives the word equation", max_marks=2,
                       allowed_marks=[0, 1, 2], guidance="")])
    if schema.__name__ == "ClassInsights":
        ids = re.findall(r"\[item_id=([^\]]+)\]", prompt) or ["1"]
        return schema.model_validate({
            "items": [{"item_id": i, "common_mistake": "Fake: states the formula but does not explain it."}
                      for i in ids],
            "struggled_concept": "Fake: linking the example back to F = ma",
            "reteach_topics": ["Fake: what each symbol in F = ma means", "Fake: worked everyday examples"],
            "summary": "Fake summary for UI testing."})
    if schema.__name__ == "FeedbackDraft":
        m = re.search(r"The student's answer:\n(.{0,40}\w)", prompt, re.S)
        q = m.group(1).split("\n")[0][:30] if m else ""
        return schema.model_validate({"feedback": f'Fake: you wrote "{q}", which is a good start. '
                                                  "Next time explain each quantity.", "quotes": [q] if q else []})
    if schema is ItemScores:
        ids = re.findall(r"\[item_id=([^\]]+)\]", prompt) or ["1"]
        return fake_item_scores(ids, prompt[:50])
    raise ValueError(f"fake backend has no example for {schema.__name__}")


def fake_script_grade(script_id: str, rubric: Rubric) -> ScriptGrade:
    """A complete ScriptGrade, as the finished pipeline would return it."""
    t = fake_transcription(script_id)
    scores = fake_item_scores([i.item_id for i in rubric.items], script_id)
    items, flags = [], set()
    for s, r in zip(scores.items, rubric.items):
        found = bool(s.evidence_quote) and s.evidence_quote.lower() in t.text.lower()
        final = min(s.marks_awarded, r.max_marks)
        items.append(GradedItem(**s.model_dump(), evidence_found=found, final_marks=final))
        if s.confidence == "low":
            flags.add(FLAG_LOW_CONFIDENCE)
        if s.marks_awarded > 0 and not found:
            flags.add(FLAG_EVIDENCE_NOT_FOUND)
    return ScriptGrade(
        script_id=script_id, run_id="fake", backend="fake", model="fake",
        calibrated=True, transcription=t, items=items,
        total=sum(i.final_marks for i in items), max_total=rubric.max_total,
        flags=sorted(flags), status="needs_review" if flags else "auto_ok",
    )
