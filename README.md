# AnchorGrade

An AI copilot that helps teachers grade **handwritten answer sheets**, built at Hacktoberfest Hack Day Bengaluru '26 (IEEE CIS) for PS 02, *Intelligent Personal / Professional Copilot*.

- The teacher sets a rubric and grades 3 **anchor** scripts to calibrate the system.
- **Gemma 4** reads each handwritten answer and scores every rubric item, quoting the exact evidence for each mark.
- **Code** (not the model) verifies the quotes, applies the rubric rules, and adds up the totals.
- Unsure or unreadable scripts are **flagged**. Nothing is released until the teacher **approves**. Every action goes into an **audit log**.
- An **evaluation harness** measures the gap to the teacher's marks, consistency, and flagging quality. See [EVAL.md](EVAL.md).

> Demo GIF / screenshot: TODO

## How it works
See [ARCHITECTURE.md](ARCHITECTURE.md) for the pipeline diagram, schemas and failure handling.

## Models
| Role | Model | How |
|---|---|---|
| Main | `gemma-4-31b-it` (Gemma 4, open-weight) | Gemini API |
| Local fallback | `gemma4:e2b` | Ollama on `localhost:11434` |

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
streamlit run app.py
```
macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate`, then the same commands.

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
