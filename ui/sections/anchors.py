import streamlit as st

from copilot import audit, pipeline, store
from copilot.schemas import AnchorGrade, AuditEntry, Rubric
from ui import components as c


def _form(rubric: Rubric, k: str, a: AnchorGrade | None, taken: set[str]) -> AnchorGrade | None:
    """Edit or add one anchor. Returns the anchor when the teacher presses Save."""
    if f"{k}_text" not in st.session_state:
        st.session_state[f"{k}_text"] = a.transcription if a else ""
    roster = store.load_roster()
    left, right = st.columns([2, 3], gap="medium")
    with left:
        if a:
            sid = a.script_id
            st.markdown(f"**{sid}**" + (f" · {store.student_names().get(sid, '')}" if sid in store.student_names() else ""))
        elif roster:
            opts = [r["roll_no"] for r in roster if r["roll_no"] not in taken]
            sid = st.selectbox("Student", opts, key=f"{k}_id", placeholder="Pick a student",
                               format_func=lambda r: f"{r} · {store.student_names().get(r, '')}")
        else:
            sid = c.script_id_from_name(st.text_input("Sheet ID", f"A{len(taken) + 1:02d}", key=f"{k}_id"))
        up = st.file_uploader("Answer sheet (photo or PDF)", type=["jpg", "jpeg", "png", "pdf"], key=f"{k}_up")
        if up and sid:
            c.save_upload(up, c.anchors_dir(), sid)
        img = c.find_image(sid, c.anchors_dir()) if sid else None
        if img:
            st.image(c.preview(img), width="stretch")
            if st.button("Read handwriting with Gemma 4", key=f"{k}_read", icon=":material/document_scanner:"):
                try:
                    with st.spinner("Reading…"):
                        t = pipeline.transcribe_image(str(img))
                    st.session_state[f"{k}_text"] = t.text
                    c.flash(f"Transcribed ({t.legibility}). Please correct any mistakes.", "info")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Could not read it: {e}")
    with right:
        st.text_area("Answer text (type it, or read it from the photo and correct it)", key=f"{k}_text",
                     height=140)
        st.markdown("**Your marks**")
        marks, notes = {}, {}
        for r in rubric.items:
            q, m, n = st.columns([3, 2, 3], vertical_alignment="center")
            q.markdown(f"**{r.item_id}** {r.description}")
            prev = a.marks.get(r.item_id, r.allowed_marks[0]) if a else r.allowed_marks[0]
            marks[r.item_id] = m.segmented_control(
                "Marks", r.allowed_marks, required=True, label_visibility="collapsed",
                default=prev if prev in r.allowed_marks else r.allowed_marks[0], key=f"{k}_m_{r.item_id}")
            notes[r.item_id] = n.text_input("Why", a.notes.get(r.item_id, "") if a else "", key=f"{k}_n_{r.item_id}",
                                            label_visibility="collapsed", placeholder="Why? (optional)")
        st.caption(f"Total: {sum(marks.values())}/{rubric.max_total}")
        if st.button("Save anchor" if a else "Add anchor", type="primary", key=f"{k}_save", icon=":material/save:"):
            text = st.session_state.get(f"{k}_text", "").strip()
            if not sid:
                st.error("Choose a student or sheet ID.")
            elif not text:
                st.error("Add the answer text first.")
            else:
                return AnchorGrade(script_id=sid, transcription=text, marks=marks,
                                   notes={i: v for i, v in notes.items() if v.strip()})
    return None


def _save(anchors: list[AnchorGrade], msg: str) -> None:
    store.save_anchors(anchors)
    audit.log(AuditEntry(actor="teacher", action="edit", script_id="anchors",
                         after=", ".join(f"{a.script_id}={sum(a.marks.values())}" for a in anchors),
                         reason=msg))
    for k in [k for k in st.session_state if str(k).startswith("anchor_")]:
        del st.session_state[k]
    c.flash(msg)
    st.rerun()


def render() -> None:
    rubric = store.load_rubric()
    anchors = store.load_anchors()
    st.caption("Grade a few answers yourself. Gemma 4 sees them as examples of how strictly *you* mark, and "
               "the system re-checks them during grading to detect drift. 3 is a good number; more helps "
               "for long rubrics.")
    if not anchors:
        st.info("No anchor scripts yet. Grading still works without them (rubric only), but it will not be "
                "calibrated to your marking.", icon=":material/anchor:")
    taken = {a.script_id for a in anchors}
    for n, a in enumerate(anchors):
        total = sum(a.marks.get(r.item_id, 0) for r in rubric.items)
        name = store.student_names().get(a.script_id, "")
        with st.expander(f"{a.script_id}{' · ' + name if name else ''}  —  {total}/{rubric.max_total}",
                         icon=":material/anchor:"):
            updated = _form(rubric, f"anchor_{a.script_id}", a, taken)
            if updated:
                anchors[n] = updated
                _save(anchors, f"Anchor {a.script_id} saved.")
            if st.button("Remove this anchor", key=f"anchor_{a.script_id}_del", icon=":material/delete:"):
                _save([x for x in anchors if x.script_id != a.script_id], f"Anchor {a.script_id} removed.")
    with st.expander("Add an anchor script", icon=":material/add:", expanded=not anchors):
        new = _form(rubric, f"anchor_new{len(anchors)}", None, taken)
        if new:
            if new.script_id in taken:
                st.error(f"{new.script_id} is already an anchor.")
            else:
                _save(anchors + [new], f"Anchor {new.script_id} added ({len(anchors) + 1} in total).")
