"""Streamlit UI. OWNER: Person B (feat/ui-eval).

Run:  streamlit run app.py
Works today with MODEL_BACKEND=fake (grades are made up).
Only call functions from copilot.pipeline / copilot.store / copilot.audit.
"""
import tempfile
from pathlib import Path

import streamlit as st

from copilot import audit, config, pipeline, store
from copilot.schemas import Script

st.set_page_config(page_title="AnchorGrade", layout="wide")
st.title("AnchorGrade — handwritten answer grading copilot")
st.caption(f"Backend: **{config.MODEL_BACKEND}** · Nothing is released until the teacher approves.")

rubric = store.load_rubric()
tab_rubric, tab_anchors, tab_grade, tab_review, tab_export, tab_audit = st.tabs(
    ["Rubric", "Anchors", "Grade", "Review", "Export", "Audit log"])

with tab_rubric:
    # TODO (Person B): editable form -> store.save_rubric(...)
    st.subheader(rubric.question)
    st.table([{"item": i.item_id, "description": i.description, "max": i.max_marks,
               "allowed": str(i.allowed_marks)} for i in rubric.items])

with tab_anchors:
    # TODO (Person B): for 3 anchor scripts: upload image, show transcription,
    # teacher enters marks per item + note -> store.save_anchors([...AnchorGrade])
    st.info(f"{len(store.load_anchors())} anchor scripts saved. TODO: anchor grading form.")

with tab_grade:
    uploads = st.file_uploader("Answer images", type=["jpg", "jpeg", "png"],
                               accept_multiple_files=True)
    if uploads and st.button("Grade all"):
        tmp = Path(tempfile.mkdtemp())
        for up in uploads:
            path = tmp / up.name
            path.write_bytes(up.getvalue())
            g = pipeline.grade_script(Script(script_id=Path(up.name).stem, image_path=str(path)),
                                      rubric, store.load_anchors())
            st.write(f"{g.script_id}: {g.total}/{g.max_total} · {g.status} · {', '.join(g.flags)}")

with tab_review:
    # TODO (Person B): flagged scripts first; show image + transcription with the
    # evidence quotes highlighted; number inputs for edits; Approve button.
    for g in store.load_grades():
        with st.expander(f"{'⚠️' if g.flags else '✅'} {g.script_id} — {g.total}/{g.max_total} — {g.status}"):
            st.write("Flags:", g.flags or "none")
            st.json(g.model_dump(), expanded=False)
            if g.status not in ("approved", "released") and st.button("Approve", key=f"ap-{g.script_id}"):
                pipeline.approve(g.script_id, edits={})
                st.rerun()

with tab_export:
    if st.button("Export approved scripts to CSV"):
        out = Path(tempfile.mkdtemp()) / "marks.csv"
        n = pipeline.export_csv(out)
        st.download_button(f"Download marks.csv ({n} scripts)", out.read_bytes(), "marks.csv")

with tab_audit:
    st.dataframe([e.model_dump() for e in reversed(audit.read_all())])
