"""Long-context suite: needle retrieval, last-write-wins, state tracking, aggregation and multi-hop over haystacks of several sizes."""
from __future__ import annotations

import random
from datetime import date, timedelta

from ..core import Ctx, Task, est_tokens, person

SUBJ = ["The regional office", "A visiting auditor", "The night shift", "Our logistics team", "The maintenance crew", "A junior analyst",
        "The procurement desk", "The facilities group", "An external consultant", "The planning committee", "The warehouse lead", "The quality board"]
VERB = ["reviewed", "postponed", "documented", "approved", "questioned", "recalibrated", "archived", "summarised", "escalated", "rescheduled", "inspected", "forwarded"]
OBJ = ["the quarterly forecast", "a batch of returned goods", "the shared calendar", "the safety checklist", "an overdue invoice", "the pallet layout",
       "a draft of the onboarding guide", "the supplier survey", "the cold-storage log", "a set of revised drawings", "the holiday roster", "the dock schedule"]
TAIL = ["before the weekly sync.", "after a long discussion.", "without any objections.", "and asked for a follow-up.", "while the system was offline.",
        "in line with last year's practice.", "and filed the paperwork the same afternoon.", "though nobody was entirely sure why.", "during the quiet hours of the morning."]
ADJ = ["amber", "granite", "silent", "northern", "copper", "hollow", "velvet", "rapid", "pale", "ember", "marble", "cobalt"]
NOUN = ["lantern", "compass", "anvil", "beacon", "ledger", "turbine", "relay", "pylon", "kettle", "gauge", "valve", "crane"]


def sentence(rng):
    return f"{rng.choice(SUBJ)} {rng.choice(VERB)} {rng.choice(OBJ)} {rng.choice(TAIL)}"


def filler_paras(rng, chars):
    paras, n = [], 0
    while n < chars:
        p = " ".join(sentence(rng) for _ in range(rng.randint(3, 6)))
        paras.append(p)
        n += len(p) + 2
    return paras


def inject(paras, items, rng):
    """items: list of (depth 0..1, text). Insert at paragraph boundaries; returns the text and actual depths."""
    paras = list(paras)
    placed = []
    for depth, text in sorted(items, key=lambda x: -x[0]):
        idx = max(0, min(len(paras), int(depth * len(paras))))
        paras.insert(idx, text)
        placed.append(idx / max(1, len(paras)))
    return "\n\n".join(paras), placed


def code(rng):
    return f"{rng.choice('KXQZMTRV')}{rng.choice('KXQZMTRV')}-{rng.randint(1000, 9999)}-{rng.choice('ABCDEFGH')}"


