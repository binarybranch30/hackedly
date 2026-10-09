import streamlit as st

from copilot import audit, config, pipeline, store
from copilot.schemas import AuditEntry, Rubric, RubricItem
from ui import components as c
from ui import theme

theme.page_header("Rubric", "What earns marks. Type it in, or let Gemma 4 draft it from a photo of the "
                  "question paper. You approve it before it is used.")
c.show_flash()

if "rubric_draft" not in st.session_state:
    st.session_state["rubric_draft"] = store.load_rubric()
    st.session_state["rubric_problems"] = []
draft: Rubric = st.session_state["rubric_draft"]

with st.expander("Draft from a question-paper photo (Gemma 4)", icon=":material/auto_awesome:"):
    photo = st.file_uploader("Photo of the question paper or marking scheme", type=["jpg", "jpeg", "png"])
    if st.button("Draft rubric", icon=":material/auto_awesome:", disabled=photo is None):
        path = c.save_upload(photo, config.workspace() / "question_papers", "question_paper")
        try:
            with st.spinner("Reading the question paper…"):
                new, problems = pipeline.extract_rubric(str(path))
            st.session_state["rubric_draft"] = new
            st.session_state["rubric_problems"] = problems
            st.session_state.pop("rubric_editor", None)
            c.flash("Draft ready. Check it below, edit anything, then save.", "info")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not draft a rubric: {e}")

for p in st.session_state["rubric_problems"]:
    st.warning(p, icon=":material/rule:")

with st.container(border=True):
    rubric_id = st.text_input("Rubric name", draft.rubric_id)
    question = st.text_area("Question", draft.question, height=90)
    st.markdown("**Items** — allowed marks are comma-separated, e.g. `0,1,2`. Add or delete rows as needed.")
    rows = [{"item_id": i.item_id, "description": i.description, "max_marks": i.max_marks,
             "allowed_marks": ",".join(map(str, i.allowed_marks)), "guidance": i.guidance} for i in draft.items]
    edited = st.data_editor(
        rows, num_rows="dynamic", hide_index=True, width="stretch", key="rubric_editor",
        column_config={
            "item_id": st.column_config.TextColumn("Item", width="small", required=True),
            "description": st.column_config.TextColumn("What earns marks", width="large", required=True),
            "max_marks": st.column_config.NumberColumn("Max", min_value=1, step=1, width="small", required=True),
            "allowed_marks": st.column_config.TextColumn("Allowed marks", width="small", required=True),
            "guidance": st.column_config.TextColumn("Marking notes", width="medium"),
        })
    save = st.button("Save rubric", type="primary", icon=":material/save:")

if save:
    try:
        items = [RubricItem(item_id=str(r["item_id"]).strip(), description=str(r["description"]).strip(),
                            max_marks=int(r["max_marks"]),
                            allowed_marks=[int(x) for x in str(r["allowed_marks"]).split(",") if x.strip()],
                            guidance=str(r.get("guidance") or "").strip())
                 for r in edited if r.get("item_id")]
        new = Rubric(rubric_id=rubric_id.strip() or "rubric", question=question.strip(), items=items)
    except (ValueError, TypeError) as e:
        st.error(f"Check the table: {e}")
        st.stop()
    problems = pipeline.check_rubric(new)
    if problems:
        for p in problems:
            st.error(p)
    else:
        store.save_rubric(new)
        audit.log(AuditEntry(actor="teacher", action="edit", script_id="rubric",
                             after=f"{len(new.items)} items, {new.max_total} marks", reason="rubric saved"))
        st.session_state["rubric_draft"] = new
        st.session_state["rubric_problems"] = []
        c.flash(f"Rubric saved: {len(new.items)} items, {new.max_total} marks.")
        st.rerun()
