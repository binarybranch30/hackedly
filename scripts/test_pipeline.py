"""Offline test of the REAL pipeline path with the model call replaced by
canned replies (no API key needed). Run:  python scripts/test_pipeline.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from copilot import config, models, pipeline, store  # noqa: E402
from copilot.schemas import AnchorGrade, Script  # noqa: E402

config.MODEL_BACKEND = "gemini"
config.BACKOFF_SECONDS = [0]
rubric = store.load_rubric()
tmp = Path(tempfile.mkdtemp())
img = tmp / "ok.png"
Image.new("RGB", (800, 600), "white").save(img)
tiny = tmp / "tiny.png"
Image.new("RGB", (50, 50), "white").save(tiny)

TEXT = "Force equals mass times acceleration, F = ma. Pushing a heavy trolley is harder."
T_OK = json.dumps({"legibility": "good", "text": TEXT, "unclear_spans": []})


def scores(m1a, quote="F = ma", conf="high"):
    return json.dumps({"items": [
        {"item_id": "1a", "marks_awarded": m1a, "evidence_quote": quote, "reasoning": "r", "confidence": conf},
        {"item_id": "1b", "marks_awarded": 1, "evidence_quote": "mass times acceleration", "reasoning": "r", "confidence": "high"},
        {"item_id": "1c", "marks_awarded": 1, "evidence_quote": "Pushing a heavy trolley", "reasoning": "r", "confidence": "high"}]})


def fake_backend(replies):
    """Replace the network call with a queue of replies (str or Exception)."""
    q = list(replies)

    def call(backend, system, prompt, image_path, schema):
        r = q.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    models._call_backend = call


def run(name, replies, path=img):
    fake_backend(replies)
    g = pipeline.grade_script(Script(script_id=name, image_path=str(path)), rubric, [])
    print(f"{name:12} total={g.total}/{g.max_total} status={g.status:12} backend={g.backend:14} flags={g.flags}")
    return g


g = run("clean", [T_OK, scores(2), scores(2)])
assert g.total == 4 and g.status == "auto_ok" and not g.flags
g = run("bad_json", [T_OK, "not json", scores(2), scores(2)])
assert g.total == 4 and not g.flags
g = run("disagree", [T_OK, scores(2), scores(0, quote="")])
assert "RUNS_DISAGREE" in g.flags
g = run("hallucinate", [T_OK, scores(2, quote="Newton's third law"), scores(2, quote="Newton's third law")])
assert "EVIDENCE_NOT_FOUND" in g.flags
g = run("unreadable", [json.dumps({"legibility": "unreadable", "text": "", "unclear_spans": []})])
assert g.flags == ["UNREADABLE"]
g = run("tiny_image", [], path=tiny)
assert g.flags == ["UNREADABLE"]
g = run("rate_limit", [T_OK, models.RateLimited("429"), models.RateLimited("429"), scores(2), scores(2)])
assert "FALLBACK_USED" in g.flags
g = run("always_bad", [T_OK] + ["{}"] * 3)
assert "MODEL_ERROR" in g.flags

# Batch + drift check: 5 scripts, then one anchor re-graded (leave-one-out)
anchors = [AnchorGrade(script_id=f"A{i}", transcription=TEXT, marks={"1a": 2, "1b": 1, "1c": 2})
           for i in range(3)]
seen = []
fake_backend([T_OK, scores(2), scores(2)] * 5 + [scores(0, quote="")])
grades, drift = pipeline.grade_batch([Script(script_id=f"B{i}", image_path=str(img)) for i in range(5)],
                                     rubric, anchors, on_progress=lambda d, n, g: seen.append(d))
print("batch", [g.total for g in grades], "progress", seen, "drift", drift)
assert seen == [1, 2, 3, 4, 5] and len(drift) == 1 and drift[0]["drifted"] and drift[0]["diff"] == -3

# Anchor transcription helper
fake_backend([T_OK])
assert pipeline.transcribe_image(str(img)).text == TEXT
try:
    pipeline.transcribe_image(str(tiny)); raise AssertionError("tiny image should fail")
except ValueError:
    pass

# Teacher approval: illegal mark rejected, legal edit recomputes total
try:
    pipeline.approve("clean", {"1b": 5}); raise AssertionError("illegal mark accepted")
except ValueError:
    pass
g = pipeline.approve("clean", {"1a": 0})
assert g.total == 2 and g.status == "approved"
print("ALL PIPELINE TESTS PASSED")