def T(sub, title, prompt, key, hint, diff, text, tokens, depth=None):
    return Task(category="longctx", subcategory=sub, title=f"{title} [{tokens // 1000}k]", prompt=prompt, key=key, answer_hint=hint, difficulty=diff,
                files={"haystack.txt": text}, est_tokens=est_tokens(text), tags=[f"size:{tokens}"] + ([f"depth:{int(depth * 100)}"] if depth is not None else []))


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("longctx")
    out = []
    for size in ctx.profile["long_sizes"]:
        chars = size * 4
        # ---- needle among near-duplicate distractors
        d = rng.choice([0.1, 0.35, 0.5, 0.7, 0.9])
        pairs = rng.sample([(a, n) for a in ADJ for n in NOUN], 8)
        target = pairs[0]
        needles = [(d, f"NOTE: The calibration code for the {target[0]} {target[1]} is {code(rng)}.")]
        ans = needles[0][1].split(" is ")[-1].rstrip(".")
        for a, n in pairs[1:]:
            needles.append((rng.random(), f"NOTE: The calibration code for the {a} {n} is {code(rng)}."))
        text, _ = inject(filler_paras(rng, chars), needles, rng)
        out.append(T("needle", "Needle among distractors", f"`tasks/{{ID}}/haystack.txt` is a long operations newsletter. What is the calibration code for the **{target[0]} {target[1]}**? Give the code exactly.",
                     {"check": "value", "expected": ans}, "<string code>", 1 if size <= 16000 else 2, text, size, d))

        # ---- last-write-wins updates
        teams = [f"{rng.choice(ADJ)}-{rng.choice(NOUN)}" for _ in range(6)]
        tg = teams[0]
        base = date(2025, 1, 6)
        updates, vals = [], {}
        n_up = rng.randint(4, 6)
        for k in range(n_up):
            v = rng.randint(100, 900)
            vals[tg] = v
            updates.append((0.1 + 0.8 * (k + rng.random() * 0.5) / n_up, f"[{(base + timedelta(days=7 * k)).isoformat()}] Quota update: team {tg} now has a weekly quota of {v} units."))
        for t2 in teams[1:]:
            for k in range(rng.randint(2, 4)):
                updates.append((rng.random(), f"[{(base + timedelta(days=rng.randint(0, 40))).isoformat()}] Quota update: team {t2} now has a weekly quota of {rng.randint(100, 900)} units."))
        updates.sort(key=lambda x: x[0])
        # make dates monotonically increasing along the file so "latest" == last occurrence
        dated = []
        for i, (dp, tx) in enumerate(updates):
            body = tx.split("] ", 1)[1]
            dated.append((dp, f"[{(base + timedelta(days=3 * i)).isoformat()}] {body}"))
        final = [t for t in dated if f"team {tg} " in t[1]][-1][1]
        val = int(final.split("quota of ")[1].split(" ")[0])
        text, _ = inject(filler_paras(rng, chars), dated, rng)
        out.append(T("latest_value", "Last value wins", f"`tasks/{{ID}}/haystack.txt` contains dated quota updates (dates increase through the file). What is the **current (most recent)** weekly quota of team **{tg}**?",
                     {"check": "value", "expected": val}, "<int>", 2, text, size))

        # ---- structured log aggregation
        n_lines = max(40, chars // 70)
        users = [f"U{i:02d}" for i in range(1, 15)]
        acts = ["LOGIN", "EXPORT", "VIEW", "EDIT", "DELETE", "SHARE"]
        tgt_u, tgt_a = rng.choice(users), rng.choice(["EXPORT", "SHARE", "DELETE"])
        lines, cnt = [], 0
        t0 = date(2025, 2, 1)
        for i in range(n_lines):
            u, a = rng.choice(users), rng.choice(acts)
            dd = t0 + timedelta(days=i * 60 // n_lines)
            lines.append(f"{dd.isoformat()} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d} user={u} action={a} object=doc_{rng.randint(100, 999)}.{rng.choice(['pdf', 'csv', 'xlsx'])}")
            if u == tgt_u and a == tgt_a:
                cnt += 1
        out.append(T("aggregate", "Count events in a long log", f"`tasks/{{ID}}/haystack.txt` is an audit log, one event per line. How many events have `user={tgt_u}` **and** `action={tgt_a}`?",
                     {"check": "value", "expected": cnt}, "<int>", 2, "\n".join(lines) + "\n", size))

        # ---- state tracking narrative
        names = []
        while len(names) < 5:
            nm = person(rng).split()[0]
            if nm not in names:
                names.append(nm)
        objs = ["silver compass", "blue folder", "brass key", "sealed envelope"]
        start_hold = {o: rng.choice(names) for o in objs}
        hold, changes = dict(start_hold), {o: 0 for o in objs}
        phr = ["{a} handed the {o} to {b}.", "{b} received the {o} from {a}.", "{a} passed the {o} along to {b}.", "{a} gave the {o} to {b} at the front desk."]
        paras = filler_paras(rng, chars)
        n_tr = min(max(12, size // 500), len(paras))
        events = []
        for _ in range(n_tr):
            o = rng.choice(objs) if rng.random() < 0.55 else objs[0]
            a_, b_ = hold[o], None
            b_ = rng.choice([c for c in names if c != a_])
            events.append(rng.choice(phr).format(a=a_, b=b_, o=o))
            hold[o] = b_
            changes[o] += 1
        pos = sorted(rng.sample(range(len(paras) + 1), len(events)))
        body = list(paras)
        for off, (p_, ev) in enumerate(zip(pos, events)):
            body.insert(p_ + off, ev)
        intro = "Initial holders: " + "; ".join(f"{c} holds the {o}" for o, c in start_hold.items()) + ".\n\n"
        text = intro + "\n\n".join(body)
        tgt = "silver compass"
        out.append(T("state_tracking", "Track an object through a long story", f"`tasks/{{ID}}/haystack.txt` begins with who holds each item, then reports hand-overs between people scattered through the text (other sentences are irrelevant filler). "
                     f"Who holds the **{tgt}** at the very end, and how many times did it change hands?",
                     {"check": "value", "expected": {"final_holder": hold[tgt], "times_transferred": changes[tgt]}}, '{"final_holder": "Name", "times_transferred": <int>}', 3, text, size))

        # ---- multi-hop
        if size >= 16000:
            depts = rng.sample(["Tooling", "Inbound", "Compliance", "Metrology", "Dispatch", "Fabrication", "Records"], 5)
            people = [person(rng) for _ in range(12)]
            works = {p: rng.choice(depts) for p in people}
            heads = {dp: person(rng) for dp in depts}
            rooms = {h: f"{rng.choice('ABCDE')}{rng.randint(100, 480)}" for h in heads.values()}
            p0 = people[0]
            items = [(0.05 + 0.4 * rng.random(), f"{p} works in the {works[p]} department.") for p in people]
            items += [(0.4 + 0.3 * rng.random(), f"The {dp} department is headed by {h}.") for dp, h in heads.items()]
            items += [(0.7 + 0.28 * rng.random(), f"{h}'s office is in room {r}.") for h, r in rooms.items()]
            text, _ = inject(filler_paras(rng, chars), items, rng)
            out.append(T("multi_hop", "Three-hop fact chain", f"`tasks/{{ID}}/haystack.txt`: which **room** is the office of the head of the department where **{p0}** works?",
                         {"check": "value", "expected": rooms[heads[works[p0]]]}, "<string room>", 3, text, size))
    return out
