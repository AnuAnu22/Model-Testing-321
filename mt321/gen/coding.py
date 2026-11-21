"""Coding: write/fix functions; graded by hidden tests executed in a subprocess."""
from __future__ import annotations

import random

from ..core import Ctx, Task

REF = {}
REF["merge_intervals"] = '''
def merge_intervals(iv, gap):
    out = []
    for s, e in sorted(iv):
        if out and s - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
'''
REF["parse_config"] = '''
import re
def parse_config(text):
    res = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if v.startswith('"'):
            end = v.find('"', 1)
            res[k] = v[1:end] if end != -1 else v[1:]
            continue
        v = v.split("#", 1)[0].strip()
        if re.fullmatch(r"-?\\d+", v):
            res[k] = int(v)
        elif v.lower() in ("true", "false"):
            res[k] = v.lower() == "true"
        else:
            res[k] = v
    return res
'''
REF["rpn"] = '''
def rpn(tokens):
    st = []
    for t in tokens:
        if t == "neg":
            st.append(-st.pop())
        elif t in "+-*/" and len(t) == 1:
            b, a = st.pop(), st.pop()
            if t == "+": st.append(a + b)
            elif t == "-": st.append(a - b)
            elif t == "*": st.append(a * b)
            else:
                if b == 0: return None
                q = abs(a) // abs(b)
                st.append(q if (a >= 0) == (b >= 0) else -q)
        else:
            st.append(int(t))
    return st[0]
'''
REF["topo_order"] = '''
import heapq
def topo_order(n, edges):
    adj = [[] for _ in range(n)]; indeg = [0] * n
    for a, b in edges:
        adj[a].append(b); indeg[b] += 1
    h = [i for i in range(n) if indeg[i] == 0]; heapq.heapify(h); out = []
    while h:
        u = heapq.heappop(h); out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: heapq.heappush(h, v)
    return out if len(out) == n else []
'''
REF["lru_hits"] = '''
from collections import OrderedDict
def lru_hits(capacity, accesses):
    if capacity <= 0: return 0
    c, hits = OrderedDict(), 0
    for a in accesses:
        if a in c:
            hits += 1; c.move_to_end(a)
        else:
            c[a] = 1
            if len(c) > capacity: c.popitem(last=False)
    return hits
'''
REF["roman_to_int"] = '''
import re
def roman_to_int(s):
    if not s or not re.fullmatch(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", s): return -1
    v = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}; t = 0
    for i, ch in enumerate(s):
        t += -v[ch] if i + 1 < len(s) and v[ch] < v[s[i+1]] else v[ch]
    return t
'''
REF["moving_average"] = '''
def moving_average(xs, k):
    if k <= 0 or k > len(xs): return []
    return [round(sum(xs[i:i+k]) / k, 2) for i in range(len(xs) - k + 1)]
'''
REF["dedupe_keep_last"] = '''
def dedupe_keep_last(seq):
    last = {x: i for i, x in enumerate(seq)}
    return [x for i, x in enumerate(seq) if last[x] == i]
'''
REF["min_window"] = '''
from collections import Counter
def min_window(s, t):
    if not t: return ""
    need, best = Counter(t), ""
    for i in range(len(s)):
        for j in range(i + len(t), len(s) + 1):
            w = Counter(s[i:j])
            if all(w[c] >= n for c, n in need.items()):
                if best == "" or j - i < len(best): best = s[i:j]
                break
    return best
'''
REF["max_depth"] = '''
def max_depth(s):
    pairs = {")": "(", "]": "[", "}": "{"}; st = []; best = 0
    for ch in s:
        if ch in "([{": st.append(ch); best = max(best, len(st))
        elif ch in pairs:
            if not st or st.pop() != pairs[ch]: return -1
    return best if not st else -1
'''
REF["rate_limit"] = '''
def rate_limit(events, limit, window):
    allowed, out = [], []
    for t in events:
        n = sum(1 for a in allowed if a > t - window)
        if n < limit: allowed.append(t); out.append(True)
        else: out.append(False)
    return out
'''
REF["format_table"] = '''
def format_table(rows):
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    fmt = lambda r: " | ".join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip()
    lines = [fmt(rows[0]), "-+-".join("-" * x for x in w)] + [fmt(r) for r in rows[1:]]
    return "\\n".join(lines)
'''

