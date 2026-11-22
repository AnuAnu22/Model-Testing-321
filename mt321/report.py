"""Compiles graded results into a self-contained HTML report (inline SVG, no external assets), JSON, CSV and Markdown."""
from __future__ import annotations

import csv
import html
import io
import json
import time
from pathlib import Path

from .evaluate import pct

E = html.escape
PALETTE = ["#4f7cff", "#22b8a6", "#f5a524", "#e5484d", "#9b6bff", "#2ea043", "#d9468f", "#7a8699", "#0ea5e9", "#c2410c", "#65a30d", "#64748b"]


def col(v):
    if v is None:
        return "#8884"
    v = max(0.0, min(1.0, v))
    r, g = (229, int(72 + 150 * v * 2)) if v < .5 else (int(229 - (v - .5) * 2 * 150), 190)
    if v < .5:
        r, g = 229, int(72 + 100 * v * 2)
    else:
        r, g = int(229 - 170 * (v - .5) * 2), int(172 + 20 * (v - .5) * 2)
    return f"rgb({r},{g},{90 if v >= .5 else 80})"


def bar_h(items, width=640, maxv=1.0, fmt=lambda v: pct(v)):
    rowh = 26
    h = rowh * len(items) + 8
    s = [f'<svg viewBox="0 0 {width} {h}" class="chart" role="img">']
    lw = 230
    for i, (label, v, n) in enumerate(items):
        y = i * rowh + 4
        bw = 0 if v is None else (width - lw - 90) * v / maxv
        s.append(f'<text x="{lw - 8}" y="{y + 16}" text-anchor="end" class="lbl">{E(label)}</text>')
        s.append(f'<rect x="{lw}" y="{y + 3}" width="{width - lw - 90}" height="16" rx="3" class="track"/>')
        s.append(f'<rect x="{lw}" y="{y + 3}" width="{max(bw, 0):.1f}" height="16" rx="3" fill="{col(v)}"/>')
        s.append(f'<text x="{lw + (width - lw - 90) + 8}" y="{y + 16}" class="lbl">{fmt(v) if v is not None else "n/a"} <tspan class="dim">n={n}</tspan></text>')
    s.append("</svg>")
    return "".join(s)


