import statistics

import streamlit as st

from copilot import store
from ui import board
from ui import components as c
from ui import theme

theme.page_header("Grade a class in minutes", "Gemma 4 reads handwritten answers and marks them like you do. "
                  "Every mark comes with evidence, and nothing is final until you approve it.")
c.show_flash()

rubric = store.load_rubric()
anchors = store.load_anchors()
grades = store.load_grades()
graded = {g.script_id for g in grades}
waiting = [p for p in c.scripts_dir().glob("*") if p.suffix.lower() in c.IMAGE_EXTS and p.stem not in graded]
need = [g for g in grades if g.status == "needs_review"]
done = [g for g in grades if g.status in ("approved", "released")]

st.markdown(board.flow_strip(), unsafe_allow_html=True)


def step(col, n, title, line, ok, link, label):
    with col.container(border=True, height="stretch"):
        icon = ":green[:material/check_circle:]" if ok else f":blue[**{n}**]"
        st.markdown(f"#### {icon} &nbsp;{title}")
        st.caption(line)
        st.page_link(link, label=label, icon=":material/arrow_forward:")


s1, s2, s3 = st.columns(3, gap="medium")
step(s1, 1, "Set up", f"{len(rubric.items)} rubric items · {rubric.max_total} marks · {len(anchors)}/3 anchors",
     store.rubric_path().exists() and len(anchors) >= 3, "views/setup.py", "Rubric & anchors")
step(s2, 2, "Grade", f"{len(waiting)} sheet(s) waiting · {len(grades)} graded",
     bool(grades) and not waiting, "views/grade.py", "Grade sheets")
step(s3, 3, "Review", f"{len(need)} need review · {len(done)} approved",
     bool(grades) and not need, "views/review.py", "Review & approve")

if grades:
    st.write("")
    a, b, d, e = st.columns(4)
    with a:
        theme.stat_card("Graded", len(grades), "description", "primary")
    with b:
        theme.stat_card("Need review", len(need), "flag", "warning")
    with d:
        theme.stat_card("Approved", len(done), "check_circle", "success")
    with e:
        theme.stat_card("Average", f"{statistics.mean(g.total for g in grades):.1f}/{rubric.max_total}",
                        "star", "info")
