"""Simple file storage: JSON files in the active workspace (data/, or data/sample/
in sample mode). Shared by UI and pipeline."""
import json
from pathlib import Path

from copilot import config
from copilot.schemas import AnchorGrade, Rubric, ScriptGrade


def rubric_path() -> Path:
    return config.workspace() / "rubric.json"


def anchors_path() -> Path:
    return config.workspace() / "anchors" / "anchors.json"


def grades_dir() -> Path:
    return config.workspace() / "grades"


def load_rubric() -> Rubric:
    path = rubric_path() if rubric_path().exists() else config.DATA_DIR / "rubric.example.json"
    return Rubric.model_validate_json(path.read_text(encoding="utf-8"))


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


def load_grades() -> list[ScriptGrade]:
    if not grades_dir().exists():
        return []
    return [ScriptGrade.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(grades_dir().glob("*.json"))]
