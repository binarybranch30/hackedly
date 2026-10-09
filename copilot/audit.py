"""Append-only audit log: one JSON line per event in audit.jsonl."""
import json

from copilot.config import AUDIT_PATH
from copilot.schemas import AuditEntry


def log(entry: AuditEntry) -> None:
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


def read_all() -> list[AuditEntry]:
    if not AUDIT_PATH.exists():
        return []
    with open(AUDIT_PATH, encoding="utf-8") as f:
        return [AuditEntry.model_validate_json(line) for line in f if line.strip()]
