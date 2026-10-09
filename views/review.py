import streamlit as st

from copilot import pipeline, store
from ui import components as c
from ui import theme
from ui.sections import export

theme.page_header("Review", "Check the evidence, adjust any mark, approve. Only approved sheets are released.")
c.show_flash()

rubric = store.load_rubric()
grades = store.load_grades()
if not grades:
    st.info("Nothing to review yet.", icon=":material/inbox:")
    st.page_link("views/grade.py", label="Grade answer sheets", icon=":material/arrow_forward:")
    st.stop()

FILTERS = {"Needs review": ["needs_review"], "Auto-OK": ["auto_ok"],
           "Approved": ["approved", "released"], "All": None}
counts = {k: sum(1 for g in grades if v is None or g.status in v) for k, v in FILTERS.items()}

top_l, top_r = st.columns([4, 1], vertical_alignment="bottom")
choice = top_l.segmented_control("Show", list(FILTERS), required=True, label_visibility="collapsed",
                                 default="Needs review" if counts["Needs review"] else "All",
                                 format_func=lambda k: f"{k} · {counts[k]}", key="review_filter")
with top_r.popover("Export", icon=":material/download:", width="stretch"):
    export.render()

shown = sorted([g for g in grades if FILTERS[choice] is None or g.status in FILTERS[choice]],
               key=lambda g: g.script_id)
if not shown:
    st.success("All caught up. Nothing in this list.", icon=":material/task_alt:")
    st.stop()

ids = [g.script_id for g in shown]
if "_next_pick" in st.session_state:  # set by buttons; applied before the selectbox exists
    st.session_state["review_pick"] = st.session_state.pop("_next_pick")
if st.session_state.get("review_pick") not in ids:
    st.session_state["review_pick"] = ids[0]
idx = ids.index(st.session_state["review_pick"])
by_id = {g.script_id: g for g in shown}

n1, n2, n3 = st.columns([1, 5, 1], vertical_alignment="bottom")
if n1.button("", icon=":material/chevron_left:", disabled=idx == 0, width="stretch", help="Previous"):
    st.session_state["review_pick"] = ids[idx - 1]
    st.rerun()
n2.selectbox("Sheet", ids, key="review_pick", label_visibility="collapsed",
             format_func=lambda s: f"{s}  ·  {by_id[s].total}/{by_id[s].max_total}  ·  "
                                   f"{c.STATUS_LABEL[by_id[s].status]}  ({ids.index(s) + 1} of {len(ids)})")
if n3.button("", icon=":material/chevron_right:", disabled=idx == len(ids) - 1, width="stretch", help="Next"):
    st.session_state["review_pick"] = ids[idx + 1]
    st.rerun()

g = by_id[st.session_state["review_pick"]]
locked = g.status in ("approved", "released")
items = {i.item_id: i for i in g.items}

photo_col, work_col = st.columns([2, 3], gap="large")

with photo_col:
    img = c.find_image(g.script_id)
    if img:
        st.image(c.preview(img), width="stretch")
    else:
        st.caption("No answer sheet file saved.")

with work_col:
    h1, h2 = st.columns([1, 1], vertical_alignment="center")
    h1.markdown(f"## {g.script_id} &nbsp;·&nbsp; {g.total}/{g.max_total}")
    with h2:
        c.status_badge(g.status)
    if g.flags:
        c.flag_badges(g.flags)
    if "FALLBACK_USED" in g.flags:
        st.caption(f"The main model was overloaded; graded with {g.model}.")

    with st.container(border=True):
        st.caption("WHAT GEMMA 4 READ  ·  highlighted = evidence used for marks")
        if g.transcription and g.transcription.text and g.transcription.legibility != "unreadable":
            st.markdown(theme.highlight(g.transcription.text, [i.evidence_quote for i in g.items])
                        .replace("\n", "<br>"), unsafe_allow_html=True)
            if g.transcription.unclear_spans:
                st.caption("Could not read with certainty: " + ", ".join(g.transcription.unclear_spans))
        else:
            st.markdown("_Nothing could be read from this sheet. Please mark it yourself._")

    edits = {}
    for r in rubric.items:
        it = items.get(r.item_id)
        with st.container(border=True):
            q, m = st.columns([3, 2], vertical_alignment="center")
            with q:
                st.markdown(f"**{r.item_id}** · {r.description}")
                if it and it.evidence_quote:
                    mark = ":green[:material/check:]" if it.evidence_found else ":red[:material/close: not in answer]"
                    st.caption(f"“{it.evidence_quote}” {mark}")
                if it:
                    st.caption(f"{it.reasoning} · {it.confidence} confidence")
            with m:
                current = it.final_marks if it else 0
                edits[r.item_id] = st.segmented_control(
                    "Marks", r.allowed_marks, required=True, disabled=locked, label_visibility="collapsed",
                    default=current if current in r.allowed_marks else r.allowed_marks[0],
                    key=f"m-{g.script_id}-{r.item_id}")
                if it and edits[r.item_id] != it.marks_awarded:
                    st.caption(f"Gemma suggested {it.marks_awarded}")

    new_total = sum(edits.values())
    f1, f2 = st.columns([2, 3], vertical_alignment="center")
    f1.markdown(f"### Total {new_total}/{rubric.max_total}"
                + (f" <span style='font-size:.9rem;color:#7E7E7E'>(was {g.total})</span>"
                   if new_total != g.total else ""), unsafe_allow_html=True)
    if locked:
        f2.button("Approved", icon=":material/lock:", disabled=True, width="stretch")
    else:
        with f2:
            b1, b2 = st.columns(2)
            approve = b1.button("Approve", type="primary", icon=":material/check:", width="stretch")
            approve_next = b2.button("Approve & next", icon=":material/skip_next:", width="stretch",
                                     disabled=idx == len(ids) - 1)
        if approve or approve_next:
            try:
                pipeline.approve(g.script_id, edits)
                c.flash(f"{g.script_id} approved: {new_total}/{rubric.max_total}.")
                if approve_next:
                    st.session_state["_next_pick"] = ids[idx + 1]
                st.rerun()
            except ValueError as e:
                st.error(str(e))
