import streamlit as st

from ui import components as c
from ui import theme
from ui.sections import audit, class_report, evaluation

theme.page_header("Insights", "What the class struggled with, how reliable the grading is, and exactly what "
                  "happened.", eyebrow=c.workspace_label())

t0, t1, t2 = st.tabs([":material/school: Class insights", ":material/monitoring: Evaluation",
                      ":material/history: Audit log"])
with t0:
    with st.container(border=True):
        class_report.render()
with t1:
    evaluation.render()
with t2:
    audit.render()
