import tempfile
from pathlib import Path

import streamlit as st

from copilot import config, pipeline, store
from ui import components as c
from ui import theme

theme.page_header("Export", "Download final marks. Only scripts you approved are included.")

grades = store.load_grades()
approved = [g for g in grades if g.status in ("approved", "released")]
pending = [g for g in grades if g.status not in ("approved", "released")]

c1, c2 = st.columns(2)
with c1:
    theme.stat_card("Ready to export", len(approved), "check_circle", "success")
with c2:
    theme.stat_card("Not yet approved", len(pending), "pending", "warning")

with st.container(border=True):
    st.markdown("#### Final marks (CSV)")
    if pending:
        st.caption(f"{len(pending)} script(s) are not approved and will be left out: "
                   + ", ".join(g.script_id for g in pending[:12]) + ("…" if len(pending) > 12 else ""))
    if st.button("Prepare marks.csv", type="primary", icon=":material/table:", disabled=not approved):
        out = Path(tempfile.mkdtemp()) / "marks.csv"
        n = pipeline.export_csv(out)
        st.session_state["export_csv"] = out.read_bytes()
        st.success(f"{n} script(s) released and written to marks.csv.")
    if "export_csv" in st.session_state:
        st.download_button("Download marks.csv", st.session_state["export_csv"], "marks.csv", "text/csv",
                           icon=":material/download:")

with st.container(border=True):
    st.markdown("#### Flagged scripts list")
    flagged = [g for g in grades if g.flags]
    if flagged:
        rows = "script_id,total,max_total,status,flags\n" + "".join(
            f"{g.script_id},{g.total},{g.max_total},{g.status},{';'.join(g.flags)}\n" for g in flagged)
        st.dataframe(c.grade_rows(flagged), hide_index=True, width="stretch")
        st.download_button("Download flagged.csv", rows, "flagged.csv", "text/csv", icon=":material/flag:")
    else:
        st.caption("No flagged scripts.")

with st.container(border=True):
    st.markdown("#### Audit log")
    st.caption("Every grade, flag, retry, fallback, edit and approval, one JSON line each.")
    if config.audit_path().exists():
        st.download_button("Download audit.jsonl", config.audit_path().read_bytes(), "audit.jsonl",
                           "application/json", icon=":material/history:")
