"""Model backends. OWNER: Person A (feat/model-pipeline).

Everything else calls ONE function:

    generate_json(system, prompt, image_path, schema) -> instance of `schema`

The backend is chosen by MODEL_BACKEND in .env (gemini | ollama | fake).
Callers learn which backend actually answered via `last_backend_used()`.
"""
import io
import json
import time
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from copilot import audit, config
from copilot.fake import fake_for_schema
from copilot.schemas import AuditEntry

T = TypeVar("T", bound=BaseModel)

_last_backend = config.MODEL_BACKEND
_gemini_client = None
_call_count = 0

MAX_IMAGE_SIDE = 2000  # px; phone photos are shrunk to this before sending

# Set to False if the go/no-go test shows Gemma 4 rejects response_json_schema;
# the schema is then only described in the prompt (validation still happens).
USE_API_SCHEMA = True


class ModelError(Exception):
    """Raised when the model never returned valid output after all retries."""


class RateLimited(Exception):
    """Raised by a backend on HTTP 429 / RESOURCE_EXHAUSTED."""


def last_backend_used() -> str:
    """Which backend actually produced the last answer (matters after fallback)."""
    return _last_backend


def call_count() -> int:
    """Total model requests made so far (including retries); used for cost/speed stats."""
    return _call_count


def model_name(backend: str) -> str:
    return {"gemini": config.GEMINI_MODEL, "ollama": config.OLLAMA_MODEL}.get(backend, "fake")


def generate_json(system: str, prompt: str, image_path: Optional[str | Path],
                  schema: Type[T], script_id: Optional[str] = None) -> T:
    """Ask the model for JSON matching `schema`, validate it, retry on errors.

    - Invalid JSON / wrong shape: re-ask with the error message (MAX_RETRIES times).
    - 429 rate limit: wait BACKOFF_SECONDS, then fall back to Ollama if AUTO_FALLBACK.
    - Still failing: raise ModelError (the pipeline turns it into a flag).
    """
    global _last_backend
    backend = config.MODEL_BACKEND
    if backend == "fake":
        _last_backend = "fake"
        return fake_for_schema(schema, prompt)

    full_prompt = (f"{prompt}\n\nReply with ONLY a JSON object matching this JSON schema:\n"
                   f"{json.dumps(schema.model_json_schema())}")
    last_error = ""
    for attempt in range(config.MAX_RETRIES + 1):
        p = full_prompt if not last_error else (
            f"{full_prompt}\n\nYour previous reply was invalid:\n{last_error}\n"
            "Reply again with ONLY valid JSON that matches the schema.")
        raw = _call_with_backoff(backend, system, p, image_path, schema, script_id)
        if raw is None:  # rate limited and fell back
            backend = "ollama"
            raw = _call_backend(backend, system, p, image_path, schema)
        try:
            result = schema.model_validate_json(_strip_fences(raw))
            _last_backend = backend
            return result
        except ValidationError as e:
            last_error = str(e)[:1500]
            audit.log(AuditEntry(actor="system", action="retry", script_id=script_id,
                                 reason=f"attempt {attempt + 1}: invalid {schema.__name__}: {last_error[:300]}",
                                 backend=backend, model=model_name(backend)))
    raise ModelError(f"{schema.__name__} invalid after {config.MAX_RETRIES + 1} attempts: {last_error[:300]}")


def _call_with_backoff(backend, system, prompt, image_path, schema, script_id) -> Optional[str]:
    """Call the backend; on 429 wait and retry. Returns None if we should fall back."""
    for wait in [*config.BACKOFF_SECONDS, None]:
        try:
            return _call_backend(backend, system, prompt, image_path, schema)
        except RateLimited as e:
            if wait is None:
                break
            audit.log(AuditEntry(actor="system", action="retry", script_id=script_id,
                                 reason=f"rate limited, waiting {wait}s: {e}", backend=backend,
                                 model=model_name(backend)))
            time.sleep(wait)
    if backend != "ollama" and config.AUTO_FALLBACK:
        audit.log(AuditEntry(actor="system", action="fallback", script_id=script_id,
                             reason="still rate limited after backoff; switching to local model",
                             backend="ollama", model=config.OLLAMA_MODEL))
        return None
    raise ModelError("rate limited and no fallback available")


def prepare_image(image_path: str | Path) -> bytes:
    """Load a photo, rotate it upright (phones store rotation in EXIF), convert to
    RGB, shrink so the longest side <= MAX_IMAGE_SIDE, and return JPEG bytes.
    Smaller uploads are faster and stay well under API request limits."""
    from PIL import Image, ImageOps

    with Image.open(image_path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _strip_fences(raw: str) -> str:
    """Models sometimes wrap JSON in ```json ... ``` fences."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    return s.strip()


def _call_backend(backend: str, system: str, prompt: str,
                  image_path: Optional[str | Path], schema: Type[BaseModel]) -> str:
    """Return the model's raw text reply."""
    global _call_count
    _call_count += 1
    if backend == "gemini":
        return _call_gemini(system, prompt, image_path, schema)
    if backend == "ollama":
        return _call_ollama(system, prompt, image_path, schema)
    raise ValueError(f"unknown backend {backend}")


def _call_gemini(system, prompt, image_path, schema) -> str:
    global _gemini_client
    from google import genai
    from google.genai import errors, types

    if _gemini_client is None:
        if not config.GEMINI_API_KEY:
            raise ModelError("GEMINI_API_KEY is not set in .env")
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)

    contents = []
    if image_path:
        contents.append(types.Part.from_bytes(data=prepare_image(image_path), mime_type="image/jpeg"))
    contents.append(prompt)

    cfg = dict(system_instruction=system, temperature=config.TEMPERATURE)
    if USE_API_SCHEMA:
        cfg.update(response_mime_type="application/json",
                   response_json_schema=schema.model_json_schema())
    try:
        resp = _gemini_client.models.generate_content(
            model=config.GEMINI_MODEL, contents=contents,
            config=types.GenerateContentConfig(**cfg))
    except errors.APIError as e:
        if e.code == 429:
            raise RateLimited(str(e)[:200]) from e
        raise
    return resp.text or ""


def _call_ollama(system, prompt, image_path, schema) -> str:
    from ollama import Client

    user = {"role": "user", "content": prompt}
    if image_path:
        user["images"] = [prepare_image(image_path)]
    resp = Client(host=config.OLLAMA_URL).chat(
        model=config.OLLAMA_MODEL,
        messages=[{"role": "system", "content": system}, user],
        format=schema.model_json_schema(),
        options={"temperature": config.TEMPERATURE},
    )
    return resp.message.content
