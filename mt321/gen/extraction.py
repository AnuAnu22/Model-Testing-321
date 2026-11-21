"""Structured extraction from messy text, including fields that are genuinely absent (must be null)."""
from __future__ import annotations

from datetime import date, timedelta

from ..core import Ctx, Task, company, person

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def fmt_date(d, style):
    return [f"{MONTHS[d.month - 1]} {d.day}, {d.year}", f"{d.day}-{MONTHS[d.month - 1][:3]}-{d.year}", f"{d.year}.{d.month:02d}.{d.day:02d}"][style]


def fmt_money(v, style):
    return [f"${v:,.2f}", f"EUR {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), f"{v:,.2f} USD".replace(",", " ")][style]


def invoice_text(rng, i):
    d = date(2025, 1, 1) + timedelta(days=rng.randint(0, 250))
    vendor = company(rng)
    total = round(rng.uniform(120, 9800), 2)
    ds, ms = rng.randint(0, 2), rng.randint(0, 2)
    po = f"PO-{rng.randint(10000, 99999)}" if rng.random() < 0.6 else None
    no = f"INV-{rng.randint(1000, 9999)}"
    lines = [f"{vendor.upper()}", f"Invoice number: {no}", f"Issued: {fmt_date(d, ds)}"]
    if po:
        lines.append(f"Your order ref: {po}")
    lines += [f"Subtotal and tax included", f"TOTAL DUE: {fmt_money(total, ms)}", "Thank you for your business."]
    cur = ["USD", "EUR", "USD"][ms]
    return no, "\n".join(lines), {"invoice_no": no, "vendor": vendor, "date": d.isoformat(), "total": total, "currency": cur, "po_number": po}


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("extract")
    out = []
    for k in range(2):
        docs, exp = [], []
        for i in range(6):
            no, txt, e = invoice_text(rng, i)
            docs.append(f"----- document {i + 1} -----\n{txt}")
            exp.append(e)
        out.append(Task(category="extraction", subcategory="invoices", title=f"Invoice batch {k + 1}", difficulty=2,
                        prompt="`tasks/{ID}/invoices.txt` holds 6 invoices in mixed formats. For each, extract `invoice_no`, `vendor` (as printed, title case is fine), `date` (ISO YYYY-MM-DD), `total` (a plain number; decimal point, no thousands separators), `currency` (USD or EUR) and `po_number` "
                               "(the customer order reference; **null if the invoice has none**). Return a list in document order.\n\nDates in the form `2025.03.12` are year.month.day. `EUR 1.234,50` means 1234.50 euros.",
                        files={"invoices.txt": "\n\n".join(docs) + "\n"},
                        key={"check": "table", "expected": exp, "keys": ["invoice_no"], "ordered": False},
                        answer_hint='[{"invoice_no": "..", "vendor": "..", "date": "YYYY-MM-DD", "total": <float>, "currency": "USD|EUR", "po_number": "..."|null}, ...]'))
    # meeting notes -> action items
    ppl = [person(rng).split()[0] for _ in range(4)]
    ppl = list(dict.fromkeys(ppl))
    items, notes = [], ["MEETING NOTES - weekly sync", ""]
    for i in range(6):
        o = ppl[i % len(ppl)]
        due = date(2025, 11, 1) + timedelta(days=rng.randint(0, 40))
        task = rng.choice(["update the roadmap", "send the revised quote", "book the audit slot", "fix the dock scheduler", "review the SOP draft", "close out PO backlog"])
        if i in (1, 4):
            notes.append(f"Discussion: {o} mentioned they might {task} at some point, nothing decided.")
            continue
        notes.append(rng.choice([f"ACTION: {o} to {task} by {due.isoformat()}.", f"{o} will {task} - due {due.strftime('%d %B %Y').lstrip('0')}. (action item)"]))
        items.append({"owner": o, "task": task, "due": due.isoformat()})
        notes.append("Some unrelated chatter about lunch plans.")
    out.append(Task(category="extraction", subcategory="action_items", title="Action items from notes", difficulty=2,
                    prompt="From `tasks/{ID}/notes.txt` extract the **committed action items** (a person explicitly assigned a task **with a due date**). Ignore tentative remarks. For each give `owner`, `task` (the verb phrase exactly as written, e.g. `update the roadmap`) and `due` (ISO date).",
                    files={"notes.txt": "\n".join(notes) + "\n"}, key={"check": "table", "expected": items, "keys": ["owner", "task"]},
                    answer_hint='[{"owner": "Name", "task": "..", "due": "YYYY-MM-DD"}, ...]'))
    # email thread latest agreement
    d1, d2, d3 = [date(2025, 12, 1) + timedelta(days=rng.randint(0, 20)) for _ in range(3)]
    hrs = [9, 10, 14, 15]
    t1, t2, t3 = rng.sample(hrs, 3)
    a, b = ppl[0], ppl[1]
    mail = (f"From: {a}\nSubject: kickoff\n\nCan we do {d1.isoformat()} at {t1}:00?\n\n---\nFrom: {b}\nSubject: Re: kickoff\n\nThat clashes with my travel. How about {d2.isoformat()} at {t2}:00?\n\n---\n"
            f"From: {a}\nSubject: Re: Re: kickoff\n\nI can't do {d2.isoformat()}. Let's move to {d3.isoformat()} at {t3}:00 instead.\n\n---\nFrom: {b}\nSubject: Re: Re: Re: kickoff\n\nPerfect, {d3.isoformat()} works for me. I will send the invite for {t3}:00.\n")
    out.append(Task(category="extraction", subcategory="thread_state", title="Latest agreed meeting time", difficulty=2,
                    prompt="In `tasks/{ID}/thread.txt`, what date and hour (24h) was the kickoff meeting finally **agreed**? Return `date` (ISO) and `hour` (int).",
                    files={"thread.txt": mail}, key={"check": "value", "expected": {"date": d3.isoformat(), "hour": t3}}, answer_hint='{"date": "YYYY-MM-DD", "hour": <int>}'))
    # phone normalisation
    nums = []
    for _ in range(6):
        a_, b_, c_ = rng.randint(201, 989), rng.randint(200, 989), rng.randint(1000, 9999)
        style = rng.randint(0, 3)
        raw = [f"({a_}) {b_}-{c_}", f"{a_}.{b_}.{c_}", f"+1 {a_} {b_} {c_}", f"1-{a_}-{b_}-{c_}"][style]
        nums.append({"raw": raw, "e164": f"+1{a_}{b_}{c_}"})
    out.append(Task(category="extraction", subcategory="normalise", title="Phone normalisation", difficulty=1,
                    prompt="Normalise these US phone numbers to E.164 (`+1` followed by 10 digits, no spaces or punctuation). Return a list of objects `{raw, e164}` in the same order.\n\n" + "\n".join(f"- {n['raw']}" for n in nums),
                    key={"check": "table", "expected": nums, "keys": ["raw"]}, answer_hint='[{"raw": "..", "e164": "+1..........."}, ...]'))
    return out
