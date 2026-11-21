"""Supply-chain / planning analytics suite built on a fully synthetic company dataset."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from ..core import Ctx, Task, company, person, to_csv, uniq

ASOF = date(2025, 9, 30)
D = "data/supply/"


def month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def month_list(y, m, n):
    out = []
    for i in range(n):
        out.append(f"{y + (m - 1 + i) // 12}-{(m - 1 + i) % 12 + 1:02d}")
    return out


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def direction(vals, thr=0.10):
    a = sum(vals[:3]) / 3
    b = sum(vals[-3:]) / 3
    if a == 0:
        return "increasing" if b > 0 else "flat"
    ch = (b - a) / a
    return "increasing" if ch > thr else "decreasing" if ch < -thr else "flat"


# ------------------------------------------------------------------ dataset
def make_dataset(ctx: Ctx):
    rng = ctx.rng("supply/data")
    ds = {}
    # org ------------------------------------------------------------
    names = uniq(rng, person, 20)
    org = [{"person_id": "D01", "name": names[0], "role": "Director", "reports_to": ""},
           {"person_id": "M01", "name": names[1], "role": "Supervisor", "reports_to": "D01"},
           {"person_id": "M02", "name": names[2], "role": "Supervisor", "reports_to": "D01"}]
    for i in range(1, 6):
        org.append({"person_id": f"B{i:02d}", "name": names[2 + i], "role": "Buyer", "reports_to": "M01"})
    for i in range(1, 6):
        org.append({"person_id": f"PL{i:02d}", "name": names[7 + i], "role": "Planner", "reports_to": "M02"})
    ds["org"] = org
    # suppliers ------------------------------------------------------
    cn = uniq(rng, company, 16)
    ds["suppliers"] = [{"supplier_id": f"S{100 + i}", "name": cn[i], "country": rng.choice(["DE", "MX", "CN", "US", "PL", "VN", "IN"]),
                        "status": rng.choices(["Active", "Probation", "Inactive"], [12, 3, 1])[0],
                        "lead_time_days": rng.choice([14, 21, 28, 35, 42, 56]), "buyer_id": f"B{rng.randint(1, 5):02d}"}
                       for i in range(16)]
    sids = [s["supplier_id"] for s in ds["suppliers"]]
    # parts ----------------------------------------------------------
    parts, bom = [], []
    eis = [f"E-{101 + i}" for i in range(14)]
    sas = [f"SA-{201 + i}" for i in range(10)]
    cs = [f"C-{3001 + i}" for i in range(44)]
    nouns = ["bracket", "housing", "gear", "shaft", "valve", "sensor", "harness", "bearing", "cover", "plate", "coupler", "spindle"]
    for e in eis:
        parts.append({"part_id": e, "description": f"{rng.choice(['Pump', 'Drive', 'Actuator', 'Mixer', 'Press'])} unit {e[2:]}", "type": "END_ITEM",
                      "uom": "EA", "std_cost": "", "list_price": rng.randrange(900, 6000, 25), "planner_id": f"PL{rng.randint(1, 5):02d}", "supplier_id": ""})
    for s in sas:
        parts.append({"part_id": s, "description": f"Subassembly {s[3:]}", "type": "SUBASSY", "uom": "EA", "std_cost": "", "list_price": "",
                      "planner_id": f"PL{rng.randint(1, 5):02d}", "supplier_id": ""})
    for i, c in enumerate(cs):
        parts.append({"part_id": c, "description": f"{rng.choice(nouns).capitalize()} {c[2:]}", "type": "COMPONENT", "uom": "EA",
                      "std_cost": round(rng.uniform(2, 180), 2), "list_price": "", "planner_id": f"PL{rng.randint(1, 5):02d}",
                      "supplier_id": sids[i % 16]})
    for s_i, s in enumerate(sas):
        for c in rng.sample(cs, rng.randint(3, 4)):
            bom.append({"parent": s, "child": c, "qty_per": rng.choice([1, 1, 2, 3, 4])})
        if s_i < 4:  # third level: SA contains a later SA
            bom.append({"parent": s, "child": sas[s_i + 5], "qty_per": rng.choice([1, 2])})
    for e in eis:
        for c in rng.sample(cs, 3):
            bom.append({"parent": e, "child": c, "qty_per": rng.choice([1, 2, 4, 6])})
        for s in rng.sample(sas, 2):
            bom.append({"parent": e, "child": s, "qty_per": rng.choice([1, 2])})
    ds["parts"], ds["bom"] = parts, bom
    pmap = {p["part_id"]: p for p in parts}
    ds["pmap"] = pmap
    # receipts -------------------------------------------------------
    months = month_list(2024, 4, 18)
    receipts, rid = [], 1
    for si, s in enumerate(ds["suppliers"]):
        sp = [p["part_id"] for p in parts if p["supplier_id"] == s["supplier_id"]]
        base_late = rng.uniform(0.1, 0.4)
        slope = rng.choice([-0.012, -0.006, 0, 0.006, 0.012, 0.018])
        vol = rng.uniform(0.8, 1.4)
        vslope = rng.choice([-0.03, 0, 0.03, 0.06])
        for mi, mk in enumerate(months):
            y, m = map(int, mk.split("-"))
            n = max(2, int(rng.randint(3, 6) * (vol + vslope * mi)))
            for _ in range(n):
                dday = date(y, m, rng.randint(1, 27))
                if dday > ASOF:
                    continue
                late = rng.random() < min(0.9, max(0.02, base_late + slope * mi))
                receipts.append({"receipt_id": f"R{rid:05d}", "supplier_id": s["supplier_id"], "part_id": rng.choice(sp),
                                 "receipt_date": dday.isoformat(), "qty_received": rng.randrange(20, 400, 5),
                                 "days_late": rng.randint(1, 12) if late else 0})
                rid += 1
    ds["receipts"] = receipts
    # PO lines -------------------------------------------------------
    po, ch = [], []
    n = 1
    for c in cs:
        for _ in range(rng.randint(3, 7)):
            need = ASOF + timedelta(days=rng.randint(-50, 100))
            oq = rng.randrange(50, 800, 10)
            rq = oq if need < ASOF - timedelta(days=25) and rng.random() < 0.8 else (rng.randrange(0, oq, 10) if need < ASOF else 0)
            aq = oq if rng.random() < 0.7 else rng.randrange(0, oq, 10)
            ack = need + timedelta(days=rng.randint(-3, 14))
            lid = f"PO{4500 + n // 3}-{n % 3 + 1}0"
            po.append({"po_line": f"{lid}#{n}", "supplier_id": pmap[c]["supplier_id"], "part_id": c, "need_date": need.isoformat(),
                       "ordered_qty": oq, "received_qty": rq, "ack_date": ack.isoformat(), "ack_qty": aq,
                       "unit_price": pmap[c]["std_cost"]})
            for _ in range(rng.choice([0, 0, 1, 2, 3])):
                old = need + timedelta(days=rng.randint(-20, 0))
                ch.append({"po_line": po[-1]["po_line"], "old_commit": old.isoformat(),
                           "new_commit": (old + timedelta(days=rng.randint(2, 30))).isoformat()})
            n += 1
    # finalise PO line ids (provisional "base#n" -> "base-n") and remap change records
    for r in po:
        base, num = r["po_line"].split("#")
        r["po_line"] = f"{base}-{num}"
    ds["po"] = po
    ds["changes"] = [{**rec, "po_line": rec["po_line"].replace("#", "-")} for rec in ch]
    # customers ------------------------------------------------------
    cn2 = uniq(rng, company, 10)
    ds["customers"] = [{"customer_id": f"C{20 + i}", "name": cn2[i].replace("Fabrication", "Group"), "region": rng.choice(["NA", "EMEA", "APAC", "LATAM"]),
                        "tier": rng.choice(["Gold", "Silver", "Bronze"]), "account_mgr": person(rng)} for i in range(10)]
    ds["shipments"], oid = [], 1
    for cu in ds["customers"]:
        items = rng.sample(eis, 4)
        slope = rng.choice([-0.05, 0, 0.05, 0.1])
        for mi, mk in enumerate(months):
            y, m = map(int, mk.split("-"))
            for it in items:
                if rng.random() < 0.8:
                    q = max(1, int(rng.randint(4, 30) * (1 + slope * mi)))
                    pr = round(pmap[it]["list_price"] * rng.uniform(0.93, 1.04), 2)
                    ds["shipments"].append({"ship_date": date(y, m, rng.randint(1, 27)).isoformat(), "customer_id": cu["customer_id"],
                                            "end_item": it, "qty": q, "unit_price": pr})
    ds["cust_orders"] = []
    for cu in ds["customers"]:
        for _ in range(rng.randint(3, 8)):
            due = ASOF + timedelta(days=rng.randint(-70, 60))
            ds["cust_orders"].append({"order_id": f"SO{9000 + oid}", "customer_id": cu["customer_id"], "end_item": rng.choice(eis),
                                      "due_date": due.isoformat(), "qty": rng.randint(2, 40),
                                      "status": "Open" if (due >= ASOF or rng.random() < 0.6) else "Shipped"})
            oid += 1
    # MPS / actuals / routing / capacity ----------------------------
    wk0 = monday(date(2025, 7, 7))
    weeks = [wk0 + timedelta(weeks=i) for i in range(25)]  # 12 past + 13 future (index 12 = 2025-09-29)
    ds["weeks"] = weeks
    ds["mps"], ds["actuals"] = [], []
    for e in eis:
        base = rng.randint(6, 26)
        sl = rng.choice([-0.4, -0.2, 0, 0.25, 0.5])
        att = rng.uniform(0.7, 1.05)
        for wi, w in enumerate(weeks):
            pq = max(0, int(round(base + sl * wi + rng.randint(-2, 2))))
            if wi >= 16 and rng.random() < 0.12:
                pq = int(pq * 2.2)  # occasional spike
            ds["mps"].append({"week_start": w.isoformat(), "end_item": e, "planned_qty": pq})
            if wi < 12:
                ds["actuals"].append({"week_start": w.isoformat(), "end_item": e, "actual_qty": max(0, int(round(pq * att + rng.randint(-2, 1))))})
    cells = ["CELL-A", "CELL-B", "CELL-C", "CELL-D", "CELL-E", "CELL-F"]
    ds["routing"] = []
    for e in eis:
        for cl in rng.sample(cells, rng.choice([1, 2])):
            ds["routing"].append({"end_item": e, "cell": cl, "hours_per_unit": round(rng.uniform(0.8, 4.5), 1)})
    ds["capacity"] = [{"cell": cl, "week_start": w.isoformat(), "capacity_hours": int(rng.choice([90, 110, 130, 150]))}
                      for cl in cells[:5] for w in weeks[12:]]
    # inventory, mrp, forecasts -------------------------------------
    ds["inventory"] = [{"part_id": p["part_id"], "on_hand": rng.randint(0, 900), "wip_qty": rng.randint(0, 150) if p["type"] != "COMPONENT" else 0,
                        "in_transit": rng.choice([0, 0, 40, 120])} for p in parts if p["type"] != "END_ITEM"]
    ds["mrp"] = []
    for r in rng.sample(po, 60):
        t = rng.choice(["RESCHEDULE_IN", "RESCHEDULE_OUT", "CANCEL", "EXPEDITE"])
        fd = date.fromisoformat(r["need_date"])
        ds["mrp"].append({"part_id": r["part_id"], "po_line": r["po_line"], "message": t, "from_date": fd.isoformat(),
                          "to_date": (fd + timedelta(days=rng.randint(-14, 21))).isoformat() if t.startswith("RESCH") else ""})
    fm = month_list(2025, 10, 6)
    ds["fc_sup"] = []
    for s in sids:
        b = rng.randrange(300, 3000, 50)
        sl = rng.choice([-80, 0, 80, 150])
        for mi, mk in enumerate(fm):
            v1 = max(0, b + sl * mi)
            ds["fc_sup"].append({"supplier_id": s, "month": mk, "version": "v1", "qty": v1})
            ds["fc_sup"].append({"supplier_id": s, "month": mk, "version": "v2", "qty": max(0, v1 + rng.randrange(-300, 400, 10))})
    ds["fc_cust"] = []
    for cu in ds["customers"]:
        b = rng.randint(30, 160)
        for mk in months[-6:]:
            fq = b + rng.randint(-10, 10)
            ds["fc_cust"].append({"customer_id": cu["customer_id"], "month": mk, "forecast_qty": fq, "order_qty": max(0, fq + rng.randint(-35, 35))})
    ds["eis"], ds["sas"], ds["cs"], ds["months"], ds["fm"] = eis, sas, cs, months, fm
    ds["cells"] = cells
    return ds


def write_dataset(ctx: Ctx, ds):
    spec = {"suppliers": "suppliers.csv", "parts": "parts.csv", "bom": "bom.csv", "receipts": "receipts.csv", "po": "po_lines.csv",
            "changes": "commit_changes.csv", "customers": "customers.csv", "shipments": "shipments.csv", "cust_orders": "customer_orders.csv",
            "mps": "mps_plan.csv", "actuals": "production_actuals.csv", "routing": "routing.csv", "capacity": "cell_capacity.csv",
            "inventory": "inventory.csv", "mrp": "mrp_messages.csv", "fc_sup": "supplier_forecast.csv", "fc_cust": "customer_forecast.csv",
            "org": "org.csv"}
    for k, fn in spec.items():
        ctx.add_shared(D + fn, to_csv(ds[k]))
    ctx.add_shared(D + "README.md", f"""# Meridian Works - planning data extract (synthetic)

