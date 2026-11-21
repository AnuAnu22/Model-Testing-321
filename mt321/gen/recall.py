"""Session-memory probes. A briefing is read once at the start; later probes ask for facts *from memory*."""
from __future__ import annotations

from ..core import Ctx, Task, person


def generate(ctx: Ctx) -> dict:
    rng = ctx.rng("recall")
    facts = [
        ("codename", "Project codename", f"{rng.choice(['HOLLOW', 'AMBER', 'COBALT', 'GRANITE'])}{rng.choice(['MERE', 'FELL', 'HAVEN', 'WICK'])}-{rng.randint(10, 99)}"),
        ("rally", "Emergency rally point", f"Dock {rng.randint(2, 9)}{rng.choice('ABCD')}"),
        ("ext", "Escalation phone extension", str(rng.randint(3000, 8999))),
        ("kickoff", "Kickoff date", f"2025-{rng.randint(10, 12)}-{rng.randint(10, 28)}"),
        ("budget", "Budget ceiling (EUR)", str(rng.randrange(20000, 90000, 500))),
        ("contact", "Primary contact", person(rng)),
        ("backup", "Backup contact", person(rng)),
        ("safeword", "Verification phrase", f"{rng.choice(['tangerine', 'basalt', 'juniper', 'saffron'])}-{rng.choice(['lattice', 'harbor', 'ember', 'quartz'])}"),
        ("room", "Lab room", f"R-{rng.randint(100, 480)}"),
        ("team", "Maximum team size", str(rng.randint(5, 14))),
    ]
    body = "# Project briefing (read once, carefully)\n\nLater tasks may ask about these facts **from memory**.\n\n" + "\n".join(f"- **{lab}:** {val}" for _, lab, val in facts) + "\n"
    brief = Task(category="recall", subcategory="briefing", title="Read the briefing", answer_hint='"ack"',
                 prompt="Read `tasks/{ID}/briefing/BRIEFING.md` carefully. Later tasks will ask about its contents **from memory** (you will be asked not to re-open it). When you have read it, answer `\"ack\"`.",
                 key={"check": "value", "expected": "ack"}, files={"briefing/BRIEFING.md": body}, difficulty=1, tags=["recall_setup"])
    fm = {k: (lab, val) for k, lab, val in facts}
    groups = [("codename", "rally"), ("ext", "kickoff"), ("budget", "contact"), ("backup", "safeword"), ("room", "team")]
    probes = []
    for i, g in enumerate(groups):
        qs = ", ".join(f"the **{fm[k][0].lower()}**" for k in g)
        probes.append(Task(category="recall", subcategory="memory_probe", title=f"Memory probe {i + 1}",
                           prompt=f"From the briefing you read at the start of this session, what are {qs}?\n\n**Answer from memory. Do not re-open `briefing/BRIEFING.md` or search for it.** If you genuinely cannot remember, use the cannot-answer rule rather than guessing.",
                           key={"check": "value", "expected": {k: fm[k][1] for k in g}}, answer_hint="{" + ", ".join(f'"{k}": "..."' for k in g) + "}",
                           difficulty=2, tags=["recall_probe"]))
    final = Task(category="recall", subcategory="memory_probe", title="Memory probe - everything",
                 prompt="One last time, **from memory** (do not re-open the briefing): list all ten briefing facts.",
                 key={"check": "value", "expected": {k: v for k, _, v in facts}}, answer_hint="{" + ", ".join(f'"{k}": "..."' for k, _, _ in facts) + "}",
                 difficulty=3, tags=["recall_probe", "recall_final"])
    return {"briefing": brief, "probes": probes, "final": final}
