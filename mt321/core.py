"""Core data structures and helpers shared by all generators."""
from __future__ import annotations

import base64
import csv
import io
import json
import random
import zlib
from dataclasses import dataclass, field
from typing import Any

CATEGORIES = {
    "supply": "Business analytics (supply chain)",
    "hallucination": "Hallucination & abstention",
    "tools": "Tool-call reliability",
    "longctx": "Long context & retrieval",
    "recall": "Session memory",
    "instruct": "Instruction following",
    "reasoning": "Reasoning & math",
    "coding": "Coding",
    "extraction": "Structured extraction",
    "safety": "Safety & robustness",
    "persistence": "Persistence & thoroughness",
    "sentinel": "Drift sentinels",
}


@dataclass
class Task:
    category: str
    subcategory: str
    title: str                      # internal only (never shown to the model)
    prompt: str                     # markdown body shown to the model
    key: dict                       # checker spec incl. expected value(s) -- PRIVATE
    difficulty: int = 1             # 1 easy .. 3 hard
    answer_hint: str = ""           # describes the shape of "answer" (shown to model)
    answer_format: str = "json"     # json | code
    files: dict[str, Any] = field(default_factory=dict)  # per-task attachments (relpath in task dir)
    reads: list[str] = field(default_factory=list)       # shared files the task needs (for token estimate)
    est_tokens: int = 0
    answerable: bool = True
    sentinel_group: int = -1
    guards: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    id: str = ""
    oracle: Any = None              # what a perfect model would write (self-test only)


class Ctx:
    """Generation context: seed, scale and the shared (data/) file registry."""

    def __init__(self, seed: int, profile: dict):
        self.seed = seed
        self.profile = profile
        self.shared: dict[str, str] = {}
        self.shared_bin: dict[str, bytes] = {}

    def rng(self, name: str) -> random.Random:
        return random.Random(f"mt321/{self.seed}/{name}")

    def add_shared(self, path: str, text: str):
        self.shared[path] = text

    def tokens_of(self, paths: list[str]) -> int:
        return sum(est_tokens(self.shared.get(p, "")) for p in paths)


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def to_csv(rows: list[dict], fields: list[str] | None = None) -> str:
    if not rows and not fields:
        return ""
    fields = fields or list(rows[0].keys())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    return buf.getvalue()


def pack_blob(obj: Any) -> str:
    return base64.b64encode(zlib.compress(json.dumps(obj, separators=(",", ":")).encode(), 9)).decode()


def unpack_blob(s: str) -> Any:
    return json.loads(zlib.decompress(base64.b64decode(s)).decode())


FIRST = ["Aiden", "Maya", "Noor", "Luis", "Priya", "Tomas", "Ingrid", "Kofi", "Hana", "Omar", "Sven", "Leila",
         "Dmitri", "Chen", "Amara", "Jonas", "Rosa", "Kenji", "Sofia", "Ravi", "Elif", "Mateo", "Zara", "Ivo"]
LAST = ["Alvarez", "Brandt", "Chaudhry", "Dubois", "Eriksen", "Fofana", "Grewal", "Haddad", "Ibarra", "Jansen",
        "Kowalski", "Lindqvist", "Moreau", "Nakamura", "Okafor", "Petrov", "Quintero", "Rahman", "Sato", "Tanaka",
        "Ueda", "Varga", "Weiss", "Yilmaz"]
SYL_A = ["Ver", "Kor", "Tal", "Bren", "Ost", "Lum", "Dray", "Mar", "Sil", "Nex", "Pol", "Quin", "Rav", "Zen", "Hal", "Fen"]
SYL_B = ["lin", "dax", "mont", "vik", "tora", "gen", "bury", "cor", "wick", "dal", "mere", "stad", "ford", "lyn", "ex", "nova"]
SUFFIX = ["Fabrication", "Components", "Metals", "Plastics", "Electronics", "Castings", "Logistics", "Industries",
          "Precision", "Systems", "Forge", "Composites", "Machining", "Controls"]


def person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def company(rng: random.Random) -> str:
    return f"{rng.choice(SYL_A)}{rng.choice(SYL_B)} {rng.choice(SUFFIX)}"


def uniq(rng: random.Random, fn, n: int) -> list:
    out, seen = [], set()
    while len(out) < n:
        v = fn(rng)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def fmt_money(x: float) -> str:
    return f"{x:,.2f}"
