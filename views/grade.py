import streamlit as st

from copilot import pipeline, store
from copilot.schemas import Script
from ui import components as c
from ui import theme

theme.page_header("Grade scripts", "Upload photos of handwritten answers. Gemma 4 reads and grades them; "
                  "doubtful ones are flagged for you.")

rubric = store.load_rubric()
anchors = store.load_anchors()

with st.container(border=True):
    st.markdown(f"**Question:** {rubric.question}")
    st.caption(f"{len(rubric.items)} rubric items · {rubric.max_total} marks · "
               f"{len(anchors)} anchor script(s) for calibration")
    uploads = st.file_uploader("Answer photos (one answer per photo). The file name becomes the script ID.",
                               type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    waiting = sorted(p for p in c.scripts_dir().glob("*") if p.suffix.lower() in c.IMAGE_EXTS
                     and p.stem not in {g.script_id for g in store.load_grades()})
    use_folder = False
    if waiting:
        use_folder = st.checkbox(f"Also grade {len(waiting)} ungraded photo(s) already in the scripts folder")
    calibrated = st.toggle("Use my anchor scripts to calibrate", value=bool(anchors), disabled=not anchors,
                           help="Puts your graded anchors in the prompt so the model marks like you.")
    if not anchors:
        st.caption("No anchors yet: grading uses the rubric only. Add anchors under **Anchor scripts**.")
    go = st.button("Grade now", type="primary", icon=":material/play_arrow:",
                   disabled=not (uploads or use_folder))

if go:
    scripts = []
    for up in uploads or []:
        sid = c.script_id_from_name(up.name)
        scripts.append(Script(script_id=sid, image_path=str(c.save_upload(up, c.scripts_dir(), sid))))
    if use_folder:
        scripts += [Script(script_id=p.stem, image_path=str(p)) for p in waiting
                    if p.stem not in {s.script_id for s in scripts}]

    bar = st.progress(0.0, text="Starting…")
    log = st.empty()
    lines = []

    def on_progress(done, total, g):
        bar.progress(done / total, text=f"Graded {done}/{total}")
        mark = "⚠" if g.status == "needs_review" else "✓"
        lines.append(f"{mark} **{g.script_id}** — {g.total}/{g.max_total} · {c.STATUS_LABEL[g.status]}"
                     + (f" · {', '.join(g.flags)}" if g.flags else "") + (f" · {g.seconds:.1f}s" if g.seconds else ""))
        log.markdown("  \n".join(lines))

    with st.spinner("Gemma 4 is reading and grading…"):
        grades, drift = pipeline.grade_batch(scripts, rubric, anchors, calibrated=calibrated,
                                             on_progress=on_progress)
    need = sum(g.status == "needs_review" for g in grades)
    st.success(f"{len(grades)} graded · {need} need review · {len(grades) - need} auto-OK")
    for d in drift:
        if d["error"]:
            st.info(f"Drift check on {d['anchor_id']} could not run: {d['error']}")
        elif d["drifted"]:
            st.warning(f"Drift warning: anchor {d['anchor_id']} got {d['system_total']} from the system "
                       f"but {d['teacher_total']} from you. Review recent scripts carefully.",
                       icon=":material/warning:")
        else:
            st.caption(f"Drift check OK: anchor {d['anchor_id']} {d['system_total']} vs your {d['teacher_total']}.")
    if need:
        st.page_link("views/review.py", label="Review flagged scripts", icon=":material/arrow_forward:")
