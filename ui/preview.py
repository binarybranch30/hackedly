"""Style preview / example of every theme helper, on fake data.

Run:  streamlit run ui/preview.py --server.port 8503
Copy patterns from here into app.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from copilot.fake import fake_script_grade  # noqa: E402
from copilot import store  # noqa: E402
from ui import theme  # noqa: E402

st.set_page_config(page_title="AnchorGrade", page_icon="✎", layout="wide")
theme.inject_css()

page = theme.sidebar_nav(["Dashboard", "Rubric", "Anchors", "Grade", "Review", "Export", "Audit log"])
rubric = store.load_rubric()
grades = [fake_script_grade(f"S{i:02d}", rubric) for i in range(4, 11)]

theme.page_header(page, "Backend: fake · nothing is released until the teacher approves")

c1, c2, c3, c4 = st.columns(4)
with c1:
    theme.stat_card("Scripts graded", len(grades), "description", "primary")
with c2:
    theme.stat_card("Need review", sum(g.status == "needs_review" for g in grades), "flag", "warning")
with c3:
    theme.stat_card("Approved", sum(g.status == "approved" for g in grades), "check_circle", "success")
with c4:
    theme.stat_card("Avg score", f"{sum(g.total for g in grades) / len(grades):.1f}/{rubric.max_total}", "star", "info")

left, right = st.columns([3, 2])
with left:
    with st.container(border=True):
        st.markdown("**Grading queue**")
        st.dataframe([{"script": g.script_id, "total": f"{g.total}/{g.max_total}",
                       "status": g.status, "flags": ", ".join(g.flags)} for g in grades],
                     hide_index=True, width="stretch")
with right:
    g = grades[0]
    with st.container(border=True):
        st.markdown(f"**{g.script_id}** &nbsp; {theme.status_badge(g.status)}", unsafe_allow_html=True)
        theme.badges(g.flags)
        st.markdown(theme.highlight(g.transcription.text, [i.evidence_quote for i in g.items]),
                    unsafe_allow_html=True)
        for it in g.items:
            st.markdown(f"`{it.item_id}` **{it.final_marks}** marks · {it.confidence} confidence · "
                        f"evidence {'✅' if it.evidence_found else '❌'}")
        st.button("Approve", type="primary")
