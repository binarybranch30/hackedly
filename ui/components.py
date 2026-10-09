"""Small helpers shared by the website pages (views/*.py)."""
from pathlib import Path

import streamlit as st

from copilot import audit, config, models, store
from copilot.schemas import ScriptGrade
from ui import theme

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".pdf")


def scripts_dir() -> Path:
    return config.workspace() / "scripts"


def anchors_dir() -> Path:
    return config.workspace() / "anchors"


STATUS_LABEL = {"needs_review": "Needs review", "auto_ok": "Auto-OK",
                "approved": "Approved", "released": "Released", "rescan": "Needs rescan"}
STATUS_BADGE = {"needs_review": "orange", "auto_ok": "blue", "approved": "green", "released": "violet",
                "rescan": "red"}
FLAG_HELP = {
    "UNREADABLE": "The photo or handwriting could not be read.",
    "LOW_CONFIDENCE": "The model said it was unsure about at least one item.",
    "EVIDENCE_NOT_FOUND": "A quoted piece of evidence is not in the answer text.",
    "RUNS_DISAGREE": "Two grading runs gave different totals.",
    "RULE_VIOLATION": "The model gave a mark the rubric does not allow (corrected).",
    "MODEL_ERROR": "The model failed to return valid output after retries.",
    "FALLBACK_USED": "The main model was overloaded; a fallback model graded part of it.",
}


def find_image(script_id: str, folder: Path | None = None) -> Path | None:
    folder = folder or scripts_dir()
    for ext in IMAGE_EXTS:
        p = folder / f"{script_id}{ext}"
        if p.exists():
            return p
    return None


@st.cache_data(show_spinner=False, max_entries=64)
def _render(path: str, mtime: float):
    return models.load_image(path)


def preview(path: Path):
    """Displayable image for a photo or PDF (PDF pages are rendered and stacked)."""
    return _render(str(path), path.stat().st_mtime)


def model_label() -> str:
    return "demo data (fake)" if config.MODEL_BACKEND == "fake" else models.model_name(config.MODEL_BACKEND)


def save_upload(upload, folder: Path, script_id: str) -> Path:
    """Save an uploaded photo/PDF as <folder>/<script_id>.<ext> (replacing older copies)."""
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


PAGE_PATHS = ["", "home", "setup", "grade", "review", "insights"]


def set_theme(mode: str) -> None:
    """Switch Streamlit's light/dark theme for this browser, then reload.
    Streamlit keeps the choice in localStorage, one key per page path."""
    import json

    import streamlit.components.v1 as components

    keys = json.dumps([f"stActiveTheme-/{p}-v2" for p in PAGE_PATHS])
    components.html(f"""<script>
      const s = window.parent.localStorage;
      for (const k of {keys}) s.setItem(k, JSON.stringify("{mode}"));
      window.parent.location.reload();
    </script>""", height=0)


def theme_button() -> None:
    """Sun/moon button pinned to the top-right corner (CSS: .st-key-ag_theme_btn)."""
    dark = theme.is_dark()
    with st.container(key="ag_theme_btn"):
        if st.button("", icon=":material/light_mode:" if dark else ":material/dark_mode:", type="tertiary",
                     help="Switch to light mode" if dark else "Switch to dark mode"):
            set_theme("Light" if dark else "Dark")


def sidebar_status() -> None:
    """Compact sidebar footer: sample-class switch + which model is grading."""
    from copilot import sample  # local import: only the website needs it

    from copilot import assessments

    with st.sidebar:
        if not config.sample_mode():
            items = assessments.list_all()
            if items:
                slugs = [m["slug"] for m in items]
                active = config.active_assessment()
                pick = st.selectbox("Assessment", slugs, index=slugs.index(active) if active in slugs else None,
                                    format_func=lambda s: assessments.label(next(m for m in items if m["slug"] == s)),
                                    placeholder="Choose an assessment")
                if pick and pick != active:
                    assessments.activate(pick)
                    st.session_state.pop("last_run", None)
                    st.rerun()
            st.page_link("views/setup.py", label="New assessment" if items else "Create an assessment",
                         icon=":material/add:")
        on = st.toggle("Sample class", value=config.sample_mode(),
                       help="A prepared class (rubric, 3 graded anchors, 8 answer-sheet PDFs) for demos. "
                            "The sheets are graded live. Your own data is kept separately.")
        if on != config.sample_mode():
            with st.spinner("Preparing the sample class…"):
                sample.enable() if on else sample.disable()
            st.session_state.pop("last_run", None)
            st.rerun()
        if on and st.button("Reset sample class", icon=":material/restart_alt:", width="stretch",
                            type="tertiary"):
            sample.build()
            st.session_state.pop("last_run", None)
            st.rerun()
        backend = config.MODEL_BACKEND
        if backend == "fake":
            st.caption(":orange[:material/science:] Demo backend: grades are made up")
        elif backend == "gemini" and not config.GEMINI_API_KEY:
            st.caption(":red[:material/key_off:] GEMINI_API_KEY missing in .env")
        else:
            st.caption(f":green[:material/circle:] Grading with **{model_label()}**")


def workspace_label() -> str:
    """Short name of what is open: the sample class or the active assessment."""
    from copilot import assessments

    if config.sample_mode():
        return "Sample class"
    meta = assessments.get(config.active_assessment()) if config.active_assessment() else None
    return assessments.label(meta) if meta else "No assessment selected"


def student_label(script_id: str) -> str:
    name = store.student_names().get(script_id, "")
    return f"{script_id} · {name}" if name else script_id


def drift_entries(limit: int = 5):
    return [e for e in reversed(audit.read_all()) if e.action == "drift_check"][:limit]


def setup_status() -> dict:
    rubric_saved = store.rubric_path().exists()
    anchors = store.load_anchors()
    return {"rubric_saved": rubric_saved, "n_anchors": len(anchors),
            "n_grades": len(store.load_grades())}
