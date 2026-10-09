"""Streamlit UI for AnchorGrade.

Run: streamlit run app.py --server.port 8502 --server.headless true
"""
import html
import re
import tempfile
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from copilot import audit, config, pipeline, store
from copilot.schemas import AnchorGrade, Rubric, RubricItem, Script


def saved_image(script_id: str, folder: str) -> Path | None:
    """Return the first persistent uploaded image for a script, if present."""
    for suffix in (".jpg", ".jpeg", ".png"):
        candidate = config.DATA_DIR / folder / f"{script_id}{suffix}"
        if candidate.exists():
            return candidate
    return None


def highlighted_transcription(text: str, quotes: list[str]) -> str:
    """Escape text and highlight every exact non-empty evidence quote."""
    pattern = "|".join(re.escape(q) for q in sorted(set(quotes), key=len, reverse=True) if q)
    if not pattern:
        return html.escape(text).replace("\n", "<br>")
    pieces, position = [], 0
    for match in re.finditer(pattern, text):
        pieces.append(html.escape(text[position:match.start()]))
        pieces.append(f"<mark>{html.escape(match.group(0))}</mark>")
        position = match.end()
    pieces.append(html.escape(text[position:]))
    return "".join(pieces).replace("\n", "<br>")


def save_upload(upload, directory: Path, script_id: str) -> Path:
    """Persist a teacher upload under its stable script id for later review."""
    suffix = Path(upload.name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        suffix = ".jpg"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{script_id}{suffix}"
    path.write_bytes(upload.getvalue())
    return path


st.set_page_config(page_title="AnchorGrade", layout="wide")
st.title("AnchorGrade — handwritten answer grading copilot")
st.caption(f"Backend: **{config.MODEL_BACKEND}** · Nothing is released until the teacher approves.")

rubric = store.load_rubric()
tab_rubric, tab_anchors, tab_grade, tab_review, tab_export, tab_audit = st.tabs(
    ["Rubric", "Anchors", "Grade", "Review", "Export", "Audit log"])

with tab_rubric:
    st.subheader("Rubric")
    with st.form("rubric_form"):
        rubric_id = st.text_input("Rubric ID", value=rubric.rubric_id)
        question = st.text_area("Question", value=rubric.question)
        st.caption("Allowed marks are comma-separated integers, for example `0,1,2`.")
        rows = []
        for index, item in enumerate(rubric.items):
            cols = st.columns([1, 3, 1, 2, 3])
            rows.append({
                "item_id": cols[0].text_input("Item ID", item.item_id, key=f"rubric-id-{index}"),
                "description": cols[1].text_input("Description", item.description, key=f"rubric-description-{index}"),
                "max_marks": cols[2].number_input("Max", min_value=0, value=item.max_marks, step=1, key=f"rubric-max-{index}"),
                "allowed": cols[3].text_input("Allowed", ",".join(map(str, item.allowed_marks)), key=f"rubric-allowed-{index}"),
                "guidance": cols[4].text_input("Guidance", item.guidance, key=f"rubric-guidance-{index}"),
            })
        save_rubric = st.form_submit_button("Save rubric")
    if save_rubric:
        try:
            items = []
            for row in rows:
                allowed = [int(value.strip()) for value in row["allowed"].split(",") if value.strip()]
                if not row["item_id"].strip() or not row["description"].strip() or not allowed:
                    raise ValueError("Every rubric row needs an item ID, description, and allowed marks.")
                if any(mark < 0 or mark > row["max_marks"] for mark in allowed):
                    raise ValueError(f"Allowed marks for {row['item_id']} must be between 0 and its maximum.")
                items.append(RubricItem(item_id=row["item_id"].strip(), description=row["description"].strip(),
                                        max_marks=row["max_marks"], allowed_marks=allowed,
                                        guidance=row["guidance"].strip()))
            if len({item.item_id for item in items}) != len(items):
                raise ValueError("Rubric item IDs must be unique.")
            store.save_rubric(Rubric(rubric_id=rubric_id.strip(), question=question.strip(), items=items))
            st.success("Rubric saved.")
            st.rerun()
        except (ValueError, ValidationError) as exc:
            st.error(f"Could not save rubric: {exc}")

with tab_anchors:
    st.subheader("Three teacher-graded anchors")
    existing_anchors = {anchor.script_id: anchor for anchor in store.load_anchors()}
    with st.form("anchors_form"):
        anchor_values = []
        for number in range(1, 4):
            default_id = f"S{number:02d}"
            existing = existing_anchors.get(default_id)
            st.markdown(f"#### Anchor {number}")
            script_id = st.text_input("Script ID", default_id, key=f"anchor-script-{number}")
            upload = st.file_uploader("Answer image", type=["jpg", "jpeg", "png"], key=f"anchor-upload-{number}")
            transcription = st.text_area("Transcription", existing.transcription if existing else "", key=f"anchor-text-{number}")
            marks, notes = {}, {}
            for item in rubric.items:
                cols = st.columns([1, 3])
                marks[item.item_id] = cols[0].number_input(
                    f"{item.item_id} marks", min_value=min(item.allowed_marks), max_value=max(item.allowed_marks),
                    value=(existing.marks.get(item.item_id, min(item.allowed_marks)) if existing else min(item.allowed_marks)),
                    step=1, key=f"anchor-mark-{number}-{item.item_id}")
                notes[item.item_id] = cols[1].text_input(
                    f"{item.item_id} note", existing.notes.get(item.item_id, "") if existing else "",
                    key=f"anchor-note-{number}-{item.item_id}")
            anchor_values.append((script_id, upload, transcription, marks, notes))
        save_anchors = st.form_submit_button("Save 3 anchors")
    if save_anchors:
        try:
            anchors, ids = [], []
            for script_id, upload, transcription, marks, notes in anchor_values:
                script_id = script_id.strip()
                ids.append(script_id)
                if not script_id or not transcription.strip():
                    raise ValueError("Every anchor needs a script ID and transcription.")
                for item in rubric.items:
                    if marks[item.item_id] not in item.allowed_marks:
                        raise ValueError(f"{script_id}: {item.item_id} must use one of {item.allowed_marks}.")
                if upload:
                    save_upload(upload, config.DATA_DIR / "anchors", script_id)
                anchors.append(AnchorGrade(script_id=script_id, transcription=transcription.strip(), marks=marks, notes=notes))
            if len(set(ids)) != 3:
                raise ValueError("The three anchor script IDs must be unique.")
            store.save_anchors(anchors)
            st.success("Three anchors saved.")
            st.rerun()
        except (ValueError, ValidationError) as exc:
            st.error(f"Could not save anchors: {exc}")
    if existing_anchors:
        st.caption("Saved anchors")
        st.dataframe([{"script_id": a.script_id, "marks": a.marks, "transcription": a.transcription} for a in existing_anchors.values()])

with tab_grade:
    uploads = st.file_uploader("Answer images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    if uploads and st.button("Grade all"):
        progress = st.progress(0, text="Starting grading…")
        grades = []
        for index, upload in enumerate(uploads, start=1):
            script_id = Path(upload.name).stem
            image_path = save_upload(upload, config.DATA_DIR / "scripts", script_id)
            grades.append(pipeline.grade_script(Script(script_id=script_id, image_path=str(image_path)), rubric,
                                                store.load_anchors()))
            progress.progress(index / len(uploads), text=f"Graded {index}/{len(uploads)}")
        needs_review = sum(grade.status == "needs_review" for grade in grades)
        st.success(f"{len(grades)} graded · {needs_review} need review · {len(grades) - needs_review} auto-ok")
        for grade in grades:
            st.write(f"{grade.script_id}: {grade.total}/{grade.max_total} · {grade.status}")

with tab_review:
    grades = sorted(store.load_grades(), key=lambda grade: (grade.status != "needs_review", grade.script_id))
    if not grades:
        st.info("No graded scripts yet.")
    for grade in grades:
        icon = "⚠️" if grade.status == "needs_review" else "🔒" if grade.status in ("approved", "released") else "✅"
        with st.expander(f"{icon} {grade.script_id} — {grade.total}/{grade.max_total} — {grade.status}", expanded=grade.status == "needs_review"):
            if grade.backend != config.MODEL_BACKEND:
                st.warning("Graded by local fallback model")
            if grade.flags:
                badges = " ".join(f"<span style='background:#f8d7da;color:#842029;padding:3px 7px;border-radius:10px;margin-right:4px'>{html.escape(flag)}</span>" for flag in grade.flags)
                st.markdown(badges, unsafe_allow_html=True)
            image_col, text_col = st.columns(2)
            with image_col:
                image_path = saved_image(grade.script_id, "scripts")
                if image_path:
                    st.image(str(image_path), caption=grade.script_id, use_container_width=True)
                else:
                    st.caption("No saved image for this script.")
            with text_col:
                transcription = grade.transcription.text if grade.transcription else "No transcription available."
                st.markdown(highlighted_transcription(transcription, [item.evidence_quote for item in grade.items]), unsafe_allow_html=True)
            if grade.status in ("approved", "released"):
                st.info("🔒 Approved scripts are locked.")
                continue
            item_by_id = {item.item_id: item for item in rubric.items}
            edits = {}
            for item in grade.items:
                rubric_item = item_by_id.get(item.item_id)
                if not rubric_item:
                    continue
                cols = st.columns([1, 1, 4, 1, 1])
                cols[0].write(item.item_id)
                edits[item.item_id] = cols[1].number_input("Marks", min_value=min(rubric_item.allowed_marks), max_value=max(rubric_item.allowed_marks), value=item.final_marks, step=1, key=f"review-{grade.script_id}-{item.item_id}")
                cols[2].write(item.reasoning)
                cols[3].write(item.confidence)
                cols[4].write("✅" if item.evidence_found else "❌")
            invalid = [item_id for item_id, mark in edits.items() if mark not in item_by_id[item_id].allowed_marks]
            if invalid:
                st.error(f"Use an allowed mark for: {', '.join(invalid)}")
            if st.button("Approve", key=f"approve-{grade.script_id}", disabled=bool(invalid)):
                pipeline.approve(grade.script_id, edits=edits)
                st.rerun()

with tab_export:
    if st.button("Export approved scripts to CSV"):
        out = Path(tempfile.mkdtemp()) / "marks.csv"
        count = pipeline.export_csv(out)
        st.download_button(f"Download marks.csv ({count} scripts)", out.read_bytes(), "marks.csv")

with tab_audit:
    script_filter = st.text_input("Filter by script ID")
    entries = list(reversed(audit.read_all()))
    if script_filter:
        entries = [entry for entry in entries if entry.script_id == script_filter]
    st.dataframe([entry.model_dump() for entry in entries], use_container_width=True)
