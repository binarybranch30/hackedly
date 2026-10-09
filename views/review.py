import streamlit as st

from copilot import pipeline, store
from ui import components as c
from ui import theme
from ui.sections import export

theme.page_header("Review", "Check the evidence, adjust any mark, approve. Only approved sheets are released.",
                  eyebrow=c.workspace_label())
c.show_flash()

rubric = store.load_rubric()
grades = store.load_grades()
if not grades:
    st.info("Nothing to review yet.", icon=":material/inbox:")
    st.page_link("views/grade.py", label="Grade answer sheets", icon=":material/arrow_forward:")
    st.stop()

FILTERS = {"Needs review": ["needs_review"], "Auto-OK": ["auto_ok"],
           "Approved": ["approved", "released"], "Rescan": ["rescan"], "All": None}
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
             format_func=lambda s: f"{c.student_label(s)}  ·  {by_id[s].total}/{by_id[s].max_total}  ·  "
                                   f"{c.STATUS_LABEL[by_id[s].status]}  ({ids.index(s) + 1} of {len(ids)})")
if n3.button("", icon=":material/chevron_right:", disabled=idx == len(ids) - 1, width="stretch", help="Next"):
    st.session_state["review_pick"] = ids[idx + 1]
    st.rerun()

g = by_id[st.session_state["review_pick"]]
locked = g.status in ("approved", "released", "rescan")
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
    if store.student_names().get(g.script_id):
        h1.caption(store.student_names()[g.script_id])
    with h2:
        c.status_badge(g.status)
    if g.flags:
        c.flag_badges(g.flags)
    if "FALLBACK_USED" in g.flags:
        st.caption(f"The main model was overloaded; graded with {g.model}.")

    if g.status == "rescan":
        with st.container(border=True):
            st.markdown(f":red[:material/visibility_off:] **You marked this sheet as not markable**  \n"
                        f"{g.teacher_note}. It is on the rescan list and will not be released. "
                        "Upload a new scan with the same name on the Grade page to grade it again.")
            if st.button("Undo", icon=":material/undo:"):
                pipeline.undo_unreadable(g.script_id)
                c.flash(f"{g.script_id} is back in review.", "info")
                st.rerun()
    elif g.status != "released":
        with st.popover("Can't mark this sheet", icon=":material/visibility_off:"):
            st.markdown("**Why can't it be marked?**")
            reason = st.radio("Reason", pipeline.RESCAN_REASONS + ["Other"], label_visibility="collapsed",
                              key=f"why-{g.script_id}")
            note = st.text_input("Note (optional)", key=f"note-{g.script_id}",
                                 placeholder="e.g. bottom half of page 2 is missing")
            st.caption("The sheet goes to the rescan list and is kept out of the released marks.")
            if st.button("Send to rescan list", type="primary", icon=":material/visibility_off:",
                         width="stretch", key=f"rescan-{g.script_id}"):
                text = note.strip() if reason == "Other" else reason + (f" — {note.strip()}" if note.strip() else "")
                pipeline.mark_unreadable(g.script_id, text)
                c.flash(f"{g.script_id} moved to the rescan list.", "warning")
                st.rerun()

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

    if g.status in ("approved", "released"):
        with st.container(border=True):
            fb_l, fb_r = st.columns([3, 2], vertical_alignment="center")
            fb_l.markdown("**Feedback for the student**")
            status_txt = {"none": "not written yet", "draft": "Gemma 4 draft, waiting for you",
                          "approved": "approved by you"}[g.feedback_status]
            fb_l.caption(status_txt)
            if fb_r.button("Redraft" if g.feedback else "Draft with Gemma 4", icon=":material/auto_awesome:",
                           key=f"fbd-{g.script_id}", width="stretch"):
                try:
                    with st.spinner("Writing feedback…"):
                        _, missing = pipeline.draft_feedback(g.script_id, rubric)
                    st.session_state[f"fbmiss-{g.script_id}"] = missing
                    st.session_state.pop(f"fbt-{g.script_id}", None)
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(str(e))
            if g.feedback:
                missing = st.session_state.get(f"fbmiss-{g.script_id}", [])
                if missing:
                    st.warning("Gemma quoted words that are not in the answer: " + "; ".join(f"“{m}”" for m in missing)
                               + ". Fix them before approving.", icon=":material/error:")
                text = st.text_area("Feedback", g.feedback, key=f"fbt-{g.script_id}", height=110,
                                    label_visibility="collapsed")
                if st.button("Approve feedback" if g.feedback_status != "approved" or text != g.feedback
                             else "Feedback approved", type="primary", icon=":material/check:",
                             disabled=g.feedback_status == "approved" and text == g.feedback,
                             key=f"fba-{g.script_id}"):
                    pipeline.approve_feedback(g.script_id, text)
                    c.flash(f"Feedback for {g.script_id} approved.")
                    st.rerun()

    new_total = sum(edits.values())
    f1, f2 = st.columns([2, 3], vertical_alignment="center")
    f1.markdown(f"### Total {new_total}/{rubric.max_total}"
                + (f" <span style='font-size:.9rem;color:#7E7E7E'>(was {g.total})</span>"
                   if new_total != g.total else ""), unsafe_allow_html=True)
    if g.status == "rescan":
        f2.button("Needs rescan", icon=":material/visibility_off:", disabled=True, width="stretch")
    elif locked:
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
