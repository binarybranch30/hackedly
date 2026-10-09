"""Shared data shapes (the CONTRACT between branches).

Change this file only on `main`, and tell your teammate when you do.

Two kinds of models live here:
- MODEL OUTPUT: what Gemma must return (Transcription, ItemScores). These are
  sent to the model as a JSON schema and every reply is validated against them.
- BUILT BY CODE: everything else. The model never fills these directly.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["high", "medium", "low"]
Legibility = Literal["good", "partial", "unreadable"]
Status = Literal["needs_review", "auto_ok", "approved", "released", "rescan"]
# "rescan": the teacher decided the sheet cannot be marked (blurred, cut off, ...)
# and needs a new scan. Such sheets are never released.

# Flag codes used by rules.py / pipeline.py and shown in the UI.
FLAG_UNREADABLE = "UNREADABLE"            # image could not be read
FLAG_LOW_CONFIDENCE = "LOW_CONFIDENCE"    # model said confidence = low
FLAG_EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"  # quote not in transcription
FLAG_RUNS_DISAGREE = "RUNS_DISAGREE"      # two grading runs differ >= threshold
FLAG_RULE_VIOLATION = "RULE_VIOLATION"    # marks outside allowed set, clamped
FLAG_MODEL_ERROR = "MODEL_ERROR"          # invalid output after all retries
FLAG_FALLBACK_USED = "FALLBACK_USED"      # graded by local model, not Gemini


# ---------- Teacher inputs ----------

class RubricItem(BaseModel):
    item_id: str                      # e.g. "1a"
    description: str                  # what earns marks
    max_marks: int
    allowed_marks: list[int]          # e.g. [0, 1, 2]
    guidance: str = ""                # extra marking notes from the teacher


class Rubric(BaseModel):
    rubric_id: str
    question: str
    items: list[RubricItem]

    @property
    def max_total(self) -> int:
        return sum(i.max_marks for i in self.items)


class Script(BaseModel):
    script_id: str                    # e.g. "S04"
    image_path: str
    role: Literal["anchor", "heldout", "live"] = "live"


class AnchorGrade(BaseModel):
    """A script graded by the teacher by hand, used as a few-shot example."""
    script_id: str
    transcription: str                # text of the answer (from model, checked by teacher)
    marks: dict[str, int]             # item_id -> marks the teacher gave
    notes: dict[str, str] = {}        # item_id -> why (optional)


# ---------- MODEL OUTPUT (sent to Gemma as JSON schema) ----------

class Transcription(BaseModel):
    legibility: Legibility
    text: str = Field(description="Exact transcription of the handwritten answer")
    unclear_spans: list[str] = Field(default_factory=list,
                                     description="Words or phrases that could not be read with certainty")


class ItemScore(BaseModel):
    item_id: str
    marks_awarded: int
    evidence_quote: str = Field(description="Exact words copied from the answer that earned the marks; empty if none")
    reasoning: str = Field(description="One short sentence")
    confidence: Confidence


class ItemScores(BaseModel):
    items: list[ItemScore]


class ItemInsight(BaseModel):
    item_id: str
    common_mistake: str = Field(description="The most common mistake on this item, one sentence; "
                                            "empty if most students got it right")


class ClassInsights(BaseModel):
    items: list[ItemInsight]
    struggled_concept: str = Field(description="The one concept the class struggled with most")
    # No minItems/maxItems in the schema: with them, Gemma 4's constrained decoding on the
    # Gemini API hangs until timeout (measured 2026-10-09). The rule is checked in code instead.
    reteach_topics: list[str] = Field(description="Exactly two short topics to re-teach")
    summary: str = Field(description="Two sentences for the teacher")

    @field_validator("reteach_topics")
    @classmethod
    def _two_topics(cls, v: list[str]) -> list[str]:
        v = [t.strip() for t in v if t.strip()]
        if len(v) < 2:
            raise ValueError("give exactly two re-teach topics")
        return v[:2]


class FeedbackDraft(BaseModel):
    feedback: str = Field(description="2-3 sentences to the student, kind and specific")
    quotes: list[str] = Field(description="The exact phrases from the student's answer that the feedback quotes")


# ---------- BUILT BY CODE ----------

class GradedItem(ItemScore):
    evidence_found: bool = False      # did the quote really appear in the transcription?
    final_marks: int = 0              # after rules (clamping); teacher may edit later


class ScriptGrade(BaseModel):
    script_id: str
    run_id: str
    backend: str                      # gemini | ollama | fake — who actually answered
    model: str
    calibrated: bool                  # were anchors used in the prompt?
    transcription: Optional[Transcription] = None
    items: list[GradedItem] = Field(default_factory=list)
    total: int = 0                    # computed by code, never by the model
    max_total: int = 0
    flags: list[str] = Field(default_factory=list)
    status: Status = "needs_review"
    seconds: float = 0.0              # wall-clock time to grade this script
    model_calls: int = 0              # number of model requests (incl. retries)
    teacher_note: str = ""            # e.g. why the teacher could not mark it
    feedback: str = ""                # short note to the student (AI draft, teacher-edited)
    feedback_status: Literal["none", "draft", "approved"] = "none"


class ClassReport(BaseModel):
    """Class insights (model) + per-item class averages (code)."""
    created: str
    model: str
    n_sheets: int
    sheet_ids: list[str]
    averages: dict[str, float]        # item_id -> class average mark (computed by code)
    max_marks: dict[str, int]
    insights: ClassInsights


class AuditEntry(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    actor: Literal["system", "teacher"]
    action: Literal["transcribe", "grade", "retry", "fallback", "flag",
                    "edit", "approve", "release", "drift_check", "error"]
    script_id: Optional[str] = None
    item_id: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    reason: str = ""
    backend: Optional[str] = None
    model: Optional[str] = None
