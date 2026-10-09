import tempfile
from pathlib import Path

import streamlit as st

from copilot import config, pipeline, store


def render() -> None:
    """Compact export panel (used inside a popover on the Review page)."""
    grades = store.load_grades()
    approved = [g for g in grades if g.status in ("approved", "released")]
    pending = sum(g.status not in ("approved", "released", "rescan") for g in grades)
    st.markdown(f"**Final marks** · {len(approved)} approved"
                + (f" · {pending} not yet approved (left out)" if pending else ""))
    if st.button("Release approved marks", type="primary", icon=":material/table:", disabled=not approved,
                 width="stretch"):
        out = Path(tempfile.mkdtemp()) / "marks.csv"
        pipeline.export_csv(out)
        st.session_state["export_csv"] = out.read_bytes()
    if "export_csv" in st.session_state:
        st.download_button("Download marks.csv", st.session_state["export_csv"], "marks.csv", "text/csv",
                           icon=":material/download:", width="stretch")
    no_fb = [g for g in approved if g.feedback_status == "none" and g.transcription and g.transcription.text]
    if no_fb and st.button(f"Draft feedback for {len(no_fb)} approved sheet(s)", icon=":material/auto_awesome:",
                           width="stretch"):
        rubric = store.load_rubric()
        bar = st.progress(0.0)
        for n, g in enumerate(no_fb, 1):
            try:
                pipeline.draft_feedback(g.script_id, rubric)
            except Exception as e:  # noqa: BLE001
                st.caption(f"{g.script_id}: {e}")
            bar.progress(n / len(no_fb))
        st.rerun()
    drafts = sum(g.feedback_status == "draft" for g in grades)
    if drafts:
        st.caption(f"{drafts} feedback draft(s) waiting for your approval in Review. "
                   "Only approved feedback is exported.")
    flagged = [g for g in grades if g.flags]
    if flagged:
        rows = "script_id,total,max_total,status,flags\n" + "".join(
            f"{g.script_id},{g.total},{g.max_total},{g.status},{';'.join(g.flags)}\n" for g in flagged)
        st.download_button(f"Flagged sheets list ({len(flagged)})", rows, "flagged.csv", "text/csv",
                           icon=":material/flag:", width="stretch")
    rescan = [g for g in grades if g.status == "rescan"]
    if rescan:
        rows = "script_id,reason\n" + "".join(f"{g.script_id},\"{g.teacher_note}\"\n" for g in rescan)
        st.download_button(f"Sheets to rescan ({len(rescan)})", rows, "rescan.csv", "text/csv",
                           icon=":material/visibility_off:", width="stretch")
    if config.audit_path().exists():
        st.download_button("Audit log", config.audit_path().read_bytes(), "audit.jsonl", "application/json",
                           icon=":material/history:", width="stretch")
