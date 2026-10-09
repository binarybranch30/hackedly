"""Model backends. OWNER: Person A (feat/model-pipeline).

Everything else calls ONE function:

    generate_json(system, prompt, image_path, schema) -> instance of `schema`

The backend is chosen by MODEL_BACKEND in .env (gemini | ollama | fake).
Callers never know which backend answered except via `last_backend_used()`.
"""
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from copilot import config
from copilot.fake import fake_for_schema

T = TypeVar("T", bound=BaseModel)

_last_backend = config.MODEL_BACKEND


class ModelError(Exception):
    """Raised when the model never returned valid output after all retries."""


class RateLimited(Exception):
    """Raised by a backend on HTTP 429 / RESOURCE_EXHAUSTED."""


def last_backend_used() -> str:
    """Which backend actually produced the last answer (matters after fallback)."""
    return _last_backend


def model_name(backend: str) -> str:
    return {"gemini": config.GEMINI_MODEL, "ollama": config.OLLAMA_MODEL}.get(backend, "fake")


def generate_json(system: str, prompt: str, image_path: Optional[str | Path],
                  schema: Type[T]) -> T:
    """Ask the model for JSON matching `schema`, validate it, retry on errors.

    TODO (Person A):
    1. Call _call_backend(...) to get raw text.
    2. schema.model_validate_json(raw). On ValidationError: append the error
       message to the prompt ("Your last reply was invalid: ...; reply again
       with ONLY valid JSON") and retry up to config.MAX_RETRIES times.
       Log each retry to the audit log (action="retry").
    3. On RateLimited: sleep through config.BACKOFF_SECONDS; if still limited
       and config.AUTO_FALLBACK, switch to "ollama" (audit action="fallback").
    4. If still invalid: raise ModelError (pipeline turns it into a flag).
    """
    global _last_backend
    if config.MODEL_BACKEND == "fake":
        _last_backend = "fake"
        return fake_for_schema(schema, prompt)
    raise NotImplementedError("TODO Person A: real backends")


def _call_backend(backend: str, system: str, prompt: str,
                  image_path: Optional[str | Path], schema: Type[BaseModel]) -> str:
    """Return the model's raw text reply."""
    if backend == "gemini":
        return _call_gemini(system, prompt, image_path, schema)
    if backend == "ollama":
        return _call_ollama(system, prompt, image_path, schema)
    raise ValueError(f"unknown backend {backend}")


def _call_gemini(system, prompt, image_path, schema) -> str:
    """TODO (Person A). Verified in docs (google-genai SDK):
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        image = client.files.upload(file=image_path)   # or types.Part.from_bytes(...)
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=config.TEMPERATURE,
                response_mime_type="application/json",
                response_json_schema=schema.model_json_schema(),  # NOT confirmed for Gemma 4: test it!
            ),
        )
        return resp.text
    If the schema config is rejected, drop those two lines and paste the
    schema into the prompt instead. Raise RateLimited on 429.
    """
    raise NotImplementedError


def _call_ollama(system, prompt, image_path, schema) -> str:
    """TODO (Person A). Verified in docs (ollama Python library):
        from ollama import Client
        resp = Client(host=config.OLLAMA_URL).chat(
            model=config.OLLAMA_MODEL,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt, "images": [str(image_path)]}],
            format=schema.model_json_schema(),
            options={"temperature": config.TEMPERATURE},
        )
        return resp.message.content
    """
    raise NotImplementedError
