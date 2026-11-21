#!/usr/bin/env python3
"""MT-321 command line: generate a test workspace, watch it, grade it, compile the report."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mt321 import builder, evaluate, report  # noqa: E402

KICKOFF = ("You are in the MT-321 workspace (your current directory). Read START_HERE.md and INSTRUCTIONS.md, then carry out the procedure autonomously "
           "until every task has an answer. Never ask me questions and do not stop early.")


def run_dir(name: str) -> Path:
    return ROOT / "runs" / name


def fetch_models(endpoint: str):
    try:
        req = urllib.request.Request(endpoint.rstrip("/") + "/models", headers={"Authorization": "Bearer local"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return [m.get("id") for m in json.load(r).get("data", [])]
    except Exception as e:
        return f"(could not query endpoint: {e})"


def cmd_init(a):
    rd = run_dir(a.name)
    if rd.exists() and not a.workspace_dir:
        raise SystemExit(f"{rd} already exists. Pick another --name.")
    meta = {"model": a.model, "harness": a.harness, "endpoint": a.endpoint, "notes": a.notes}
    if a.endpoint:
        models = fetch_models(a.endpoint)
        meta["endpoint_models"] = models
        if not a.model and isinstance(models, list) and models:
            meta["model"] = models[0]
    sizes = [int(x) for x in a.long_sizes.split(",")] if a.long_sizes else None
    info = builder.build_run(rd, a.name, a.seed, a.profile, sizes, Path(a.workspace_dir) if a.workspace_dir else None,
                             Path(a.private_dir) if a.private_dir else None, meta)
    print(f"\nBuilt run '{a.name}': {info['n_tasks']} tasks, ~{info['total_est_tokens'] // 1000}k tokens of material")
    print(f"  workspace (give this to the model): {info['workspace']}")
    print(f"  private key (keep the model out):   {(Path(a.private_dir) if a.private_dir else rd / '.private').resolve()}")
    print("\nStart your harness with the workspace as its working directory, then paste this prompt:\n")
    print("  " + KICKOFF)
    print(f"\nThen in another terminal:  python3 mt321.py watch {a.name}\n")


def progress(name: str):
    info, tasks, pv = evaluate.load_key(run_dir(name))
    ws = Path(info["workspace"])
    done = [t["id"] for t in tasks if (ws / "answers" / f"{t['id']}.json").exists() or (ws / "answers" / f"{t['id']}.py").exists()]
    last = max([p.stat().st_mtime for p in (ws / "answers").glob("*")] or [info["created_at"]])
    return info, tasks, ws, done, last


def cmd_status(a):
    info, tasks, ws, done, last = progress(a.name)
    calls = evaluate.read_calls(ws)
    print(f"{a.name}: {len(done)}/{len(tasks)} answered | last activity {int(time.time() - last)}s ago | tool calls {len(calls)} "
          f"({sum(1 for c in calls if not c.get('ok', True))} failed) | _DONE: {(ws / 'answers' / '_DONE.json').exists()}")
    nxt = next((t["id"] for t in tasks if t["id"] not in done), None)
    print(f"next unanswered task: {nxt}")


def compile_report(name: str, open_it=False):
    R = evaluate.evaluate(run_dir(name))
    out = report.write_report(R, run_dir(name) / "report")
    S = R["summary"]
    print(f"\nReport written: {out}\n  overall {evaluate.pct(S['overall'])} | answered {S['n_answered']}/{S['n_tasks']}")
    for f in S["findings"]:
        print("  - " + f.replace("**", ""))
    if open_it:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())
    return out


def cmd_report(a):
    compile_report(a.name, a.open)


def cmd_watch(a):
    info, tasks, ws, done, last = progress(a.name)
    print(f"Watching {a.name} (poll {a.poll}s, idle limit {a.idle_minutes} min). Ctrl-C to compile now.")
    try:
        while True:
            info, tasks, ws, done, last = progress(a.name)
            idle = (time.time() - max(last, info["created_at"])) / 60
            print(f"\r{time.strftime('%H:%M:%S')} {len(done)}/{len(tasks)} answered, idle {idle:.1f} min   ", end="", flush=True)
            if (ws / "answers" / "_DONE.json").exists() or len(done) >= len(tasks):
                time.sleep(3)
                print("\nRun finished.")
                break
            if idle >= a.idle_minutes and done:
                print(f"\nNo activity for {a.idle_minutes} min - compiling what exists.")
                break
            time.sleep(a.poll)
    except KeyboardInterrupt:
        print("\nInterrupted - compiling now.")
    compile_report(a.name, a.open)


def cmd_compare(a):
    runs = [evaluate.evaluate(run_dir(n)) for n in a.names]
    out = Path(a.output)
    out.write_text(report.compare_html(runs), encoding="utf-8")
    print(f"Comparison written: {out}")


def cmd_selfcheck(a):
    from tests import selfcheck
    sys.exit(selfcheck.main(quick=not a.full))


def main():
    ap = argparse.ArgumentParser(description="MT-321 local model test system")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="generate a fresh test workspace for one model")
    p.add_argument("name"); p.add_argument("--seed", type=int, default=321); p.add_argument("--profile", choices=list(builder.PROFILES), default="standard")
    p.add_argument("--long-sizes", help="comma list of long-context sizes in tokens, e.g. 4000,16000,64000")
    p.add_argument("--model"); p.add_argument("--harness"); p.add_argument("--endpoint", help="OpenAI-compatible base URL, e.g. http://localhost:8080/v1 (only used to record metadata)")
    p.add_argument("--notes"); p.add_argument("--workspace-dir", help="put the workspace somewhere else (best isolation)"); p.add_argument("--private-dir")
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("status"); p.add_argument("name"); p.set_defaults(fn=cmd_status)
    p = sub.add_parser("report", help="grade and compile the report"); p.add_argument("name"); p.add_argument("--open", action="store_true"); p.set_defaults(fn=cmd_report)
    p = sub.add_parser("watch", help="wait until the model is finished (or idle), then compile automatically")
    p.add_argument("name"); p.add_argument("--poll", type=int, default=30); p.add_argument("--idle-minutes", type=float, default=45); p.add_argument("--open", action="store_true"); p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("compare", help="side-by-side HTML of several runs"); p.add_argument("names", nargs="+"); p.add_argument("-o", "--output", default="comparison.html"); p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("selfcheck", help="validate the suite with a simulated perfect and a simulated bad model"); p.add_argument("--full", action="store_true"); p.set_defaults(fn=cmd_selfcheck)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
