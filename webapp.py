"""Hackedly website (multi-page dashboard).

Run:  streamlit run webapp.py
Pages live in views/. Shared look in ui/theme.py, helpers in ui/components.py.
"""
import os

import streamlit as st

from copilot import config
from ui import components, theme

st.set_page_config(page_title="Hackedly", page_icon=":material/grading:", layout="wide")
theme.inject_css()
st.logo("ui/logo-dark.svg" if theme.is_dark() else "ui/logo.svg", size="large")

pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/setup.py", title="Set up", icon=":material/tune:"),
    st.Page("views/grade.py", title="Grade", icon=":material/play_circle:"),
    st.Page("views/review.py", title="Review", icon=":material/fact_check:"),
    st.Page("views/insights.py", title="Insights", icon=":material/insights:"),
]
# Public demo: a fresh deployment with no data of its own opens on the sample class.
if os.getenv("HACKEDLY_DEMO", "").lower() in ("1", "true") and not config.sample_mode() \
        and not config.active_assessment() and "demo_init" not in st.session_state:
    from copilot import assessments, sample
    if not assessments.list_all():
        sample.enable()
    st.session_state["demo_init"] = True

page = st.navigation(pages)
components.theme_button()
components.sidebar_status()
if config.sample_mode():
    st.markdown("<div style='background:var(--ag-primary-soft);color:var(--ag-primary);border-radius:.8rem;"
                "padding:.55rem 1rem;font-size:.88rem;margin-bottom:1rem'><b>Sample class</b> · prepared rubric, "
                "3 teacher-graded anchors and 8 answer sheets. Grading runs live with Gemma 4.</div>",
                unsafe_allow_html=True)
page.run()
