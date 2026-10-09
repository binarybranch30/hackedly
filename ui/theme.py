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

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, button, input, textarea { font-family: 'Cairo', sans-serif; }
.block-container { padding-top: 1.5rem; max-width: 1300px; }

/* Sidebar: white panel, blue active item */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #EEEEEE; }
[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: .55rem .9rem; border-radius: .75rem; margin-bottom: .25rem; width: 100%;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: #1E33F2; color: #FFFFFF;
}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: #FFFFFF; font-weight: 600; }
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child { display: none; }

/* Cards */
.ag-card { background: #FFFFFF; border-radius: .875rem; padding: 1.1rem 1.25rem;
           box-shadow: 0 2px 12px rgba(30, 51, 242, .06); margin-bottom: 1rem; }
.ag-stat { display: flex; align-items: center; gap: 1rem; }
.ag-stat-icon { width: 3.2rem; height: 3.2rem; border-radius: 50%; display: flex;
                align-items: center; justify-content: center; font-size: 1.4rem; flex-shrink: 0; }
.ag-stat-value { font-size: 1.6rem; font-weight: 700; line-height: 1.1; color: #24292D; }
.ag-stat-label { font-size: .85rem; color: #7E7E7E; }
.ag-title { font-size: 1.6rem; font-weight: 700; color: #24292D; margin: 0; }
.ag-subtitle { color: #7E7E7E; margin: 0 0 1rem 0; }

/* Badges */
.ag-badge { display: inline-block; padding: .15rem .6rem; border-radius: 1rem; font-size: .75rem;
            font-weight: 600; margin: 0 .25rem .25rem 0; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #FFFFFF; border-radius: .875rem; }
mark { background: #FFF1D6; padding: 0 .15rem; border-radius: 3px; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_nav(pages: list[str], brand: str = "AnchorGrade", tagline: str = "Grading copilot") -> str:
    """Sidebar menu; returns the selected page name."""
    st.sidebar.markdown(
        f"<div style='padding:.5rem .25rem 1rem'><span style='font-size:1.5rem;font-weight:700;"
        f"color:{PRIMARY}'>✎ {html.escape(brand)}</span><br>"
        f"<span style='color:#7E7E7E;font-size:.85rem'>{html.escape(tagline)}</span></div>",
        unsafe_allow_html=True)
    return st.sidebar.radio("Menu", pages, label_visibility="collapsed")


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"<p class='ag-title'>{html.escape(title)}</p>"
                f"<p class='ag-subtitle'>{html.escape(subtitle)}</p>", unsafe_allow_html=True)


def stat_card(label: str, value, icon: str = "●", color: str = "primary") -> None:
    """A white card with a coloured icon circle. Use inside st.columns()."""
    c = COLORS.get(color, color)
    st.markdown(
        f"<div class='ag-card ag-stat'>"
        f"<div class='ag-stat-icon' style='background:{c}1A;color:{c}'>{html.escape(icon)}</div>"
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