BUGGY = {
    "moving_average": '''def moving_average(xs, k):
    """Average of every window of k consecutive values, rounded to 2 decimals."""
    out = []
    for i in range(len(xs) - k):
        out.append(sum(xs[i:i + k]) / k)
    return out
''',
    "dedupe_keep_last": '''def dedupe_keep_last(seq):
    """Remove duplicates keeping the LAST occurrence of each value; order = order of those last occurrences."""
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
''',
}


def load(name):
    ns = {}
    exec(REF[name], ns)
    return ns[name]


def tests_for(name, rng: random.Random):
    f = load(name)
    cases = []
    if name == "merge_intervals":
        cases = [([], 0), ([[1, 2]], 5), ([[5, 6], [1, 2], [2, 4]], 0), ([[1, 2], [4, 5]], 2), ([[1, 10], [2, 3]], 0), ([[1, 2], [4, 5]], 1)]
        for _ in range(8):
            cases.append(([[s, s + rng.randint(0, 6)] for s in [rng.randint(0, 40) for _ in range(rng.randint(2, 9))]], rng.randint(0, 3)))
        return [{"args": [list(map(list, a)), g], "expected": f(list(map(list, a)), g)} for a, g in cases]
    if name == "parse_config":
        base = ["# comment", "", "port = 8080  # web", 'name = "my # app"', "debug = TRUE", "ratio = 3.5", "path=/usr/local", "retries = -3", 'msg = "hello world" # tail', "bad line", "port = 9090"]
        texts = ["\n".join(base), "a=1\nb = two\nc = \"3\"\nd = False", "   x  =  7   \n# y = 1\nz = \"\"", ""]
        for _ in range(5):
            lines = rng.sample(base, rng.randint(3, 8))
            texts.append("\n".join(lines))
        return [{"args": [t], "expected": f(t)} for t in texts]
    if name == "rpn":
        cs = [["3"], ["2", "3", "+"], ["7", "2", "/"], ["-7", "2", "/"], ["7", "-2", "/"], ["5", "0", "/"], ["4", "neg", "3", "*"], ["10", "2", "8", "*", "+", "3", "-"], ["-1", "neg", "neg"]]
        def tree(d):
            if d == 0 or rng.random() < 0.3:
                return [str(rng.randint(-9, 20))]
            op = rng.choice(["+", "-", "*", "/", "neg"])
            if op == "neg":
                return tree(d - 1) + ["neg"]
            return tree(d - 1) + tree(d - 1) + [op]
        for _ in range(8):
            cs.append(tree(3))
        return [{"args": [c], "expected": f(c)} for c in cs]
    if name == "topo_order":
        cs = [(3, []), (4, [[2, 1], [3, 1]]), (3, [[0, 1], [1, 2], [2, 0]]), (5, [[4, 0], [3, 0]]), (1, [])]
        for _ in range(8):
            n = rng.randint(3, 9)
            perm = list(range(n)); rng.shuffle(perm)
            e = [[perm[i], perm[j]] for i in range(n) for j in range(i + 1, n) if rng.random() < 0.25]
            cs.append((n, e))
        return [{"args": [n, e], "expected": f(n, e)} for n, e in cs]
    if name == "lru_hits":
        cs = [(0, [1, 1]), (1, [1, 1, 2, 1]), (2, [1, 2, 1, 3, 2, 1]), (3, [])]
        for _ in range(8):
            cs.append((rng.randint(1, 4), [rng.randint(1, 6) for _ in range(rng.randint(5, 25))]))
        return [{"args": [c, a], "expected": f(c, a)} for c, a in cs]
    if name == "roman_to_int":
        cs = ["I", "IV", "IX", "XLII", "MCMXCIV", "MMMCMXCIX", "IIII", "VX", "IC", "", "xiv", "MMMM", "XIIX", "CMC", "LVIII", "DCCC"]
        return [{"args": [c], "expected": f(c)} for c in cs]
    if name == "moving_average":
        cs = [([1, 2, 3, 4], 2), ([1, 2, 3], 3), ([1, 2], 5), ([4, 5, 6], 0), ([], 1), ([1.5, 2.5, 3.5, 10], 3)]
        for _ in range(6):
            cs.append(([rng.randint(0, 20) for _ in range(rng.randint(3, 10))], rng.randint(1, 4)))
        return [{"args": [x, k], "expected": f(x, k)} for x, k in cs]
    if name == "dedupe_keep_last":
        cs = [[], [1], [1, 2, 1], [3, 3, 3], ["a", "b", "a", "c", "b"]]
        for _ in range(6):
            cs.append([rng.randint(1, 6) for _ in range(rng.randint(4, 14))])
        return [{"args": [c], "expected": f(c)} for c in cs]
    if name == "min_window":
        cs = [("ADOBECODEBANC", "ABC"), ("a", "a"), ("a", "aa"), ("abc", ""), ("aabdec", "abc"), ("bba", "ab"), ("xyz", "q")]
        for _ in range(5):
            cs.append(("".join(rng.choice("abcd") for _ in range(rng.randint(6, 16))), "".join(rng.choice("abcd") for _ in range(rng.randint(2, 4)))))
        return [{"args": [s, t], "expected": f(s, t)} for s, t in cs]
    if name == "max_depth":
        cs = ["", "abc", "(a)", "([{}])", "(]", "((", "{[()()]}", "([)]", "())", "a(b[c]{d(e)})", "}{"]
        return [{"args": [c], "expected": f(c)} for c in cs]
    if name == "rate_limit":
        cs = [([], 2, 5), ([1, 2, 3], 2, 10), ([1, 2, 7, 8], 2, 5), ([0, 0, 0], 1, 1), ([1, 6, 11], 1, 5)]
        for _ in range(6):
            ev = sorted(rng.randint(0, 30) for _ in range(rng.randint(5, 14)))
            cs.append((ev, rng.randint(1, 3), rng.randint(2, 8)))
        return [{"args": [e, l, w], "expected": f(e, l, w)} for e, l, w in cs]
    if name == "format_table":
        cs = [[["a", "bb"], ["ccc", "d"]], [["id", "name", "qty"], ["1", "bolt", "20"], ["22", "nut", "5"]], [["x"], ["yy"]]]
        for _ in range(4):
            cols = rng.randint(2, 4)
            cs.append([["".join(rng.choice("abcdef") for _ in range(rng.randint(1, 6))) for _ in range(cols)] for _ in range(rng.randint(2, 5))])
        return [{"args": [c], "expected": f(c)} for c in cs]
    raise KeyError(name)


