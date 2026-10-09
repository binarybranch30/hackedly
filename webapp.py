"""AnchorGrade website (multi-page dashboard).

Run:  streamlit run webapp.py
Pages live in views/. Shared look in ui/theme.py, helpers in ui/components.py.
"""
import streamlit as st

from ui import components, theme

st.set_page_config(page_title="AnchorGrade", page_icon=":material/grading:", layout="wide")
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
page.run()
