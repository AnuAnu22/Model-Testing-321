"""Drift sentinels: structurally identical easy tasks repeated through the session to expose degradation over time."""
from __future__ import annotations

from ..core import Ctx, Task, to_csv

WORDS = ["pylon", "quartz", "harbor", "lantern", "meadow", "copper", "violet", "ember", "gadget", "willow", "falcon", "mosaic", "nectar", "orchid", "plume"]


def make_group(ctx: Ctx, g: int) -> list[Task]:
    rng = ctx.rng(f"sentinel/{g}")
    out = []
    rows = [{"item": f"I-{rng.randint(100, 999)}", "qty": rng.randint(1, 99), "bin": f"{rng.choice('ABCD')}{rng.randint(1, 20)}"} for _ in range(8)]
    r = rng.choice(rows)
    out.append(Task(category="sentinel", subcategory="csv_lookup", title="Sentinel: small CSV lookup", prompt=f"`tasks/{{ID}}/stock.csv` is a small table. What is the `qty` of item **{r['item']}**?",
                    key={"check": "value", "expected": r["qty"]}, difficulty=1, files={"stock.csv": to_csv(rows)}, sentinel_group=g, answer_hint="<int>"))
    a, b, c = rng.randint(3, 9), rng.randint(4, 12), rng.randint(2, 8)
    out.append(Task(category="sentinel", subcategory="arithmetic", title="Sentinel: three-step arithmetic", prompt=f"A crate holds {a} boxes, each box holds {b} items. A shop receives {c} crates and then sells {rng.randint(1, 9)} items... "
                    "ignore that last sentence - it is unfinished. How many items did the shop receive in total?", key={"check": "value", "expected": a * b * c}, difficulty=1, sentinel_group=g, answer_hint="<int>"))
    ws = rng.sample(WORDS, 6)
    out.append(Task(category="sentinel", subcategory="sort_words", title="Sentinel: sort a list", prompt=f"Sort these words alphabetically (a to z) and return them as a list: {', '.join(ws)}",
                    key={"check": "value", "expected": sorted(ws)}, difficulty=1, sentinel_group=g, answer_hint='["w1", ... 6 words]'))
    para = " ".join(rng.choice(WORDS) for _ in range(40))
    ch = rng.choice("aeop")
    out.append(Task(category="sentinel", subcategory="count_words", title="Sentinel: count words by initial", prompt=f"How many words in this text start with the letter **{ch}**?\n\n> {para}",
                    key={"check": "value", "expected": sum(1 for w in para.split() if w.startswith(ch))}, difficulty=1, sentinel_group=g, answer_hint="<int>"))
    return out
