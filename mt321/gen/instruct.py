"""Instruction following: exact formats and verifiable constraints."""
from __future__ import annotations

import csv
import io

from ..core import Ctx, Task, person

DIG = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def T(sub, title, prompt, key, hint, diff):
    return Task(category="instruct", subcategory=sub, title=title, prompt=prompt, key=key, answer_hint=hint, difficulty=diff)


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("instruct")
    out = []
    # 1 exact line
    recs = [(f"A{rng.randint(10, 99)}", rng.choice(["bolt", "nut", "washer", "clip", "pin", "rod"]), rng.randint(1, 60)) for _ in range(5)]
    exp = ";".join(f"{i}|{n}|{q}" for i, n, q in sorted(recs, key=lambda r: (-r[2], r[0])))
    lst = "\n".join(f"- {i}, {n}, {q}" for i, n, q in recs)
    out.append(T("exact_format", "Delimited line", f"Records (id, name, qty):\n{lst}\n\nProduce **one string**: each record as `ID|NAME|QTY`, records sorted by QTY descending (ties by ID ascending), joined with `;` and **no spaces anywhere**.",
                 {"check": "value", "expected": exp}, "<string>", 1))
    # 2 words predicate
    L, st = rng.choice([5, 6, 7]), rng.choice("bcdfgmprst")
    out.append(T("constraints", "Word list constraints", f"Give a list of exactly 5 **distinct** strings of lowercase letters, each exactly **{L} letters long**, each starting with **{st}**, in **alphabetical order**. (They do not need to be dictionary words.)",
                 {"check": "predicate", "name": "words", "params": {"n": 5, "length": L, "start": st}}, '["....", ... 5 items]', 1))
    # 3 digit transform
    txt = f"Order {rng.randint(10, 99)} ships on 2025-{rng.randint(1, 12):02d}-{rng.randint(10, 28)} from dock {rng.randint(1, 9)}"
    def tr(s):
        o, prev = "", False
        for ch in s:
            if ch.isdigit():
                o += ("-" if prev else "") + DIG[int(ch)].upper(); prev = True
            else:
                o += ch; prev = False
        return o
    out.append(T("transformation", "Digit-to-word rewriting", f"Rewrite the text below replacing **every digit** with its English word in UPPERCASE (zero, one, ... nine). When several digits are adjacent, separate their words with a single hyphen. Leave everything else unchanged.\n\n> {txt}",
                 {"check": "value", "expected": tr(txt)}, "<string>", 2))
    # 4 grouping
    ppl = [(person(rng).split()[0], rng.choice(["red", "blue", "green"])) for _ in range(9)]
    ppl = list(dict.fromkeys(ppl))
    g = {}
    for n, t in ppl:
        g.setdefault(t, []).append(n)
    exp = {t: {"members": sorted(m), "count": len(m)} for t, m in g.items()}
    out.append(T("restructure", "Group into JSON", "Group these (name, team) pairs by team. `answer` must be an object keyed by team name; each value an object with `members` (names sorted alphabetically) and `count`.\n\n" + "\n".join(f"- {n}: {t}" for n, t in ppl),
                 {"check": "value", "expected": exp}, '{"red": {"members": [...], "count": <int>}, ...}', 2))
    # 5 filter-sort
    nums = [rng.randint(5, 120) for _ in range(14)]
    out.append(T("filter_sort", "Filter and sort", f"From this list keep only numbers divisible by **neither 3 nor 5**, remove duplicates, and return them sorted **descending**.\n\n{nums}",
                 {"check": "value", "expected": sorted({n for n in nums if n % 3 and n % 5}, reverse=True)}, "[<int>, ...]", 2))
    # 6 sentence predicate
    n = rng.choice([11, 12, 13])
    w1, w2 = rng.sample(["harbor", "lantern", "winter", "copper", "river", "market"], 2)
    out.append(T("constraints", "Sentence constraints", f"Write one sentence about a quiet morning that has **exactly {n} words** (split on spaces), includes the words **{w1}** and **{w2}**, starts with a capital letter, ends with a period and contains **no digits and no commas**.",
                 {"check": "predicate", "name": "sentence", "params": {"words": n, "include": [w1, w2], "no_digits": True, "no_commas": True, "capital": True, "period": True}}, "<string>", 2))
    # 7 acrostic
    tw = rng.choice(["RIVER", "LANTERN", "HARBOR", "COPPER"])
    out.append(T("constraints", "Acrostic", f"Return a list of words whose **first letters spell {tw}** in order (one word per letter). Every word must have at least 5 letters, all lowercase, and no word may repeat.",
                 {"check": "predicate", "name": "acrostic", "params": {"target": tw, "min_len": 5}}, '["...", ...]', 2))
    # 8 csv exact
    rows = [(rng.choice(["Ng, Mai", "O'Neil", 'Ana "Ace" Lopez', "Lee"]), rng.choice(["Ops", "Fin, Risk", "R&D"]), rng.randint(10, 99)) for _ in range(4)]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["name", "dept", "score"])
    w.writerows(rows)
    lst = "\n".join(f"{i + 1}. name={r[0]!r} ; dept={r[1]!r} ; score={r[2]}" for i, r in enumerate(rows))
    out.append(T("exact_format", "CSV with quoting rules", f"Produce valid **RFC-4180 CSV text** (header `name,dept,score`, then one row per record, newline `\\n` separators, fields containing commas, quotes or newlines quoted with `\"`, embedded quotes doubled). The python reprs below show the raw values:\n\n{lst}",
                 {"check": "value", "expected": buf.getvalue().strip()}, "<string with newlines>", 3))
    # 9 lipogram
    bl = rng.choice(["e", "a", "o"])
    out.append(T("constraints", "Lipogram", f"Write one sentence of at least 8 words about the sea that never uses the letter **{bl}** (upper or lower case) and ends with a period.",
                 {"check": "predicate", "name": "sentence", "params": {"min_words": 8, "banned_letters": bl, "period": True}}, "<string>", 3))
    return out
