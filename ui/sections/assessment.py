import streamlit as st

from copilot import assessments, audit, config, store
from copilot.schemas import AuditEntry
from ui import components as c


def new_assessment_form(key: str, first: bool = False) -> None:
    with st.form(key, border=not first):
        if first:
            st.markdown("#### Create your first assessment")
            st.caption("An assessment is one test or question set for one class. It keeps its own rubric, "
                       "anchor scripts, student list, answer sheets and marks.")
        a, b, d = st.columns([3, 2, 2])
        name = a.text_input("Assessment name", placeholder="e.g. Unit Test 2 — Newton's laws")
        cls = b.text_input("Class / section", placeholder="e.g. 9A")
        subject = d.text_input("Subject", placeholder="e.g. Physics")
        if st.form_submit_button("Create assessment", type="primary", icon=":material/add:"):
            try:
                slug = assessments.create(name, cls, subject)
                audit.log(AuditEntry(actor="teacher", action="edit", script_id="assessment",
                                     after=slug, reason=f"created '{name}'"))
                c.flash(f"Created “{name}”. Next: add your students and rubric.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def roster_editor() -> None:
    roster = store.load_roster()
    st.markdown(f"#### Students ({len(roster)})")
    st.caption("Add every student in the class. Answer sheets are matched to students by roll number "
               "(e.g. a file named R07.pdf belongs to roll number R07); you can also match them on the "
               "Grade page.")
    sheets = st.file_uploader("Add students from their answer sheets: files named “R07 Asha Rao.pdf” become "
                              "roll number R07, Asha Rao (the sheets are queued for grading too)",
                              type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True,
                              key=f"roster_sheets_{st.session_state.get('roster_up_n', 0)}")
    if sheets and st.button(f"Add {len(sheets)} sheet(s)", icon=":material/person_add:"):
        pairs, skipped = [], []
        for up in sheets:
            parsed = store.parse_sheet_filename(up.name)
            if not parsed:
                skipped.append(up.name)
                continue
            pairs.append(parsed)
            c.save_upload(up, c.scripts_dir(), parsed[0])
        added = store.add_students(pairs)
        st.session_state["roster_up_n"] = st.session_state.get("roster_up_n", 0) + 1
        st.session_state.pop("roster_editor", None)
        c.flash(f"{added} student(s) added, {len(pairs)} sheet(s) queued."
                + (f" Skipped (name not like “R07 Name”): {', '.join(skipped)}" if skipped else ""))
        st.rerun()
    up = st.file_uploader("Or import a class list (CSV with roll number and name columns)", type=["csv"],
                          key=f"roster_csv_{st.session_state.get('roster_up_n', 0)}")
    if up is not None and st.button("Import students", icon=":material/upload:"):
        try:
            rows = store.parse_roster_csv(up.getvalue())
            known = {r["roll_no"] for r in roster}
            merged = roster + [r for r in rows if r["roll_no"] not in known]
            store.save_roster(merged)
            st.session_state["roster_up_n"] = st.session_state.get("roster_up_n", 0) + 1
            c.flash(f"Imported {len(merged) - len(roster)} new student(s).")
            st.session_state.pop("roster_editor", None)
            st.rerun()
        except ValueError as e:
            st.error(str(e))
    edited = st.data_editor(
        roster or [{"roll_no": "", "name": ""}], num_rows="dynamic", hide_index=True, width="stretch",
        key="roster_editor",
        column_config={"roll_no": st.column_config.TextColumn("Roll number", required=True, width="small"),
                       "name": st.column_config.TextColumn("Student name", width="large")})
    if st.button("Save students", type="primary", icon=":material/save:"):
        rows = [{"roll_no": c.script_id_from_name(str(r.get("roll_no") or "").strip()),
                 "name": str(r.get("name") or "").strip()}
                for r in edited if str(r.get("roll_no") or "").strip()]
        ids = [r["roll_no"] for r in rows]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            st.error("Roll numbers must be unique: " + ", ".join(dupes))
        else:
            store.save_roster(rows)
            audit.log(AuditEntry(actor="teacher", action="edit", script_id="roster",
                                 after=f"{len(rows)} students", reason="class list saved"))
            c.flash(f"Saved {len(rows)} student(s).")
            st.rerun()


def render() -> None:
    if config.sample_mode():
        st.info("You are in the **sample class**. Switch off *Sample class* in the sidebar to set up "
                "your own assessments.", icon=":material/school:")
        roster_editor()
        return
    slug = config.active_assessment()
    if not slug:
        new_assessment_form("first_assessment", first=True)
        return
    meta = assessments.get(slug) or {"name": slug}
    with st.container(border=True):
        with st.form("assessment_meta", border=False):
            a, b, d = st.columns([3, 2, 2])
            name = a.text_input("Assessment name", meta.get("name", ""))
            cls = b.text_input("Class / section", meta.get("class_name", ""))
            subject = d.text_input("Subject", meta.get("subject", ""))
            if st.form_submit_button("Save details", icon=":material/save:"):
                assessments.update(slug, name=name, class_name=cls, subject=subject)
                c.flash("Details saved.")
                st.rerun()
    with st.container(border=True):
        roster_editor()
    with st.expander("Start another assessment", icon=":material/add:"):
        new_assessment_form("another_assessment")
    with st.expander("Delete this assessment", icon=":material/delete:"):
        st.warning("This permanently deletes its rubric, students, answer sheets, marks and audit log.")
        sure = st.checkbox(f"Yes, delete “{meta.get('name', slug)}”")
        if st.button("Delete assessment", disabled=not sure, icon=":material/delete_forever:"):
            assessments.delete(slug)
            c.flash("Assessment deleted.", "info")
            st.rerun()
