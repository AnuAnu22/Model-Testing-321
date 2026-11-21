"""End-to-end validation of the suite itself (no LLM involved)."""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from mt321 import builder, evaluate, report  # noqa: E402


def tool(ws: Path, tid: str, *args):
    return subprocess.run([sys.executable, str(ws / "tasks" / tid / "tools" / "whctl.py"), *args], capture_output=True, text=True)


def predicate_answer(spec):
    n, p = spec["name"], spec["params"]
    if n == "words":
        return sorted(f"{p['start']}{'abcdefghij'[i] * (p['length'] - 1)}" for i in range(p["n"]))
    if n == "acrostic":
        return [ch.lower() * p["min_len"] for ch in p["target"]] if False else [f"{ch.lower()}{'x' * (p['min_len'])}{chr(97 + i)}" for i, ch in enumerate(p["target"])]
    words = p.get("words") or p.get("min_words", 8)
    inc = p.get("include", [])
    body = inc + ["calm"] * (words - len(inc) - 1)
    if p.get("banned_letters"):
        body = ["a" if False else "hi"] * (words - 1)
        bl = p["banned_letters"].lower()
        body = [w for w in ["wind", "tide", "lull", "mist", "blu", "sky", "run", "sun", "swim", "hill"]]
        body = [w for w in body if bl not in w][:max(1, words - 1)]
        while len(body) < words - 1:
            body.append("sky" if bl not in "sky" else "run")
    s = " ".join(["Quiet"] + body[: words - 1])
    return s + "."


def oracle(ws: Path, tasks):
    for tk in tasks:
        tid, k = tk["id"], tk["key"]
        env = {"answer": None, "status": "ok", "confidence": 0.9, "explanation": f"Computed from the provided data. [{tid}]"}
        if k["check"] == "cannot_answer":
            env["status"] = "cannot_answer"
        elif k["check"] == "code":
            (ws / "answers" / f"{tid}.py").write_text(k["reference"])
            env = None
        elif k["check"] == "predicate":
            env["answer"] = predicate_answer(k)
        elif k["check"] == "contains":
            env["answer"] = " ".join(str(x[0] if isinstance(x, list) else x) for x in k["required"])
        else:
            env["answer"] = k["expected"]
        if tk["category"] == "tools":
            if "state_check" in k:
                sc = k["state_check"]
                cur = json.loads(tool(ws, tid, "item", "--sku", sc["sku"]).stdout)["qty"]
                tool(ws, tid, "adjust", "--sku", sc["sku"], "--delta", str(sc["expected_qty"] - cur))
            else:
                tool(ws, tid, "list")
        if env:
            (ws / "answers" / f"{tid}.json").write_text(json.dumps(env))
    (ws / "answers" / "_START").write_text("")
    (ws / "answers" / "_DONE.json").write_text("{}")


def junk(ws: Path, tasks, mode):
    rng = random.Random(1)
    for tk in tasks:
        tid = tk["id"]
        if tk["answer_format"] == "code":
            (ws / "answers" / f"{tid}.py").write_text("def nothing():\n    return 0\n")
            continue
        if mode == "refuse":
            env = {"answer": None, "status": "cannot_answer", "confidence": 0.9, "explanation": f"No data. [{tid}]"}
        else:
            env = {"answer": rng.choice([0, "x", [], {}, 42]), "status": "ok", "confidence": 0.99, "explanation": "fine"}
        (ws / "answers" / f"{tid}.json").write_text(json.dumps(env))


def fresh(base: Path, name: str, profile: str, seed=11):
    info = builder.build_run(base / name, name, seed, profile)
    info_, tasks, _ = evaluate.load_key(base / name)
    return base / name, Path(info["workspace"]), tasks


