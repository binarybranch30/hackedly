import csv
import json
from pathlib import Path

import streamlit as st

from ui import theme

theme.page_header("Evaluation", "How close is the system to the teacher, how consistent is it, and do its "
                  "flags catch the hard scripts? Measured, not claimed.")

RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results"


def read_csv(name: str) -> list[dict]:
    p = RESULTS / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


summary, consistency, flagging = read_csv("summary.csv"), read_csv("consistency.csv"), read_csv("flagging.csv")

st.info("**Small sample.** About 10 handwritten answers (7 held out), one teacher, answers written by our "
        "team. These numbers are indicative, not statistically significant.", icon=":material/info:")

if not summary:
    st.warning("No evaluation results yet. Run `python eval/run_eval.py` after the teacher marks are in "
               "`data/teacher_marks.csv`.", icon=":material/hourglass_empty:")
    st.stop()

raw = sorted((RESULTS / "raw").rglob("*.json"))
backends = {json.loads(p.read_text()).get("backend") for p in raw[:20]} if raw else set()
if "fake" in backends:
    st.error("These results came from the FAKE backend (made-up grades). Do not present them.",
             icon=":material/dangerous:")

by = {r["setting"]: r for r in summary}
cal, uncal = by.get("calibrated"), by.get("uncalibrated")
c1, c2, c3, c4 = st.columns(4)


def f(v, fmt="{:.2f}"):
    try:
        return fmt.format(float(v))
    except (TypeError, ValueError):
        return "—"


with c1:
    theme.stat_card("Avg gap, uncalibrated (marks)", f(uncal and uncal["mae_total"]), "straighten", "warning")
with c2:
    theme.stat_card("Avg gap, with anchors (marks)", f(cal and cal["mae_total"]), "anchor", "primary")
with c3:
    theme.stat_card("Avg spread over runs (marks)", f(cal and cal["mean_range"]), "repeat", "info")
with c4:
    theme.stat_card("Same total every run", f(cal and cal["percent_identical"], "{:.0f}%"), "check_circle", "success")

with st.container(border=True):
    st.markdown("#### 1 · Gap to teacher (mean absolute error) and consistency")
    st.dataframe(summary, hide_index=True, width="stretch")

left, right = st.columns(2, gap="medium")
with left:
    with st.container(border=True):
        st.markdown("#### 2 · Consistency per script")
        st.dataframe(consistency, hide_index=True, width="stretch")
with right:
    with st.container(border=True):
        st.markdown("#### 3 · Do flags catch the hard scripts?")
        if flagging:
            r = flagging[0]
            st.table({"": ["Flagged", "Not flagged"],
                      "Hard (error ≥ 1)": [r.get("flagged_hard"), r.get("unflagged_hard")],
                      "Not hard": [r.get("flagged_not_hard"), r.get("unflagged_not_hard")]})
            st.caption(f"Mean error flagged: {r.get('mean_error_flagged')} · unflagged: "
                       f"{r.get('mean_error_unflagged')} · agreement with teacher's 'hard' tags: "
                       f"{r.get('teacher_hard_agreement')}/{r.get('n')}")
st.caption(f"Raw outputs for every number: `eval/results/raw/` ({len(raw)} files).")
