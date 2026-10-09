"""Hackedly website (multi-page dashboard).

Run:  streamlit run webapp.py
Pages live in views/. Shared look in ui/theme.py, helpers in ui/components.py.
"""
import streamlit as st

from copilot import config
from ui import components, theme

st.set_page_config(page_title="Hackedly", page_icon=":material/grading:", layout="wide")
theme.inject_css()
st.logo("ui/logo.svg", size="large")

pages = {
    "Overview": [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:", default=True),
    ],
    "Set up": [
        st.Page("views/rubric.py", title="Rubric", icon=":material/rule:"),
        st.Page("views/anchors.py", title="Anchor scripts", icon=":material/anchor:"),
    ],
    "Grade": [
        st.Page("views/grade.py", title="Grade scripts", icon=":material/upload_file:"),
        st.Page("views/review.py", title="Review & approve", icon=":material/fact_check:"),
        st.Page("views/export.py", title="Export", icon=":material/download:"),
    ],
    "Trust": [
        st.Page("views/evaluation.py", title="Evaluation", icon=":material/monitoring:"),
        st.Page("views/audit.py", title="Audit log", icon=":material/history:"),
    ],
}
page = st.navigation(pages)
components.sidebar_status()
if config.sample_mode():
    st.info("**Sample class.** Prepared example answers and marks that show the whole workflow. They are "
            "not live model output. New photos you upload here are graded by the real backend. "
            "Switch off *Sample class* in the sidebar to return to your own data.", icon=":material/school:")
page.run()
