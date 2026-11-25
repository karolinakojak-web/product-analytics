#!/usr/bin/env python3
"""Check a monthly Jobs Done article against the data and the editorial rules.

    python3 check_article.py data/drafts/article_2026-10.md

The article reports LumApps and Beekeeper combined: an overview, then five feature
paragraphs. Checks:

  OVERVIEW the five KPI lines, to the digit, as prepare_data.py prints them: they are
           the figures of the dashboard's Overview tab.
  NUMBERS  every other figure must trace back to the CSVs in data/. A figure written
           with an explicit sign must carry the sign the data has: the July 2026 issue
           stated Content at -0.5% MoM when it had in fact grown +0.5%, which is the
           class of error this catches.
  RULES    the editorial conventions recorded in jobs_done_post/writing-rules.md and
           .claude/skills/monthly-jobs-done-article/references/writing-rules.md.
  VOLUME   no daily volume alert left without a verdict, and a "*Data warning: ...*"
           line when a data incident is on record for the period.

Exit codes: 0 clean, 1 failures, 2 the article or its data could not be read.
Warnings never fail the run; they ask a human to confirm a judgement the script
cannot make on its own.
"""

import re
import sys
from pathlib import Path

import prepare_data
from jobs_done_common import (EMOJI, FRESH_HOURS, GO_LIVE, KPI_EMOJI, SCOPE, YOY, check_numbers, check_scope,
                              check_overview, check_volume, check_wording, dashboard_line,
                              overview_lines, pct, stale)
from prepare_data import adj_month, data_file, month_kpis, read_features, read_totals

FEATURES_SECTION = "## Features of the month"
FEATURE_PARAGRAPHS = 5
INTRO_LINK = "*Don't you know what \"Jobs Done\" metrics are?"
OPENING = ("Hi Team, here is how our key product usage KPI, Jobs Done, performed in {month} "
           "across LumApps and Beekeeper.")
FEATURE_NAME = re.compile(r"\*\*([A-Z][\w &]*?)\*\*")


def total_values(totals, month):
    """Every figure the overview prose may quote: this month, and the two before it,
    since an article legitimately contrasts this month's move with last month's."""
    out = []
    for back in (0, 1, 2):
        m = adj_month(month, -back)
        cur, prev = month_kpis(totals, m), month_kpis(totals, adj_month(m, -1))
        if not cur:
            continue
        for k in ("jd", "users", "mau"):
            out += [("M", cur[k] / 1e6), ("K", cur[k] / 1e3)]
        out.append(("%", cur["reach"]))
        if prev:
            out += [("%", pct(cur[k], prev[k])) for k in ("jd", "users", "jpu", "mau")]
    return [(u, v) for u, v in out if v is not None]


def feature_values(history, totals, group, name, month):
    """Every figure a paragraph on this feature may quote."""
    by_month = history.get((group, name), {})
    cur = by_month.get(month)
    if not cur:
        return []
    prev, before = by_month.get(adj_month(month, -1)), by_month.get(adj_month(month, -2))
    out = [("M", cur["jd"] / 1e6), ("K", cur["jd"] / 1e3), ("K", cur["users"] / 1e3),
           ("M", cur["users"] / 1e6)]
    if cur["mau"]:
        out.append(("%", cur["users_28d"] / cur["mau"] * 100))       # reach, 28-day users
    group_jd = sum(m[month]["jd"] for (g, _), m in history.items() if g == group and m.get(month))
    total = totals.get(month, {}).get("jd")
    out += [("%", cur["jd"] / group_jd * 100)] if group_jd else []   # share of its group
    out += [("%", cur["jd"] / total * 100)] if total else []         # share of all Jobs Done

    def jpu(r):
        return r["jd"] / r["users"] if r and r["users"] else None

    for a, b in ((cur, prev), (prev, before)):     # this month's move, and last month's
        if a and b:
            out += [("%", pct(a["jd"], b["jd"])), ("%", pct(a["users"], b["users"]))]
            if jpu(a) and jpu(b):
                out.append(("%", pct(jpu(a), jpu(b))))
    if prev:
        change = cur["jd"] - prev["jd"]    # "up 714K Jobs Done"
        out += [("M", prev["jd"] / 1e6), ("K", prev["jd"] / 1e3), ("K", prev["users"] / 1e3),
                ("M", change / 1e6), ("K", change / 1e3)]
    return [(u, v) for u, v in out if v is not None]


def agent_values(month):
    """Figures the Agents paragraph may quote about individual agents."""
    path = data_file("agents", month)
    if not path.exists():
        return []
    agents = {}
    for r in prepare_data._read(path):
        agents.setdefault(r["Agent"], {})[r["Calendar Month"][:7]] = r
    cur = {a: m[month] for a, m in agents.items() if m.get(month)}
    num = prepare_data.num
    total = sum(num(r["Jobs Done"]) for r in cur.values())
    out = []
    for a, r in cur.items():
        jd, users = num(r["Jobs Done"]), num(r["Jobs Done Users"])
        out += [("K", jd / 1e3), ("K", users / 1e3)]
        if total:
            out.append(("%", jd / total * 100))
        prev = agents[a].get(adj_month(month, -1))
        if prev:
            out += [("%", pct(jd, num(prev["Jobs Done"]))),
                    ("%", pct(users, num(prev["Jobs Done Users"]))),
                    ("K", num(prev["Jobs Done"]) / 1e3)]
    return [(u, v) for u, v in out if v is not None]


