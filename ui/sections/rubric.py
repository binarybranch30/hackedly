import streamlit as st

from copilot import audit, config, pipeline, store
from copilot.schemas import AuditEntry, Rubric, RubricItem
from ui import components as c
from ui import theme


def render() -> None:
    c.show_flash()

    # Drafts are kept per workspace so switching assessments never mixes rubrics.
    ws = str(config.workspace())
    if st.session_state.get("rubric_ws") != ws:
        st.session_state["rubric_ws"] = ws
        st.session_state["rubric_draft"] = store.load_rubric()
        st.session_state["rubric_problems"] = []
        st.session_state.pop("rubric_editor", None)
    draft: Rubric = st.session_state["rubric_draft"]
    if not store.rubric_path().exists():
        st.info("No rubric saved yet. Add one row per markable point (as many as you need), or draft it "
                "from a photo of the question paper.", icon=":material/rule:")

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
        question = st.text_area("Question(s)", draft.question, height=90,
                                placeholder="Paste the question text. For several questions, list them all.")
        st.markdown("**Items** — one row per markable point, as many as you need (e.g. Q1a, Q1b, Q2…). "
                    "*Allowed marks* is optional: leave it blank to allow every whole mark from 0 to Max, "
                    "or list them, e.g. `0,2,4` for no odd marks.")
        rows = [{"item_id": i.item_id, "description": i.description, "max_marks": i.max_marks,
                 "allowed_marks": ",".join(map(str, i.allowed_marks)), "guidance": i.guidance} for i in draft.items]
        if not rows:
            rows = [{"item_id": "Q1", "description": "", "max_marks": 2, "allowed_marks": "", "guidance": ""}]
        edited = st.data_editor(
            rows, num_rows="dynamic", hide_index=True, width="stretch", key="rubric_editor",
            column_config={
                "item_id": st.column_config.TextColumn("Item", width="small", required=True),
                "description": st.column_config.TextColumn("What earns marks", width="large", required=True),
                "max_marks": st.column_config.NumberColumn("Max", min_value=1, step=1, width="small", required=True),
                "allowed_marks": st.column_config.TextColumn("Allowed marks", width="small"),
                "guidance": st.column_config.TextColumn("Marking notes", width="medium"),
            })
        save = st.button("Save rubric", type="primary", icon=":material/save:")

    if save:
        try:
            items = []
            for r in edited:
                if not str(r.get("item_id") or "").strip():
                    continue
                mx = int(r.get("max_marks") or 0)
                allowed_txt = str(r.get("allowed_marks") or "").strip()
                allowed = ([int(x) for x in allowed_txt.replace(" ", "").split(",") if x] if allowed_txt
                           else list(range(0, mx + 1)))  # blank = every whole mark from 0 to max
                items.append(RubricItem(item_id=str(r["item_id"]).strip(),
                                        description=str(r.get("description") or "").strip(), max_marks=mx,
                                        allowed_marks=sorted(set(allowed)),
                                        guidance=str(r.get("guidance") or "").strip()))
            new = Rubric(rubric_id=rubric_id.strip() or "rubric", question=question.strip(), items=items)
        except (ValueError, TypeError) as e:
            st.error(f"Check the table: {e}")
            return
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
