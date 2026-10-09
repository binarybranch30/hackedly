import streamlit as st

from copilot import config, pipeline, store
from copilot.schemas import Script
from ui import board
from ui import components as c
from ui import theme

theme.page_header("Grade", "Gemma 4 reads each answer sheet and grades it against your rubric. "
                  "Code checks every mark. Unsure sheets go to you.")

rubric = store.load_rubric()
anchors = store.load_anchors()
graded = {g.script_id for g in store.load_grades()}
files = sorted(p for p in c.scripts_dir().glob("*") if p.suffix.lower() in c.IMAGE_EXTS)
waiting = [p for p in files if p.stem not in graded]

st.markdown(board.flow_strip(), unsafe_allow_html=True)

with st.container(border=True):
    left, right = st.columns([3, 2], gap="large", vertical_alignment="center")
    with left:
        st.markdown(f"**{len(waiting)} answer sheet(s) waiting**" if waiting else "**No sheets waiting**")
        if waiting:
            st.caption(" · ".join(p.name for p in waiting[:10]) + (" …" if len(waiting) > 10 else ""))
        st.caption(f"Rubric: {len(rubric.items)} items, {rubric.max_total} marks · "
                   f"{len(anchors)} anchor script(s) · model: {c.model_label()}")
    with right:
        go = st.button(f"Grade {len(waiting)} sheet(s) now" if waiting else "Nothing to grade",
                       type="primary", icon=":material/play_arrow:", disabled=not waiting, width="stretch")
    with st.expander("Add answer sheets or change settings"):
        uploads = st.file_uploader("Photos or PDFs, one answer per file. The file name becomes the sheet ID.",
                                   type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)
        if uploads and st.button("Add to queue", icon=":material/add:"):
            for up in uploads:
                c.save_upload(up, c.scripts_dir(), c.script_id_from_name(up.name))
            st.rerun()
        calibrated = st.toggle("Use my anchor scripts to calibrate", value=bool(anchors), disabled=not anchors,
                               help="Puts your 3 graded anchors in the prompt so the model marks like you.")
        if graded and st.button("Clear previous results and grade everything again",
                                icon=":material/restart_alt:"):
            for g in store.load_grades():
                (store.grades_dir() / f"{g.script_id}.json").unlink(missing_ok=True)
            st.session_state.pop("last_run", None)
            st.rerun()

if go:
    ids = [p.stem for p in waiting]
    state, results = {}, {}
    status_line = st.empty()
    holder = st.empty()

    def redraw():
        holder.markdown(board.render(ids, state, results), unsafe_allow_html=True)

    def on_event(sid, step, status, detail):
        state[(sid, step)] = (status, detail)
        redraw()

    def on_progress(done, total, g):
        results[g.script_id] = g
        status_line.markdown(f"**Grading… {done}/{total} done**")
        redraw()

    redraw()
    status_line.markdown(f"**Grading {len(ids)} sheet(s), {min(len(ids), config.PARALLEL_SCRIPTS)} at a time…**")
    grades, drift = pipeline.grade_batch([Script(script_id=p.stem, image_path=str(p)) for p in waiting],
                                         rubric, anchors, calibrated=calibrated,
                                         on_progress=on_progress, on_event=on_event)
    st.session_state["last_run"] = {"ids": ids, "state": state, "drift": drift}
    st.rerun()

run = st.session_state.get("last_run")
if run:
    results = {g.script_id: g for g in store.load_grades()}
    done = [results[i] for i in run["ids"] if i in results]
    need = sum(g.status == "needs_review" for g in done)
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.success(f"**{len(done)} graded** · {need} need your review · {len(done) - need} auto-OK",
              icon=":material/task_alt:")
    if need:
        b.page_link("views/review.py", label="Review now", icon=":material/arrow_forward:")
    st.markdown(board.render(run["ids"], run["state"], results), unsafe_allow_html=True)
    for d in run["drift"]:
        if d.get("drifted"):
            st.warning(f"Drift check: anchor {d['anchor_id']} got {d['system_total']} from the system, "
                       f"{d['teacher_total']} from you.", icon=":material/warning:")
        elif d.get("system_total") is not None:
            st.caption(f"Drift check passed: anchor {d['anchor_id']} {d['system_total']} vs your "
                       f"{d['teacher_total']}.")
