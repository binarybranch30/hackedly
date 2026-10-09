# Hackedly

An AI copilot that helps teachers grade **handwritten answer sheets**, built at Hacktoberfest Hack Day Bengaluru '26 (IEEE CIS) for PS 02, *Intelligent Personal / Professional Copilot*.

- The teacher sets a rubric and grades 3 **anchor** scripts to calibrate the system.
- **Gemma 4** reads each handwritten answer and scores every rubric item, quoting the exact evidence for each mark.
- **Code** (not the model) verifies the quotes, applies the rubric rules, and adds up the totals.
- Unsure or unreadable scripts are **flagged**. Nothing is released until the teacher **approves**. Every action goes into an **audit log**.
- An **evaluation harness** measures the gap to the teacher's marks, consistency, and flagging quality. See [EVAL.md](EVAL.md).

> Demo GIF / screenshot: TODO

## How it works
For each answer photo, the workflow runs these steps:

1. **Image check** (code): the photo is rotated upright and shrunk. Unusable images are flagged `UNREADABLE`.
2. **Read** (Gemma 4 vision): the photo is transcribed into structured JSON (`legibility`, `text`, `unclear_spans`).
3. **Grade ×2** (Gemma 4): the rubric and the teacher's 3 anchor scripts go in as examples. For every item, the model returns marks, an exact evidence quote and a confidence. Grading runs twice to check consistency.
4. **Rules** (code): checks that each quote is really in the answer, snaps marks to allowed values, and adds up the total.
5. **Route**: if the model reported low confidence, a quote is missing, the two runs disagree, the image is unreadable, the model failed, or the fallback model was used, the script goes to **teacher review**.
6. **Approve → release**: the teacher edits marks and approves. The CSV export includes approved scripts only.
7. **Drift check**: every 5 scripts, an anchor is re-graded and compared with the teacher's marks.

Every step is written to `audit.jsonl`. Model replies are validated against a schema and retried with the error message. On rate limits the system backs off, then falls back to local Gemma. The teacher can also start from a **photo of the question paper**: Gemma 4 drafts the rubric, code checks it, and the teacher approves it.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram, schemas and failure handling.

## Models
| Role | Model | How |
|---|---|---|
| Main | `gemma-4-26b-a4b-it` (Gemma 4, open-weight) | Gemini API |
| Fallback when the main one is overloaded | `gemma-4-31b-it` (Gemma 4) | Gemini API |
| Optional local fallback | `gemma4:e2b` | Ollama on `localhost:11434` |

Both API models are configurable in `.env` (`GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`). In our tests on 2026-10-09, the 26B-A4B model answered in about 1 second per call, while the 31B model took 30–60 seconds and often returned `503 high demand`. That is why the 26B-A4B model is the default.

Switch with `MODEL_BACKEND=gemini|ollama|fake` in `.env`.

## Key dependencies
`google-genai`, `ollama`, `pydantic`, `streamlit`, `python-dotenv`, `pillow`

## Run it (Windows)
```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      &REM then put your GEMINI_API_KEY in .env
ollama pull gemma4:e2b      &REM optional, for the local backend
python scripts\smoke_test.py
streamlit run webapp.py
```
macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same commands.

## Use it with your own class
1. **Set up → Create an assessment** (name, class, subject). Each assessment keeps its own rubric, students, sheets, marks and audit log; switch between them in the sidebar.
2. **Students:** type the class list or import a CSV with roll number and name columns.
3. **Rubric:** one row per markable point, as many as you need. Leave *Allowed marks* blank for 0 to max. Or draft it from a photo of the question paper.
4. **Anchor scripts:** grade a few answers yourself (3 recommended) so Gemma 4 learns your strictness.
5. **Grade:** upload photos or PDFs (one student per file). Name files by roll number, or match files like `IMG_2034.jpg` to students on the page, then press *Grade*.
6. **Review:** check evidence, change marks, approve, or send unreadable sheets to the rescan list. **Export** gives the released marks with student names.

Student data stays on the server in `data/assessments/` and is git-ignored.

## Useful scripts
| Command | What it does |
|---|---|
| `python scripts/smoke_test.py` | Quick end-to-end check (works with `MODEL_BACKEND=fake`) |
| `python scripts/test_pipeline.py` | Offline tests of every failure path (no API key needed) |
| `python scripts/test_assessments.py` | Offline tests for assessments, class lists and exports |
| `python scripts/gonogo.py a.jpg b.jpg c.jpg` | Try the real model on real handwriting |
| `streamlit run webapp.py` | **The website**: dashboard, rubric, anchors, grading, review & approve, export, evaluation, audit log |
| `streamlit run ui/preview.py` | Style preview of the dashboard theme |

## Evaluation
`python eval/run_eval.py`. Results and the small-sample disclosure are in [EVAL.md](EVAL.md).

## Limitations
- Tiny test set (≈10 scripts, 1 teacher). The numbers are indicative only.
- If the transcription is wrong, the evidence check can pass on wrong text. The teacher reviews the image.
- The system copies one teacher's style, including that teacher's biases.

## Team
TODO: names and roles

## License
[MIT](LICENSE)
