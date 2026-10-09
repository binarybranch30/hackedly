"""AnchorGrade HTML and CSV reporting.

Generates self-contained HTML dashboards and CSV export files for graded scripts.
"""
import base64
import csv
import html
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from copilot import config
from copilot.schemas import GradedItem, Rubric, ScriptGrade

PRIMARY = "#1E33F2"
SUCCESS = "#2BC155"
WARNING = "#FFAC30"
DANGER = "#FF4C41"
INFO = "#51A6F5"
MUTED = "#7E7E7E"
BG_COLOR = "#F5F6FA"

FLAG_COLORS = {
    "LOW_CONFIDENCE": WARNING,
    "RUNS_DISAGREE": WARNING,
    "FALLBACK_USED": INFO,
    "EVIDENCE_NOT_FOUND": DANGER,
    "UNREADABLE": DANGER,
    "MODEL_ERROR": DANGER,
    "RULE_VIOLATION": DANGER,
}

STATUS_COLORS = {
    "needs_review": WARNING,
    "auto_ok": INFO,
    "approved": SUCCESS,
    "released": PRIMARY,
}


def _encode_thumbnail(image_path: Path | str) -> Optional[str]:
    """Load an image, rotate upright, resize to at most 900px wide, and return base64 data URI."""
    try:
        p = Path(image_path)
        if not p.is_file():
            return None
        with Image.open(p) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if im.width > 900:
                new_h = max(1, int(im.height * (900 / im.width)))
                im = im.resize((900, new_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64_str}"
    except Exception:
        return None


def _find_image_file(script_id: str, image_dir: Optional[Path | str] = None) -> Optional[Path]:
    """Look up an image for script_id across image_dir, DATA_DIR/scripts, and DATA_DIR/anchors."""
    extensions = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
    direct = Path(script_id)
    if direct.is_file():
        return direct

    search_dirs = []
    if image_dir:
        search_dirs.append(Path(image_dir))
    search_dirs.append(config.DATA_DIR / "scripts")
    search_dirs.append(config.DATA_DIR / "anchors")

    for d in search_dirs:
        if not d.exists():
            continue
        for ext in extensions:
            cand = d / f"{script_id}{ext}"
            if cand.is_file():
                return cand
    return None


def _highlight_transcription(text: str, quotes: list[str]) -> str:
    """Escape text and wrap each non-empty evidence quote in <mark>."""
    if not text:
        return ""
    valid_quotes = sorted({q for q in quotes if q and q.strip()}, key=len, reverse=True)
    if not valid_quotes:
        return html.escape(text).replace("\n", "<br>")

    pattern = "|".join(re.escape(q) for q in valid_quotes)
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error:
        return html.escape(text).replace("\n", "<br>")

    pieces = []
    pos = 0
    for match in regex.finditer(text):
        start, end = match.span()
        if start > pos:
            pieces.append(html.escape(text[pos:start]))
        pieces.append(f"<mark>{html.escape(match.group(0))}</mark>")
        pos = end
    if pos < len(text):
        pieces.append(html.escape(text[pos:]))

    return "".join(pieces).replace("\n", "<br>")


def _badge_html(label: str, color: str) -> str:
    return f"<span class='ag-badge' style='background:{color}1A;color:{color}'>{html.escape(label)}</span>"


def _status_badge_html(status: str) -> str:
    color = STATUS_COLORS.get(status, MUTED)
    return _badge_html(status.replace("_", " "), color)


def _flag_badges_html(flags: list[str]) -> str:
    if not flags:
        return _badge_html("no flags", SUCCESS)
    return "".join(_badge_html(f, FLAG_COLORS.get(f, DANGER)) for f in flags)


def _lowest_confidence_item(items: list[GradedItem]) -> str:
    """Return item_id of lowest confidence item, or empty string."""
    if not items:
        return ""
    order = {"low": 0, "medium": 1, "high": 2}
    lowest = min(items, key=lambda it: order.get(it.confidence, 3))
    return lowest.item_id


def write_report(grades: list[ScriptGrade], rubric: Rubric, out_dir: Path,
                 image_dir: Optional[Path | str] = None) -> dict:
    """Generate report.html, flagged.csv, and marks_all.csv in out_dir.

    Returns {"report": Path, "flagged": Path, "marks": Path, "n_flagged": int}.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.html"
    flagged_path = out_dir / "flagged.csv"
    marks_path = out_dir / "marks_all.csv"

    # 1. Prepare data
    n_scripts = len(grades)
    n_review = sum(1 for g in grades if g.status == "needs_review")
    n_auto_ok = sum(1 for g in grades if g.status == "auto_ok")
    n_approved = sum(1 for g in grades if g.status in ("approved", "released"))
    avg_total = (sum(g.total for g in grades) / n_scripts) if n_scripts > 0 else 0.0

    all_approved = (n_scripts > 0 and all(g.status in ("approved", "released") for g in grades))
    show_draft_banner = not all_approved

    backends = sorted({g.backend for g in grades if g.backend}) or [config.MODEL_BACKEND]
    models = sorted({g.model for g in grades if g.model}) or ["gemma-4"]
    backend_info = f"{', '.join(backends)} / {', '.join(models)}"

    gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    flagged_grades = [g for g in grades if g.flags]
    # Sorted order: flagged first, then by script_id
    sorted_grades = sorted(grades, key=lambda g: (0 if g.flags else 1, g.script_id))

    rubric_by_id = {item.item_id: item for item in rubric.items}

    # 2. Build report.html
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AnchorGrade Grading Report</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

* {{ box-sizing: border-box; }}
body {{
  font-family: 'Cairo', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: {BG_COLOR};
  color: #24292D;
  margin: 0;
  padding: 2rem 1.5rem;
  line-height: 1.5;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}

/* Header */
.report-header {{ margin-bottom: 1.5rem; }}
.report-title {{
  font-size: 2rem;
  font-weight: 700;
  color: {PRIMARY};
  margin: 0 0 0.25rem 0;
}}
.report-meta {{
  color: {MUTED};
  font-size: 0.9rem;
  margin: 0 0 1rem 0;
}}

/* Draft Banner */
.draft-banner {{
  background: #FFF3CD;
  color: #856404;
  border: 1px solid #FFEEBA;
  border-left: 6px solid {WARNING};
  border-radius: 10px;
  padding: 0.85rem 1.25rem;
  font-weight: 700;
  font-size: 1rem;
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}

/* White Cards */
.ag-card {{
  background: #FFFFFF;
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 2px 12px rgba(30, 51, 242, 0.06);
  margin-bottom: 1.5rem;
}}

/* Summary Stats */
.stat-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}}
.stat-card {{
  display: flex;
  align-items: center;
  gap: 1rem;
  background: #FFFFFF;
  border-radius: 14px;
  padding: 1.1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(30, 51, 242, 0.06);
}}
.stat-icon {{
  width: 3.2rem;
  height: 3.2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  flex-shrink: 0;
}}
.stat-value {{
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1.1;
  color: #24292D;
}}
.stat-label {{
  font-size: 0.85rem;
  color: {MUTED};
}}

/* Badges */
.ag-badge {{
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 600;
  margin: 0 0.25rem 0.25rem 0;
}}

/* Flagged scripts section */
.flagged-section h2 {{
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  color: #24292D;
}}
.flagged-list {{
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}}
.flagged-item {{
  padding: 0.6rem 0.85rem;
  background: #FFFDF7;
  border: 1px solid #FFE69C;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
}}
.flagged-link {{
  color: {PRIMARY};
  text-decoration: none;
  font-weight: 700;
}}
.flagged-link:hover {{
  text-decoration: underline;
}}

/* Script Section */
.script-card {{
  border-top: 4px solid {PRIMARY};
}}
.script-card.flagged {{
  border-top: 4px solid {WARNING};
}}
.script-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #EEEEEE;
}}
.script-title {{
  font-size: 1.35rem;
  font-weight: 700;
  color: #24292D;
  margin: 0;
}}
.script-header-right {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}}
.score-pill {{
  background: {PRIMARY}1A;
  color: {PRIMARY};
  font-weight: 700;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.9rem;
}}

/* Script Body Grid */
.script-body {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-bottom: 1.25rem;
}}
@media (max-width: 850px) {{
  .script-body {{ grid-template-columns: 1fr; }}
}}
.image-pane {{
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}}
.script-thumb {{
  max-width: 100%;
  max-height: 500px;
  height: auto;
  border-radius: 6px;
  object-fit: contain;
}}
.transcription-pane h4 {{
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  color: #24292D;
}}
.transcription-text {{
  background: #F9FAFB;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  padding: 1rem;
  font-size: 0.95rem;
  line-height: 1.6;
  max-height: 480px;
  overflow-y: auto;
  white-space: pre-wrap;
}}

/* Highlighting */
mark {{
  background: #FFF1D6;
  color: #24292D;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-weight: 600;
  border-bottom: 2px solid {WARNING};
}}

/* Item Table */
.table-wrap {{
  overflow-x: auto;
  margin-top: 1rem;
}}
table.item-table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
  text-align: left;
}}
table.item-table th {{
  background: {BG_COLOR};
  color: #24292D;
  font-weight: 700;
  padding: 0.65rem 0.85rem;
  border-bottom: 2px solid #E5E7EB;
}}
table.item-table td {{
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid #EEEEEE;
  vertical-align: top;
}}
table.item-table tr:last-child td {{
  border-bottom: none;
}}
table.item-table tr:hover td {{
  background: #FAFAFC;
}}
.muted-text {{
  color: {MUTED};
}}

/* Print Styles */
@media print {{
  body {{
    background: #FFFFFF !important;
    color: #000000 !important;
    padding: 0 !important;
    font-size: 10pt;
  }}
  .container {{ max-width: 100% !important; }}
  .stat-grid {{
    grid-template-columns: repeat(5, 1fr) !important;
    gap: 0.5rem !important;
  }}
  .stat-card, .ag-card {{
    box-shadow: none !important;
    border: 1px solid #D1D5DB !important;
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  .script-card {{
    break-inside: avoid;
    page-break-inside: avoid;
    margin-bottom: 1.5rem !important;
  }}
  .transcription-text {{
    max-height: none !important;
    overflow: visible !important;
  }}
  .no-print {{ display: none !important; }}
  a {{
    color: inherit !important;
    text-decoration: none !important;
  }}
  .draft-banner {{
    border: 2px solid {WARNING} !important;
    background: #FFFDF0 !important;
  }}
}}
</style>
</head>
<body>
<div class="container">

<div class="report-header">
  <h1 class="report-title">✎ AnchorGrade Report</h1>
  <div class="report-meta">
    Generated: {html.escape(gen_time)} &nbsp;·&nbsp; Backend / Model: {html.escape(backend_info)} &nbsp;·&nbsp; Rubric: {html.escape(rubric.rubric_id)}
  </div>
</div>
""")

    if show_draft_banner:
        html_parts.append("""
<div class="draft-banner">
  ⚠️ DRAFT — not released until teacher approval
</div>
""")

    html_parts.append(f"""
<div class="stat-grid">
  <div class="stat-card">
    <div class="stat-icon" style="background:{PRIMARY}1A;color:{PRIMARY}">📄</div>
    <div>
      <div class="stat-value">{n_scripts}</div>
      <div class="stat-label">Scripts</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background:{WARNING}1A;color:{WARNING}">⚠️</div>
    <div>
      <div class="stat-value">{n_review}</div>
      <div class="stat-label">Need Review</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background:{INFO}1A;color:{INFO}">✓</div>
    <div>
      <div class="stat-value">{n_auto_ok}</div>
      <div class="stat-label">Auto-OK</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background:{SUCCESS}1A;color:{SUCCESS}">🔒</div>
    <div>
      <div class="stat-value">{n_approved}</div>
      <div class="stat-label">Approved</div>
    </div>
  </div>
  <div class="stat-card">
    <div class="stat-icon" style="background:{PRIMARY}1A;color:{PRIMARY}">★</div>
    <div>
      <div class="stat-value">{avg_total:.1f} / {rubric.max_total}</div>
      <div class="stat-label">Average Total/Max</div>
    </div>
  </div>
</div>
""")

    # Flagged scripts section
    html_parts.append("""
<div class="ag-card flagged-section">
  <h2>Flagged scripts</h2>
""")
    if flagged_grades:
        html_parts.append("<ul class=\"flagged-list\">")
        for fg in flagged_grades:
            sid_esc = html.escape(fg.script_id)
            badges = _flag_badges_html(fg.flags)
            html_parts.append(
                f"<li class=\"flagged-item\">"
                f"<div><a class=\"flagged-link\" href=\"#script-{sid_esc}\">Script {sid_esc}</a>"
                f"<span class=\"muted-text\"> — {fg.total}/{fg.max_total} marks</span></div>"
                f"<div>{badges}</div>"
                f"</li>"
            )
        html_parts.append("</ul>")
    else:
        html_parts.append(f"<p style='color:{SUCCESS};font-weight:600;margin:0;'>✓ No flagged scripts. All scripts passed automated checks.</p>")
    html_parts.append("</div>\n")

    # Script sections
    for g in sorted_grades:
        sid_esc = html.escape(g.script_id)
        is_flagged = bool(g.flags)
        card_class = "ag-card script-card flagged" if is_flagged else "ag-card script-card"

        # Image lookup & thumbnail
        img_file = _find_image_file(g.script_id, image_dir)
        img_data_uri = _encode_thumbnail(img_file) if img_file else None

        # Transcription highlighting
        raw_text = g.transcription.text if g.transcription else ""
        quotes = [item.evidence_quote for item in g.items if item.evidence_quote]
        highlighted = _highlight_transcription(raw_text, quotes) if raw_text else "<span class='muted-text'>No transcription available</span>"

        status_badge = _status_badge_html(g.status)
        flag_badges = _flag_badges_html(g.flags)

        html_parts.append(f"""
<div class="{card_class}" id="script-{sid_esc}">
  <div class="script-header">
    <h3 class="script-title">Script: {sid_esc}</h3>
    <div class="script-header-right">
      <span class="score-pill">{g.total} / {g.max_total} marks</span>
      {status_badge}
      {flag_badges}
    </div>
  </div>
  <div class="script-body">
    <div class="image-pane">
""")
        if img_data_uri:
            html_parts.append(f"      <img src=\"{img_data_uri}\" alt=\"Script {sid_esc}\" class=\"script-thumb\" />")
        else:
            html_parts.append("      <span class=\"muted-text\">No image file found</span>")

        html_parts.append(f"""
    </div>
    <div class="transcription-pane">
      <h4>Transcription</h4>
      <div class="transcription-text">{highlighted}</div>
    </div>
  </div>
  <div class="table-wrap">
    <table class="item-table">
      <thead>
        <tr>
          <th>Item ID</th>
          <th>Rubric Description</th>
          <th>Marks</th>
          <th>Confidence</th>
          <th>Evidence Quote</th>
          <th style="text-align:center;">Evidence Found</th>
          <th>Reasoning</th>
        </tr>
      </thead>
      <tbody>
""")

        if g.items:
            for it in g.items:
                ritem = rubric_by_id.get(it.item_id)
                r_desc = ritem.description if ritem else ""
                r_max = ritem.max_marks if ritem else it.final_marks
                conf_color = WARNING if it.confidence == "low" else (INFO if it.confidence == "medium" else SUCCESS)
                conf_badge = _badge_html(it.confidence, conf_color)
                ev_icon = "✅" if it.evidence_found else "❌"
                quote_esc = html.escape(it.evidence_quote) if it.evidence_quote else "<span class='muted-text'>—</span>"

                html_parts.append(f"""
        <tr>
          <td><strong>{html.escape(it.item_id)}</strong></td>
          <td>{html.escape(r_desc)}</td>
          <td><strong>{it.final_marks}</strong> / {r_max}</td>
          <td>{conf_badge}</td>
          <td>{quote_esc}</td>
          <td style="text-align:center;">{ev_icon}</td>
          <td>{html.escape(it.reasoning)}</td>
        </tr>
""")
        else:
            html_parts.append("        <tr><td colspan=\"7\" class=\"muted-text\" style=\"text-align:center;\">No scored items available.</td></tr>\n")

        html_parts.append("""
      </tbody>
    </table>
  </div>
</div>
""")

    html_parts.append("""
</div>
</body>
</html>
""")

    report_path.write_text("".join(html_parts), encoding="utf-8")

    # 3. Build flagged.csv
    with open(flagged_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["script_id", "total", "max_total", "status", "flags", "lowest_confidence_item"])
        for g in flagged_grades:
            writer.writerow([
                g.script_id,
                g.total,
                g.max_total,
                g.status,
                ";".join(g.flags),
                _lowest_confidence_item(g.items),
            ])

    # 4. Build marks_all.csv
    with open(marks_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        item_ids = [it.item_id for it in rubric.items]
        writer.writerow(["draft", "script_id"] + item_ids + ["total", "status", "flags"])
        for g in sorted(grades, key=lambda x: x.script_id):
            draft_val = "no" if g.status in ("approved", "released") else "yes"
            item_marks = {it.item_id: it.final_marks for it in g.items}
            row = [draft_val, g.script_id] + [item_marks.get(iid, "") for iid in item_ids] + [
                g.total, g.status, ";".join(g.flags)
            ]
            writer.writerow(row)

    return {
        "report": report_path,
        "flagged": flagged_path,
        "marks": marks_path,
        "n_flagged": len(flagged_grades),
    }
