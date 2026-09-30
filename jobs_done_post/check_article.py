#!/usr/bin/env python3
"""Check a Jobs Done article against the data and the editorial rules.

    python3 check_article.py articles/article_2026-08.md

Two families of checks:

  NUMBERS  every figure in the article must trace back to the CSVs in data/.
           A figure written with an explicit sign must carry the sign the data
           has: the July 2026 issue stated Content at -0.5% MoM when it had in
           fact grown +0.5%, which is the class of error this catches.

  RULES    the editorial conventions recorded in jobs_done_post/writing-rules.md and
           .claude/skills/monthly-jobs-done-article/references/writing-rules.md. Deterministic, so
           they never depend on anyone remembering them.

Exit codes: 0 clean, 1 failures, 2 the article or its data could not be read.
Warnings never fail the run; they ask a human to confirm a judgement the script
cannot make on its own.
"""

import csv
import re
import sys
from pathlib import Path

from jobs_done_common import (EMOJI, FRESH_HOURS, GO_LIVE, SCOPE, SCOPE_GROUP, YOY,
                              check_numbers, check_wording, num, pct, stale)

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

SCOPE_SENTENCE_FROM = "2026-09"   # first issue carrying the sentence

READ = []   # data files the check read, for the freshness check


def fail(msg):
    print(f"  KO  {msg}")


def adj(ym, d):
    y, m = int(ym[:4]), int(ym[5:7]) + d
    while m > 12: m -= 12; y += 1
    while m < 1:  m += 12; y -= 1
    return f"{y}-{m:02d}"


