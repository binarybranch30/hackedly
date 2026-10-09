import statistics

import streamlit as st

from copilot import config, store
from ui import components as c
from ui import theme

theme.page_header("Dashboard", "Your grading at a glance. Nothing is released until you approve it.")
c.show_flash()

grades = store.load_grades()
status = c.setup_status()
rubric = store.load_rubric()

need = [g for g in grades if g.status == "needs_review"]
done = [g for g in grades if g.status in ("approved", "released")]
timed = [g.seconds for g in grades if g.seconds]

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    theme.stat_card("Scripts graded", len(grades), "description", "primary")
with c2:
    theme.stat_card("Need review", len(need), "flag", "warning")
with c3:
    theme.stat_card("Approved", len(done), "check_circle", "success")
with c4:
    avg = f"{statistics.mean(g.total for g in grades):.1f}/{rubric.max_total}" if grades else "—"
    theme.stat_card("Average score", avg, "star", "info")
with c5:
    theme.stat_card("Sec / script", f"{statistics.mean(timed):.1f}" if timed else "—", "timer", "muted")

left, right = st.columns([3, 2], gap="medium")

with left:
    with st.container(border=True):
        st.markdown("#### Grading queue")
        if grades:
            order = {"needs_review": 0, "auto_ok": 1, "approved": 2, "released": 3}
            rows = c.grade_rows(sorted(grades, key=lambda g: (order.get(g.status, 9), g.script_id)))
            st.dataframe(rows, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(rows)))
            if need:
                st.page_link("views/review.py", label=f"Review {len(need)} flagged script(s)",
                             icon=":material/arrow_forward:")
        else:
            st.info("No scripts graded yet.", icon=":material/inbox:")
            st.page_link("views/grade.py", label="Grade your first scripts", icon=":material/upload_file:")

with right:
    with st.container(border=True):
        st.markdown("#### Setup checklist")
        steps = [
            (status["rubric_saved"], "Rubric saved", "views/rubric.py",
             "using the example" if not status["rubric_saved"] else rubric.rubric_id),
            (status["n_anchors"] >= 3, "3 anchor scripts graded by you", "views/anchors.py",
             f"{status['n_anchors']}/3 saved"),
            (config.MODEL_BACKEND != "fake", "Real model connected", None,
             f"backend: {config.MODEL_BACKEND}"),
        ]
        for ok, label, link, detail in steps:
            icon = ":material/check_circle:" if ok else ":material/radio_button_unchecked:"
            if link:
                st.page_link(link, label=f"{label} — {detail}", icon=icon)
            else:
                st.markdown(f"{icon} {label} — {detail}")

    with st.container(border=True):
        st.markdown("#### Drift checks")
        st.caption("Every 5 scripts an anchor is re-graded and compared with your marks.")
        entries = c.drift_entries()
        if not entries:
            st.caption("No drift checks yet.")
        for e in entries:
            drift = e.reason == "DRIFT WARNING"
            st.markdown(f"{':material/warning:' if drift else ':material/check:'} **{e.script_id}** — "
                        f"you gave {e.before}, system gave {e.after or 'n/a'} · {e.ts[11:16]} UTC")
