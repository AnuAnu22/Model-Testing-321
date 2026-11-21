"""Procedurally generated reasoning & math problems with exact answers."""
from __future__ import annotations

import itertools
import math
from datetime import date, timedelta
from fractions import Fraction

from ..core import Ctx, Task, person


def T(sub, title, prompt, key, hint, diff):
    return Task(category="reasoning", subcategory=sub, title=title, prompt=prompt, key=key, answer_hint=hint, difficulty=diff)


def logic_puzzle(rng):
    names = ["Alma", "Boris", "Chen"]
    attrs = {"pet": ["cat", "dog", "parrot"], "color": ["red", "green", "blue"], "drink": ["tea", "coffee", "milk"]}
    sol = {k: rng.sample(v, 3) for k, v in attrs.items()}  # sol[k][i] = value for names[i]
    facts = []  # (kind, ...) true statements
    for k, vs in sol.items():
        for i, v in enumerate(vs):
            facts.append(("has", names[i], k, v))
            for j, w in enumerate(vs):
                if j != i:
                    facts.append(("not", names[j], k, v))
    for i in range(3):
        for k1, k2 in itertools.permutations(attrs, 2):
            facts.append(("link", k1, sol[k1][i], k2, sol[k2][i]))

    def consistent(assign, cl):
        # assign: dict attr -> tuple of values by person index
        t = cl[0]
        if t == "has":
            return assign[cl[2]][names.index(cl[1])] == cl[3]
        if t == "not":
            return assign[cl[2]][names.index(cl[1])] != cl[3]
        k1, v1, k2, v2 = cl[1:]
        return assign[k1].index(v1) == assign[k2].index(v2)

    perms = {k: list(itertools.permutations(v)) for k, v in attrs.items()}

    def count(clues):
        n = 0
        for a in perms["pet"]:
            for b in perms["color"]:
                for c in perms["drink"]:
                    asg = {"pet": a, "color": b, "drink": c}
                    if all(consistent(asg, cl) for cl in clues):
                        n += 1
                        if n > 1:
                            return n
        return n
    rng.shuffle(facts)
    clues = []
    for f in facts:
        clues.append(f)
        if count(clues) == 1:
            break
    # prune redundant clues
    for f in list(clues):
        trial = [c for c in clues if c is not f]
        if count(trial) == 1:
            clues = trial

    def txt(cl):
        if cl[0] == "has":
            return f"{cl[1]}'s {cl[2]} is {'the ' if False else ''}{cl[3]}." if cl[2] != "pet" else f"{cl[1]} owns the {cl[3]}."
        if cl[0] == "not":
            return f"{cl[1]}'s {cl[2]} is not {cl[3]}." if cl[2] != "pet" else f"{cl[1]} does not own the {cl[3]}."
        d = {"pet": "the {} owner", "color": "the person who likes {}", "drink": "the {} drinker"}
        a = d[cl[1]].format(cl[2])
        b = {"pet": "owns the {}", "color": "likes {}", "drink": "drinks {}"}[cl[3]].format(cl[4])
        return f"{a.capitalize()} {b}." if cl[1] != "color" else f"The person who likes {cl[2]} {b}."
    exp = {names[i]: {k: sol[k][i] for k in attrs} for i in range(3)}
    return names, attrs, [txt(c) for c in clues], exp


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("reasoning")
    out = []
    # work rate
    a, b = rng.choice([(6, 3), (12, 4), (10, 15), (8, 24), (9, 18)])
    out.append(T("word_problem", "Combined work rate", f"Pump A can empty a tank in {a} hours; pump B alone can empty it in {b} hours. Running together, how many hours to empty the tank? (2 decimals)",
                 {"check": "value", "expected": round(a * b / (a + b), 2), "tol_abs": 0.011}, "<float>", 1))
    # date arithmetic
    d0 = date(2025, rng.randint(1, 12), rng.randint(1, 28))
    n = rng.randint(100, 900)
    d1 = d0 + timedelta(days=n)
    out.append(T("dates", "Date arithmetic", f"What calendar date is exactly **{n} days after {d0.isoformat()}**, and what day of the week is it? (`date` as YYYY-MM-DD, `weekday` as full English name)",
                 {"check": "value", "expected": {"date": d1.isoformat(), "weekday": d1.strftime("%A")}}, '{"date": "YYYY-MM-DD", "weekday": "Monday"}', 2))
    # compound interest
    P, r, y = rng.randrange(2000, 20000, 500), rng.choice([3.6, 4.8, 6.0, 7.2]), rng.choice([3, 5, 7])
    val = P * (1 + r / 100 / 12) ** (12 * y)
    out.append(T("finance", "Compound interest", f"{P} is invested at {r}% nominal annual interest compounded **monthly** for {y} years. What is the final balance, rounded to 2 decimals?",
                 {"check": "value", "expected": round(val, 2), "tol_abs": 0.02}, "<float>", 2))
    # base conversion
    x, yv = rng.randint(200, 2000), rng.randint(200, 2000)
    def tobase(v, b):
        s = ""
        while v:
            s = "0123456789"[v % b] + s
            v //= b
        return s or "0"
    out.append(T("number_systems", "Base conversion", f"Compute {x} + {yv} in decimal, then give the result in base 7 and in base 2 (strings of digits, no prefixes).",
                 {"check": "value", "expected": {"base7": tobase(x + yv, 7), "base2": tobase(x + yv, 2)}}, '{"base7": "...", "base2": "..."}', 2))
    # logic puzzle
    names, attrs, clues, exp = logic_puzzle(rng)
    out.append(T("logic", "Logic grid puzzle", "Alma, Boris and Chen each have exactly one pet (cat, dog, parrot), one favourite color (red, green, blue) and one favourite drink (tea, coffee, milk), all different between people. Clues:\n\n"
                 + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(clues)) + "\n\nThe puzzle has exactly one solution. Give each person's pet, color and drink.",
                 {"check": "value", "expected": exp}, '{"Alma": {"pet": "..", "color": "..", "drink": ".."}, "Boris": {...}, "Chen": {...}}', 3))
    # recurrence
    k = rng.randint(10, 14)
    a0 = rng.randint(2, 6)
    seq = [a0]
    for i in range(2, k + 1):
        seq.append(seq[-1] * 2 - i)
    out.append(T("sequences", "Recurrence", f"A sequence has a_1 = {a0} and a_n = 2*a_(n-1) - n for n >= 2. What is a_{k}?", {"check": "value", "expected": seq[-1]}, "<int>", 2))
    # probability
    tgt = rng.randint(6, 9)
    cnt = sum(1 for p in itertools.product(range(1, 7), repeat=2) if sum(p) >= tgt and 6 in p)
    cond = sum(1 for p in itertools.product(range(1, 7), repeat=2) if sum(p) >= tgt)
    fr = Fraction(cnt, cond)
    out.append(T("probability", "Conditional probability", f"Two fair six-sided dice are rolled. Given that the sum is at least {tgt}, what is the probability that at least one die shows a 6? Give a reduced fraction as a string like `3/7`.",
                 {"check": "value", "expected": f"{fr.numerator}/{fr.denominator}"}, '"p/q"', 3))
    # critical path
    tasks = {}
    names_t = ["A", "B", "C", "D", "E", "F", "G"]
    for i, t in enumerate(names_t):
        deps = rng.sample(names_t[:i], min(i, rng.randint(0, 2))) if i else []
        tasks[t] = (rng.randint(2, 9), deps)
    fin = {}
    for t in names_t:
        fin[t] = tasks[t][0] + max([fin[d] for d in tasks[t][1]] or [0])
    desc = "\n".join(f"- {t}: {d} days, after {', '.join(dp) if dp else 'nothing (starts immediately)'}" for t, (d, dp) in tasks.items())
    out.append(T("scheduling", "Critical path", f"Tasks can run in parallel unless a dependency forbids it. What is the minimum total number of days to finish all tasks?\n\n{desc}",
                 {"check": "value", "expected": max(fin.values())}, "<int>", 3))
    # counting 4-digit numbers
    m = rng.choice([5, 4, 3])
    cnt = sum(1 for v in range(1000, 10000) if len(set(str(v))) == 4 and v % m == 0)
    out.append(T("combinatorics", "Counting numbers", f"How many 4-digit numbers (1000-9999) have **all four digits different** and are divisible by {m}?", {"check": "value", "expected": cnt}, "<int>", 3))
    # round trip speed
    v1, v2 = rng.choice([(30, 60), (40, 60), (20, 30), (45, 90)])
    hm = 2 * v1 * v2 / (v1 + v2)
    out.append(T("word_problem", "Average speed trap", f"A car drives to a town at {v1} km/h and returns along the same road at {v2} km/h. What is the average speed for the whole round trip in km/h? (2 decimals)",
                 {"check": "value", "expected": round(hm, 2), "tol_abs": 0.011}, "<float>", 2))
    # modular
    base, ex = rng.choice([7, 13, 17, 19]), rng.randint(150, 900)
    out.append(T("number_theory", "Last two digits", f"What are the last two digits of {base}^{ex}? Give as a 2-character string like `07`.", {"check": "value", "expected": f"{pow(base, ex, 100):02d}"}, '"NN"', 3))
    # interval scheduling
    ivs = sorted({(s := rng.randint(0, 20), s + rng.randint(1, 6)) for _ in range(12)})
    best, endt = 0, -1
    for s, e in sorted(ivs, key=lambda x: (x[1], x[0])):
        if s >= endt:
            best += 1
            endt = e
    out.append(T("scheduling", "Max non-overlapping meetings", f"Meetings as (start, end) in hours: {ivs}. A meeting that ends at hour h and one that starts at hour h do not overlap. What is the maximum number of meetings one person can attend?",
                 {"check": "value", "expected": best}, "<int>", 2))
    # letter counting
    words = ["strawberry", "irregular", "carrier", "referral", "mirror", "terror", "barrier", "overrun"]
    sent = " ".join(rng.choice(words) for _ in range(9))
    ch = "r"
    out.append(T("precision", "Count a letter", f"How many times does the letter **r** appear (case-insensitive) in this text? `{sent}`", {"check": "value", "expected": sent.count(ch)}, "<int>", 2))
    # big multiplication
    p, q = rng.randint(1000, 9999), rng.randint(1000, 9999)
    out.append(T("arithmetic", "Four-digit product", f"Compute {p} x {q} exactly.", {"check": "value", "expected": p * q, "tol_abs": 0.5, "tol_rel": 0}, "<int>", 1))
    # unit chain
    kmh = rng.randint(40, 130)
    out.append(T("units", "Unit conversion chain", f"A train travels at {kmh} km/h. How far does it travel in 25 minutes and 30 seconds, in metres? (nearest integer)", {"check": "value", "expected": round(kmh * 1000 / 3600 * (25 * 60 + 30)), "tol_abs": 1.01}, "<int>", 2))
    # percent change chain
    v0 = rng.randrange(200, 900, 10)
    ch1, ch2 = rng.choice([10, 15, 20]), rng.choice([10, 20, 25])
    out.append(T("word_problem", "Successive percentage changes", f"A price of {v0} rises by {ch1}%, then the new price falls by {ch2}%. What is the final price, and what is the overall percentage change from the original? (2 decimals each)",
                 {"check": "value", "expected": {"final_price": round(v0 * (1 + ch1 / 100) * (1 - ch2 / 100), 2), "overall_change_pct": round(((1 + ch1 / 100) * (1 - ch2 / 100) - 1) * 100, 2)}, "tol_abs": 0.011},
                 '{"final_price": <float>, "overall_change_pct": <float>}', 2))
    return out
