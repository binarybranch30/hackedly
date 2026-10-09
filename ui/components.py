"""Small helpers shared by the website pages (views/*.py)."""
from pathlib import Path

import streamlit as st

from copilot import audit, config, models, store
from copilot.schemas import ScriptGrade
from ui import theme

IMAGE_EXTS = (".jpg", ".jpeg", ".png")
SCRIPTS_DIR = config.DATA_DIR / "scripts"
ANCHORS_DIR = config.DATA_DIR / "anchors"

STATUS_LABEL = {"needs_review": "Needs review", "auto_ok": "Auto-OK",
                "approved": "Approved", "released": "Released"}
STATUS_BADGE = {"needs_review": "orange", "auto_ok": "blue", "approved": "green", "released": "violet"}
FLAG_HELP = {
    "UNREADABLE": "The photo or handwriting could not be read.",
    "LOW_CONFIDENCE": "The model said it was unsure about at least one item.",
    "EVIDENCE_NOT_FOUND": "A quoted piece of evidence is not in the answer text.",
    "RUNS_DISAGREE": "Two grading runs gave different totals.",
    "RULE_VIOLATION": "The model gave a mark the rubric does not allow (corrected).",
    "MODEL_ERROR": "The model failed to return valid output after retries.",
    "FALLBACK_USED": "Graded by the local fallback model.",
}


def find_image(script_id: str, folder: Path = SCRIPTS_DIR) -> Path | None:
    for ext in IMAGE_EXTS:
        p = folder / f"{script_id}{ext}"
        if p.exists():
            return p
    return None


def save_upload(upload, folder: Path, script_id: str) -> Path:
    """Save an uploaded image as <folder>/<script_id>.<ext> (replacing older copies)."""
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(upload.name).suffix.lower()
    ext = ext if ext in IMAGE_EXTS else ".jpg"
    for old in IMAGE_EXTS:
        (folder / f"{script_id}{old}").unlink(missing_ok=True)
    path = folder / f"{script_id}{ext}"
    path.write_bytes(upload.getvalue())
    return path


def script_id_from_name(name: str) -> str:
    """'Riya Sharma Q1.JPG' -> 'Riya_Sharma_Q1' (safe for file names)."""
    stem = Path(name).stem.strip()
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in stem) or "script"


def flag_badges(flags: list[str]) -> None:
    """Coloured flag pills; hover shows what the flag means."""
    if not flags:
        st.markdown(theme.badge_html("no flags", "success"), unsafe_allow_html=True)
        return
    html_ = "".join(
        theme.badge_html(f.replace("_", " ").lower(), theme.FLAG_COLORS.get(f, "danger"))
        .replace("<span ", f"<span title='{FLAG_HELP.get(f, '')}' ", 1) for f in flags)
    st.markdown(html_, unsafe_allow_html=True)


def status_badge(status: str) -> None:
    st.badge(STATUS_LABEL.get(status, status), color=STATUS_BADGE.get(status, "gray"))


def grade_rows(grades: list[ScriptGrade]) -> list[dict]:
    return [{"Script": g.script_id, "Score": f"{g.total}/{g.max_total}",
             "Status": STATUS_LABEL.get(g.status, g.status),
             "Flags": ", ".join(f.replace("_", " ").lower() for f in g.flags) or "—",
             "Model": g.model, "Time": f"{g.seconds:.1f}s" if g.seconds else "—"} for g in grades]


def flash(msg: str, kind: str = "success") -> None:
    """Show a message after the next rerun."""
    st.session_state["_flash"] = (kind, msg)


def show_flash() -> None:
    if "_flash" in st.session_state:
        kind, msg = st.session_state.pop("_flash")
        getattr(st, kind)(msg)


def sidebar_status() -> None:
    """Backend card at the bottom of the sidebar."""
    with st.sidebar:
        backend = config.MODEL_BACKEND
        st.caption("MODEL BACKEND")
        st.markdown(f"**{models.model_name(backend)}**  \n`{backend}`")
        if backend == "fake":
            st.warning("Demo mode: grades are made up. Set `MODEL_BACKEND=gemini` in `.env`.",
                       icon=":material/science:")
        elif backend == "gemini" and not config.GEMINI_API_KEY:
            st.error("GEMINI_API_KEY is missing in `.env`.", icon=":material/key_off:")
        elif config.AUTO_FALLBACK and backend == "gemini":
            st.caption(f"Falls back to `{config.OLLAMA_MODEL}` on rate limits.")


def drift_entries(limit: int = 5):
    return [e for e in reversed(audit.read_all()) if e.action == "drift_check"][:limit]


def setup_status() -> dict:
    rubric_saved = store.RUBRIC_PATH.exists()
    anchors = store.load_anchors()
    return {"rubric_saved": rubric_saved, "n_anchors": len(anchors),
            "n_grades": len(store.load_grades())}
