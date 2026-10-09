"""All settings in one place. Values come from .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AUDIT_PATH = ROOT / "audit.jsonl"

# The ONE switch: gemini | ollama | fake
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "fake").lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
AUTO_FALLBACK = os.getenv("AUTO_FALLBACK", "true").lower() == "true"

MAX_RETRIES = 2                   # re-ask the model this many times on invalid JSON
BACKOFF_SECONDS = [2, 4, 8]       # waits after a 429 rate-limit error
TEMPERATURE = 0.0
DISAGREE_THRESHOLD = 1            # flag if two grading runs differ by >= this many marks
EVIDENCE_MATCH_RATIO = 0.85       # fuzzy-match threshold for evidence quotes
