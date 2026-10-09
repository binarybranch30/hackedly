"""Live pipeline board: one row per answer sheet, one column per step.

The Grade page re-renders this HTML every time the pipeline emits an event, so
the audience sees each sheet move through Check -> Read -> Grade -> Verify.
"""
import html

COLUMNS = [  # (step key, title, who does it)
    ("check", "Check file", "code"),
    ("read", "Read handwriting", "Gemma 4"),
    ("grade", "Grade ×2", "Gemma 4"),
    ("verify", "Verify & total", "code"),
]
_ICON = {"pending": "radio_button_unchecked", "running": "progress_activity", "ok": "check_circle",
         "warn": "error", "fail": "cancel"}
_COLOR = {"pending": "#C4C8D4", "running": "#1E33F2", "ok": "#2BC155", "warn": "#FFAC30", "fail": "#FF4C41"}

CSS = """
<style>
.pb { width: 100%; border-collapse: separate; border-spacing: 0 6px; font-family: 'Cairo', sans-serif; }
.pb th { text-align: left; font-size: .78rem; font-weight: 600; color: #7E7E7E; padding: 0 12px 2px; }
.pb th small { display: block; font-weight: 400; color: #A0A4B0; }
.pb td { background: #FFFFFF; padding: 10px 12px; font-size: .9rem; color: #24292D;
         border-top: 1px solid #EEF0F4; border-bottom: 1px solid #EEF0F4; }
.pb td:first-child { border-left: 1px solid #EEF0F4; border-radius: 12px 0 0 12px; font-weight: 700; }
.pb td:last-child { border-right: 1px solid #EEF0F4; border-radius: 0 12px 12px 0; }
.pb .st { display: flex; align-items: center; gap: 6px; }
.pb .ic { font-family: 'Material Symbols Rounded'; font-size: 1.25rem; line-height: 1; }
.pb .dt { font-size: .76rem; color: #7E7E7E; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.pb .running .ic { animation: pbspin 1s linear infinite; }
.pb .score { font-size: 1.15rem; font-weight: 700; }
.pb .pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: .74rem; font-weight: 600; margin-left: 6px; }
@keyframes pbspin { to { transform: rotate(360deg); } }
.pf { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin: .2rem 0 1rem; font-family: 'Cairo', sans-serif; }
.pf .s { background: #FFFFFF; border: 1px solid #E3E6EE; border-radius: 999px; padding: 4px 12px; font-size: .82rem; }
.pf .s b { color: #1E33F2; }
.pf .a { color: #A0A4B0; font-family: 'Material Symbols Rounded'; }
</style>
"""


def flow_strip() -> str:
    """One-line explanation of the pipeline, shown above the board."""
    steps = [("Check file", "code"), ("Read handwriting", "Gemma 4"), ("Grade twice", "Gemma 4"),
             ("Verify evidence & add up", "code"), ("You approve", "teacher")]
    parts = []
    for n, (name, who) in enumerate(steps):
        if n:
            parts.append("<span class='a'>arrow_forward</span>")
        parts.append(f"<span class='s'>{html.escape(name)} · <b>{html.escape(who)}</b></span>")
    return CSS + "<div class='pf'>" + "".join(parts) + "</div>"


def _cell(state: tuple[str, str] | None) -> str:
    status, detail = state or ("pending", "")
    return (f"<td class='{status}'><div class='st' style='color:{_COLOR[status]}'>"
            f"<span class='ic'>{_ICON[status]}</span>"
            f"<span class='dt'>{html.escape(detail)}</span></div></td>")


def render(rows: list[str], state: dict, results: dict) -> str:
    """rows: script ids in display order; state[(sid, step)] = (status, detail);
    results[sid] = ScriptGrade once finished."""
    head = "<tr><th>Sheet</th>" + "".join(
        f"<th>{t}<small>{w}</small></th>" for _, t, w in COLUMNS) + "<th>Result</th></tr>"
    body = []
    for sid in rows:
        g = results.get(sid)
        if g is None:
            result = "<td><span class='dt'>waiting…</span></td>"
        else:
            review = g.status == "needs_review"
            pill_c = "#FFAC30" if review else "#2BC155"
            label = "needs review" if review else "auto-OK"
            result = (f"<td><span class='score'>{g.total}/{g.max_total}</span>"
                      f"<span class='pill' style='background:{pill_c}22;color:{pill_c}'>{label}</span></td>")
        body.append(f"<tr><td>{html.escape(sid)}</td>" +
                    "".join(_cell(state.get((sid, k))) for k, _, _ in COLUMNS) + result + "</tr>")
    return CSS + f"<table class='pb'>{head}{''.join(body)}</table>"
