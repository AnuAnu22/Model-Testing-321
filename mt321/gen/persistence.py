"""Persistence & thoroughness: long, tedious, many-item tasks where laziness, skipping and drift show up as partial credit."""
from __future__ import annotations

from ..core import Ctx, Task, to_csv


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("persist")
    out = []
    n_items = ctx.profile.get("batch_items", 60)

    # 1 batch classification with explicit rules
    kws = {"BILLING": ["invoice", "refund", "charge", "payment"], "OUTAGE": ["down", "unreachable", "timeout", "crash"], "ACCESS": ["password", "login", "locked", "permission"]}
    rules = "Rules (apply in this priority order, first match wins, case-insensitive substring match):\n1. contains any of: down, unreachable, timeout, crash -> `OUTAGE`\n2. contains any of: password, login, locked, permission -> `ACCESS`\n3. contains any of: invoice, refund, charge, payment -> `BILLING`\n4. otherwise -> `OTHER`"
    pool = [w for v in kws.values() for w in v] + ["printer", "feature", "colour", "update", "question"]
    tick, exp = [], {}
    for i in range(n_items):
        words = [rng.choice(["the", "my", "our", "a"]) for _ in range(2)] + rng.sample(pool, rng.randint(1, 3)) + [rng.choice(["again", "today", "please", "urgent"])]
        rng.shuffle(words)
        txt = " ".join(words)
        tid = f"K{i + 1:03d}"
        tick.append({"ticket_id": tid, "text": txt})
        low = txt.lower()
        c = "OUTAGE" if any(w in low for w in kws["OUTAGE"]) else "ACCESS" if any(w in low for w in kws["ACCESS"]) else "BILLING" if any(w in low for w in kws["BILLING"]) else "OTHER"
        exp[tid] = c
    out.append(Task(category="persistence", subcategory="batch", title=f"Classify {n_items} tickets", difficulty=2,
                    prompt=f"`tasks/{{ID}}/tickets.csv` has {n_items} support tickets. Classify **every** ticket.\n\n{rules}\n\nAnswer: an object mapping ticket_id -> category for all tickets.",
                    files={"tickets.csv": to_csv(tick)}, key={"check": "value", "expected": exp}, answer_hint='{"K001": "OUTAGE", ...}', est_tokens=n_items * 12))

    # 2 reconcile two ledgers
    n = ctx.profile.get("recon_rows", 200)
    A = [{"id": f"L{i:04d}", "amount": round(rng.uniform(10, 2000), 2)} for i in range(1, n + 1)]
    B = [dict(r) for r in A]
    miss = sorted(rng.sample(range(n), 6))
    mism = sorted(rng.sample([i for i in range(n) if i not in miss], 7))
    for i in mism:
        B[i]["amount"] = round(B[i]["amount"] + rng.choice([-1, 1]) * rng.choice([0.01, 0.5, 12.0, 100.0]), 2)
    missing_ids = [A[i]["id"] for i in miss]
    B = [r for k, r in enumerate(B) if k not in miss]
    extras = [{"id": f"L{n + 10 + j:04d}", "amount": round(rng.uniform(10, 500), 2)} for j in range(3)]
    B += extras
    rng.shuffle(B)
    out.append(Task(category="persistence", subcategory="reconcile", title="Reconcile two ledgers", difficulty=3,
                    prompt="`tasks/{ID}/ledger_a.csv` and `ledger_b.csv` should be identical but are not. Compare them by `id` and return three **sorted** lists of ids: `missing_in_b` (in A, not in B), `extra_in_b` (in B, not in A) and `amount_mismatch` (in both, amounts differ).",
                    files={"ledger_a.csv": to_csv(A), "ledger_b.csv": to_csv(B)},
                    key={"check": "value", "expected": {"missing_in_b": sorted(missing_ids), "extra_in_b": sorted(e["id"] for e in extras), "amount_mismatch": sorted(A[i]["id"] for i in mism)}},
                    answer_hint='{"missing_in_b": [...], "extra_in_b": [...], "amount_mismatch": [...]}', est_tokens=n * 20))

    # 3 pipeline of ordered transformations
    nums = [rng.randint(-50, 99) for _ in range(40)]
    x = list(nums)
    x = [v for v in x if v % 2 == 0 or v < 0]
    x = [v * 3 + 1 for v in x]
    x = sorted(set(x), reverse=True)
    x = x[: max(1, len(x) - 3)]
    x = [v if v > 0 else -v for v in x]
    chk = sum((i + 1) * v for i, v in enumerate(x))
    out.append(Task(category="persistence", subcategory="pipeline", title="Six-step transformation pipeline", difficulty=3,
                    prompt=f"Start with this list:\n\n{nums}\n\nApply these steps **in order**:\n1. keep only values that are even **or** negative\n2. replace each value v with v*3 + 1\n3. remove duplicates and sort **descending**\n4. drop the last 3 elements\n5. replace each value by its absolute value\n6. compute the checksum = sum over 1-based position i of i * value\n\nReturn the final list and the checksum.",
                    key={"check": "value", "expected": {"final_list": x, "checksum": chk}}, answer_hint='{"final_list": [...], "checksum": <int>}'))

    # 4 many small independent questions (stamina)
    qs, ans = [], {}
    for i in range(25):
        a, b = rng.randint(11, 99), rng.randint(11, 99)
        kind = i % 5
        if kind == 0:
            qs.append(f"q{i + 1}: {a} + {b}"); ans[f"q{i + 1}"] = a + b
        elif kind == 1:
            qs.append(f"q{i + 1}: {a} * 3 - {b}"); ans[f"q{i + 1}"] = a * 3 - b
        elif kind == 2:
            qs.append(f"q{i + 1}: the larger of {a} and {b}"); ans[f"q{i + 1}"] = max(a, b)
        elif kind == 3:
            qs.append(f"q{i + 1}: the remainder of {a * 7 + b} divided by {b}"); ans[f"q{i + 1}"] = (a * 7 + b) % b
        else:
            w = rng.choice(["lantern", "meadow", "quartz", "harbor"])
            qs.append(f"q{i + 1}: the number of letters in '{w}'"); ans[f"q{i + 1}"] = len(w)
    out.append(Task(category="persistence", subcategory="stamina", title="25 small questions in one task", difficulty=1,
                    prompt="Answer **all 25** items. `answer` is an object mapping q1..q25 to integers.\n\n" + "\n".join(f"- {q}" for q in qs),
                    key={"check": "value", "expected": ans}, answer_hint='{"q1": <int>, ... "q25": <int>}'))

    # 5 cross-file consistency
    keys = [f"param_{i}" for i in range(1, 13)]
    base = {k: rng.randint(1, 99) for k in keys}
    files, bad = {}, []
    for nm in ["app", "worker", "cron", "gateway"]:
        d = dict(base)
        for k in rng.sample(keys, 2):
            d[k] = d[k] + rng.randint(1, 9)
        files[f"{nm}.conf"] = "\n".join(f"{k}={v}" for k, v in d.items()) + "\n"
        if nm != "app":
            bad += [k for k in keys if d[k] != base[k]]
    # recompute vs app.conf as reference
    app = dict(l.split("=") for l in files["app.conf"].split())
    incons = set()
    for nm in ["worker", "cron", "gateway"]:
        d = dict(l.split("=") for l in files[f"{nm}.conf"].split())
        incons |= {k for k in keys if d[k] != app[k]}
    out.append(Task(category="persistence", subcategory="cross_file", title="Cross-file configuration consistency", difficulty=3,
                    prompt="`tasks/{ID}/app.conf` is the reference. `worker.conf`, `cron.conf` and `gateway.conf` (same folder) should hold identical values. Return the sorted list of parameter names whose value differs from `app.conf` in **at least one** of the other three files.",
                    files=files, key={"check": "set", "expected": sorted(incons)}, answer_hint='["param_3", ...]'))
    return out