def expected_scope(history, month):
    """{domain group: [features, largest first]} tracked in the report month."""
    scope = {}
    for (group, name), by_month in history.items():
        row = by_month.get(month)
        if row and row["jd"] and GO_LIVE.get(name, month) <= month:
            scope.setdefault(group, []).append((row["jd"], name))
    return {g: [n for _, n in sorted(v, reverse=True)] for g, v in scope.items()}


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_article.py data/drafts/article_YYYY-MM.md")
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"[check_article] no such file: {path}")
    m = re.search(r"article_(\d{4}-\d{2})\.md$", path.name)
    if not m:
        sys.exit(f"[check_article] filename must be article_YYYY-MM.md, got {path.name}")
    month = m.group(1)
    text = path.read_text(encoding="utf-8")
    failures, warnings = [], []

    totals, history = read_totals(month), read_features(month)
    cur, prev = month_kpis(totals, month), month_kpis(totals, adj_month(month, -1))
    if not cur:
        sys.exit(f"[check_article] {month} missing from the data. Run: python3 prepare_data.py "
                 f"--month {month}")
    month_name = prepare_data.date(int(month[:4]), int(month[5:]), 1).strftime("%B")

    # ---- structure -------------------------------------------------------
    if not re.search(r"^# Jobs Done - \w+ \d{4} Product Performance$", text, re.M):
        failures.append("title must read '# Jobs Done - <Month> <Year> Product Performance'")
    for needle, what in ((OPENING.format(month=month_name), "standard opening sentence"),
                         (INTRO_LINK, "italicised intro link"),
                         ("## High level overview", "overview heading"),
                         (FEATURES_SECTION, f"'{FEATURES_SECTION}' section"),
                         (dashboard_line("month"), "italicised dashboard line, copied as it is")):
        if needle not in text:
            failures.append(f"missing {what}")

    # ---- wording ---------------------------------------------------------
    check_wording(text, failures, warnings)
    for hit in re.finditer(YOY, text, re.I):
        failures.append(f"year-over-year: the dashboard shows none, so the article neither: "
                        f"{hit.group(0)!r}")

    # ---- overview --------------------------------------------------------
    overview = text.split("## High level overview", 1)[-1].split(FEATURES_SECTION)[0]
    check_overview(overview, overview_lines(cur, prev, "MoM"), failures)
    prose = "\n".join(l for l in overview.splitlines() if not l.strip().startswith(KPI_EMOJI))
    check_numbers(prose, total_values(totals, month), "overview", failures)

    # ---- features --------------------------------------------------------
    sec = text.split(FEATURES_SECTION, 1)[1] if FEATURES_SECTION in text else ""
    want = expected_scope(history, month)
    group_of = {n: g for g, ns in want.items() for n in ns}
    if sec:
        check_scope(sec, want, month, failures)
        paras = [p.strip() for p in sec.split("\n\n")
                 if re.match(r"^[^\w\s*]", p.strip()) and "**" in p]
        if len(paras) != FEATURE_PARAGRAPHS:
            failures.append(f"features: {len(paras)} feature paragraphs, write {FEATURE_PARAGRAPHS}")
        # One or two sentences introduce the features, before the first of them.
        before = sec.split(paras[0])[0] if paras else sec
        intro = [p for p in before.split("\n\n") if p.strip() and not SCOPE.search(p)
                 and not p.strip().startswith(("---", "*"))]
        if not intro:
            failures.append("features: introduce the features with one or two sentences, "
                            "after the scope sentence and before the first feature")
        for p in sec.split("\n\n"):
            fm = FEATURE_NAME.search(p)
            name = fm.group(1) if fm else None
            if name and p.strip() in paras:
                if name not in group_of:
                    failures.append(f"features: {name} is not a feature tracked in {month}")
                elif name in EMOJI and not p.strip().startswith(EMOJI[name]):
                    failures.append(f"features: {name} should open on {EMOJI[name]}")
            if name:
                vals = feature_values(history, totals, group_of.get(name), name, month)
            else:   # the introduction tells the month's story: any feature may be quoted
                vals = [v for n, g in group_of.items()
                        for v in feature_values(history, totals, g, n, month)]
            if name == "Agents":
                vals += agent_values(month)
            check_numbers(p, total_values(totals, month) + vals, f"features/{name or 'intro'}",
                          failures)

    # ---- data volume -----------------------------------------------------
    # A broken pipeline leaves the figures traceable but wrong.
    check_volume(prepare_data.volume_alerts(month), text, failures)
    read = [data_file(k, month) for k in ("totals", "features", "daily_volume")]
    for p in read:
        if not p.exists():
            failures.append(f"no {p.name} on file: re-run python3 prepare_data.py --month {month}")

    # ---- freshness -------------------------------------------------------
    for p, hours in stale([p for p in read if p.exists()]):
        failures.append(f"data is {hours:.0f}h old ({p.name}): an article is checked on data "
                        f"fetched within {FRESH_HOURS}h. Re-run python3 prepare_data.py")

    # ---- report ----------------------------------------------------------
    print(f"[check_article] {path.name} ({month})")
    for w in warnings:
        print(f"  !   {w}")
    for f in failures:
        print(f"  KO  {f}")
    if failures:
        print(f"\n  {len(failures)} failure(s). Fix the article, or the data is stale: "
              f"python3 prepare_data.py --month {month}")
        return 1
    print(f"  OK  no failures ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
