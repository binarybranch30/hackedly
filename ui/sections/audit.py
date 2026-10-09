import streamlit as st

from copilot import audit
from ui import theme


def render() -> None:
    entries = list(reversed(audit.read_all()))
    if not entries:
        st.info("The audit log is empty.", icon=":material/history:")
        return

    c1, c2, c3 = st.columns([2, 2, 1])
    actions = sorted({e.action for e in entries})
    pick = c1.multiselect("Action", actions, placeholder="All actions")
    sid = c2.text_input("Script ID contains")
    actor = c3.segmented_control("Actor", ["system", "teacher"], selection_mode="multi")

    rows = [e for e in entries if (not pick or e.action in pick)
            and (not sid or sid.lower() in (e.script_id or "").lower())
            and (not actor or e.actor in actor)]
    st.caption(f"{len(rows)} of {len(entries)} events")
    st.dataframe([{"Time (UTC)": e.ts[:19].replace("T", " "), "Actor": e.actor, "Action": e.action,
                   "Script": e.script_id, "Item": e.item_id, "Before": e.before, "After": e.after,
                   "Reason": e.reason, "Model": e.model} for e in rows],
                 hide_index=True, width="stretch", height=560)
