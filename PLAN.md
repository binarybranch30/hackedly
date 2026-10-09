# Plan — Hack Day Bengaluru '26 · PS 02

**Deadline: 15:15. We submit at 15:00.** Feature freeze 14:00 · Code freeze 14:30.

## MVP (must work by 14:00)
- Rubric + 3 teacher-graded anchors
- Gemma 4 two-step pipeline: transcribe → grade each item with an evidence quote (graded twice)
- Code does evidence check, clamping, totals; routing to `needs_review`
- Review screen: edit + approve; CSV export (approved only); audit log
- JSON validate + retry with error; backoff on 429; backend switch in `.env`
- `eval/run_eval.py`: the 3 metrics on Gemma 4 31B, results in EVAL.md
- README, MIT license, public repo

## Stretch (only if MVP is done before 14:00)
1. Automatic fallback to Ollama on 429
2. Gemma 4 31B vs E2B row in the eval (1 run per script)
3. Drift-check banner
4. Human-vs-human baseline (second blind grader)

**Future work, not built today:** rubric extraction from a question-paper photo; Gemma function calling.

## Schedule
| Time | What | Done when |
|---|---|---|
| 11:00 | Start `ollama pull gemma4:e2b` (5–7 GB) | download running |
| 11:00–11:25 | **De-risk**: 3 real photos → `gemma-4-31b-it` | GO / NO-GO called at 11:25 |
| 11:25–11:40 | Skeleton on `main` (done), create branches | both branches pushed |
| 11:40–13:00 | Build in parallel; data team: 10 photos + teacher marks **by 12:15** | each branch runs on its own |
| 13:00–13:30 | **Merge #1**: one real script end-to-end in the UI | smoke test passes on `gemini` |
| 13:30 | **Start eval runs** (background terminal) | raw files appearing |
| 14:00 | **Feature freeze**: bug fixes only; fill EVAL tables | tables filled from files |
| 14:30 | **Code freeze**, tag `v1` | — |
| 14:30–14:55 | README final, rehearse demo ×2, repo public | — |
| **15:00** | **Submit** (15:00–15:15 buffer only) | — |

**Rule:** if a task runs 30 min over, cut it or ask for help. Eval numbers matter more than UI polish.

## De-risk (first 25 min) — Person A
Send 3 real handwritten photos with the transcribe prompt and the grade prompt. Write down:
1. Is the transcription mostly correct? 2. Is `response_json_schema` accepted for Gemma 4? (Not confirmed in Google's docs.) 3. Seconds per call. 4. Any 429s.

- **GO** if ≥2 of 3 transcriptions are mostly right.
- **NO-GO** (decide at 11:25, don't debate): use neater block handwriting, crop tightly, one answer per photo. The rest of the plan stays the same.
- If the schema setting is rejected: paste the schema into the prompt and rely on Pydantic validate + retry.

## Who does what
| Person | Branch | Owns |
|---|---|---|
| A | `feat/model-pipeline` | `copilot/models.py`, `prompts.py`, `rules.py`, `pipeline.grade_script` |
| B | `feat/ui-eval` | `app.py`, `eval/run_eval.py` |
| C, D | `main` (docs/data only) | `data/`, README, DEMO, EVAL tables |

**Contract:** `copilot/schemas.py` and `copilot/config.py` change only on `main`, and you tell each other when you do. B builds against `MODEL_BACKEND=fake` until merge #1.
**Merging:** `git pull origin main` into your branch first, then `python scripts/smoke_test.py`, then merge.

## Risks → fallbacks
| Risk | Fallback |
|---|---|
| Gemma can't read the handwriting | neater samples, tighter crops; disclose it |
| JSON schema not enforced | schema in prompt + validate/retry (already the design) |
| Rate limits / API down | backoff → Ollama → cached results for the demo |
| E2B download too slow | phone hotspot; if not working by 13:30, drop the E2B row |
| Eval too slow | 3 runs instead of 5 for consistency; disclose it |
| Python 3.14 install errors | `py -3.12 -m venv .venv` |
| Merge breaks things | smoke test; revert to last tag |
| Venue wifi dies during demo | pre-recorded video + real results saved earlier (never demo fake data as real) |