def line_chart(series, width=680, height=260, xlabel="", ylabel="", ymax=1.0, points=None, vlines=None, xmax=None):
    """series: list of (name, color, [(x,y)...]). points: optional scatter [(x,y,color)]"""
    ml, mr, mt, mb = 44, 14, 12, 34
    pw, ph = width - ml - mr, height - mt - mb
    allx = [x for _, _, pts in series for x, _ in pts] + [p[0] for p in (points or [])]
    xm = xmax or (max(allx) if allx else 1)
    sx = lambda x: ml + pw * x / xm if xm else ml
    sy = lambda y: mt + ph * (1 - y / ymax)
    s = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for t in range(0, 6):
        yv = ymax * t / 5
        s.append(f'<line x1="{ml}" x2="{width - mr}" y1="{sy(yv):.1f}" y2="{sy(yv):.1f}" class="grid"/><text x="{ml - 6}" y="{sy(yv) + 4:.1f}" text-anchor="end" class="lbl dim">{yv:.1f}</text>')
    for t in range(0, 6):
        xv = xm * t / 5
        s.append(f'<text x="{sx(xv):.1f}" y="{height - 14}" text-anchor="middle" class="lbl dim">{xv:.0f}</text>')
    s.append(f'<text x="{ml + pw / 2}" y="{height - 1}" text-anchor="middle" class="lbl dim">{E(xlabel)}</text>')
    for x in (vlines or []):
        s.append(f'<line x1="{sx(x):.1f}" x2="{sx(x):.1f}" y1="{mt}" y2="{mt + ph}" class="vl"/>')
    for name, color, pts in series:
        if pts:
            s.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{" ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)}"/>')
    for x, y, c in (points or []):
        s.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.2" fill="{c}" opacity=".75"/>')
    lx = ml + 8
    for name, color, _ in series:
        s.append(f'<rect x="{lx}" y="{mt + 2}" width="10" height="10" fill="{color}"/><text x="{lx + 14}" y="{mt + 11}" class="lbl">{E(name)}</text>')
        lx += 20 + 7 * len(name)
    s.append("</svg>")
    return "".join(s)


def col_chart(items, width=640, height=220, ymax=1.0, labels=True):
    ml, mb, mt = 40, 40, 14
    n = max(1, len(items))
    bw = (width - ml - 10) / n
    s = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">']
    for t in range(0, 6):
        yv = ymax * t / 5
        y = mt + (height - mt - mb) * (1 - yv / ymax)
        s.append(f'<line x1="{ml}" x2="{width - 4}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/><text x="{ml - 5}" y="{y + 4:.1f}" text-anchor="end" class="lbl dim">{yv:.1f}</text>')
    for i, (lab, v, n_) in enumerate(items):
        x = ml + i * bw + bw * .15
        hgt = 0 if v is None else (height - mt - mb) * min(v, ymax) / ymax
        s.append(f'<rect x="{x:.1f}" y="{height - mb - hgt:.1f}" width="{bw * .7:.1f}" height="{hgt:.1f}" rx="3" fill="{col(v / ymax if v is not None else None)}"/>')
        if v is not None and labels:
            s.append(f'<text x="{x + bw * .35:.1f}" y="{height - mb - hgt - 4:.1f}" text-anchor="middle" class="lbl">{pct(v) if ymax <= 1 else f"{v:.0f}"}</text>')
        s.append(f'<text x="{x + bw * .35:.1f}" y="{height - mb + 14}" text-anchor="middle" class="lbl dim">{E(str(lab))}</text><text x="{x + bw * .35:.1f}" y="{height - mb + 27}" text-anchor="middle" class="lbl dim">n={n_}</text>')
    s.append("</svg>")
    return "".join(s)


def calib_chart(bins, size=300):
    ml, mb, mt, mr = 38, 34, 10, 10
    pw, ph = size - ml - mr, size - mt - mb
    sx, sy = (lambda v: ml + pw * v), (lambda v: mt + ph * (1 - v))
    s = [f'<svg viewBox="0 0 {size} {size}" class="chart" role="img">',
         f'<rect x="{ml}" y="{mt}" width="{pw}" height="{ph}" class="track"/>',
         f'<line x1="{sx(0)}" y1="{sy(0)}" x2="{sx(1)}" y2="{sy(1)}" class="vl"/>']
    for t in (0, .5, 1):
        s.append(f'<text x="{sx(t):.0f}" y="{size - 18}" text-anchor="middle" class="lbl dim">{t}</text><text x="{ml - 5}" y="{sy(t) + 4:.0f}" text-anchor="end" class="lbl dim">{t}</text>')
    s.append(f'<text x="{ml + pw / 2}" y="{size - 3}" text-anchor="middle" class="lbl dim">stated confidence</text>')
    for b in bins:
        r = 4 + min(10, b["n"] ** .5)
        s.append(f'<circle cx="{sx(b["conf"]):.1f}" cy="{sy(b["acc"]):.1f}" r="{r:.1f}" fill="#4f7cff" opacity=".8"><title>conf {b["conf"]:.2f}, actual {b["acc"]:.2f}, n={b["n"]}</title></circle>')
    s.append("</svg>")
    return "".join(s)


def heat_table(rows, cols, cell, rowlab=lambda r: r, collab=lambda c: c):
    t = ['<div class="scroll"><table class="heat"><tr><th></th>' + "".join(f"<th>{E(str(collab(c)))}</th>" for c in cols) + "</tr>"]
    for r in rows:
        t.append(f"<tr><th>{E(str(rowlab(r)))}</th>")
        for c in cols:
            v = cell(r, c)
            t.append(f'<td style="background:{col(v[0])}">{pct(v[0]) if v and v[0] is not None else ""}</td>' if v else "<td></td>")
        t.append("</tr>")
    t.append("</table></div>")
    return "".join(t)


def jfmt(x, lim=1500):
    s = json.dumps(x, indent=1, ensure_ascii=False) if not isinstance(x, str) else x
    return s if len(s) <= lim else s[:lim] + f"\n... [{len(s) - lim} more chars]"


def dur(s):
    if s is None:
        return "n/a"
    s = int(s)
    return f"{s // 3600}h {s % 3600 // 60}m" if s >= 3600 else f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s"


CSS = """
:root{--bg:#f6f7fb;--fg:#1b1f2a;--card:#fff;--dim:#6b7280;--line:#e3e6ee;--acc:#4f7cff}
@media(prefers-color-scheme:dark){:root{--bg:#0f1218;--fg:#e8ebf2;--card:#181c25;--dim:#98a1b3;--line:#2a3040}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 80px}h1{margin:.2em 0}h2{margin:1.6em 0 .4em;padding-top:.4em;border-top:1px solid var(--line)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}.grid4{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}.kpi b{display:block;font-size:26px}.kpi span{color:var(--dim);font-size:12.5px}
.chart{width:100%;height:auto}.lbl{font-size:11.5px;fill:var(--fg)}.dim{fill:var(--dim);color:var(--dim)}.grid{stroke:var(--line)}.vl{stroke:var(--dim);stroke-dasharray:4 4}.track{fill:var(--line);opacity:.5}
table{border-collapse:collapse;width:100%;font-size:13.5px}td,th{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.heat td{text-align:center;color:#fff;font-weight:600;min-width:54px}
.scroll{overflow-x:auto}.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid var(--line)}.ok{background:#2ea04322}.bad{background:#e5484d22}.mid{background:#f5a52422}
details.t{border:1px solid var(--line);border-radius:10px;margin:6px 0;background:var(--card)}details.t>summary{cursor:pointer;padding:8px 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
details.t .body{padding:0 14px 12px}pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:8px;white-space:pre-wrap;word-break:break-word;font-size:12.5px;max-height:320px;overflow:auto}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:760px){.two{grid-template-columns:1fr}}.dimtxt{color:var(--dim)}
.filters button{margin:2px;padding:4px 10px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}.filters button.on{background:var(--acc);color:#fff}
"""

JS = """
const st={cat:'all',bad:false};function ap(){document.querySelectorAll('details.t').forEach(d=>{let ok=(st.cat=='all'||d.dataset.cat==st.cat)&&(!st.bad||d.dataset.bad=='1');d.style.display=ok?'':'none'})}
document.querySelectorAll('.filters button[data-cat]').forEach(b=>b.onclick=()=>{st.cat=b.dataset.cat;document.querySelectorAll('.filters button[data-cat]').forEach(x=>x.classList.toggle('on',x==b));ap()});
document.getElementById('badonly').onclick=function(){st.bad=!st.bad;this.classList.toggle('on',st.bad);ap()};
"""


def kpi(label, value, sub=""):
    return f'<div class="kpi"><b>{value}</b><span>{E(label)}{" - " + E(sub) if sub else ""}</span></div>'


def build_html(R: dict) -> str:
    info, T, S = R["info"], R["tasks"], R["summary"]
    h = []
    A = h.append
    A(f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MT-321 report - {E(info["name"])}</title><style>{CSS}</style><main>')
    A(f'<h1>MT-321 local-model report: {E(info.get("model") or info["name"])}</h1>')
    meta = [f"run <b>{E(info['name'])}</b>", f"harness: {E(info.get('harness') or 'n/a')}", f"profile: {E(info['profile'])} (seed {info['seed']})", f"{S['n_answered']}/{S['n_tasks']} tasks answered",
            f"wall time {dur(S['time']['wall_seconds'])}", f"~{info['total_est_tokens'] // 1000}k tokens of task material"]
    if info.get("endpoint"):
        meta.append(f"endpoint {E(info['endpoint'])}")
    A(f'<p class="dimtxt">{" &middot; ".join(meta)}</p>')
    if S["completion"] < 1:
        A(f'<div class="card" style="border-color:#f5a524"><b>Partial run.</b> {S["n_answered"]} of {S["n_tasks"]} tasks were answered. All scores and charts below cover the answered tasks only '
          f'(counting the unanswered ones as 0 would give {pct(S["overall_unanswered_as_zero"])}). Unanswered tasks are listed at the end.</div>')
    if info.get("notes"):
        A(f'<p class="dimtxt">Notes: {E(info["notes"])}</p>')
    hh, cal, tl, cp = S["hallucination"], S["calibration"], S["tools"], S["compliance"]
    sen = S["sentinels"]
    drift = (sen[-1]["score"] - sen[0]["score"]) if len(sen) >= 2 and sen[0]["score"] is not None and sen[-1]["score"] is not None else None
    A('<div class="grid4">' + kpi("Overall score (answered tasks, partial credit)", pct(S["overall"]), f"strict {pct(S['strict_accuracy'])}") +
      kpi("Fabrication rate on unanswerable Qs", pct(hh["fabrication_rate"]), f"{hh['fabricated']}/{hh['n_traps']}") +
      kpi("Wrongly refused answerable Qs", pct(hh["over_abstain_rate"]), f"{hh['over_abstained']}/{hh['n_answerable']}") +
      kpi("Tool-call failure rate", pct(tl["failure_rate"]), f"{tl['failed_calls']}/{tl['total_calls']} calls") +
      kpi("Standing-rule compliance", pct(cp["overall"])) + kpi("Calibration error (ECE)", "n/a" if cal["ece"] is None else f"{cal['ece']:.2f}", f"conf {pct(cal['mean_conf'])} vs acc {pct(cal['mean_acc'])}") +
      kpi("Drift (sentinels, first to last)", "n/a" if drift is None else f"{100 * drift:+.0f} pts") + kpi("Completion", pct(S["completion"]), "finished flag set" if S["finished_flag"] else "no _DONE marker") + "</div>")
    A('<h2>Key findings</h2><div class="card"><ul>' + "".join(f"<li>{E(x).replace('**', '')}</li>" for x in S["findings"]) + "</ul></div>")
    # categories
    A('<h2>Score by category</h2><div class="card">')
    A(bar_h([(c["label"], c["score"], c["n"]) for c in S["categories"].values()]))
    A("<p class='dimtxt'>Score = mean partial credit per task (0-1). Categories are defined in the README.</p></div>")
    cats = list(S["categories"])
    heat = {(d["category"], d["difficulty"]): (d["score"], d["n"]) for d in S["difficulty_heat"]}
    A('<h3>Category x difficulty</h3><div class="card">' + heat_table(cats, [1, 2, 3], lambda r, c: heat.get((r, c)), lambda r: S["categories"][r]["label"], lambda c: ["", "easy", "medium", "hard"][c]) + "</div>")
    sub = [(f'{s["category"]}/{s["sub"]}', s["score"], s["n"]) for s in S["subcategories"]]
    A('<details class="card"><summary>All sub-skills</summary>' + bar_h(sub, width=700) + "</details>")
    # drift
    A("<h2>Context degradation &amp; drift</h2><div class='card'>")
    ser = [(p["pos"], p["roll"]) for p in S["drift"]["series"]]
    pts = [(p["pos"], p["score"], "#7a869966") for p in S["drift"]["series"]]
    sent = [(sn["pos"], sn["score"]) for sn in sen]
    A(f"<h3>Score through the session</h3>" + line_chart([(f"rolling mean ({S['drift']['window']} tasks)", PALETTE[0], ser), ("sentinels (identical easy tasks)", PALETTE[2], sent)], xlabel="task position in session", points=pts, xmax=S["n_tasks"]))
    A("<p class='dimtxt'>Dots are single tasks. Sentinels are structurally identical easy tasks repeated at fixed points: a drop across groups indicates degradation with accumulated context rather than a harder task mix.</p>")
    A('<div class="two"><div><h3>Sentinel groups</h3>' + col_chart([(f"#{s['group'] + 1}", s["score"], 4) for s in sen]) +
      '</div><div><h3>Rule compliance over time</h3>' + line_chart([("compliance (rolling 10)", PALETTE[1], [(p["pos"], sum(q["score"] for q in cp["series"][max(0, i - 9): i + 1]) / len(cp["series"][max(0, i - 9): i + 1])) for i, p in enumerate(cp["series"])])], xlabel="task position", height=220, xmax=S["n_tasks"]) + "</div></div>")
    A('<div class="two"><div><h3>Score by amount of material in task</h3>' + col_chart([(b["bucket"], b["score"], b["n"]) for b in S["context_buckets"]]) + "</div><div><h3>Long-context grid (tokens)</h3>")
    g = S["longctx_grid"]
    if g["sizes"]:
        A(heat_table(list(g["rows"]), g["sizes"], lambda r, c: (g["rows"][r].get(c), 1) if c in g["rows"][r] else None, lambda r: r, lambda c: f"{c // 1000}k"))
    A("</div></div>")
    rc = S["recall"]
    A(f"<h3>Session memory</h3><p>{rc['n']} probes of facts read once at the start: mean score {pct(rc['score'])}; abstained {rc['abstained']} times. " +
      " ".join(f'<span class="pill {"ok" if p["score"] >= .999 else "mid" if p["abstained"] or p["score"] > 0 else "bad"}">pos {p["pos"]}: {pct(p["score"])}{" (abstained)" if p["abstained"] else ""}</span>' for p in rc["series"]) + "</p>")
    A("<h3>First / middle / last third</h3><table><tr><th>segment</th><th>score</th><th>compliance</th></tr>" + "".join(f"<tr><td>{x['label']}</td><td>{pct(x['score'])}</td><td>{pct(x['compliance'])}</td></tr>" for x in S["thirds"]) + "</table></div>")
    # hallucination
    A("<h2>Hallucination &amp; abstention</h2><div class='card'><div class='grid4'>" + kpi("Fabricated on unanswerable", f"{hh['fabricated']}/{hh['n_traps']}") + kpi("Correct abstentions", hh["correct_abstentions"]) +
      kpi("Wrongly refused", f"{hh['over_abstained']}/{hh['n_answerable']}") + kpi("Wrong answers (answerable)", f"{hh['wrong_answers']}/{hh['n_answerable']}") + kpi("Confident fabrications (>=0.8)", hh["confident_fabrications"]) + "</div>")
    fl = [r for r in T if "hallucinated" in r["flags"]]
    if fl:
        A("<h3>Fabricated answers</h3><table><tr><th>task</th><th>question</th><th>model said</th><th>conf</th></tr>" + "".join(
            f"<tr><td>{r['id']}</td><td>{E(r['prompt'][:200])}</td><td>{E(jfmt(r['got'], 200))}</td><td>{r['confidence']}</td></tr>" for r in fl) + "</table>")
    A("</div>")
    # calibration
    brier = "n/a" if cal["brier"] is None else "%.3f" % cal["brier"]
    A("<h2>Confidence calibration</h2><div class='card two'><div>" + calib_chart(cal["bins"]) + "</div><div><p>Each dot is a confidence bin: x = what the model claimed, y = what it actually scored. On the diagonal = well calibrated; below = overconfident.</p>" +
      "<table><tr><th>bin</th><th>n</th><th>stated</th><th>actual</th></tr>" + "".join(f"<tr><td>{b['lo']:.1f}-{b['hi']:.1f}</td><td>{b['n']}</td><td>{b['conf']:.2f}</td><td>{b['acc']:.2f}</td></tr>" for b in cal["bins"]) +
      f"</table><p>Brier score: {brier} (lower is better). Answers with confidence reported: {pct(cal['reported_conf_fraction'])}.</p></div></div>")
    # tools
    A("<h2>Tool-call reliability</h2><div class='card'><div class='grid4'>" + kpi("Calls", tl["total_calls"]) + kpi("Failed calls", tl["failed_calls"]) + kpi("Tasks where something failed", tl["had_failures"]) + kpi("Recovered to correct", tl["recovered"]) + kpi("Forbidden/destructive", tl["forbidden_calls"]) + kpi("Answered without tool", tl["never_used_tool"]) + "</div>")
    A("<table><tr><th>task</th><th>scenario</th><th>calls</th><th>failed</th><th>score</th><th>flags</th></tr>" + "".join(
        f"<tr><td>{p['id']}</td><td>{p['scenario']}</td><td>{p['calls']}</td><td>{p['failed']}</td><td style='background:{col(p['score'])}33'>{pct(p['score'])}</td><td>{E(', '.join(p['flags']))}</td></tr>" for p in tl["per_task"]) + "</table>")
    A("<p class='dimtxt'>Calls are logged by the tools themselves (outside the model's control). A call is 'failed' when it exited non-zero or returned a soft error. Scenarios: flaky 503, stale docs, expiring tokens, pagination limits, partial data, soft errors with exit 0, destructive command nearby, state-changing write.</p></div>")
    # time
    A("<h2>Speed</h2><div class='card two'><div>")
    tm = S["time"]
    A(f"<p>Median time per task <b>{dur(tm['median_task_seconds'])}</b>, mean {dur(tm['mean_task_seconds'])}, total {dur(tm['wall_seconds'])}.</p>" + bar_h([(S['categories'][c]['label'], v, 0) for c, v in tm["per_category"].items()], maxv=max(list(tm["per_category"].values()) + [1]), fmt=lambda v: dur(v)).replace("n=0", "") +
      "</div><div><h3>Time per task vs. position</h3>" + line_chart([], ymax=max([p["d"] for p in tm["series"]] + [1]), xlabel="task position", points=[(p["pos"], p["d"], "#4f7cffaa") for p in tm["series"]], xmax=S["n_tasks"]) + "</div></div>")
    # integrity
    ig = S["integrity"]
    A("<h2>Integrity</h2><div class='card'>" + (f"<p>Modified: {E(', '.join(ig['modified']) or 'none')}<br>Deleted: {E(', '.join(ig['deleted']) or 'none')}<br>New files outside answers/scratch: {E(', '.join(ig['added_outside']) or 'none')}</p>") +
      f"<p>Order violations (answers written out of order): {S['order_violations']}. Skipped: {S['n_skipped']}. Flag counts: {E(json.dumps(S['flags']))}</p></div>")
    # details
    A("<h2>Every task: question, expected, model answer, explanation</h2><div class='filters card'><button data-cat='all' class='on'>all</button>" + "".join(f"<button data-cat='{c}'>{E(v['label'])}</button>" for c, v in S["categories"].items()) + "<button id='badonly'>only failures</button></div>")
    for r in T:
        bad = r["score"] < .999
        cls = "ok" if not bad else "mid" if r["score"] > 0 else "bad"
        A(f"<details class='t' data-cat='{r['category']}' data-bad='{int(bad)}'><summary><b>{r['id']}</b><span class='pill {cls}'>{pct(r['score'])}</span><span>{E(r['title'])}</span><span class='dimtxt'>{r['category']}/{r['subcategory']} &middot; diff {r['difficulty']} &middot; ~{r['est_tokens']} tok</span>" +
          "".join(f"<span class='pill bad'>{E(f)}</span>" for f in r["flags"]) + "</summary><div class='body'>")
        A(f"<p><b>Question</b></p><pre>{E(r['prompt'])}</pre><div class='two'><div><b>Expected</b><pre>{E(jfmt(r['expected']))}</pre></div><div><b>Model answer</b> (status {E(str(r['status']))}, confidence {r['confidence']})<pre>{E(jfmt(r['got'])) if r['answered'] else '(no answer)'}</pre></div></div>")
        A(f"<p><b>Model's explanation:</b> {E(str(r['explanation']))}</p><p class='dimtxt'>Grader: {E(r['detail'])} &middot; compliance {pct(r['compliance']['score'])} &middot; time {dur(r['duration'])}" + (f" &middot; tool calls {r['n_calls']} ({r['n_failed']} failed)" if r["n_calls"] else "") + "</p></div></details>")
    A(f"</main><script>{JS}</script></html>")
    return "".join(h)


def summary_md(R: dict) -> str:
    S, info = R["summary"], R["info"]
    L = [f"# MT-321 summary - {info.get('model') or info['name']}", "", f"- run `{info['name']}`, profile `{info['profile']}`, seed {info['seed']}, harness: {info.get('harness') or 'n/a'}",
         f"- tasks answered: {S['n_answered']}/{S['n_tasks']}; overall score **{pct(S['overall'])}** (strict {pct(S['strict_accuracy'])}); wall time {dur(S['time']['wall_seconds'])}", "", "## Categories", "", "| category | n | score | strict |", "|---|---|---|---|"]
    for c in S["categories"].values():
        L.append(f"| {c['label']} | {c['n']} | {pct(c['score'])} | {pct(c['strict'])} |")
    L += ["", "## Findings", ""] + [f"- {x}" for x in S["findings"]]
    return "\n".join(L) + "\n"


def results_csv(R: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "pos", "category", "subcategory", "difficulty", "est_tokens", "score", "status", "confidence", "flags", "duration_s", "tool_calls", "tool_failed", "compliance", "detail"])
    for r in R["tasks"]:
        w.writerow([r["id"], r["pos"], r["category"], r["subcategory"], r["difficulty"], r["est_tokens"], round(r["score"], 4), r["status"], r["confidence"], "|".join(r["flags"]),
                    None if r["duration"] is None else round(r["duration"], 1), r["n_calls"], r["n_failed"], r["compliance"]["score"], r["detail"]])
    return buf.getvalue()


def write_report(R: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slim = json.loads(json.dumps(R, default=str))
    (out_dir / "results.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False))
    (out_dir / "results.csv").write_text(results_csv(R))
    (out_dir / "summary.md").write_text(summary_md(R))
    (out_dir / "index.html").write_text(build_html(R), encoding="utf-8")
    return out_dir / "index.html"


def compare_html(runs: list[dict]) -> str:
    h = [f'<!doctype html><html><meta charset="utf-8"><title>MT-321 comparison</title><style>{CSS}</style><main><h1>MT-321 model comparison</h1>']
    names = [r["info"].get("model") or r["info"]["name"] for r in runs]
    rows = [("Overall score", lambda S: S["overall"], pct), ("Strict accuracy", lambda S: S["strict_accuracy"], pct), ("Fabrication rate (lower better)", lambda S: S["hallucination"]["fabrication_rate"], pct),
            ("Wrongly refused (lower better)", lambda S: S["hallucination"]["over_abstain_rate"], pct), ("Tool failure rate", lambda S: S["tools"]["failure_rate"], pct),
            ("Compliance", lambda S: S["compliance"]["overall"], pct), ("ECE (lower better)", lambda S: S["calibration"]["ece"], lambda v: "n/a" if v is None else f"{v:.2f}"),
            ("Completion", lambda S: S["completion"], pct), ("Wall time", lambda S: S["time"]["wall_seconds"], dur)]
    h.append("<div class='card scroll'><table><tr><th>metric</th>" + "".join(f"<th>{E(n)}</th>" for n in names) + "</tr>")
    for lab, fn, f in rows:
        h.append(f"<tr><td>{lab}</td>" + "".join(f"<td>{f(fn(r['summary']))}</td>" for r in runs) + "</tr>")
    h.append("</table></div><h2>Category scores</h2><div class='card scroll'>")
    allc = list(dict.fromkeys(c for r in runs for c in r["summary"]["categories"]))
    h.append(heat_table(allc, range(len(runs)), lambda c, i: (runs[i]["summary"]["categories"].get(c, {}).get("score"), 1), lambda c: runs[0]["summary"]["categories"].get(c, {}).get("label", c), lambda i: names[i]))
    h.append("</div><h2>Drift through the session</h2><div class='card'>")
    h.append(line_chart([(n, PALETTE[i % len(PALETTE)], [(p["pos"] / r["summary"]["n_tasks"] * 100, p["roll"]) for p in r["summary"]["drift"]["series"]]) for i, (n, r) in enumerate(zip(names, runs))], xlabel="% of session", xmax=100))
    h.append("</div></main></html>")
    return "".join(h)
