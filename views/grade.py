import streamlit as st

from copilot import config, pipeline, store
from copilot.schemas import Script
from ui import board
from ui.sections import class_report
from ui import components as c
from ui import theme

theme.page_header("Grade", "Gemma 4 reads each answer sheet and grades it against your rubric. "
                  "Code checks every mark. Unsure sheets go to you.", eyebrow=c.workspace_label())
c.show_flash()

if not config.sample_mode() and not config.active_assessment():
    st.info("Create an assessment first: it holds the rubric, students and answer sheets.",
            icon=":material/add:")
    st.page_link("views/setup.py", label="Set up an assessment", icon=":material/arrow_forward:")
    st.stop()

rubric = store.load_rubric()
if not rubric.items:
    st.info("This assessment has no rubric yet. Add one before grading.", icon=":material/rule:")
    st.page_link("views/setup.py", label="Write the rubric", icon=":material/arrow_forward:")
    st.stop()

anchors = store.load_anchors()
roster = store.load_roster()
names = store.student_names()
grades = {g.script_id: g for g in store.load_grades()}
files = sorted(p for p in c.scripts_dir().glob("*") if p.suffix.lower() in c.IMAGE_EXTS)
waiting = [p for p in files if p.stem not in grades]
have_sheet = {p.stem for p in files}
missing = [r for r in roster if r["roll_no"] not in have_sheet]

st.markdown(board.flow_strip(), unsafe_allow_html=True)

with st.container(border=True):
    left, right = st.columns([3, 2], gap="large", vertical_alignment="center")
    with left:
        st.markdown(f"**{len(waiting)} answer sheet(s) waiting**" if waiting else "**No sheets waiting**")
        bits = [f"{len(rubric.items)} rubric items · {rubric.max_total} marks",
                f"{len(anchors)} anchor(s)", f"model: {c.model_label()}"]
        if roster:
            bits.insert(0, f"{len(roster)} students · {len(have_sheet & set(names))} with a sheet")
        st.caption(" · ".join(bits))
    with right:
        go = st.button(f"Grade {len(waiting)} sheet(s) now" if waiting else "Nothing to grade",
                       type="primary", icon=":material/play_arrow:", disabled=not waiting, width="stretch")

    up_col, opt_col = st.columns([3, 2], gap="large")
    with up_col:
        uploads = st.file_uploader("Add answer sheets: photos or PDFs, one student per file. Name them "
                                   "“R07 Asha Rao.pdf” and the student is added to the class list "
                                   "automatically; other names can be matched below.",
                                   type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True,
                                   key=f"sheets_up_{st.session_state.get('sheets_up_n', 0)}")
        if uploads and st.button(f"Add {len(uploads)} file(s)", icon=":material/add:"):
            st.session_state["sheets_up_n"] = st.session_state.get("sheets_up_n", 0) + 1  # empties the box
            new_students = []
            for up in uploads:
                parsed = store.parse_sheet_filename(up.name)   # "R07 Asha Rao.pdf" -> ("R07", "Asha Rao")
                sid = parsed[0] if parsed else c.script_id_from_name(up.name)
                if parsed:
                    new_students.append(parsed)
                c.save_upload(up, c.scripts_dir(), sid)
                pipeline.reopen_for_new_scan(sid)  # a new scan replaces one marked "needs rescan"
            added = store.add_students(new_students)
            c.flash(f"Added {len(uploads)} file(s)" + (f"; {added} student(s) added to the class list." if added else "."))
            st.rerun()
    with opt_col:
        calibrated = st.toggle("Calibrate with my anchor scripts", value=bool(anchors), disabled=not anchors,
                               help="Puts your graded anchors in the prompt so the model marks like you.")
        if grades and st.button("Clear all marks and grade again", icon=":material/restart_alt:",
                                type="tertiary"):
            for sid in grades:
                (store.grades_dir() / f"{sid}.json").unlink(missing_ok=True)
            st.session_state.pop("last_run", None)
            st.rerun()

# Match sheets to students (needed when files are named like IMG_2034.jpg)
unmatched = [p for p in waiting if roster and p.stem not in names]
if roster and (unmatched or missing):
    with st.expander(f"Match sheets to students · {len(unmatched)} unmatched file(s), "
                     f"{len(missing)} student(s) without a sheet", icon=":material/link:",
                     expanded=bool(unmatched)):
        if unmatched:
            free = [r["roll_no"] for r in missing]
            table = st.data_editor(
                [{"file": p.name, "student": None} for p in unmatched], hide_index=True, width="stretch",
                disabled=["file"], key="match_editor",
                column_config={"file": st.column_config.TextColumn("File"),
                               "student": st.column_config.SelectboxColumn(
                                   "Student", options=[f"{r} · {names.get(r, '')}" for r in free])})
            if st.button("Apply matches", icon=":material/link:"):
                done = 0
                for row in table:
                    if row["student"]:
                        roll = row["student"].split(" · ")[0]
                        src = c.scripts_dir() / row["file"]
                        if src.exists() and not c.find_image(roll):
                            src.rename(src.with_name(roll + src.suffix.lower()))
                            done += 1
                c.flash(f"Matched {done} sheet(s).")
                st.rerun()
        if missing:
            st.caption("No sheet yet: " + ", ".join(f"{r['roll_no']} {r['name']}".strip() for r in missing[:40])
                       + (" …" if len(missing) > 40 else ""))

if go:
    ids = [p.stem for p in waiting]
    labels = {i: c.student_label(i) for i in ids}
    state, results = {}, {}
    status_line = st.empty()
    holder = st.empty()

    def redraw():
        holder.markdown(board.render(ids, state, results, labels), unsafe_allow_html=True)

    def on_event(sid, step, status, detail):
        state[(sid, step)] = (status, detail)
        redraw()

    def on_progress(done, total, g):
        results[g.script_id] = g
        status_line.markdown(f"**Grading… {done}/{total} done**")
        redraw()

    redraw()
    status_line.markdown(f"**Grading {len(ids)} sheet(s), {min(len(ids), config.PARALLEL_SCRIPTS)} at a time…**")
    _, drift = pipeline.grade_batch([Script(script_id=p.stem, image_path=str(p)) for p in waiting],
                                    rubric, anchors, calibrated=calibrated,
                                    on_progress=on_progress, on_event=on_event)
    st.session_state["last_run"] = {"ids": ids, "state": state, "drift": drift, "ws": str(config.workspace())}
    st.rerun()

run = st.session_state.get("last_run")
if run and run.get("ws", str(config.workspace())) == str(config.workspace()):
    results = {g.script_id: g for g in store.load_grades()}
    done = [results[i] for i in run["ids"] if i in results]
    need = sum(g.status == "needs_review" for g in done)
    a, b = st.columns([3, 1], vertical_alignment="center")
    a.success(f"**{len(done)} graded** · {need} need your review · {len(done) - need} auto-OK",
              icon=":material/task_alt:")
    if need:
        b.page_link("views/review.py", label="Review now", icon=":material/arrow_forward:")
    st.markdown(board.render(run["ids"], run["state"], results, {i: c.student_label(i) for i in run["ids"]}),
                unsafe_allow_html=True)
    with st.container(border=True):
        class_report.render(compact=True)
    for d in run["drift"]:
        if d.get("drifted"):
            st.warning(f"Drift check: anchor {d['anchor_id']} got {d['system_total']} from the system, "
                       f"{d['teacher_total']} from you.", icon=":material/warning:")
        elif d.get("system_total") is not None:
            st.caption(f"Drift check passed: anchor {d['anchor_id']} {d['system_total']} vs your "
                       f"{d['teacher_total']}.")
