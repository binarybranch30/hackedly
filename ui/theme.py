"""Dashboard look for the Streamlit app: sidebar nav, stat cards, badges.

Visual style only (colours, spacing, font). No code or images are copied from
any template. Call `inject_css()` once at the top of app.py.
"""
import html

import streamlit as st

PRIMARY = "#1E33F2"
COLORS = {
    "primary": "#1E33F2",
    "success": "#2BC155",
    "warning": "#FFAC30",
    "danger": "#FF4C41",
    "info": "#51A6F5",
    "muted": "#7E7E7E",
}

# Colour tokens for each mode. Streamlit's own widgets follow .streamlit/config.toml;
# our custom HTML (cards, board, badges) follows these.
PALETTES = {
    "light": {"bg": "#F5F6FA", "card": "#FFFFFF", "sidebar": "#FFFFFF", "text": "#24292D",
              "muted": "#7E7E7E", "faint": "#A0A4B0", "border": "#EEF0F4", "hover": "#EEF0FE",
              "mark": "#FFF1D6", "primary": "#1E33F2", "shadow": "rgba(30, 51, 242, .06)"},
    "dark": {"bg": "#0E1220", "card": "#171C2E", "sidebar": "#121626", "text": "#E6E8EF",
             "muted": "#9AA0B4", "faint": "#6B7189", "border": "#262C40", "hover": "#1F2640",
             "mark": "rgba(255, 172, 48, .30)", "primary": "#5B6CFF", "shadow": "rgba(0, 0, 0, .35)"},
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,500,1,0');
:root { __VARS__ }
html, body, .stMarkdown p, .stMarkdown li, input, textarea,
[data-testid="stSidebarNav"] a span:not([data-testid="stIconMaterial"]) { font-family: 'Cairo', 'Source Sans Pro', sans-serif; }
.block-container { padding-top: 3.2rem; max-width: 1320px; }
[data-testid="stHeader"] { background: transparent; }
.ag-icon { font-family: 'Material Symbols Rounded'; font-size: 1.5rem; line-height: 1; }

/* Built-in multipage nav (st.navigation): pill-shaped items, blue active item */
[data-testid="stSidebarNav"] a { border-radius: .75rem; padding: .45rem .8rem; margin: .1rem 0; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--ag-primary); }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #FFFFFF !important; font-weight: 600; }
[data-testid="stSidebarNav"] a:hover:not([aria-current="page"]) { background: var(--ag-hover); }
[data-testid="stSidebar"] { background: var(--ag-sidebar); border-right: 1px solid var(--ag-border); }

/* Cards */
.ag-card { background: var(--ag-card); border-radius: .875rem; padding: 1.1rem 1.25rem;
           box-shadow: 0 2px 12px var(--ag-shadow); margin-bottom: 1rem; }
.ag-stat { display: flex; align-items: center; gap: .8rem; }
.ag-stat > div:last-child { min-width: 0; }
.ag-stat-icon { width: 2.8rem; height: 2.8rem; border-radius: 50%; display: flex;
                align-items: center; justify-content: center; font-size: 1.4rem; flex-shrink: 0; }
.ag-stat-value { font-size: 1.6rem; font-weight: 700; line-height: 1.1; color: var(--ag-text); }
.ag-stat-label { font-size: .85rem; color: var(--ag-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ag-title { font-size: 1.9rem; font-weight: 700; color: var(--ag-text); margin: 0; line-height: 1.2; }
.ag-subtitle { color: var(--ag-muted); margin: .2rem 0 1.2rem 0; font-size: 1rem; }

/* Badges */
.ag-badge { display: inline-block; padding: .15rem .6rem; border-radius: 1rem; font-size: .75rem;
            font-weight: 600; margin: 0 .25rem .25rem 0; }
[data-testid="stVerticalBlockBorderWrapper"] { background: var(--ag-card); border-radius: .875rem; }
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


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='ag-title'>{html.escape(title)}</div>"
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
