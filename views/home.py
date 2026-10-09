import base64
import io
import statistics

import streamlit as st

from copilot import store
from ui import board
from ui import components as c
from ui import theme

c.show_flash()
rubric = store.load_rubric()
anchors = store.load_anchors()
grades = store.load_grades()
graded = {g.script_id for g in grades}
waiting = [p for p in c.scripts_dir().glob("*") if p.suffix.lower() in c.IMAGE_EXTS and p.stem not in graded]
need = [g for g in grades if g.status == "needs_review"]
done = [g for g in grades if g.status in ("approved", "released")]
rescan = [g for g in grades if g.status == "rescan"]
pal = theme.palette()


@st.cache_data(show_spinner=False, max_entries=32)
def thumb_b64(path: str, mtime: float) -> str:
    im = c.preview(c.Path(path)).copy()
    im.thumbnail((520, 700))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def hero_card() -> str:
    """The most interesting graded sheet (needs review first), shown like a report card."""
    # Prefer a sheet that has marks to show (an unreadable sheet has none), flagged ones first.
    pick = (next((g for g in need if g.items), None) or next((g for g in grades if g.items), None)
            or (need or grades or [None])[0])
    if pick is None:
        rows = [(f"{i.item_id}  {i.description}", f"– / {i.max_marks}", pal["faint"]) for i in rubric.items]
        return board.sheet_card("Your class", f"{len(waiting)} sheet(s) waiting to be graded",
                                ("Not graded yet", "#5B667A"), rows, f"– / {rubric.max_total}",
                                "Press Grade to mark them with Gemma 4.")
    marks = {i.item_id: i.final_marks for i in pick.items}
    rows = []
    for r in rubric.items:
        m = marks.get(r.item_id)
        tone = pal["faint"] if m is None else ("#0E7C66" if m == r.max_marks else
                                               "#B86E00" if m < r.max_marks / 2 else pal["text"])
        rows.append((f"{r.item_id}  {r.description}", f"{'–' if m is None else m} / {r.max_marks}", tone))
    pill = {"needs_review": ("Review pending", "#B86E00"), "auto_ok": ("Auto-OK", "#0E7C66"),
            "approved": ("Approved", "#0E7C66"), "released": ("Released", "#2F6FD0"),
            "rescan": ("Needs rescan", "#D6453D")}[pick.status]
    img = c.find_image(pick.script_id)
    b64 = thumb_b64(str(img), img.stat().st_mtime) if img else None
    pos = sorted(graded).index(pick.script_id) + 1
    return board.sheet_card(f"{pick.script_id} · {rubric.rubric_id}", f"Sheet {pos} of {len(graded)}", pill,
                            rows, f"{pick.total} / {pick.max_total}",
                            "Marked against your saved rubric by " + (pick.model or "Gemma 4")
                            + ". You can adjust any mark.", b64)


left, right = st.columns([6, 5], gap="large", vertical_alignment="center")
with left:
    st.markdown("<div class='ag-eyebrow'>Gemma 4 grading copilot</div>"
                "<div class='ag-title' style='font-size:2.75rem'>Handwritten answers in.<br>Graded marks out.</div>"
                "<div class='ag-subtitle' style='font-size:1.08rem;margin-top:1rem'>Upload scanned answer sheets. "
                "Gemma 4 reads them and marks each question against your rubric, quoting the evidence for every "
                "mark. Code checks the arithmetic, and nothing is released until you approve it.</div>",
                unsafe_allow_html=True)
    b1, b2, _ = st.columns([1.1, 1.3, 1])
    if b1.button("Grade sheets", type="primary", icon=":material/play_arrow:", width="stretch"):
        st.switch_page("views/grade.py")
    if b2.button("Review marks" + (f" ({len(need)})" if need else ""), icon=":material/fact_check:",
                 width="stretch"):
        st.switch_page("views/review.py")
with right:
    st.markdown(hero_card(), unsafe_allow_html=True)

st.write("")
st.markdown("### How grading works")
s1, s2, s3 = st.columns(3, gap="large")
steps = [
    (s1, "1", "Save the rubric", f"Marking criteria plus 3 answers you graded yourself, so Gemma 4 learns "
     f"your strictness. Now: {len(rubric.items)} items, {len(anchors)}/3 anchors.", "views/setup.py", "Set up"),
    (s2, "2", "Upload the scripts", f"Scans or photos, PDF or image. Each sheet is read, graded twice and "
     f"checked live. Now: {len(waiting)} waiting, {len(grades)} graded.", "views/grade.py", "Grade"),
    (s3, "3", "Review and release", f"Marks per question with evidence. Confirm or adjust, then release. "
     f"Now: {len(need)} need review, {len(done)} approved"
     + (f", {len(rescan)} to rescan." if rescan else "."), "views/review.py", "Review"),
]
for col, n, title, text, link, label in steps:
    with col:
        st.markdown(f"<div style='font-family:var(--ag-head);font-size:2.6rem;font-weight:800;"
                    f"color:var(--ag-primary);line-height:1'>{n}</div>", unsafe_allow_html=True)
        st.markdown(f"**{title}**")
        st.caption(text)
        st.page_link(link, label=label, icon=":material/arrow_forward:")

if grades:
    st.write("")
    a, b, d, e = st.columns(4)
    with a:
        theme.stat_card("Sheets graded", len(grades), "description", "primary")
    with b:
        theme.stat_card("Need review", len(need), "flag", "warning")
    with d:
        theme.stat_card("Approved", len(done), "check_circle", "success")
    with e:
        theme.stat_card("Class average", f"{statistics.mean(g.total for g in grades):.1f}/{rubric.max_total}",
                        "monitoring", "info")