SPECS = {
    "merge_intervals": ("merge_intervals(intervals, gap)", "Intervals are `[start, end]` integer pairs (start <= end), unsorted. Merge intervals that overlap **or whose gap is at most `gap`** (i.e. next.start - current.end <= gap) after sorting by start. Return a sorted list of `[start, end]` lists. Empty input -> `[]`.", 2),
    "parse_config": ("parse_config(text)", "Parse `key = value` lines into a dict. Rules: ignore blank lines, lines starting with `#`, and lines without `=`. Split on the **first** `=`; strip whitespace. If the value starts with a double quote, the value is the text up to the next double quote (a string, may contain `#`; anything after is ignored). Otherwise strip a trailing `# comment` and whitespace, then: integer-looking values (`-?\\d+`) -> `int`; `true`/`false` (any case) -> `bool`; everything else (including `3.5`) stays a `str`. Later duplicate keys override earlier ones.", 3),
    "rpn": ("rpn(tokens)", "Evaluate a reverse-Polish expression. `tokens` is a list of strings: integers (may be negative), `+ - * /`, and `neg` (unary minus). `/` is **integer division truncating toward zero**. If any division by zero occurs return `None`. Otherwise return the final integer.", 2),
    "topo_order": ("topo_order(n, edges)", "Nodes are `0..n-1`; each edge `[a, b]` means a must come before b. Return the **lexicographically smallest** topological order as a list. If the graph has a cycle return `[]`.", 3),
    "lru_hits": ("lru_hits(capacity, accesses)", "Simulate an LRU cache of the given capacity over the list of keys `accesses`; return the number of **hits**. A hit refreshes recency. Capacity 0 means no caching (0 hits).", 2),
    "roman_to_int": ("roman_to_int(s)", "Convert a **valid** upper-case Roman numeral (1..3999, standard subtractive forms only) to an int. Return `-1` for anything invalid (empty string, lowercase, non-standard such as `IIII`, `VX`, `IC`).", 2),
    "min_window": ("min_window(s, t)", "Return the shortest substring of `s` that contains every character of `t` with multiplicity. Among equally short answers return the **leftmost**. Return `\"\"` if impossible or if `t` is empty.", 3),
    "max_depth": ("max_depth(s)", "`s` may contain `()`, `[]`, `{}` mixed with other characters (ignored). Return the maximum nesting depth if all brackets are correctly matched and nested, otherwise `-1`.", 2),
    "rate_limit": ("rate_limit(events, limit, window)", "`events` is a non-decreasing list of integer timestamps. An event at time t is **allowed** if fewer than `limit` previously **allowed** events have a timestamp strictly greater than `t - window`; otherwise it is rejected (rejected events do not count). Return a list of booleans.", 3),
    "format_table": ("format_table(rows)", "`rows` is a list of lists of strings; the first row is the header. Left-justify every cell to its column's max width, join cells with `\" | \"`, and right-strip each line. Insert a second line made of `-` repeated to each column width, joined with `\"-+-\"`. Join lines with `\"\\n\"` (no trailing newline).", 2),
}
BUGFIX = {
    "moving_average": ("moving_average(xs, k)", "Return the average of every window of `k` consecutive values in `xs`, each **rounded to 2 decimals**, in order. If `k <= 0` or `k > len(xs)` return `[]`.", 2),
    "dedupe_keep_last": ("dedupe_keep_last(seq)", "Remove duplicates keeping the **last** occurrence of each value; the result preserves the relative order of those last occurrences (e.g. `[1,2,1,3]` -> `[2,1,3]`).", 2),
}