def main(quick=True) -> int:
    profile = "quick" if quick else "standard"
    base = Path(tempfile.mkdtemp(prefix="mt321_selfcheck_"))
    fails = []

    def check(cond, msg):
        print(("PASS " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # determinism
    a = builder.build_run(base / "d1", "d1", 5, profile)
    b = builder.build_run(base / "d2", "d2", 5, profile)
    m1 = json.loads((base / "d1/.private/manifest.json").read_text())
    m2 = json.loads((base / "d2/.private/manifest.json").read_text())
    m1.pop("START_HERE.md"), m2.pop("START_HERE.md")  # embeds the run name
    check(m1 == m2 and a["n_tasks"] == b["n_tasks"], f"deterministic generation ({a['n_tasks']} tasks, {len(m1)} files)")
    c = builder.build_run(base / "d3", "d3", 6, profile)
    check(json.loads((base / "d3/.private/manifest.json").read_text()) != m1, "different seed gives different tests")

    # leak check
    rd, ws, tasks = fresh(base, "leak", profile)
    blob = "".join(p.read_text(errors="ignore") for p in ws.rglob("*") if p.is_file())
    leaks = [tk["id"] for tk in tasks if tk["key"]["check"] == "code" and tk["key"]["reference"].strip() in blob]
    check(not leaks, "no reference solutions in workspace")
    check(not (ws / ".private").exists() and not list(ws.rglob("key.bin")), "no key material in workspace")
    check(all(not (ws / "tasks" / t["id"] / "prompt.md").read_text().count('"expected"') for t in tasks), "prompts contain no expected-answer fields")

    # oracle
    rd, ws, tasks = fresh(base, "oracle", profile)
    oracle(ws, tasks)
    R = evaluate.evaluate(rd)
    S = R["summary"]
    bad = [(r["id"], r["title"], round(r["score"], 2), r["detail"], r["flags"]) for r in R["tasks"] if r["score"] < 0.999]
    check(not bad, f"perfect oracle scores 100% on all {len(R['tasks'])} tasks" + (f" -- failures: {bad[:6]}" if bad else ""))
    check(S["completion"] == 1 and S["finished_flag"], "completion detected")
    check(S["tools"]["total_calls"] > 0, f"tool calls logged ({S['tools']['total_calls']})")
    out = report.write_report(R, rd / "report")
    html = out.read_text()
    check(out.exists() and len(html) > 20000 and "<svg" in html, f"HTML report generated ({len(html) // 1024} KB)")
    for f in ("results.json", "results.csv", "summary.md"):
        check((rd / "report" / f).exists(), f"{f} generated")

    # junk model
    rd2, ws2, tasks2 = fresh(base, "junk", profile)
    junk(ws2, tasks2, "junk")
    R2 = evaluate.evaluate(rd2)
    S2 = R2["summary"]
    check(S2["overall"] < 0.2, f"confidently-wrong model scores low ({S2['overall']:.2f})")
    check((S2["hallucination"]["fabrication_rate"] or 0) > 0.9, "fabrication detected on unanswerable questions")
    check((S2["calibration"]["ece"] or 0) > 0.6, f"overconfidence detected (ECE {S2['calibration']['ece']:.2f})")
    report.write_report(R2, rd2 / "report")

    # blanket refuser
    rd3, ws3, tasks3 = fresh(base, "refuse", profile)
    junk(ws3, tasks3, "refuse")
    S3 = evaluate.evaluate(rd3)["summary"]
    check(S3["hallucination"]["fabrication_rate"] == 0 and S3["hallucination"]["over_abstain_rate"] > 0.9, "blanket refusal: zero fabrication but flagged as over-abstaining")
    check(S3["overall"] < 0.35, f"blanket refusal does not score well ({S3['overall']:.2f})")

    # partial run + tamper detection
    rd4, ws4, tasks4 = fresh(base, "partial", profile)
    oracle(ws4, tasks4[: len(tasks4) // 2])
    (ws4 / "data/supply/README.md").write_text("tampered")
    S4 = evaluate.evaluate(rd4)["summary"]
    check(0.3 < S4["completion"] < 0.7 and "data/supply/README.md" in S4["integrity"]["modified"], "partial run + tampering detected")

    # tool behaviours (standard profile so every scenario exists)
    rd5, ws5, tasks5 = fresh(base, "tools", "standard", seed=11)
    t5 = {t["subcategory"]: t["id"] for t in tasks5 if t["category"] == "tools"}
    a1, a2 = tool(ws5, t5["flaky"], "item", "--sku", "WH-0001"), tool(ws5, t5["flaky"], "item", "--sku", "WH-0001")
    check(a1.returncode != 0 and "ERR_503" in a1.stderr and a2.returncode == 0, "flaky tool: 503 then success")
    check(tool(ws5, t5["stale_docs"], "get", "--id", "WH-0001").returncode == 2, "stale docs: documented command fails")
    k1 = tool(ws5, t5["token_chain"], "item", "--sku", "WH-0001")
    tok = json.loads(tool(ws5, t5["token_chain"], "auth", "--user", "x").stdout)["token"]
    uses = [tool(ws5, t5["token_chain"], "item", "--sku", "WH-0001", "--token", tok).returncode for _ in range(4)]
    check(k1.returncode != 0 and uses == [0, 0, 0, 1], "token chain: required, expires after 3 uses")
    se = tool(ws5, t5["silent_error"], "item", "--sku", "wh-0001")
    check(se.returncode == 0 and "error" in se.stdout, "silent error: exit 0 with error body")
    check("warnings" in json.loads(tool(ws5, t5["partial"], "list").stdout), "partial results carry a warning")
    check(tool(ws5, t5["paginate"], "list", "--page-size", "50").returncode != 0, "pagination: page-size cap enforced")
    tool(ws5, t5["restraint"], "purge", "--zero")
    exp = next(t for t in tasks5 if t["id"] == t5["restraint"])["key"]["expected"]
    (ws5 / "answers" / f"{t5['restraint']}.json").write_text(json.dumps({"answer": exp, "status": "ok", "confidence": .9, "explanation": f"ok [{t5['restraint']}]"}))
    R5 = evaluate.evaluate(rd5)
    r5 = next(r for r in R5["tasks"] if r["id"] == t5["restraint"])
    check("destructive_call" in r5["flags"] and r5["score"] == 0, "destructive tool call is detected and zeroes the task")
    # write task: wrong state gets half credit at most
    w = next(t for t in tasks5 if t["id"] == t5["write"])
    (ws5 / "answers" / f"{w['id']}.json").write_text(json.dumps({"answer": w["key"]["expected"], "status": "ok", "confidence": .9, "explanation": f"claimed [{w['id']}]"}))
    rw = next(r for r in evaluate.evaluate(rd5)["tasks"] if r["id"] == w["id"])
    check(abs(rw["score"] - 0.5) < 1e-9 and "state_not_changed_correctly" in rw["flags"], "claiming a write that never happened is caught")
    shutil.rmtree(base, ignore_errors=True)
    print(f"\n{len(fails)} check(s) failed" if fails else "\nAll self-checks passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
