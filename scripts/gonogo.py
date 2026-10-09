"""Go/no-go test on REAL handwritten photos with the real model.

    python scripts/gonogo.py photo1.jpg photo2.jpg photo3.jpg

Prints each transcription + grade, seconds per call, and whether the API
accepted the JSON schema setting. Read the transcriptions yourself:
GO if at least 2 of 3 are mostly correct.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import config, models, prompts, rules, store  # noqa: E402
from copilot.schemas import ItemScores, Transcription  # noqa: E402

if config.MODEL_BACKEND == "fake":
    sys.exit("Set MODEL_BACKEND=gemini (or ollama) in .env first.")

rubric = store.load_rubric()
print(f"Backend: {config.MODEL_BACKEND} / {models.model_name(config.MODEL_BACKEND)}")

# Does the API accept response_json_schema for this model?
try:
    models._call_backend(config.MODEL_BACKEND, "Reply in JSON.", "Say hello.", None, Transcription)
    print("JSON schema setting: ACCEPTED")
except Exception as e:  # noqa: BLE001
    print(f"JSON schema setting: REJECTED ({type(e).__name__}: {str(e)[:200]})")
    print("-> set USE_API_SCHEMA = False in copilot/models.py (schema stays in the prompt)")
    models.USE_API_SCHEMA = False

for path in sys.argv[1:]:
    print(f"\n===== {path} =====")
    t0 = time.time()
    t = models.generate_json(prompts.TRANSCRIBE_SYSTEM, "Transcribe this handwritten answer.",
                             path, Transcription)
    t1 = time.time()
    print(f"[transcribe {t1 - t0:.1f}s] legibility={t.legibility} unclear={t.unclear_spans}\n{t.text}")
    s = models.generate_json(prompts.GRADE_SYSTEM, prompts.build_grade_prompt(rubric, t, None),
                             path, ItemScores)
    items, total, flags = rules.apply(rubric, s, t)
    print(f"[grade {time.time() - t1:.1f}s] total={total}/{rubric.max_total} flags={flags}")
    for i in items:
        print(f"  {i.item_id}: {i.final_marks} ({i.confidence}) evidence_found={i.evidence_found} "
              f"quote={i.evidence_quote!r}")