def load(platform):
    """Latest all/features CSV pair for a platform."""
    def latest(pat):
        f = sorted(DATA_DIR.glob(pat))
        return f[-1] if f else None
    a_path, f_path = latest(f"{platform}_all_*.csv"), latest(f"{platform}_features_*.csv")
    if not a_path or not f_path:
        sys.exit(f"[check_article] no data for {platform} in {DATA_DIR}. Run: python3 prepare_data.py")
    READ.extend([a_path, f_path])
    allr, feat = {}, {}
    with open(a_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            allr[r["Calendar Month"]] = r
    with open(f_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            feat.setdefault(r["Feature"], {})[r["Calendar Month"]] = r
    return allr, feat


def load_agents(platform):
    """{agent: {month: row}} from the per-agent file, empty when there is none."""
    f = sorted(DATA_DIR.glob(f"{platform}_agents_*.csv"))
    if not f:
        return {}
    READ.append(f[-1])
    out = {}
    with open(f[-1], encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["Agent"], {})[r["Calendar Month"]] = r
    return out


def agent_values(agents, month):
    """Figures the Agents paragraph may quote about individual agents."""
    cur = {a: m[month] for a, m in agents.items() if m.get(month)}
    total = sum(num(r["Jobs Done"]) for r in cur.values())
    out = []
    for a, r in cur.items():
        jd, users = num(r["Jobs Done"]), num(r["Jobs Done Users"])
        out += [("K", jd / 1e3), ("K", users / 1e3)]
        if total:
            out.append(("%", jd / total * 100))          # share of all agents
        prev = agents[a].get(adj(month, -1))
        if prev:
            out += [("%", pct(jd, num(prev["Jobs Done"]))),
                    ("%", pct(users, num(prev["Jobs Done Users"]))),
                    ("K", num(prev["Jobs Done"]) / 1e3)]
    return [(u, v) for u, v in out if v is not None]


def platform_values(allr, month):
    """Every figure the overview and platform intro may legitimately quote."""
    cur, prev, yoy = allr.get(month), allr.get(adj(month, -1)), allr.get(adj(month, -12))
    if not cur:
        sys.exit(f"[check_article] month {month} missing from the data. Run: python3 prepare_data.py --fetch --month {month}")
    out = []
    out_freq = []
    if prev and cur.get("Frequency"):
        out_freq.append(("%", pct(num(cur["Frequency"]), num(prev["Frequency"]))))
    for col, unit in (("Jobs Done", "M"), ("Jobs Done Users", "K"), ("MAU", "K")):
        v = num(cur[col])
        out += [(unit, v / (1e6 if unit == "M" else 1e3)), ("K", v / 1e3), ("M", v / 1e6)]
        if prev:
            out.append(("%", pct(v, num(prev[col]))))
        if yoy:
            out.append(("%", pct(v, num(yoy[col]))))
    # Neighbouring months are fair game: an article legitimately says "stays below
    # June's 35.8M", or contrasts this month's move with last month's.
    for back in (1, 2):
        m, before = adj(month, -back), adj(month, -back - 1)
        if not allr.get(m):
            continue
        out += [("M", num(allr[m]["Jobs Done"]) / 1e6), ("K", num(allr[m]["MAU"]) / 1e3),
                ("K", num(allr[m]["Jobs Done Users"]) / 1e3)]
        if allr.get(before):
            for col in ("Jobs Done", "Jobs Done Users", "MAU", "Frequency"):
                out.append(("%", pct(num(allr[m][col]), num(allr[before][col]))))
    return [(u, v) for u, v in out + out_freq if v is not None]


def feature_values(feat, name, month, allr):
    cur = feat.get(name, {}).get(month)
    if not cur:
        return None
    prev, yoy = feat[name].get(adj(month, -1)), feat[name].get(adj(month, -12))
    out = []
    jd, users, freq, mau = (num(cur["Jobs Done"]), num(cur["Jobs Done Users"]),
                            num(cur["Frequency"]), num(cur.get("MAU", 0)))
    out += [("M", jd / 1e6), ("K", jd / 1e3), ("K", users / 1e3), ("M", users / 1e6)]
    if mau:
        out.append(("%", users / mau * 100))          # reach
    before = feat[name].get(adj(month, -2))
    for col, val in (("Jobs Done", jd), ("Jobs Done Users", users), ("Frequency", freq)):
        if prev:
            out.append(("%", pct(val, num(prev[col]))))
            if before:   # last month's own move, e.g. "after July's -9.4%"
                out.append(("%", pct(num(prev[col]), num(before[col]))))
        if yoy:
            out.append(("%", pct(val, num(yoy[col]))))
    if prev:
        out += [("M", num(prev["Jobs Done"]) / 1e6), ("K", num(prev["Jobs Done Users"]) / 1e3)]
        # share of the platform's monthly change
        pc, pp = allr.get(month), allr.get(adj(month, -1))
        if pc and pp:
            chg = num(pc["Jobs Done"]) - num(pp["Jobs Done"])
            if chg:
                out.append(("%", (jd - num(prev["Jobs Done"])) / chg * 100))
    return [(u, v) for u, v in out if v is not None]


def expected_scope(feat, month):
    """{domain group: {features}} tracked in the report month."""
    scope = {}
    for name, months in feat.items():
        row = months.get(month)
        if row and num(row["Jobs Done"]) and GO_LIVE.get(name, month) <= month:
            scope.setdefault(row["Product Domain Group"], set()).add(name)
    return scope


def check_scope(sec, feat, month, plat, failures):
    m = SCOPE.search(sec)
    if not m:
        failures.append(f"{plat}: missing the scope sentence 'Jobs Done covers <Domain> (<Feature>, ...)'")
        return
    written = {d: {f.strip() for f in fs.split(",") if f.strip()}
               for d, fs in SCOPE_GROUP.findall(m.group(1))}
    want = expected_scope(feat, month)
    for d in sorted(want.keys() - written.keys()):
        failures.append(f"{plat}: scope sentence misses the domain {d} ({', '.join(sorted(want[d]))})")
    for d in sorted(written.keys() - want.keys()):
        failures.append(f"{plat}: scope sentence lists {d}, which is not tracked in {month}")
    for d in sorted(want.keys() & written.keys()):
        for f in sorted(want[d] - written[d]):
            failures.append(f"{plat}: scope sentence misses {f} under {d}")
        for f in sorted(written[d] - want[d]):
            failures.append(f"{plat}: scope sentence lists {f} under {d}, which is not tracked in {month}")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_article.py articles/article_YYYY-MM.md")
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"[check_article] no such file: {path}")
    m = re.search(r"article_(\d{4}-\d{2})\.md$", path.name)
    if not m:
        sys.exit(f"[check_article] filename must be article_YYYY-MM.md, got {path.name}")
    month = m.group(1)
    text = path.read_text(encoding="utf-8")

    failures, warnings = [], []

    # ---- structure -------------------------------------------------------
    if not re.search(r"^# Jobs Done - \w+ \d{4} Product Performance$", text, re.M):
        failures.append("title must read '# Jobs Done - <Month> <Year> Product Performance'")
    for needle, what in (
        ("Hi Team, here is how our key product usage KPI", "standard opening sentence"),
        ("*Don't you know what \"Jobs Done\" metrics are?", "italicised intro link"),
        ("*Full breakdown available in the [LumApps Jobs Done dashboard]", "italicised LumApps dashboard link"),
        ("*Full breakdown available in the [Beekeeper Jobs Done dashboard]", "italicised Beekeeper dashboard link"),
    ):
        if needle not in text:
            failures.append(f"missing {what}")

    # ---- wording ---------------------------------------------------------
    check_wording(text, failures, warnings)

    # ---- sections --------------------------------------------------------
    overview = text.split("## LumApps")[0]
    body = text.split("## LumApps", 1)[1] if "## LumApps" in text else ""
    sections = {}
    if body:
        la, _, bk = body.partition("## Beekeeper")
        sections = {"lumapps": la, "beekeeper": bk}

    for plat, sec in sections.items():
        paras = [p for p in sec.split("\n\n")
                 if re.match(r"^[^\w\s*]", p.strip()) and "**" in p]
        if len(paras) > 3:
            failures.append(f"{plat}: {len(paras)} feature paragraphs, 3 is the maximum")
        for p in paras:
            for hit in re.finditer(YOY, p, re.I):
                failures.append(f"{plat}: year-over-year in a feature paragraph: {hit.group(0)!r}")
            fm = re.search(r"\*\*([A-Z][\w &]*?)\*\*", p)
            if fm and fm.group(1) in EMOJI and EMOJI[fm.group(1)] not in p:
                failures.append(f"{plat}: {fm.group(1)} should use {EMOJI[fm.group(1)]}")

    # ---- figures ---------------------------------------------------------
    la_all, la_feat = load("lumapps")
    bk_all, bk_feat = load("beekeeper")
    la_agents = load_agents("lumapps")
    check_numbers(overview, platform_values(la_all, month) + platform_values(bk_all, month),
                  "overview", failures)
    for plat, sec, (allr, feat) in (("lumapps", sections.get("lumapps", ""), (la_all, la_feat)),
                                    ("beekeeper", sections.get("beekeeper", ""), (bk_all, bk_feat))):
        if not sec:
            continue
        if month >= SCOPE_SENTENCE_FROM:
            check_scope(sec, feat, month, plat, failures)
        allowed = platform_values(allr, month)
        for p in sec.split("\n\n"):
            fm = re.search(r"\*\*([A-Z][\w &]*?)\*\*", p)
            vals = feature_values(feat, fm.group(1), month, allr) if fm else None
            if fm and fm.group(1) == "Agents" and plat == "lumapps":
                vals = (vals or []) + agent_values(la_agents, month)
            check_numbers(p, allowed + (vals or []), f"{plat}/{fm.group(1) if fm else 'intro'}",
                          failures)

    # ---- freshness -------------------------------------------------------
    for p, hours in stale(READ):
        failures.append(f"data is {hours:.0f}h old ({p.name}): an article is checked on data "
                        f"fetched within {FRESH_HOURS}h. Re-run python3 prepare_data.py")

    # ---- report ----------------------------------------------------------
    print(f"[check_article] {path.name} ({month})")
    for w in warnings:
        print(f"  !   {w}")
    for f in failures:
        fail(f)
    if failures:
        print(f"\n  {len(failures)} failure(s). Fix the article, or the data is stale: "
              f"python3 prepare_data.py")
        return 1
    print(f"  OK  no failures ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
