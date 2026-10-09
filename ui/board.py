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
_COLOR = {"pending": "var(--ag-faint)", "running": "var(--ag-primary)", "ok": "var(--ag-primary)", "warn": "#C77D00", "fail": "#D6453D"}

CSS = """
<style>
.pb { width: 100%; border-collapse: separate; border-spacing: 0 6px; font-family: var(--ag-body); }
.pb th { text-align: left; font-size: .78rem; font-weight: 600; color: var(--ag-muted); padding: 0 12px 2px; }
.pb th small { display: block; font-weight: 400; color: var(--ag-faint); }
.pb td { background: var(--ag-card); padding: 10px 12px; font-size: .9rem; color: var(--ag-text);
         border-top: 1px solid var(--ag-border); border-bottom: 1px solid var(--ag-border); }
.pb td:first-child { border-left: 1px solid var(--ag-border); border-radius: 12px 0 0 12px; font-weight: 700; }
.pb td:last-child { border-right: 1px solid var(--ag-border); border-radius: 0 12px 12px 0; }
.pb .st { display: flex; align-items: center; gap: 6px; }
.pb .ic { font-family: 'Material Symbols Rounded'; font-size: 1.25rem; line-height: 1; }
.pb .dt { font-size: .76rem; color: var(--ag-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.pb .running .ic { animation: pbspin 1s linear infinite; }
.pb .score { font-family: var(--ag-head); font-size: 1.15rem; font-weight: 700; }
.pb .pill { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: .74rem; font-weight: 600; margin-left: 6px; }
@keyframes pbspin { to { transform: rotate(360deg); } }
.pf { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin: .2rem 0 1rem; font-family: var(--ag-body); }
.pf .s { background: var(--ag-card); border: 1px solid var(--ag-border); color: var(--ag-text); font-weight: 500; border-radius: 999px; padding: 3px 10px; font-size: .78rem; }
.pf .s b { color: var(--ag-primary); }
.pf .a { color: var(--ag-faint); font-family: 'Material Symbols Rounded'; }
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
            pill_c = "#C77D00" if review else "#0E7C66"
            label = "needs review" if review else "auto-OK"
            result = (f"<td><span class='score'>{g.total}/{g.max_total}</span>"
                      f"<span class='pill' style='background:{pill_c}22;color:{pill_c}'>{label}</span></td>")
        body.append(f"<tr><td>{html.escape(sid)}</td>" +
                    "".join(_cell(state.get((sid, k))) for k, _, _ in COLUMNS) + result + "</tr>")
    return CSS + f"<table class='pb'>{head}{''.join(body)}</table>"


SHEET_CSS = """
<style>
.sc { background: var(--ag-card); border: 1px solid var(--ag-border); border-radius: 1.1rem; padding: 1.2rem 1.3rem 1rem;
      box-shadow: 0 18px 40px var(--ag-shadow); font-family: var(--ag-body); color: var(--ag-text); }
.sc .hd { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: .9rem; }
.sc .t { font-weight: 700; font-size: .95rem; } .sc .st { font-size: .78rem; color: var(--ag-muted); }
.sc .pill { font-size: .72rem; font-weight: 600; padding: .2rem .65rem; border-radius: 999px; white-space: nowrap; }
.sc .bd { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: .8rem; }
.sc .paper { background: var(--ag-paper); border: 1px solid var(--ag-border); border-radius: .8rem; overflow: hidden;
             min-height: 170px; display: flex; align-items: center; justify-content: center; }
.sc .paper img { width: 100%; height: 100%; object-fit: cover; object-position: top; max-height: 230px; }
.sc .row { display: flex; justify-content: space-between; align-items: center; border: 1px solid var(--ag-border);
           border-radius: .7rem; padding: .5rem .75rem; font-size: .83rem; margin-bottom: .45rem; }
.sc .row span:first-child { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc .row b, .sc .row span + span { font-weight: 700; white-space: nowrap; margin-left: .6rem; } .sc .tot { background: var(--ag-ink); color: var(--ag-ink-text); border: none; font-weight: 700; }
.sc .ft { font-size: .76rem; color: var(--ag-muted); margin-top: .6rem; }
</style>
"""


def sheet_card(title: str, subtitle: str, pill: tuple[str, str], rows: list[tuple[str, str, str]],
               total: str, note: str, image_b64: str | None = None) -> str:
    """A graded answer sheet at a glance (Home page hero). rows: (label, "4 / 5", colour)."""
    label, color = pill
    paper = (f"<img src='data:image/jpeg;base64,{image_b64}' alt='answer sheet'>" if image_b64
             else "<span class='st'>no sheet yet</span>")
    items = "".join(f"<div class='row'><span>{html.escape(a)}</span><b style='color:{c}'>{html.escape(b)}</b></div>"
                    for a, b, c in rows)
    return (SHEET_CSS + f"<div class='sc'><div class='hd'><div><div class='t'>{html.escape(title)}</div>"
            f"<div class='st'>{html.escape(subtitle)}</div></div>"
            f"<span class='pill' style='background:{color}22;color:{color}'>{html.escape(label)}</span></div>"
            f"<div class='bd'><div class='paper'>{paper}</div><div>{items}"
            f"<div class='row tot'><span>Total</span><span>{html.escape(total)}</span></div></div></div>"
            f"<div class='ft'>{html.escape(note)}</div></div>")