def generate(ctx: Ctx) -> list[Task]:
    rng = ctx.rng("coding")
    out = []
    for name, (sig, spec, diff) in SPECS.items():
        out.append(Task(category="coding", subcategory="implement", title=f"Implement {name}", answer_format="code", difficulty=diff,
                        prompt=f"Write a Python 3 function `{sig}`.\n\n{spec}\n\nUse only the standard library. Save a **single file** `answers/{{ID}}.py` that defines `{name}` at module level (no input(), no top-level side effects). Hidden tests will import and call it. "
                               "You are encouraged to test your own code before finishing.",
                        key={"check": "code", "entry": name, "tests": tests_for(name, rng), "reference": REF[name]}, answer_hint="(write answers/{ID}.py)",
                        tags=["code"]))
    for name, (sig, spec, diff) in BUGFIX.items():
        out.append(Task(category="coding", subcategory="bugfix", title=f"Fix bug in {name}", answer_format="code", difficulty=diff,
                        prompt=f"`tasks/{{ID}}/buggy.py` contains a function `{sig}` that is supposed to behave as follows:\n\n{spec}\n\nIt has bugs. Save a **corrected full copy** as `answers/{{ID}}.py` (do not edit the original). Hidden tests will import and call it.",
                        files={"buggy.py": BUGGY[name]}, key={"check": "code", "entry": name, "tests": tests_for(name, rng), "reference": REF[name]},
                        answer_hint="(write answers/{ID}.py)", tags=["code"]))
    return out
