"""Simple file storage: JSON files under data/. Shared by UI and pipeline."""
import json

from copilot.config import DATA_DIR
from copilot.schemas import AnchorGrade, Rubric, ScriptGrade

RUBRIC_PATH = DATA_DIR / "rubric.json"
ANCHORS_PATH = DATA_DIR / "anchors" / "anchors.json"
GRADES_DIR = DATA_DIR / "grades"


def load_rubric() -> Rubric:
    path = RUBRIC_PATH if RUBRIC_PATH.exists() else DATA_DIR / "rubric.example.json"
    return Rubric.model_validate_json(path.read_text(encoding="utf-8"))


def save_rubric(rubric: Rubric) -> None:
    RUBRIC_PATH.write_text(rubric.model_dump_json(indent=2), encoding="utf-8")


def load_anchors() -> list[AnchorGrade]:
    if not ANCHORS_PATH.exists():
        return []
    data = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    return [AnchorGrade.model_validate(a) for a in data]


def save_anchors(anchors: list[AnchorGrade]) -> None:
    ANCHORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANCHORS_PATH.write_text(json.dumps([a.model_dump() for a in anchors], indent=2),
                            encoding="utf-8")


def save_grade(grade: ScriptGrade) -> None:
    GRADES_DIR.mkdir(parents=True, exist_ok=True)
    (GRADES_DIR / f"{grade.script_id}.json").write_text(grade.model_dump_json(indent=2),
                                                        encoding="utf-8")


def load_grades() -> list[ScriptGrade]:
    if not GRADES_DIR.exists():
        return []
    return [ScriptGrade.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(GRADES_DIR.glob("*.json"))]
