"""Append-only audit log: one JSON line per event in audit.jsonl."""
import json
import threading

from copilot import config
from copilot.schemas import AuditEntry


_lock = threading.Lock()  # scripts are graded in parallel threads


def log(entry: AuditEntry) -> None:
    path = config.audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


def read_all() -> list[AuditEntry]:
    path = config.audit_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [AuditEntry.model_validate_json(line) for line in f if line.strip()]
