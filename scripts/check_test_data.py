"""Validate teacher marks and answer photos before spending real model quota."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from copilot import store  # noqa: E402


def photo_exists(script_id: str) -> bool:
    return any((ROOT / "data" / "scripts" / f"{script_id}{suffix}").exists()
               for suffix in (".jpg", ".jpeg", ".png"))


def main() -> int:
    problems: list[str] = []
    try:
        rubric = store.load_rubric()
    except Exception as exc:
        print(f"TEST DATA PROBLEMS:\n- Could not load rubric: {exc}")
        return 1

    path = ROOT / "data" / "teacher_marks.csv"
    if not path.exists():
        print(f"TEST DATA PROBLEMS:\n- Missing {path.relative_to(ROOT)}")
        return 1

    required = {"script_id", "role", "total", "teacher_says_hard"}
    required.update(item.item_id for item in rubric.items)
    roles = {"anchor": 0, "heldout": 0}
    seen_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing_headers = sorted(required - headers)
        if missing_headers:
            problems.append("CSV missing columns: " + ", ".join(missing_headers))
        for line, row in enumerate(reader, start=2):
            script_id = (row.get("script_id") or "").strip()
            if not script_id:
                problems.append(f"row {line}: missing script_id")
                continue
            if script_id in seen_ids:
                problems.append(f"row {line}: duplicate script_id {script_id}")
            seen_ids.add(script_id)

            role = (row.get("role") or "").strip()
            if role not in roles:
                problems.append(f"row {line} ({script_id}): role must be anchor or heldout")
            else:
                roles[role] += 1

            hard = (row.get("teacher_says_hard") or "").strip().lower()
            if hard not in {"yes", "no", "true", "false", "1", "0"}:
                problems.append(f"row {line} ({script_id}): teacher_says_hard must be yes or no")

            marks: list[int] = []
            valid_marks = True
            for item in rubric.items:
                value = (row.get(item.item_id) or "").strip()
                if not value:
                    problems.append(f"row {line} ({script_id}): missing mark for {item.item_id}")
                    valid_marks = False
                    continue
                try:
                    mark = int(value)
                except ValueError:
                    problems.append(f"row {line} ({script_id}): {item.item_id} is not an integer")
                    valid_marks = False
                    continue
                if mark not in item.allowed_marks:
                    problems.append(f"row {line} ({script_id}): {item.item_id}={mark} is not in {item.allowed_marks}")
                marks.append(mark)

            try:
                total = int((row.get("total") or "").strip())
            except ValueError:
                problems.append(f"row {line} ({script_id}): total is missing or not an integer")
                total = None
            if valid_marks and total is not None and total != sum(marks):
                problems.append(f"row {line} ({script_id}): total {total} does not equal item sum {sum(marks)}")
            if not photo_exists(script_id):
                problems.append(f"row {line} ({script_id}): no photo in data/scripts/ (.jpg, .jpeg, or .png)")

    if roles["anchor"] < 3:
        problems.append(f"need at least 3 anchors; found {roles['anchor']}")
    if roles["heldout"] < 5:
        problems.append(f"need at least 5 held-out scripts; found {roles['heldout']}")

    if problems:
        print("TEST DATA PROBLEMS:")
        print("\n".join(f"- {problem}" for problem in problems))
        return 1
    print(f"OK — {roles['anchor']} anchors and {roles['heldout']} held-out scripts validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
