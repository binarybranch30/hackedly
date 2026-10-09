import streamlit as st

from copilot import config, pipeline, store
from ui import components as c
from ui import theme

theme.page_header("Review & approve", "Check the evidence, change any mark, then approve. "
                  "Only approved scripts can be exported.")
c.show_flash()

rubric = store.load_rubric()
grades = store.load_grades()
if not grades:
    st.info("Nothing to review yet.", icon=":material/inbox:")
    st.page_link("views/grade.py", label="Grade scripts", icon=":material/upload_file:")
    st.stop()

FILTERS = {"Needs review": ["needs_review"], "Auto-OK": ["auto_ok"],
           "Approved": ["approved", "released"], "All": None}
counts = {k: sum(1 for g in grades if v is None or g.status in v) for k, v in FILTERS.items()}
default = "Needs review" if counts["Needs review"] else "All"
choice = st.segmented_control("Show", list(FILTERS), default=default, required=True,
                              format_func=lambda k: f"{k} ({counts[k]})", key="review_filter")
shown = sorted([g for g in grades if FILTERS[choice] is None or g.status in FILTERS[choice]],
               key=lambda g: g.script_id)
if not shown:
    st.success("Nothing here. All caught up!", icon=":material/task_alt:")
    st.stop()

ids = [g.script_id for g in shown]
if "_next_pick" in st.session_state:  # set by buttons; applied before the selectbox exists
    st.session_state["review_pick"] = st.session_state.pop("_next_pick")
if st.session_state.get("review_pick") not in ids:
    st.session_state["review_pick"] = ids[0]
nav1, nav2, nav3 = st.columns([1, 6, 1], vertical_alignment="bottom")
idx = ids.index(st.session_state["review_pick"])
if nav1.button("Previous", icon=":material/chevron_left:", disabled=idx == 0, width="stretch"):
    st.session_state["review_pick"] = ids[idx - 1]
    st.rerun()
if nav3.button("Next", icon=":material/chevron_right:", disabled=idx == len(ids) - 1, width="stretch"):
    st.session_state["review_pick"] = ids[idx + 1]
    st.rerun()
by_id = {g.script_id: g for g in shown}
nav2.selectbox("Script", ids, key="review_pick",
               format_func=lambda s: f"{s} · {by_id[s].total}/{by_id[s].max_total} · "
                                     f"{c.STATUS_LABEL[by_id[s].status]}")
g = by_id[st.session_state["review_pick"]]
locked = g.status in ("approved", "released")

head = st.container(border=True)
with head:
    a, b = st.columns([3, 2], vertical_alignment="center")
    with a:
        st.markdown(f"### {g.script_id} &nbsp; {g.total}/{g.max_total}")
        c.flag_badges(g.flags)
    with b:
        c.status_badge(g.status)
        bits = [g.model]
        if g.seconds:
            bits.append(f"{g.seconds:.1f}s · {g.model_calls} model calls")
        bits.append("calibrated with anchors" if g.calibrated else "rubric only")
        st.caption(" · ".join(bits))
    if g.backend not in (config.MODEL_BACKEND, "fake"):
        st.warning("Part of this script was graded by the local fallback model.", icon=":material/swap_horiz:")

img_col, txt_col = st.columns(2, gap="medium")
with img_col:
    with st.container(border=True):
        st.markdown("**Answer photo**")
        img = c.find_image(g.script_id)
        if img:
            st.image(str(img), width="stretch")
        else:
            st.caption("No photo saved for this script.")
with txt_col:
    with st.container(border=True):
        st.markdown("**What Gemma read** (highlighted = evidence used for marks)")
        if g.transcription:
            st.caption(f"Legibility: {g.transcription.legibility}"
                       + (f" · unclear: {', '.join(g.transcription.unclear_spans)}"
                          if g.transcription.unclear_spans else ""))
            st.markdown(theme.highlight(g.transcription.text, [i.evidence_quote for i in g.items])
                        .replace("\n", "<br>"), unsafe_allow_html=True)
        else:
            st.caption("No transcription (unreadable or failed). Mark it yourself below.")

st.markdown("#### Marks")
items = {i.item_id: i for i in g.items}
edits = {}
for r in rubric.items:
    it = items.get(r.item_id)
    with st.container(border=True):
        left, right = st.columns([3, 2], gap="medium")
        with left:
            st.markdown(f"**{r.item_id}** — {r.description}")
            if it and it.evidence_quote:
                st.markdown(f"Evidence: “{it.evidence_quote}” "
                            + (":green[found in answer]" if it.evidence_found else ":red[NOT found in answer]"))
            elif it:
                st.caption("No evidence quoted.")
            if it:
                st.caption(f"{it.reasoning} · confidence: **{it.confidence}**")
            else:
                st.caption("The model gave no mark for this item.")
        with right:
            current = it.final_marks if it else 0
            edits[r.item_id] = st.segmented_control(
                f"Marks (max {r.max_marks})", r.allowed_marks, default=current if current in r.allowed_marks
                else r.allowed_marks[0], required=True, disabled=locked,
                key=f"m-{g.script_id}-{r.item_id}")
            if it and edits[r.item_id] != it.marks_awarded:
                st.caption(f"Model suggested {it.marks_awarded}")

new_total = sum(edits.values())
foot = st.columns([3, 1, 1], vertical_alignment="center")
foot[0].markdown(f"**Total: {new_total}/{rubric.max_total}**"
                 + (f" &nbsp; (was {g.total})" if new_total != g.total else ""))
if locked:
    foot[2].button("Approved", icon=":material/lock:", disabled=True, width="stretch")
else:
    approve_next = foot[1].button("Approve & next", icon=":material/skip_next:", width="stretch",
                                  disabled=idx == len(ids) - 1)
    approve = foot[2].button("Approve", type="primary", icon=":material/check:", width="stretch")
    if approve or approve_next:
        try:
            pipeline.approve(g.script_id, edits)
            c.flash(f"{g.script_id} approved with {new_total}/{rubric.max_total}.")
            if approve_next:
                st.session_state["_next_pick"] = ids[idx + 1]
            st.rerun()
        except ValueError as e:
            st.error(str(e))