All files are CSV with a header row. **As-of date: {ASOF.isoformat()}** (a Tuesday). "Today" means this date for every question.
Weeks start on Monday and are identified by their Monday date. The current week starts 2025-09-29.

| file | contents |
|---|---|
| suppliers.csv | supplier master: id, name, country, status, lead_time_days, buyer_id |
| parts.csv | part master. type = END_ITEM / SUBASSY / COMPONENT; planner_id; supplier_id (components only); list_price (end items); std_cost (components) |
| bom.csv | single-level bill of material rows: parent, child, qty_per. Multi-level structures chain through SUBASSY parts |
| receipts.csv | goods receipts: supplier, part, receipt_date, qty_received, days_late (0 = on time, otherwise days after the need date) |
| po_lines.csv | purchase-order lines: need_date, ordered_qty, received_qty, ack_date / ack_qty (supplier acknowledgement), unit_price. Open qty = ordered_qty - received_qty |
| commit_changes.csv | history of supplier commit-date changes per PO line (old_commit -> new_commit) |
| customers.csv / shipments.csv / customer_orders.csv | customer master, shipped history (qty x unit_price = revenue), open/shipped sales orders |
| mps_plan.csv | master production schedule, planned_qty by end item by week (25 weeks: 12 past, current week, 12 future) |
| production_actuals.csv | actual built qty by end item by week (past weeks only) |
| routing.csv / cell_capacity.csv | end item -> work cell with hours per unit; weekly capacity hours per cell (current + future weeks) |
| inventory.csv | on_hand, wip_qty, in_transit per part (non end items) |
| mrp_messages.csv | MRP action messages per PO line |
| supplier_forecast.csv | forward demand signal to each supplier by month, versions v1 (older) and v2 (newer) |
| customer_forecast.csv | forecast vs actual order quantity per customer by month |
| org.csv | people: planners, buyers, supervisors and who they report to |

