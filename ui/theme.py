"""Dashboard look for the Streamlit app: sidebar nav, stat cards, badges.

Visual style only (colours, spacing, font). No code or images are copied from
any template. Call `inject_css()` once at the top of app.py.
"""
import html

import streamlit as st

PRIMARY = "#0E7C66"
COLORS = {
    "primary": "#0E7C66",
    "success": "#0E7C66",
    "warning": "#B86E00",
    "danger": "#D6453D",
    "info": "#2F6FD0",
    "muted": "#5B667A",
}

# Colour tokens for each mode. Streamlit's own widgets follow .streamlit/config.toml;
# our custom HTML (cards, board, badges) follows these.
PALETTES = {
    "light": {"bg": "#F6F7F4", "card": "#FFFFFF", "sidebar": "#FFFFFF", "text": "#0F1B2D",
              "muted": "#5B667A", "faint": "#9AA3B2", "border": "#E4E6E0", "hover": "#EEF3EF",
              "mark": "#FCEBC8", "primary": "#0E7C66", "primary-soft": "#DDEFE9",
              "ink": "#0F1B2D", "ink-text": "#FFFFFF", "paper": "#FBF8EF",
              "shadow": "rgba(15, 27, 45, .07)"},
    "dark": {"bg": "#0B1422", "card": "#13213A", "sidebar": "#0F1A2D", "text": "#EEF2F6",
             "muted": "#A7B1C2", "faint": "#6C7890", "border": "#22314B", "hover": "#1A2A45",
             "mark": "rgba(252, 196, 90, .28)", "primary": "#2BB394", "primary-soft": "rgba(43, 179, 148, .16)",
             "ink": "#EEF2F6", "ink-text": "#0B1422", "paper": "#1B2A44",
             "shadow": "rgba(0, 0, 0, .35)"},
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,1,0');
:root { __VARS__ --ag-head: 'Bricolage Grotesque', 'Plus Jakarta Sans', sans-serif;
        --ag-body: 'Plus Jakarta Sans', sans-serif; }
.block-container { padding-top: 3rem; max-width: 1240px; }
[data-testid="stHeader"] { background: transparent; }
.ag-icon { font-family: 'Material Symbols Rounded'; font-size: 1.4rem; line-height: 1; }

/* Sidebar + built-in navigation: navy pill for the active page */
[data-testid="stSidebar"] { background: var(--ag-sidebar); border-right: 1px solid var(--ag-border); }
[data-testid="stSidebarNav"] a { border-radius: 999px; padding: .45rem .9rem; margin: .12rem 0; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--ag-ink); }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: var(--ag-ink-text) !important; font-weight: 600; }
[data-testid="stSidebarNav"] a:hover:not([aria-current="page"]) { background: var(--ag-hover); }

/* Bordered containers become white cards */
[data-testid="stVerticalBlockBorderWrapper"] { background: var(--ag-card); border-radius: 1rem; }

/* Page title */
.ag-title { font-family: var(--ag-head); font-size: 2.3rem; font-weight: 800; color: var(--ag-text);
            margin: 0; line-height: 1.1; letter-spacing: -.02em; }
.ag-subtitle { color: var(--ag-muted); margin: .4rem 0 1.4rem 0; font-size: 1.02rem; max-width: 720px; }
.ag-eyebrow { display: inline-block; background: var(--ag-primary-soft); color: var(--ag-primary);
              font-size: .78rem; font-weight: 600; padding: .25rem .7rem; border-radius: 999px; margin-bottom: .8rem; }

/* Stat cards */
.ag-card { background: var(--ag-card); border: 1px solid var(--ag-border); border-radius: 1rem;
           padding: 1rem 1.2rem; margin-bottom: 1rem; }
.ag-stat { display: flex; align-items: center; gap: .8rem; }
.ag-stat > div:last-child { min-width: 0; }
.ag-stat-icon { width: 2.6rem; height: 2.6rem; border-radius: .8rem; display: flex;
                align-items: center; justify-content: center; flex-shrink: 0; }
