import streamlit as st

from ui import components as c
from ui import theme
from ui.sections import anchors, rubric

theme.page_header("Set up", "Tell Hackedly what earns marks, and grade 3 answers yourself so it learns "
                  "how strict you are.")
c.show_flash()

t1, t2 = st.tabs([":material/rule: Rubric", ":material/anchor: Anchor scripts"])
with t1:
    rubric.render()
with t2:
    anchors.render()