Rows are synthetic; any resemblance to real companies is accidental. Only trust what is in these files.
""")


# ------------------------------------------------------------------ helpers
def explode(ds, part, qty=1, acc=None):
    acc = acc if acc is not None else defaultdict(float)
    for r in ds["bom"]:
        if r["parent"] == part:
            acc[r["child"]] += qty * r["qty_per"]
            explode(ds, r["child"], qty * r["qty_per"], acc)
    return acc


def where_used(ds, part):
    out = set()
    for r in ds["bom"]:
        if r["child"] == part:
            out.add(r["parent"])
            out |= where_used(ds, r["parent"])
    return out


def open_qty(r):
    return r["ordered_qty"] - r["received_qty"]


def sname(ds, sid):
    return next(s["name"] for s in ds["suppliers"] if s["supplier_id"] == sid)


def mk(cat_sub, title, prompt, key, hint, diff, ctx, reads, **kw):
    return Task(category="supply", subcategory=cat_sub, title=title, prompt=prompt, key=key, answer_hint=hint, difficulty=diff,
                reads=[D + r for r in reads] + [D + "README.md"], est_tokens=ctx.tokens_of([D + r for r in reads]), **kw)


# ------------------------------------------------------------------ tasks
def generate(ctx: Ctx) -> list[Task]:
    ds = make_dataset(ctx)
    write_dataset(ctx, ds)
    rng = ctx.rng("supply/tasks")
    T: list[Task] = []
    sup = rng.sample(ds["suppliers"], 6)
    cus = rng.sample(ds["customers"], 4)
    eis = rng.sample(ds["eis"], 8)

    # 1 receipts trend
    s = sup[0]
    mons = month_list(2025, 1, 9)
    rec = defaultdict(int)
    for r in ds["receipts"]:
        if r["supplier_id"] == s["supplier_id"]:
            rec[r["receipt_date"][:7]] += r["qty_received"]
    vals = [rec.get(m, 0) for m in mons]
    exp = {"monthly": dict(zip(mons, vals)), "direction": direction(vals)}
    T.append(mk("trend", "Supplier receipt volume trend",
                f"Using `receipts.csv`, compute the **total qty_received per calendar month** (by receipt_date) for supplier **{s['supplier_id']}** for every month from 2025-01 through 2025-09 (use 0 if none).\n\n"
                "Then give the overall `direction`: compare the average of the first 3 months with the average of the last 3 months. "
                "If the last-3 average is more than 10% above the first-3 average answer `increasing`; more than 10% below -> `decreasing`; otherwise `flat`.",
                {"check": "value", "expected": exp, "tol_abs": 0.5}, '{"monthly": {"2025-01": <int>, ... "2025-09": <int>}, "direction": "increasing|decreasing|flat"}', 2, ctx, ["receipts.csv"]))

    # 2 OTTR by quarter
    s = sup[1]
    q = defaultdict(lambda: [0, 0])
    for r in ds["receipts"]:
        if r["supplier_id"] == s["supplier_id"] and r["receipt_date"] >= "2024-10-01":
            d = date.fromisoformat(r["receipt_date"])
            k = f"{d.year}-Q{(d.month - 1) // 3 + 1}"
            q[k][0] += r["days_late"] == 0
            q[k][1] += 1
    ks = sorted(q)
    ottr = {k: round(100 * q[k][0] / q[k][1], 1) for k in ks}
    worst = min(ks, key=lambda k: ottr[k])
    T.append(mk("trend", "Supplier OTTR by quarter",
                f"For supplier **{s['supplier_id']}**, using receipts dated 2024-10-01 or later in `receipts.csv`, compute on-time receipt rate (OTTR) per calendar quarter: "
                "percentage of receipt rows with `days_late` = 0, rounded to 1 decimal. Also name the quarter with the lowest OTTR (`worst_quarter`).",
                {"check": "value", "expected": {"ottr_pct": ottr, "worst_quarter": worst}, "tol_abs": 0.11},
                '{"ottr_pct": {"2024-Q4": <float>, ...}, "worst_quarter": "YYYY-Qn"}', 2, ctx, ["receipts.csv"]))

    # 3 past due ranking
    pdv = defaultdict(float)
    for r in ds["po"]:
        if r["need_date"] < ASOF.isoformat() and open_qty(r) > 0:
            pdv[r["supplier_id"]] += open_qty(r) * r["unit_price"]
    top = sorted(pdv.items(), key=lambda x: -x[1])[:5]
    rows = [{"supplier_id": k, "past_due_value": round(v, 2)} for k, v in top]
    T.append(mk("ranking", "Past-due exposure ranking",
                "A PO line is **past due** when `need_date` is before the as-of date and open qty (ordered_qty - received_qty) is greater than 0. Past-due value = open qty x unit_price.\n\n"
                "Rank the **top 5 suppliers by total past-due value** (largest first). Round values to 2 decimals.",
                {"check": "table", "expected": rows, "keys": ["supplier_id"], "ordered": True}, '[{"supplier_id": "S1xx", "past_due_value": <float>}, ... 5 rows, largest first]',
                2, ctx, ["po_lines.csv"]))

    # 4 forward demand trend
    s = sup[2]
    f2 = {r["month"]: r["qty"] for r in ds["fc_sup"] if r["supplier_id"] == s["supplier_id"] and r["version"] == "v2"}
    T.append(mk("trend", "Forward demand to supplier",
                f"Use the newest forecast version (`v2`) in `supplier_forecast.csv` for supplier **{s['supplier_id']}**. Return qty per month (2025-10 .. 2026-03) and the month with the highest qty (`peak_month`).",
                {"check": "value", "expected": {"monthly": f2, "peak_month": max(f2, key=lambda k: (f2[k], k))}, "tol_abs": 0.5}, '{"monthly": {"2025-10": <int>, ...}, "peak_month": "YYYY-MM"}', 1, ctx, ["supplier_forecast.csv"]))

    # 5 commitment lookup
    r = rng.choice(ds["po"])
    T.append(mk("lookup", "PO line commitment lookup",
                f"Look up PO line **{r['po_line']}** in `po_lines.csv` and return its `supplier_id`, `part_id`, `need_date`, `ack_date`, `ack_qty` and `open_qty`.",
                {"check": "value", "expected": {"supplier_id": r["supplier_id"], "part_id": r["part_id"], "need_date": r["need_date"], "ack_date": r["ack_date"],
                                                 "ack_qty": r["ack_qty"], "open_qty": open_qty(r)}},
                '{"supplier_id": "...", "part_id": "...", "need_date": "YYYY-MM-DD", "ack_date": "YYYY-MM-DD", "ack_qty": <int>, "open_qty": <int>}', 1, ctx, ["po_lines.csv"]))

    # 6 gap to commitment
    gaps = []
    for r in ds["po"]:
        oq = open_qty(r)
        if oq > 0 and r["ack_qty"] < oq:
            gaps.append((oq - r["ack_qty"], r["po_line"]))
    gaps.sort(key=lambda x: (-x[0], x[1]))
    rows = [{"po_line": p, "gap_qty": g} for g, p in gaps[:5]]
    T.append(mk("ranking", "Gap between need and acknowledged supply",
                "For every PO line with open qty > 0 (open qty = ordered_qty - received_qty), the **gap** is `open_qty - ack_qty` when positive (the supplier acknowledged less than we still need). "
                "List the **5 PO lines with the largest gap** (descending; ties broken by po_line ascending).",
                {"check": "table", "expected": rows, "keys": ["po_line"], "ordered": True}, '[{"po_line": "...", "gap_qty": <int>}, ... 5 rows]', 2, ctx, ["po_lines.csv"]))

    # 7 decommits
    push = defaultdict(int)
    for c in ds["changes"]:
        push[c["po_line"]] += (date.fromisoformat(c["new_commit"]) - date.fromisoformat(c["old_commit"])).days
    top = sorted(push.items(), key=lambda x: (-x[1], x[0]))[:5]
    T.append(mk("ranking", "Top commit push-outs",
                "In `commit_changes.csv` each row is one supplier commit-date change; push-out days for a row = new_commit - old_commit in days. Sum push-out days per `po_line` and return the **top 5 PO lines** (descending; ties by po_line ascending).",
                {"check": "table", "expected": [{"po_line": k, "pushout_days": v} for k, v in top], "keys": ["po_line"], "ordered": True},
                '[{"po_line": "...", "pushout_days": <int>}, ... 5 rows]', 2, ctx, ["commit_changes.csv"]))

    # 8 supplier master lookup (join with org)
    s = sup[3]
    buyer = next(p for p in ds["org"] if p["person_id"] == s["buyer_id"])
    T.append(mk("lookup", "Supplier master data",
                f"Find the supplier whose name is **{s['name']}** and report its `supplier_id`, `country`, `status`, `lead_time_days` and the **name of its buyer** (`buyer_name`, from `org.csv`).",
                {"check": "value", "expected": {"supplier_id": s["supplier_id"], "country": s["country"], "status": s["status"], "lead_time_days": s["lead_time_days"], "buyer_name": buyer["name"]}},
                '{"supplier_id": "...", "country": "..", "status": "..", "lead_time_days": <int>, "buyer_name": "..."}', 1, ctx, ["suppliers.csv", "org.csv"]))

    # 9 customer shipments trend
    cu = cus[0]
    sh = defaultdict(int)
    for r in ds["shipments"]:
        if r["customer_id"] == cu["customer_id"]:
            sh[r["ship_date"][:7]] += r["qty"]
    mons2 = month_list(2025, 1, 9)
    vv = [sh.get(m, 0) for m in mons2]
    T.append(mk("trend", "Customer shipment trend",
                f"Total shipped `qty` per month (by ship_date) for customer **{cu['customer_id']}**, 2025-01 .. 2025-09 from `shipments.csv`, plus `direction` (first-3-month average vs last-3-month average; >10% up = increasing, >10% down = decreasing, else flat).",
                {"check": "value", "expected": {"monthly": dict(zip(mons2, vv)), "direction": direction(vv)}, "tol_abs": 0.5},
                '{"monthly": {"2025-01": <int>, ...}, "direction": "increasing|decreasing|flat"}', 1, ctx, ["shipments.csv"]))

    # 10 revenue impact
    comp = rng.choice(ds["cs"])
    impacted = sorted(e for e in where_used(ds, comp) if e.startswith("E-"))
    fut = [w.isoformat() for w in ds["weeks"][12:20]]
    rev = 0.0
    for r in ds["mps"]:
        if r["end_item"] in impacted and r["week_start"] in fut:
            rev += r["planned_qty"] * ds["pmap"][r["end_item"]]["list_price"]
    T.append(mk("impact", "Downstream revenue at risk",
                f"Component **{comp}** will be unavailable for the next 8 weeks (weeks starting 2025-09-29 through 2025-11-17 inclusive). Any end item that uses it **at any BOM level** cannot be built in that window.\n\n"
                "Revenue at risk = sum over the affected end items and those 8 weeks of `planned_qty` (mps_plan.csv) x `list_price` (parts.csv). Return the sorted list of affected end items and the revenue.",
                {"check": "value", "expected": {"affected_end_items": impacted, "revenue_at_risk": round(rev, 2)}},
                '{"affected_end_items": ["E-1xx", ...sorted], "revenue_at_risk": <float>}', 3, ctx, ["bom.csv", "mps_plan.csv", "parts.csv"]))

    # 11 customer master
    cu = cus[1]
    T.append(mk("lookup", "Customer master data", f"Find customer **{cu['name']}** in `customers.csv` and return `customer_id`, `region`, `tier` and `account_mgr`.",
                {"check": "value", "expected": {"customer_id": cu["customer_id"], "region": cu["region"], "tier": cu["tier"], "account_mgr": cu["account_mgr"]}},
                '{"customer_id": "...", "region": "...", "tier": "...", "account_mgr": "..."}', 1, ctx, ["customers.csv"]))

    # 12 customer past-due detail
    cu = max(cus, key=lambda c: sum(1 for o in ds["cust_orders"] if o["customer_id"] == c["customer_id"] and o["status"] == "Open" and o["due_date"] < ASOF.isoformat()))
    rows = sorted([{"order_id": o["order_id"], "end_item": o["end_item"], "qty": o["qty"], "days_past_due": (ASOF - date.fromisoformat(o["due_date"])).days}
                   for o in ds["cust_orders"] if o["customer_id"] == cu["customer_id"] and o["status"] == "Open" and o["due_date"] < ASOF.isoformat()],
                  key=lambda r: (-r["days_past_due"], r["order_id"]))
    T.append(mk("detail", "Customer past-due detail",
                f"List every **open** sales order for customer **{cu['customer_id']}** in `customer_orders.csv` whose `due_date` is before the as-of date. For each give `order_id`, `end_item`, `qty`, `days_past_due` (as-of date minus due date). Sort by days_past_due descending, then order_id.",
                {"check": "table", "expected": rows, "keys": ["order_id"], "ordered": True}, '[{"order_id": "SO...", "end_item": "E-1xx", "qty": <int>, "days_past_due": <int>}, ...]', 2, ctx, ["customer_orders.csv"]))

    # 13 MPS plan trend
    e = eis[0]
    fw = [w.isoformat() for w in ds["weeks"][12:]]
    mp = {r["week_start"]: r["planned_qty"] for r in ds["mps"] if r["end_item"] == e and r["week_start"] in fw}
    T.append(mk("trend", "MPS plan over time",
                f"For end item **{e}**, list planned_qty for each of the 13 weeks from 2025-09-29 onward (`mps_plan.csv`), give the `peak_week` (earliest week if tied) and the `total` planned qty.",
                {"check": "value", "expected": {"weekly": mp, "peak_week": min((w for w in mp if mp[w] == max(mp.values()))), "total": sum(mp.values())}, "tol_abs": 0.5},
                '{"weekly": {"2025-09-29": <int>, ...13 weeks}, "peak_week": "YYYY-MM-DD", "total": <int>}', 1, ctx, ["mps_plan.csv"]))

    # 14 plan vs actual
    e = eis[1]
    pw = [w.isoformat() for w in ds["weeks"][4:12]]
    pl = {r["week_start"]: r["planned_qty"] for r in ds["mps"] if r["end_item"] == e and r["week_start"] in pw}
    ac = {r["week_start"]: r["actual_qty"] for r in ds["actuals"] if r["end_item"] == e and r["week_start"] in pw}
    rows = [{"week_start": w, "plan": pl[w], "actual": ac[w], "delta": ac[w] - pl[w]} for w in pw]
    T.append(mk("comparison", "Plan vs actual production",
                f"For end item **{e}**, for the 8 weeks starting 2025-08-04 through 2025-09-22, compare plan (mps_plan.csv) vs actual (production_actuals.csv). Return per-week plan, actual, delta (actual - plan) and the overall `attainment_pct` (total actual / total plan x 100, 1 decimal).",
                {"check": "value", "expected": {"weeks": rows, "attainment_pct": round(100 * sum(ac.values()) / sum(pl.values()), 1)}, "tol_abs": 0.11},
                '{"weeks": [{"week_start": "...", "plan": <int>, "actual": <int>, "delta": <int>}, ...8], "attainment_pct": <float>}', 2, ctx, ["mps_plan.csv", "production_actuals.csv"]))

    # 15 pacing rank
    att = {}
    for e2 in ds["eis"]:
        pp = sum(r["planned_qty"] for r in ds["mps"] if r["end_item"] == e2 and r["week_start"] in pw)
        aa = sum(r["actual_qty"] for r in ds["actuals"] if r["end_item"] == e2 and r["week_start"] in pw)
        att[e2] = round(100 * aa / pp, 1) if pp else 0
    worst5 = sorted(att.items(), key=lambda x: (x[1], x[0]))[:5]
    T.append(mk("ranking", "Slipping end items (pacing)",
                "Using the same 8-week window (2025-08-04 .. 2025-09-22), compute attainment % (sum actual / sum plan x 100, 1 decimal) per end item. Return the **5 end items with the lowest attainment**, lowest first (ties by id).",
                {"check": "table", "expected": [{"end_item": k, "attainment_pct": v} for k, v in worst5], "keys": ["end_item"], "ordered": True, "tol_abs": 0.11},
                '[{"end_item": "E-1xx", "attainment_pct": <float>}, ... 5 rows]', 2, ctx, ["mps_plan.csv", "production_actuals.csv"]))

    # 16 demonstrated execution exception
    exc = []
    for e2 in ds["eis"]:
        mx = max(r["actual_qty"] for r in ds["actuals"] if r["end_item"] == e2)
        for r in ds["mps"]:
            if r["end_item"] == e2 and r["week_start"] in fw[:8] and r["planned_qty"] > 1.2 * mx:
                exc.append({"end_item": e2, "week_start": r["week_start"]})
    T.append(mk("exception", "Plan above demonstrated execution",
                "An end item is **planned above demonstrated execution** in a week when its planned_qty is more than 1.2 x the **maximum weekly actual_qty ever recorded** for that item (production_actuals.csv). Check the 8 future weeks starting 2025-09-29 through 2025-11-17 and list every (end_item, week_start) exception.",
                {"check": "set", "expected": exc}, '[{"end_item": "E-1xx", "week_start": "YYYY-MM-DD"}, ...]  (empty list if none)', 3, ctx, ["mps_plan.csv", "production_actuals.csv"]))

    # 17 overload
    f4 = [w.isoformat() for w in ds["weeks"][12:16]]
    req = defaultdict(float)
    for r in ds["mps"]:
        if r["week_start"] in f4:
            for rt in ds["routing"]:
                if rt["end_item"] == r["end_item"]:
                    req[(rt["cell"], r["week_start"])] += r["planned_qty"] * rt["hours_per_unit"]
    cap = {(c["cell"], c["week_start"]): c["capacity_hours"] for c in ds["capacity"]}
    over = sorted([{"cell": c, "week_start": w} for (c, w), h in req.items() if (c, w) in cap and h > cap[(c, w)]], key=lambda x: (x["cell"], x["week_start"]))
    nocap = sorted({c for (c, w) in req if (c, w) not in cap})
    T.append(mk("exception", "Capacity overload with data gaps",
                "Required hours for a cell in a week = sum over end items of planned_qty x hours_per_unit (routing.csv). A cell is **overloaded** in a week when required hours exceed `capacity_hours` in cell_capacity.csv. "
                "Check the 4 weeks starting 2025-09-29, 2025-10-06, 2025-10-13, 2025-10-20.\n\nReturn every overloaded (cell, week_start), and separately list any cells that have routed work but **no capacity data at all** (these cannot be assessed).",
                {"check": "value", "expected": {"overloaded": over, "no_capacity_data": nocap}},
                '{"overloaded": [{"cell": "CELL-X", "week_start": "YYYY-MM-DD"}, ...], "no_capacity_data": ["CELL-?"]}', 3, ctx, ["mps_plan.csv", "routing.csv", "cell_capacity.csv"],
                tags=["honest_limit"]))

    # 18 shortage triage
    e = eis[2]
    f4m = [r for r in ds["mps"] if r["end_item"] == e and r["week_start"] in f4]
    units = sum(r["planned_qty"] for r in f4m)
    need = explode(ds, e, units)
    inv = {r["part_id"]: r for r in ds["inventory"]}
    short = []
    for c, qn in need.items():
        if not c.startswith("C-"):
            continue
        supply = inv[c]["on_hand"] + inv[c]["in_transit"] + sum(open_qty(p) for p in ds["po"] if p["part_id"] == c and open_qty(p) > 0 and "2025-09-29" <= p["need_date"] <= "2025-10-26")
        if qn > supply:
            short.append((qn - supply, c))
    short.sort(key=lambda x: (-x[0], x[1]))
    T.append(mk("summary", "Shortage triage",
                f"Build plan: end item **{e}**, total planned qty over the 4 weeks starting 2025-09-29..2025-10-20 (see mps_plan.csv). Explode the full multi-level BOM to get total requirement of each COMPONENT (C-xxxx) for those units.\n\n"
                "Available supply for a component = inventory on_hand + in_transit + open qty (ordered - received, only if > 0) of its PO lines with need_date between 2025-09-29 and 2025-10-26 inclusive. "
                "Shortfall = requirement - supply when positive.\n\nReturn `num_short_components`, the 3 worst `top_shortages` (largest shortfall first, ties by part id) with their shortfall qty, and `total_shortfall_units`.",
                {"check": "value", "expected": {"num_short_components": len(short), "top_shortages": [{"part_id": p, "shortfall": g} for g, p in short[:3]], "total_shortfall_units": sum(g for g, _ in short)}},
                '{"num_short_components": <int>, "top_shortages": [{"part_id": "C-..", "shortfall": <num>}, x3], "total_shortfall_units": <num>}', 3, ctx,
                ["bom.csv", "mps_plan.csv", "inventory.csv", "po_lines.csv"]))

    # 19 pegging
    comp = rng.choice(ds["cs"])
    sup_qty = 200 + rng.randint(0, 150)
    demands = []
    for w in f4:
        for e2 in sorted(ds["eis"]):
            pq = next(r["planned_qty"] for r in ds["mps"] if r["end_item"] == e2 and r["week_start"] == w)
            per = explode(ds, e2, 1).get(comp, 0)
            if per and pq:
                demands.append((w, e2, pq * per))
    left, alloc = sup_qty, {}
    for w, e2, q in demands:
        a = min(left, q)
        alloc[(e2)] = alloc.get(e2, 0) + a
        left -= a
    exp = {"allocated_by_end_item": {k: v for k, v in sorted(alloc.items()) if v > 0}, "unallocated_demand": sum(q for *_, q in demands) - sup_qty if sum(q for *_, q in demands) > sup_qty else 0}
    T.append(mk("drilldown", "Constrained supply pegging",
                f"Only **{sup_qty}** units of component **{comp}** are available for the 4 weeks starting 2025-09-29..2025-10-20. Its demand comes from end-item MPS lines: planned_qty x (qty of {comp} needed per end item, via full BOM explosion).\n\n"
                "Peg the supply to demand in order of **week (earliest first), then end item id ascending**, giving each line as much as remains (partial allocation allowed). Return total allocated per end item (end items with 0 allocated omitted) and the `unallocated_demand` (total demand not covered; 0 if fully covered).",
                {"check": "value", "expected": exp}, '{"allocated_by_end_item": {"E-1xx": <num>, ...}, "unallocated_demand": <num>}', 3, ctx, ["bom.csv", "mps_plan.csv"]))

    # 20 BOM explosion
    e = rng.choice([x for x in ds["eis"] if any(r["parent"] == x and r["child"] in ds["sas"] for r in ds["bom"])])
    n = rng.choice([5, 8, 12])
    ex = {k: v for k, v in sorted(explode(ds, e, n).items()) if k.startswith("C-")}
    T.append(mk("bom", "Multi-level BOM explosion", f"Fully explode end item **{e}** for **{n} units** through all BOM levels (`bom.csv`). Return the total quantity of each COMPONENT part (C-xxxx; ignore subassemblies in the result) required.",
                {"check": "value", "expected": ex, "tol_abs": 0.5}, '{"C-3001": <num>, ...}  (components only)', 3, ctx, ["bom.csv"]))

    # 21 line of balance
    comp = rng.choice(ds["cs"])
    sup_by = defaultdict(float)
    for p in ds["po"]:
        if p["part_id"] == comp and open_qty(p) > 0:
            wk = monday(date.fromisoformat(p["need_date"])).isoformat()
            sup_by[wk] += open_qty(p)
    inv = {r["part_id"]: r for r in ds["inventory"]}
    bal = inv[comp]["on_hand"]
    lob, first_neg = {}, None
    for w in [x.isoformat() for x in ds["weeks"][12:20]]:
        dem = sum(r["planned_qty"] * explode(ds, r["end_item"], 1).get(comp, 0) for r in ds["mps"] if r["week_start"] == w)
        bal += sup_by.get(w, 0) - dem
        lob[w] = bal
        if bal < 0 and first_neg is None:
            first_neg = w
    T.append(mk("trend", "Line of balance",
                f"Build a weekly line of balance for component **{comp}** over the 8 weeks starting 2025-09-29..2025-11-17. Start with `on_hand` from inventory.csv. For each week add supply (open PO qty = ordered - received, if > 0, whose need_date falls in that Monday-start week; earlier open lines are ignored) and subtract demand (that week's MPS planned_qty of every end item x qty of {comp} per end item via full BOM explosion). "
                "Return the ending balance for each week and `first_negative_week` (null if never negative).",
                {"check": "value", "expected": {"balance": lob, "first_negative_week": first_neg}, "tol_abs": 0.5},
                '{"balance": {"2025-09-29": <num>, ...8 weeks}, "first_negative_week": "YYYY-MM-DD"|null}', 3, ctx, ["bom.csv", "mps_plan.csv", "inventory.csv", "po_lines.csv"]))

    # 22 planner/buyer hierarchy
    p = rng.choice([x for x in ds["parts"] if x["type"] == "COMPONENT"])
    pl_ = next(o for o in ds["org"] if o["person_id"] == p["planner_id"])
    byr = next(o for o in ds["org"] if o["person_id"] == next(s for s in ds["suppliers"] if s["supplier_id"] == p["supplier_id"])["buyer_id"])
    sv = next(o for o in ds["org"] if o["person_id"] == pl_["reports_to"])
    T.append(mk("lookup", "Ownership hierarchy", f"For part **{p['part_id']}**, who is its planner (`planner_name`), the planner's supervisor (`planner_supervisor`), and the buyer for its supplier (`buyer_name`)? Use parts.csv, suppliers.csv and org.csv.",
                {"check": "value", "expected": {"planner_name": pl_["name"], "planner_supervisor": sv["name"], "buyer_name": byr["name"]}},
                '{"planner_name": "...", "planner_supervisor": "...", "buyer_name": "..."}', 2, ctx, ["parts.csv", "suppliers.csv", "org.csv"]))

    # 23 inventory/buildability
    e = eis[3]
    direct = [r for r in ds["bom"] if r["parent"] == e]
    best = None
    for r in direct:
        i = inv[r["child"]]
        b = (i["on_hand"] + i["wip_qty"]) // r["qty_per"]
        if best is None or (b, r["child"]) < best[:2]:
            best = (b, r["child"])
    T.append(mk("summary", "Buildability summary",
                f"For end item **{e}**, look only at its **direct (level-1) BOM children**. For each child, buildable units = floor((on_hand + wip_qty) / qty_per) using inventory.csv. The end item's `buildable_units` is the minimum across children and `limiting_part` is the child that sets it (ties: lowest part id).",
                {"check": "value", "expected": {"buildable_units": best[0], "limiting_part": best[1]}}, '{"buildable_units": <int>, "limiting_part": "..."}', 2, ctx, ["bom.csv", "inventory.csv"]))

    # 24 MRP messages
    comp = max(ds["cs"], key=lambda c: sum(1 for m in ds["mrp"] if m["part_id"] == c))
    rows = sorted([{"po_line": m["po_line"], "message": m["message"], "from_date": m["from_date"]} for m in ds["mrp"] if m["part_id"] == comp], key=lambda r: r["po_line"])
    T.append(mk("lookup", "MRP messages", f"List all MRP action messages for part **{comp}** from `mrp_messages.csv` with `po_line`, `message`, `from_date`, sorted by po_line ascending.",
                {"check": "table", "expected": rows, "keys": ["po_line"], "ordered": True}, '[{"po_line": "...", "message": "...", "from_date": "YYYY-MM-DD"}, ...]', 1, ctx, ["mrp_messages.csv"]))

    # 25 supplier forecast compare
    s = sup[4]
    v = defaultdict(dict)
    for r in ds["fc_sup"]:
        if r["supplier_id"] == s["supplier_id"]:
            v[r["month"]][r["version"]] = r["qty"]
    rows = [{"month": m, "v1": v[m]["v1"], "v2": v[m]["v2"], "delta": v[m]["v2"] - v[m]["v1"]} for m in sorted(v)]
    big = max(rows, key=lambda r: (abs(r["delta"]), r["month"]))["month"]
    T.append(mk("comparison", "Forecast version comparison",
                f"For supplier **{s['supplier_id']}**, compare forecast versions v1 and v2 by month in `supplier_forecast.csv`. Give v1, v2, delta (v2 - v1) per month, and `largest_change_month` (largest absolute delta).",
                {"check": "value", "expected": {"months": rows, "largest_change_month": big}}, '{"months": [{"month": "YYYY-MM", "v1": <int>, "v2": <int>, "delta": <int>}, ...6], "largest_change_month": "YYYY-MM"}', 2, ctx, ["supplier_forecast.csv"]))

    # 26 customer forecast vs orders
    cu = cus[2]
    rows = [{"month": r["month"], "forecast": r["forecast_qty"], "orders": r["order_qty"], "variance_pct": round(100 * (r["order_qty"] - r["forecast_qty"]) / r["forecast_qty"], 1)}
            for r in ds["fc_cust"] if r["customer_id"] == cu["customer_id"]]
    tf, to = sum(r["forecast"] for r in rows), sum(r["orders"] for r in rows)
    T.append(mk("comparison", "Customer demand vs forecast",
                f"For customer **{cu['customer_id']}** (`customer_forecast.csv`): per month give forecast, orders (order_qty) and variance_pct = (orders - forecast) / forecast x 100 (1 decimal). Also give overall `total_variance_pct` over all 6 months (same formula on the totals, 1 decimal).",
                {"check": "value", "expected": {"months": rows, "total_variance_pct": round(100 * (to - tf) / tf, 1)}, "tol_abs": 0.11},
                '{"months": [{"month": "..", "forecast": <int>, "orders": <int>, "variance_pct": <float>}, ...], "total_variance_pct": <float>}', 2, ctx, ["customer_forecast.csv"]))

    # ---- unanswerable / data-limit twins (counted under hallucination in report via tag)
    cap_missing = "CELL-F"
    T.append(mk("honest_limit", "Capacity for a cell with no data",
                f"What is the weekly capacity (in hours) of **{cap_missing}** for the week starting 2025-10-06? Answer from the provided files.",
                {"check": "cannot_answer"}, '{"answer": <number>} - or follow the "cannot answer" rule if the data cannot support it', 2, ctx, ["cell_capacity.csv"], answerable=False, tags=["hallucination_trap"]))
    T.append(mk("honest_limit", "Supplier scorecard rating that is not in the data",
                f"What is supplier **{sup[5]['supplier_id']}**'s quality PPM (defective parts per million) for 2025 Q3?", {"check": "cannot_answer"},
                '{"answer": <number>} or cannot_answer', 1, ctx, ["suppliers.csv", "receipts.csv"], answerable=False, tags=["hallucination_trap"]))
    T.append(mk("honest_limit", "Part that does not exist",
                "What is the standard cost of component **C-3999**, and which supplier provides it?", {"check": "cannot_answer"}, '{"answer": {"std_cost": <number>, "supplier_id": ".."}} or cannot_answer', 1, ctx, ["parts.csv"],
                answerable=False, tags=["hallucination_trap"]))
    return T