.ag-stat-value { font-family: var(--ag-head); font-size: 1.6rem; font-weight: 700; line-height: 1.1; color: var(--ag-text); }
.ag-stat-label { font-size: .82rem; color: var(--ag-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Badges */
.ag-badge { display: inline-block; padding: .15rem .65rem; border-radius: 999px; font-size: .74rem;
            font-weight: 600; margin: 0 .25rem .25rem 0; }
mark { background: var(--ag-mark); color: inherit; padding: 0 .15rem; border-radius: 3px; }
</style>
"""


def is_dark() -> bool:
    """Is the viewer using the dark theme? (Streamlit reports it per session.)"""
    try:
        return st.context.theme.type == "dark"
    except Exception:  # older Streamlit / bare mode
        return False


def palette() -> dict:
    return PALETTES["dark" if is_dark() else "light"]


def inject_css() -> None:
    tokens = " ".join(f"--ag-{k}: {v};" for k, v in palette().items())
    st.markdown(_CSS.replace("__VARS__", tokens), unsafe_allow_html=True)


def sidebar_nav(pages: list[str], brand: str = "Hackedly", tagline: str = "Grading copilot") -> str:
    """Sidebar menu; returns the selected page name."""
    st.sidebar.markdown(
        f"<div style='padding:.5rem .25rem 1rem'><span style='font-size:1.5rem;font-weight:700;"
        f"color:{PRIMARY}'>✎ {html.escape(brand)}</span><br>"
        f"<span style='color:#7E7E7E;font-size:.85rem'>{html.escape(tagline)}</span></div>",
        unsafe_allow_html=True)
    return st.sidebar.radio("Menu", pages, label_visibility="collapsed")


def page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eb = f"<div class='ag-eyebrow'>{html.escape(eyebrow)}</div>" if eyebrow else ""
    st.markdown(eb + f"<div class='ag-title'>{html.escape(title)}</div>"
                f"<div class='ag-subtitle'>{html.escape(subtitle)}</div>", unsafe_allow_html=True)


def stat_card(label: str, value, icon: str = "description", color: str = "primary") -> None:
    """A white card with a coloured icon circle. Use inside st.columns().
    `icon` is a Material Symbols name, e.g. description, flag, check_circle, star, timer."""
    c = COLORS.get(color, color)
    st.markdown(
        f"<div class='ag-card ag-stat'>"
        f"<div class='ag-stat-icon' style='background:{c}1A;color:{c}'>"
        f"<span class='ag-icon'>{html.escape(icon)}</span></div>"
        f"<div><div class='ag-stat-value'>{html.escape(str(value))}</div>"
        f"<div class='ag-stat-label'>{html.escape(label)}</div></div></div>",
        unsafe_allow_html=True)


# Flag code -> badge colour. Unknown codes are shown in red.
FLAG_COLORS = {
    "LOW_CONFIDENCE": "warning", "RUNS_DISAGREE": "warning", "FALLBACK_USED": "info",
    "EVIDENCE_NOT_FOUND": "danger", "UNREADABLE": "danger", "MODEL_ERROR": "danger",
    "RULE_VIOLATION": "danger",
}
STATUS_COLORS = {"needs_review": "warning", "auto_ok": "info", "approved": "success", "released": "primary"}


def badge_html(text: str, color: str = "danger") -> str:
    c = COLORS.get(color, color)
    return f"<span class='ag-badge' style='background:{c}1A;color:{c}'>{html.escape(text)}</span>"


def badges(flags: list[str]) -> None:
    st.markdown("".join(badge_html(f, FLAG_COLORS.get(f, "danger")) for f in flags) or
                badge_html("no flags", "success"), unsafe_allow_html=True)


def status_badge(status: str) -> str:
    return badge_html(status.replace("_", " "), STATUS_COLORS.get(status, "muted"))


def highlight(text: str, quotes: list[str]) -> str:
    """Escape `text` and wrap each evidence quote in <mark>. Returns HTML."""
    out = html.escape(text)
    for q in sorted({q for q in quotes if q}, key=len, reverse=True):
        eq = html.escape(q)
        out = out.replace(eq, f"<mark>{eq}</mark>")
    return out

# For a white card around Streamlit widgets use: with st.container(border=True): ...
