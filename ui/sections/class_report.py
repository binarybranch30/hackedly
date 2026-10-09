"""Class insights card: Gemma 4's reading of the whole class + per-item class averages."""
import html
from datetime import datetime

import altair as alt
import streamlit as st

from copilot import pipeline, store
from ui import components as c
from ui import theme

# Single-series bar colour per mode (validated: lightness band, chroma floor, 3:1 vs card surface).
BAR = {"light": "#0B8268", "dark": "#28A889"}


def averages_chart(report, rubric) -> alt.Chart:
    pal = theme.palette()
    desc = {i.item_id: i.description for i in rubric.items}
    rows = [{"item": f"{i}  {desc.get(i, '')[:38]}", "item_id": i, "description": desc.get(i, ""),
             "pct": round(100 * avg / max(report.max_marks.get(i, 1), 1)),
             "label": f"{avg:g} / {report.max_marks.get(i, 0)}"} for i, avg in report.averages.items()]
    base = alt.Chart(alt.Data(values=rows)).encode(
        y=alt.Y("item:N", sort=None, title=None,
                axis=alt.Axis(labelColor=pal["text"], labelFontSize=12, labelLimit=260, ticks=False, domain=False)))
    bars = base.mark_bar(color=BAR["dark" if theme.is_dark() else "light"], cornerRadiusEnd=4, height=16).encode(
        x=alt.X("pct:Q", scale=alt.Scale(domain=[0, 100]), title="Class average, % of the item's marks",
                axis=alt.Axis(labelColor=pal["muted"], titleColor=pal["muted"], gridColor=pal["border"],
                              domain=False, ticks=False, values=[0, 25, 50, 75, 100])),
        tooltip=[alt.Tooltip("item_id:N", title="Item"), alt.Tooltip("description:N", title="What earns marks"),
                 alt.Tooltip("label:N", title="Class average"), alt.Tooltip("pct:Q", title="% of marks")])
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=pal["muted"]).encode(
        x="pct:Q", text="label:N")
    return (bars + labels).properties(height=max(120, 36 * len(rows))).configure_view(stroke=None) \
        .configure(background="transparent")


def render(compact: bool = False) -> None:
    rubric = store.load_rubric()
    report = store.load_class_report()
    graded = [g for g in store.load_grades() if g.items and g.transcription and g.status != "rescan"]

    head_l, head_r = st.columns([3, 1], vertical_alignment="center")
    with head_l:
        st.markdown("#### Class insights")
        if report:
            when = datetime.fromisoformat(report.created).strftime("%d %b, %H:%M UTC")
            st.caption(f"Gemma 4 read {report.n_sheets} answer sheets · {report.model} · {when}. "
                       "Averages are calculated by code; the observations are Gemma 4's.")
        else:
            st.caption("After grading, Gemma 4 reads every answer and tells you what the class struggled with.")
    with head_r:
        label = "Refresh insights" if report else "Write class insights"
        if st.button(label, type="secondary" if report else "primary", icon=":material/auto_awesome:",
                     width="stretch", disabled=len(graded) < 2, key=f"insights_btn_{compact}"):
            try:
                with st.spinner(f"Gemma 4 is reading {len(graded)} answers…"):
                    pipeline.class_report(rubric)
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not write the insights: {e}")
    if len(graded) < 2:
        st.info("Grade at least 2 readable sheets to get class insights.", icon=":material/insights:")
        return
    if not report:
        return
    new = len({g.script_id for g in graded} - set(report.sheet_ids))
    if new:
        st.caption(f":orange[:material/update:] {new} sheet(s) graded since this report. Refresh to include them.")

    chart_col, text_col = st.columns([3, 2], gap="large")
    with chart_col:
        st.altair_chart(averages_chart(report, rubric), width="stretch")
        with st.expander("Show as a table", icon=":material/table:"):
            st.dataframe([{"Item": i, "Class average": a, "Max": report.max_marks.get(i, 0),
                           "%": round(100 * a / max(report.max_marks.get(i, 1), 1))}
                          for i, a in report.averages.items()], hide_index=True, width="stretch")
    with text_col:
        ins = report.insights
        st.markdown("<div class='ag-eyebrow'>Struggled most with</div>"
                    f"<div style='font-family:var(--ag-head);font-size:1.35rem;font-weight:700;"
                    f"line-height:1.25;margin-bottom:.9rem'>{html.escape(ins.struggled_concept)}</div>",
                    unsafe_allow_html=True)
        st.markdown("**Re-teach next lesson**")
        for n, t in enumerate(ins.reteach_topics, 1):
            st.markdown(f"<div style='display:flex;gap:.6rem;align-items:baseline;margin:.3rem 0'>"
                        f"<span style='font-family:var(--ag-head);font-weight:800;color:var(--ag-primary)'>{n}</span>"
                        f"<span>{html.escape(t)}</span></div>", unsafe_allow_html=True)
        st.caption(ins.summary)
    if not compact:
        st.markdown("**Most common mistake per item**")
        desc = {i.item_id: i.description for i in rubric.items}
        for it in ins.items:
            avg, mx = report.averages.get(it.item_id, 0), report.max_marks.get(it.item_id, 0)
            with st.container(border=True):
                a, b = st.columns([1, 4], vertical_alignment="center")
                a.markdown(f"**{it.item_id}** · {avg:g}/{mx}")
                b.markdown(f"{html.escape(it.common_mistake) or '_Most students got this right._'}  \n"
                           f"<span style='color:var(--ag-muted);font-size:.82rem'>{html.escape(desc.get(it.item_id, ''))}"
                           "</span>", unsafe_allow_html=True)
