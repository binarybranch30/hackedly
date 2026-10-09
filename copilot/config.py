"""All settings in one place. Values come from .env (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
AUDIT_PATH = ROOT / "audit.jsonl"

# Sample mode: a separate, prepared workspace for demos (data/sample/).
# Real data in data/ is never touched while sample mode is on.
SAMPLE_DIR = DATA_DIR / "sample"
SAMPLE_FLAG = DATA_DIR / ".sample_mode"


def sample_mode() -> bool:
    return SAMPLE_FLAG.exists()


def workspace() -> Path:
    """Folder holding the active rubric, anchors, grades and photos."""
    return SAMPLE_DIR if sample_mode() else DATA_DIR


def audit_path() -> Path:
    return SAMPLE_DIR / "audit.jsonl" if sample_mode() else AUDIT_PATH

# The ONE switch: gemini | ollama | fake
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "fake").lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")
# Second Gemma 4 model on the same API, used when the main one is overloaded (503/429).
# Empty string disables it.
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemma-4-26b-a4b-it")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
AUTO_FALLBACK = os.getenv("AUTO_FALLBACK", "true").lower() == "true"
# Gemma 4 "thinking" on the Gemini API: minimal is much faster; high may reason better.
GEMMA_THINKING = os.getenv("GEMMA_THINKING", "minimal")   # minimal | high | off
PARALLEL_SCRIPTS = int(os.getenv("PARALLEL_SCRIPTS", "4"))  # scripts graded at the same time
REQUEST_TIMEOUT_S = 180

MAX_RETRIES = 2                   # re-ask the model this many times on invalid JSON
BACKOFF_SECONDS = [5, 15]         # waits after a 429 / 503 (overloaded) error, then fall back
TEMPERATURE = 0.0
DISAGREE_THRESHOLD = 1            # flag if two grading runs differ by >= this many marks
EVIDENCE_MATCH_RATIO = 0.85       # fuzzy-match threshold for evidence quotes
