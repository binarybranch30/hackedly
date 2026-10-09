import streamlit as st

from ui import theme
from ui.sections import audit, evaluation

theme.page_header("Insights", "How reliable is the grading, and what exactly happened. Measured, not claimed.")

t1, t2 = st.tabs([":material/monitoring: Evaluation", ":material/history: Audit log"])
with t1:
    evaluation.render()
with t2:
    audit.render()
