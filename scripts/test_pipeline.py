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

config.MODEL_BACKEND = "gemini"   # tests never call the network: _call_backend is replaced
config.BACKOFF_SECONDS = [0]
config.AUTO_FALLBACK = True
config.PARALLEL_SCRIPTS = 1        # the reply queue below assumes one script at a time
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
        models._local.calls = models.call_count() + 1
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
assert g.total == 4 and g.status == "auto_ok" and not g.flags and g.model_calls == 3
g = run("bad_json", [T_OK, "not json", scores(2), scores(2)])
assert g.total == 4 and not g.flags and g.model_calls == 4
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
config.QUOTA_BACKOFF_SECONDS = [0, 0]
g = run("quota_429", [T_OK, models.RateLimited("429", code=429), models.RateLimited("429", code=429), scores(2), scores(2)])
assert g.total == 4 and "FALLBACK_USED" not in g.flags, "a 429 is retried on the same model first"
config.GEMINI_RPM = 2
models._recent_calls.clear()
models._rate_gate(); models._rate_gate()
assert len(models._recent_calls) == 2, "the limiter lets calls through up to the per-minute cap"
models._recent_calls.clear()
config.GEMINI_RPM = 0
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
g = pipeline.approve("unreadable", {"1a": 1, "1b": 1, "1c": 0})   # teacher marks by hand
assert g.total == 2 and len(g.items) == 3 and g.status == "approved"

# Rubric extraction: model draft is code-checked, problems reported, nothing saved
bad = json.dumps({"rubric_id": "d", "question": "Q (4 marks)", "items": [
    {"item_id": "1a", "description": "Defines it", "max_marks": 2, "allowed_marks": [0, 1, 2], "guidance": ""},
    {"item_id": "1a", "description": "", "max_marks": 2, "allowed_marks": [1, 3], "guidance": ""}]})
fake_backend([bad])
draft, problems = pipeline.extract_rubric(str(img))
print("rubric problems:", problems)
assert len(draft.items) == 2 and "duplicate item ids" in problems and len(problems) >= 4
assert pipeline.check_rubric(rubric) == [], "example rubric should be valid"

# Parallel batch: 6 scripts on 3 threads with a stateless, schema-aware mock
config.PARALLEL_SCRIPTS = 3


def by_schema(backend, system, prompt, image_path, schema):
    models._local.calls = models.call_count() + 1
    return T_OK if schema.__name__ == "Transcription" else scores(2)


models._call_backend = by_schema
grades, _ = pipeline.grade_batch([Script(script_id=f"P{i}", image_path=str(img)) for i in range(6)], rubric, [])
assert [g.script_id for g in grades] == [f"P{i}" for i in range(6)], "results keep input order"
assert all(g.total == 4 and g.model_calls == 3 for g in grades), [(g.total, g.model_calls) for g in grades]
print("parallel batch OK")

# Live step events arrive on the caller's thread, in order per script
seen_events = []
grades, _ = pipeline.grade_batch([Script(script_id="E1", image_path=str(img))], rubric, [],
                                 on_event=lambda sid, step, status, detail: seen_events.append((step, status)))
assert [e for e in seen_events if e[1] != "running"] == [("check", "ok"), ("read", "ok"), ("grade", "ok"),
                                                         ("verify", "ok")], seen_events
print("events OK:", seen_events)

# A 2-page PDF answer sheet is rendered, stacked and accepted
pdf = tmp / "sheet.pdf"
pages = [Image.new("RGB", (800, 1000), "white"), Image.new("RGB", (800, 1000), "white")]
pages[0].save(pdf, save_all=True, append_images=pages[1:])
w, h = models.load_image(pdf).size
assert h == 2 * round(w * 1000 / 800), (w, h)  # two pages stacked
g = pipeline.grade_script(Script(script_id="PDF1", image_path=str(pdf)), rubric, [])
assert g.total == 4 and not g.flags, g.flags
print("pdf OK")

# Teacher: "cannot mark this sheet" -> rescan list, never released, undo works, new scan reopens it
g = pipeline.mark_unreadable("E1", "Too blurry to read")
assert g.status == "rescan" and g.teacher_note == "Too blurry to read"
out = tmp / "marks.csv"
pipeline.export_csv(out)
assert "E1" not in out.read_text(), "rescan sheets must not be released"
assert pipeline.undo_unreadable("E1").status == "needs_review"
pipeline.mark_unreadable("E1", "")
assert pipeline.reopen_for_new_scan("E1") and not any(x.script_id == "E1" for x in store.load_grades())
assert not pipeline.reopen_for_new_scan("clean"), "only rescan sheets are reopened"
print("rescan OK")
print("ALL PIPELINE TESTS PASSED")
