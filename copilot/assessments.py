"""Assessments: one folder per test/question set, each with its own rubric, anchor
scripts, student list (roster), answer sheets, grades and audit log.

    data/assessments/<slug>/meta.json      name, class, subject, created
    data/assessments/<slug>/rubric.json    ... same layout as any workspace
"""
import json
import re
import shutil
from datetime import datetime, timezone

from copilot import config


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "assessment"


def list_all() -> list[dict]:
    """All assessments, newest first: [{slug, name, class_name, subject, created}]."""
    out = []
    root = config.assessments_dir()
    if root.exists():
        for d in root.iterdir():
            meta = d / "meta.json"
            if d.is_dir() and meta.exists():
                out.append({"slug": d.name, **json.loads(meta.read_text(encoding="utf-8"))})
    return sorted(out, key=lambda m: m.get("created", ""), reverse=True)


def get(slug: str) -> dict | None:
    return next((m for m in list_all() if m["slug"] == slug), None)


def create(name: str, class_name: str = "", subject: str = "") -> str:
    """Create an empty assessment and make it the active one. Returns its slug."""
    if not name.strip():
        raise ValueError("Give the assessment a name.")
    base = _slug(f"{name} {class_name}")
    slug, n = base, 2
    while (config.assessments_dir() / slug).exists():
        slug, n = f"{base}-{n}", n + 1
    d = config.assessments_dir() / slug
    for sub in ("scripts", "anchors", "grades"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    meta = {"name": name.strip(), "class_name": class_name.strip(), "subject": subject.strip(),
            "created": datetime.now(timezone.utc).isoformat()}
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    activate(slug)
    return slug


def update(slug: str, **fields) -> None:
    d = config.assessments_dir() / slug
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    meta.update({k: v.strip() for k, v in fields.items() if isinstance(v, str)})
    (d / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def activate(slug: str) -> None:
    config.active_file().parent.mkdir(parents=True, exist_ok=True)
    config.active_file().write_text(slug, encoding="utf-8")


def delete(slug: str) -> None:
    """Delete an assessment and everything in it (sheets, grades, audit log)."""
    d = config.assessments_dir() / slug
    if d.is_dir() and d.parent == config.assessments_dir():
        shutil.rmtree(d)
    if config.active_file().exists() and config.active_file().read_text(encoding="utf-8").strip() == slug:
        config.active_file().unlink()


def label(meta: dict) -> str:
    extra = " · ".join(x for x in (meta.get("class_name"), meta.get("subject")) if x)
    return meta["name"] + (f" ({extra})" if extra else "")
