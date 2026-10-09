"""Quick check that the skeleton works end to end. Run after every merge:

    python scripts/smoke_test.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copilot import audit, config, pipeline, store  # noqa: E402
from copilot.schemas import Script  # noqa: E402

rubric = store.load_rubric()
grade = pipeline.grade_script(Script(script_id="SMOKE", image_path="none.jpg"), rubric, [])
print(grade.model_dump_json(indent=2))
assert grade.total == sum(i.final_marks for i in grade.items), "total must be computed by code"

pipeline.approve("SMOKE", edits={})
out = Path(tempfile.mkdtemp()) / "marks.csv"
assert pipeline.export_csv(out) >= 1
print(out.read_text())
print(f"OK — backend={config.MODEL_BACKEND}, audit entries={len(audit.read_all())}")
