"""Simple file storage: JSON files in the active workspace (data/, or data/sample/
in sample mode). Shared by UI and pipeline."""
import csv
import io
import json
import re
from pathlib import Path

from copilot import config
from copilot.schemas import AnchorGrade, ClassReport, Rubric, ScriptGrade


def rubric_path() -> Path:
    return config.workspace() / "rubric.json"


def anchors_path() -> Path:
    return config.workspace() / "anchors" / "anchors.json"


def grades_dir() -> Path:
    return config.workspace() / "grades"


def load_rubric() -> Rubric:
    """The workspace's rubric. A new assessment starts with an EMPTY rubric; only the
    default data/ workspace falls back to the example rubric."""
    if rubric_path().exists():
        return Rubric.model_validate_json(rubric_path().read_text(encoding="utf-8"))
    if config.workspace() == config.DATA_DIR:
        return Rubric.model_validate_json((config.DATA_DIR / "rubric.example.json").read_text(encoding="utf-8"))
    return Rubric(rubric_id=config.workspace().name, question="", items=[])


def save_rubric(rubric: Rubric) -> None:
    rubric_path().parent.mkdir(parents=True, exist_ok=True)
    rubric_path().write_text(rubric.model_dump_json(indent=2), encoding="utf-8")


def load_anchors() -> list[AnchorGrade]:
    if not anchors_path().exists():
        return []
    data = json.loads(anchors_path().read_text(encoding="utf-8"))
    return [AnchorGrade.model_validate(a) for a in data]


def save_anchors(anchors: list[AnchorGrade]) -> None:
    anchors_path().parent.mkdir(parents=True, exist_ok=True)
    anchors_path().write_text(json.dumps([a.model_dump() for a in anchors], indent=2),
                              encoding="utf-8")


def save_grade(grade: ScriptGrade) -> None:
    grades_dir().mkdir(parents=True, exist_ok=True)
    (grades_dir() / f"{grade.script_id}.json").write_text(grade.model_dump_json(indent=2),
                                                          encoding="utf-8")


def roster_path() -> Path:
    return config.workspace() / "roster.csv"


def load_roster() -> list[dict]:
    """Students in this class: [{"roll_no": "R01", "name": "Asha"}]. Empty if none."""
    if not roster_path().exists():
        return []
    with open(roster_path(), newline="", encoding="utf-8") as f:
        return [{"roll_no": r.get("roll_no", "").strip(), "name": r.get("name", "").strip()}
                for r in csv.DictReader(f) if r.get("roll_no", "").strip()]


def save_roster(rows: list[dict]) -> None:
    roster_path().parent.mkdir(parents=True, exist_ok=True)
    with open(roster_path(), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["roll_no", "name"])
        w.writeheader()
        for r in rows:
            w.writerow({"roll_no": r["roll_no"], "name": r.get("name", "")})


def parse_roster_csv(data: bytes) -> list[dict]:
    """Read an uploaded class list. Accepts headers like roll_no/roll/id and name/student."""
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    def key(c: str) -> str:  # "Roll No." / "roll_no" / "ROLL-NO" -> "rollno"
        return "".join(ch for ch in c.lower() if ch.isalnum())

    cols = {key(c): c for c in (reader.fieldnames or [])}
    roll = next((cols[k] for k in ("rollno", "roll", "rollnumber", "id", "studentid", "admissionno")
                 if k in cols), None)
    name = next((cols[k] for k in ("name", "student", "studentname", "fullname") if k in cols), None)
    if roll is None:
        raise ValueError("The CSV needs a roll number column (roll_no, roll, id or student_id).")
    return [{"roll_no": r[roll].strip(), "name": (r.get(name) or "").strip() if name else ""}
            for r in reader if (r.get(roll) or "").strip()]


_SHEET_NAME = re.compile(r"^\s*([A-Za-z]{0,3}\d+)(?:[\s_\-.]+(.*?))?\s*$")


def parse_sheet_filename(filename: str) -> tuple[str, str] | None:
    """'R07 Asha Rao.pdf' -> ('R07', 'Asha Rao'); 'R07.jpg' -> ('R07', '');
    anything else (e.g. 'IMG_2034.jpg' -> no: 'IMG' has no digits right after) -> None."""
    m = _SHEET_NAME.match(Path(filename).stem)
    if not m:
        return None
    roll = m.group(1).upper()
    name = " ".join((m.group(2) or "").replace("_", " ").split())
    return roll, name.title() if name.islower() else name


def add_students(pairs: list[tuple[str, str]]) -> int:
    """Add (roll_no, name) pairs to the class list; fills in missing names. Returns how many changed."""
    roster = load_roster()
    by_roll = {r["roll_no"]: r for r in roster}
    changed = 0
    for roll, name in pairs:
        if roll not in by_roll:
            roster.append({"roll_no": roll, "name": name})
            by_roll[roll] = roster[-1]
            changed += 1
        elif name and not by_roll[roll]["name"]:
            by_roll[roll]["name"] = name
            changed += 1
    if changed:
        save_roster(roster)
    return changed


def class_report_path() -> Path:
    return config.workspace() / "class_report.json"


def load_class_report() -> ClassReport | None:
    p = class_report_path()
    return ClassReport.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else None


def save_class_report(report: ClassReport) -> None:
    class_report_path().write_text(report.model_dump_json(indent=2), encoding="utf-8")


def student_names() -> dict[str, str]:
    return {r["roll_no"]: r["name"] for r in load_roster()}


def load_grades() -> list[ScriptGrade]:
    if not grades_dir().exists():
        return []
    return [ScriptGrade.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(grades_dir().glob("*.json"))]
