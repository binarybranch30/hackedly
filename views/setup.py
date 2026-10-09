import streamlit as st

from copilot import config
from ui import components as c
from ui import theme
from ui.sections import anchors, assessment, rubric

theme.page_header("Set up", "Create an assessment, add your students, say what earns marks, and grade a few "
                  "answers yourself so Hackedly learns how strict you are.", eyebrow=c.workspace_label())
c.show_flash()

if not config.sample_mode() and not config.active_assessment():
    assessment.render()  # nothing else makes sense until an assessment exists
    st.stop()

t0, t1, t2 = st.tabs([":material/groups: Assessment & students", ":material/rule: Rubric",
                      ":material/anchor: Anchor scripts"])
with t0:
    assessment.render()
with t1:
    rubric.render()
with t2:
    anchors.render()
