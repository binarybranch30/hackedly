import streamlit as st

from copilot import audit, pipeline, store
from copilot.schemas import AnchorGrade, AuditEntry
from ui import components as c
from ui import theme

theme.page_header("Anchor scripts", "Grade 3 answers yourself. They are shown to Gemma 4 as examples so it "
                  "marks like you, and are re-checked to detect drift.")
c.show_flash()

rubric = store.load_rubric()
saved = store.load_anchors()
N = 3

tabs = st.tabs([f"Anchor {n + 1}" + (f" · {saved[n].script_id}" if n < len(saved) else "") for n in range(N)])
for n, tab in enumerate(tabs):
    a = saved[n] if n < len(saved) else None
    k = f"anchor{n}"
    # Pre-fill widget state once from saved anchors
    if f"{k}_text" not in st.session_state:
        st.session_state[f"{k}_text"] = a.transcription if a else ""
    with tab:
        left, right = st.columns([2, 3], gap="medium")
        with left:
            with st.container(border=True):
                sid = st.text_input("Script ID", a.script_id if a else f"A{n + 1:02d}", key=f"{k}_id")
                up = st.file_uploader("Answer photo", type=["jpg", "jpeg", "png"], key=f"{k}_up")
                if up:
                    c.save_upload(up, c.anchors_dir(), c.script_id_from_name(sid))
                img = c.find_image(c.script_id_from_name(sid), c.anchors_dir())
                if img:
                    st.image(str(img), width="stretch")
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
            with st.container(border=True):
                st.text_area("Answer text (check and correct it)", key=f"{k}_text", height=150)
                st.markdown("**Your marks**")
                for r in rubric.items:
                    cols = st.columns([3, 2, 3], vertical_alignment="center")
                    cols[0].markdown(f"**{r.item_id}** {r.description}")
                    prev = a.marks.get(r.item_id, r.allowed_marks[0]) if a else r.allowed_marks[0]
                    cols[1].segmented_control("Marks", r.allowed_marks, required=True, label_visibility="collapsed",
                                              default=prev if prev in r.allowed_marks else r.allowed_marks[0],
                                              key=f"{k}_m_{r.item_id}")
                    cols[2].text_input("Why (optional)", a.notes.get(r.item_id, "") if a else "",
                                       key=f"{k}_n_{r.item_id}", label_visibility="collapsed",
                                       placeholder="Why? (optional)")

if st.button("Save anchors", type="primary", icon=":material/save:"):
    anchors, errors = [], []
    for n in range(N):
        k = f"anchor{n}"
        text = st.session_state.get(f"{k}_text", "").strip()
        if not text:
            continue
        sid = c.script_id_from_name(st.session_state.get(f"{k}_id", f"A{n + 1:02d}"))
        anchors.append(AnchorGrade(
            script_id=sid, transcription=text,
            marks={r.item_id: st.session_state[f"{k}_m_{r.item_id}"] for r in rubric.items},
            notes={r.item_id: st.session_state.get(f"{k}_n_{r.item_id}", "") for r in rubric.items
                   if st.session_state.get(f"{k}_n_{r.item_id}")}))
    ids = [a.script_id for a in anchors]
    if not anchors:
        errors.append("Fill in the answer text of at least one anchor.")
    if len(ids) != len(set(ids)):
        errors.append("Anchor script IDs must be different.")
    if errors:
        for e in errors:
            st.error(e)
    else:
        store.save_anchors(anchors)
        audit.log(AuditEntry(actor="teacher", action="edit", script_id="anchors",
                             after=", ".join(f"{a.script_id}={sum(a.marks.values())}" for a in anchors),
                             reason=f"{len(anchors)} anchor(s) saved"))
        c.flash(f"Saved {len(anchors)} anchor(s)." + ("" if len(anchors) == N else " Add all 3 for the best calibration."))
        st.rerun()
