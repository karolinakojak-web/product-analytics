#!/usr/bin/env python3
"""Prepare the quarterly Jobs Done analytics, LumApps and Beekeeper combined.

A quarter is read as the dashboard's Overview tab reads it with its Time Frame set to
"1 quarter ago for 1 quarter":

  Jobs Done               the daily Jobs Done of the calendar quarter, summed
  Users with a Job Done   unique users over the calendar quarter (not additive)
  MAU                     users active over the 28 days that end the quarter
  Reach                   users with a Job Done over those 28 days / MAU

and every change compares with the same figures for the quarter before.

Writes to data/quarterly/, one file per kind:
  totals_YYYY-QN.csv           both platforms together, last QUARTERS quarters
  features_YYYY-QN.csv         domain group x feature, same quarters
  companies_YYYY-QN.csv        top organizations per feature, report quarter only
  group_companies_YYYY-QN.csv  top organizations per domain group, same quarter
  feature_weeks_YYYY-QN.csv    weekly Jobs Done per feature, report quarter and the one
                               before, to catch steps and spikes
  anomaly_drivers_YYYY-QN.csv  the organizations behind each step or spike
  integrity_YYYY-QN.csv        checks on the company directory (see below)
  daily_volume_YYYY-QN.csv     daily Jobs Done per cell, to catch broken data

Usage:
    python3 prepare_quarterly.py                          last complete quarter
    python3 prepare_quarterly.py --quarter 2026-Q3
    python3 prepare_quarterly.py --quarter 2026-Q3 --no-fetch   re-read data/quarterly/
                                        (script work only, never for an article)
"""

import argparse
import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import median

from jobs_done_common import (GO_LIVE, LOOKER, QUARTERLY_EXCLUDED_ORGANIZATIONS, SMALL_SHARE,
                              STEP_WEEKS, VOLUME_HEADERS, anomaly_caveat, anomaly_review,
                              comparison_caveat, fetch_daily_volume, fmt_change, fmt_level, kpis,
                              looker_sdk_or_exit, month_label, num, overview_lines,
                              print_volume_alerts, read_volume_episodes, run_features, run_query,
                              weekly_anomaly, without_excluded_organizations)

DATA_DIR = Path(__file__).parent / "data" / "quarterly"

QUARTERS = 5          # the report quarter and the four before it
TOP_COMPANIES = 5     # kept per feature and per domain group; the article quotes the top 3

P = LOOKER["prefix"]
# Calendar quarter: the daily Jobs Done summed, the users counted once over the quarter.
JD, USERS = f"{P}.jobs_done", f"{P}.active_users"
# Last day of the quarter: the 28-day users (for Reach) and MAU.
USERS_28D, MAU = f"{P}.active_users_28d", LOOKER["mau_field"]
DAILY_JD, ORG = LOOKER["daily_jd_field"], LOOKER["org_field"]
QDIM, WDIM = f"{P}.calendar_quarter", f"{P}.calendar_week"
GROUP, FEATURE, DOMAIN = f"{P}.product_domain_group", f"{P}.feature", f"{P}.product_domain"
NAME_F, SLUG_F = LOOKER["company_fields"]

# The Salesforce account some customer organizations sit under by mistake (see
# integrity below). Its name says nothing about the organization.
CATCH_ALL_ACCOUNT = "LumApps"

TOTAL_HEADERS = ["Quarter", "Jobs Done", "Jobs Done Users", "Jobs Done Users 28d", "MAU"]
FEATURE_HEADERS = ["Quarter", "Product Domain Group", "Feature", "Jobs Done", "Jobs Done Users"]
COMPANY_HEADERS = ["Product Domain Group", "Feature", "Rank", "Company", "Slug", "Jobs Done"]
GROUP_COMPANY_HEADERS = ["Product Domain Group", "Rank", "Company", "Slug", "Jobs Done"]
WEEK_HEADERS = ["Week", "Product Domain Group", "Feature", "Jobs Done"]
INTEGRITY_HEADERS = ["Check", "Feature", "Organization", "Value", "Expected"]
DRIVER_HEADERS = ["Feature", "Kind", "Week", "Rank", "Company", "Slug", "Change", "Share of change"]


def data_file(kind: str, quarter: str) -> Path:
    return DATA_DIR / f"{kind}_{quarter}.csv"


# ---------------------------------------------------------------------------
# Quarters
# ---------------------------------------------------------------------------

def parse_quarter(q: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})-Q([1-4])", q)
    if not m:
        sys.exit(f"Error: quarter must look like 2026-Q3, got {q!r}")
    return int(m.group(1)), int(m.group(2))


def shift_quarter(q: str, delta: int) -> str:
    y, n = parse_quarter(q)
    i = y * 4 + (n - 1) + delta
    return f"{i // 4}-Q{i % 4 + 1}"


def quarter_start(q: str) -> date:
    y, n = parse_quarter(q)
    return date(y, 3 * (n - 1) + 1, 1)


def quarter_end(q: str) -> date:
    return quarter_start(shift_quarter(q, 1)) - timedelta(days=1)


def quarter_last_month(q: str) -> str:
    y, n = parse_quarter(q)
    return f"{y}-{3 * n:02d}"


def volume_period(q: str) -> tuple[date, date]:
    """The days the volume check covers: the quarter before and this one."""
    return quarter_start(shift_quarter(q, -1)), quarter_end(q)


def default_quarter() -> str:
    """Last complete calendar quarter."""
    t = date.today()
    return shift_quarter(f"{t.year}-Q{(t.month - 1) // 3 + 1}", -1)


def looker_quarter(v: str) -> str:
    """Looker's calendar_quarter ('2026-07') as '2026-Q3'."""
    y, m = v[:4], int(v[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}"


def date_range(first: str, last: str) -> str:
    """Looker filter covering every day from quarter `first` to quarter `last`."""
    return f"{quarter_start(first):%Y/%m/%d} to {quarter_start(shift_quarter(last, 1)):%Y/%m/%d}"


def every_day(first: str, last: str) -> dict:
    """Every day from quarter `first` to quarter `last`: the calendar figures."""
    return {f"{P}.calendar_date": date_range(first, last), f"{P}.day_selection": "any^_day"}


# ---------------------------------------------------------------------------
# Looker fetch
# ---------------------------------------------------------------------------

def _write(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({h: ("" if r.get(h) is None else r[h]) for h in headers})


def _company_names(sdk, cfg: dict, filters: dict, orgs: set) -> dict[str, tuple]:
    """organization_id -> (account name, slug).

    Dimensions only, no measure, so the join cannot inflate anything.
    """
    if not orgs:
        return {}
    rows = run_query(sdk, [ORG, NAME_F, SLUG_F], [], {**filters, ORG: ",".join(sorted(orgs))},
                     cfg=cfg)
    return {r[ORG]: (r[NAME_F].strip(), (r[SLUG_F] or "").strip())
            for r in rows if r.get(NAME_F) and r[NAME_F].strip()}


def _anomaly_drivers(sdk, cfg: dict, weeks: list[dict]) -> list[dict]:
    """For each step or spike, the organizations whose own weekly Jobs Done moved the most.

    A spike: each organization's spike week against the median of its neighbouring
    weeks. A step: each organization's median after against its median before. One
    organization explaining most of it points to that customer; a change spread over
    many points to what is counted (a tracking or product change), as with Search in
    August 2026.
    """
    series: dict[tuple, list] = {}
    for w in weeks:
        series.setdefault((w["Product Domain Group"], w["Feature"]), []).append(
            (w["Week"], num(w["Jobs Done"])))
    out = []
    for (group, feature), s in series.items():
        a = weekly_anomaly(s)
        if not a:
            continue
        week = date.fromisoformat(a["week"])
        span = STEP_WEEKS if a["kind"] == "step" else 4
        level = DOMAIN if group in cfg.get("domain_level_groups", []) else FEATURE
        window = {f"{P}.calendar_date": f"{week - timedelta(weeks=span):%Y/%m/%d} to "
                                        f"{week + timedelta(weeks=span + 1):%Y/%m/%d}",
                  f"{P}.day_selection": "any^_day"}
        rows = run_query(sdk, [WDIM, ORG], [DAILY_JD], {**window, GROUP: group, level: feature},
                         limit="50000", cfg=cfg)
        by_org: dict[str, dict] = {}
        for r in rows:
            by_org.setdefault(r[ORG], {})[r[WDIM]] = r[DAILY_JD] or 0
        moves = {}
        for t, v in by_org.items():
            before = [x for w, x in v.items() if w < a["week"]] or [0]
            if a["kind"] == "spike":
                after = [x for w, x in v.items() if w > a["week"]] or [0]
                moves[t] = v.get(a["week"], 0) - median(before + after)
            else:
                moves[t] = median([x for w, x in v.items() if w >= a["week"]] or [0]) - median(before)
        total = sum(moves.values()) or 1
        lead = sorted(moves, key=lambda t: -moves[t] if a["change"] > 0 else moves[t])[:8]
        names = _company_names(sdk, cfg, window, set(lead))
        for i, t in enumerate([t for t in lead if t in names][:3], 1):
            out.append({"Feature": feature, "Kind": a["kind"], "Week": a["week"], "Rank": i,
                        "Company": names[t][0], "Slug": names[t][1], "Change": round(moves[t]),
                        "Share of change": round(moves[t] / total * 100, 1)})
    return out


def _ranked(rows: list[dict], names: dict, integrity: list, label: str) -> list[tuple]:
    """The top named organizations of a shortlist, with the problems on the way.

    An organization with no name ahead of the third named one would have been in the
    top 3: say so rather than drop it quietly. One under the catch-all account would
    show a name that is not its own: keep it, and report it.
    """
    named = [r for r in rows if r[ORG] in names][:TOP_COMPANIES]
    cutoff = named[2][JD] if len(named) >= 3 else 0
    for r in rows:
        if r[ORG] not in names and r[JD] >= cutoff:
            integrity.append({"Check": "unnamed organization in a top 3", "Feature": label,
                              "Organization": r[ORG], "Value": r[JD], "Expected": ""})
    for r in named[:3]:
        if names[r[ORG]][0] == CATCH_ALL_ACCOUNT:
            integrity.append({"Check": "catch-all account in a top 3", "Feature": label,
                              "Organization": names[r[ORG]][1] or r[ORG], "Value": r[JD],
                              "Expected": ""})
    return [(i, r, names[r[ORG]]) for i, r in enumerate(named, 1)]


def fetch(quarter: str) -> None:
    sdk = looker_sdk_or_exit()
    # every query leaves the excluded organizations out
    cfg = without_excluded_organizations(LOOKER, QUARTERLY_EXCLUDED_ORGANIZATIONS)
    first = shift_quarter(quarter, -(QUARTERS - 1))
    quarter_ends = {f"{P}.calendar_date": date_range(first, quarter),
                    f"{P}.day_selection": "last^_day^_of^_quarter"}

    # Two queries, as the Overview tab reads them: the calendar quarter for Jobs Done and
    # users, its last day for the 28-day users and MAU. MAU joins another table, which a
    # daily sum must not go through.
    # One query per quarter for the calendar figures: unique users over five quarters of
    # days at once is too heavy for ClickHouse (502 on 18 November 2026).
    span = [shift_quarter(quarter, -k) for k in range(QUARTERS - 1, -1, -1)]
    ends = {r[QDIM]: r for r in run_query(sdk, [QDIM], [USERS_28D, MAU], quarter_ends, cfg=cfg)}
    totals = [r for q in span for r in run_query(sdk, [QDIM], [JD, USERS], every_day(q, q), cfg=cfg)]
    _write(data_file("totals", quarter), TOTAL_HEADERS,
           [{"Quarter": looker_quarter(r[QDIM]), "Jobs Done": r[JD], "Jobs Done Users": r[USERS],
             "Jobs Done Users 28d": ends.get(r[QDIM], {}).get(USERS_28D),
             "MAU": ends.get(r[QDIM], {}).get(MAU)} for r in totals])

    features = [{"Quarter": looker_quarter(r[QDIM]), "Product Domain Group": r[GROUP],
                 "Feature": r[FEATURE], "Jobs Done": r[JD], "Jobs Done Users": r[USERS]}
                for q in span for r in run_features(sdk, QDIM, [JD, USERS], every_day(q, q), cfg=cfg)]
    _write(data_file("features", quarter), FEATURE_HEADERS, features)

    # Organizations are ranked on organization_id, straight from the fact table, and
    # only then named, so the figures stay right whatever the directory holds. Never
    # per Salesforce account: the account "LumApps" holds dozens of customers. Each
    # organization's Jobs Done over the calendar quarter, as the feature totals.
    in_quarter = every_day(quarter, quarter)
    ranked: dict[tuple, list] = {}
    for r in run_features(sdk, "", [JD], in_quarter, (ORG,), limit="50000", cfg=cfg):
        if r.get(JD):
            ranked.setdefault((r[GROUP], r[FEATURE]), []).append(r)
    # a few spares per feature, in case some of the top organizations have no name
    shortlist = {k: sorted(rows, key=lambda x: -x[JD])[:TOP_COMPANIES + 5]
                 for k, rows in ranked.items()}
    # The article ranks organizations per domain group too: each organization's Jobs
    # Done summed over every feature of the group, from the same rows.
    by_group: dict[str, dict] = {}
    for (group, _), rows in ranked.items():
        for r in rows:
            by_group.setdefault(group, {}).setdefault(r[ORG], 0)
            by_group[group][r[ORG]] += r[JD]
    group_shortlist = {g: sorted(({ORG: t, JD: v} for t, v in ts.items()),
                                 key=lambda x: -x[JD])[:TOP_COMPANIES + 5]
                       for g, ts in by_group.items()}
    names = _company_names(sdk, cfg, in_quarter,
                           {r[ORG] for rows in (*shortlist.values(), *group_shortlist.values())
                            for r in rows})
    companies, group_companies, integrity = [], [], []
    for (group, feature), rows in shortlist.items():
        for i, r, (name, slug) in _ranked(rows, names, integrity, feature):
            companies.append({"Product Domain Group": group, "Feature": feature, "Rank": i,
                              "Company": name, "Slug": slug, "Jobs Done": r[JD]})
    for group, rows in group_shortlist.items():
        for i, r, (name, slug) in _ranked(rows, names, integrity, group):
            group_companies.append({"Product Domain Group": group, "Rank": i, "Company": name,
                                    "Slug": slug, "Jobs Done": r[JD]})
    _write(data_file("companies", quarter), COMPANY_HEADERS, companies)
    _write(data_file("group_companies", quarter), GROUP_COMPANY_HEADERS, group_companies)

    # The company join must not change the total: summed through it, the quarter's
    # Jobs Done must equal the plain total. More means the directory holds several
    # rows for some organizations.
    plain = sum(r[JD] or 0 for r in run_query(sdk, [], [JD], in_quarter, cfg=cfg))
    joined = sum(r[JD] or 0 for r in run_query(sdk, [NAME_F], [JD], in_quarter, limit="50000",
                                                cfg=cfg))
    integrity.append({"Check": "company join total", "Feature": "", "Organization": "",
                      "Value": joined, "Expected": plain})
    _write(data_file("integrity", quarter), INTEGRITY_HEADERS, integrity)

    # Weekly Jobs Done per feature over this quarter and the one before: a step
    # in it (a tracking change, a big launch) makes the QoQ misleading.
    two = {f"{P}.calendar_date": date_range(shift_quarter(quarter, -1), quarter),
           f"{P}.day_selection": "any^_day"}
    weeks = [{"Week": r[WDIM], "Product Domain Group": r[GROUP], "Feature": r[FEATURE],
              "Jobs Done": r[DAILY_JD]}
             for r in run_features(sdk, WDIM, [DAILY_JD], two, cfg=cfg)]
    _write(data_file("feature_weeks", quarter), WEEK_HEADERS, weeks)
    _write(data_file("anomaly_drivers", quarter), DRIVER_HEADERS, _anomaly_drivers(sdk, cfg, weeks))

    # Daily volume over this quarter and the one before, with four weeks ahead
    # for the baseline: a day far off its usual level may be broken data.
    start, end = volume_period(quarter)
    _write(data_file("daily_volume", quarter), VOLUME_HEADERS,
           fetch_daily_volume(sdk, start - timedelta(weeks=4), end + timedelta(days=1), cfg=cfg))

    print(f"[looker] {len(totals)} quarters, {len(features)} feature rows, "
          f"{len(companies)} company rows -> {DATA_DIR}\n", file=sys.stderr)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def pct(a, b):
    return (a - b) / b * 100 if b else None


def _read(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Error: {path} not found. Run without --no-fetch: --quarter {path.stem[-7:]}")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_totals(quarter: str) -> dict[str, dict]:
    """quarter -> {jd, users, users_28d, mau}."""
    return {r["Quarter"]: {"jd": num(r["Jobs Done"]), "users": num(r["Jobs Done Users"]),
                           "users_28d": num(r["Jobs Done Users 28d"]), "mau": num(r["MAU"])}
            for r in _read(data_file("totals", quarter))}


def quarter_kpis(totals: dict, quarter: str) -> dict | None:
    t = totals.get(quarter)
    return kpis(t["jd"], t["users"], t["mau"], t["users_28d"]) if t else None


def read_features(quarter: str) -> dict[tuple, dict]:
    """(domain group, feature) -> {quarter: {jd, users}}."""
    out: dict[tuple, dict] = {}
    for r in _read(data_file("features", quarter)):
        out.setdefault((r["Product Domain Group"], r["Feature"]), {})[r["Quarter"]] = {
            "jd": num(r["Jobs Done"]), "users": num(r["Jobs Done Users"])}
    return out


def read_companies(quarter: str) -> tuple[dict, dict]:
    """({(group, feature): rows}, {group: rows}), each list in rank order."""
    companies: dict[tuple, list] = {}
    for r in _read(data_file("companies", quarter)):
        companies.setdefault((r["Product Domain Group"], r["Feature"]), []).append(r)
    group_companies: dict[str, list] = {}
    for r in _read(data_file("group_companies", quarter)):
        group_companies.setdefault(r["Product Domain Group"], []).append(r)
    return companies, group_companies


def scope(history: dict, quarter: str) -> dict[str, list]:
    """{group: [features, largest first]} live and non-zero in the quarter."""
    live_until = quarter_last_month(quarter)
    out: dict[str, list] = {}
    for (group, name), by_q in history.items():
        row = by_q.get(quarter)
        if row and row["jd"] and GO_LIVE.get(name, live_until) <= live_until:
            out.setdefault(group, []).append((row["jd"], name))
    return {g: [n for _, n in sorted(v, reverse=True)] for g, v in out.items()}


def weekly_anomalies(quarter: str) -> tuple[dict, dict]:
    """({feature: step or spike}, {feature: [(week, jobs done)]})."""
    weekly: dict[str, list] = {}
    for w in _read(data_file("feature_weeks", quarter)):
        weekly.setdefault(w["Feature"], []).append((w["Week"], num(w["Jobs Done"])))
    return {f: a for f, a in ((f, weekly_anomaly(v)) for f, v in weekly.items()) if a}, weekly


def streak(values: list[float]) -> str:
    """Consecutive quarters up or down at the end of a QoQ series."""
    if not values or values[-1] == 0:
        return ""
    up = values[-1] > 0
    n = 0
    for v in reversed(values):
        if (v > 0) != up or v == 0:
            break
        n += 1
    if n == len(values):
        # the streak fills the whole window, so it may well be longer
        return f"{'up' if up else 'down'} in every quarter of the window ({n}+ in a row)"
    return f"{n} quarters {'up' if up else 'down'} in a row" if n > 1 else ""


def fmt_share(v: float) -> str:
    """A share as the article writes it: two decimals under 0.1%."""
    return f"{v:.2f}" if v < 0.1 else f"{v:.1f}"


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyse(quarter: str) -> list[dict]:
    prev = shift_quarter(quarter, -1)
    totals = read_totals(quarter)
    history = read_features(quarter)
    companies, group_companies = read_companies(quarter)
    if quarter not in totals:
        sys.exit(f"Error: {quarter} missing from the data. Re-run without --no-fetch.")

    print(f"\n{'=' * 80}\nHIGH LEVEL OVERVIEW — copy these five lines as they are\n{'=' * 80}")
    for line in overview_lines(quarter_kpis(totals, quarter), quarter_kpis(totals, prev), "QoQ"):
        print(f"  {line}")

    print(f"\n{'=' * 80}\nBOTH PLATFORMS — QUARTER BY QUARTER\n{'=' * 80}")
    print(f"  {'Quarter':<9} {'Jobs Done':>10} {'QoQ':>7} {'Users':>9} {'QoQ':>7} "
          f"{'Jobs/User':>9} {'MAU':>9} {'QoQ':>7} {'Reach':>7}")
    for q in sorted(totals):
        k, b = quarter_kpis(totals, q), quarter_kpis(totals, shift_quarter(q, -1))
        chg = (lambda key: fmt_change(pct(k[key], b[key])) if b else "n/a")
        mark = " ◄ report quarter" if q == quarter else ""
        print(f"  {q:<9} {fmt_level(k['jd']):>10} {chg('jd'):>7} {fmt_level(k['users']):>9} "
              f"{chg('users'):>7} {k['jpu']:>9.1f} {fmt_level(k['mau']):>9} {chg('mau'):>7} "
              f"{k['reach']:>6.1f}%{mark}")

    total_jd = totals[quarter]["jd"]
    groups = scope(history, quarter)
    live_until = quarter_last_month(quarter)
    held_back = [f"{name} ({group}), live from {GO_LIVE[name]}"
                 for (group, name), by_q in history.items()
                 if by_q.get(quarter, {}).get("jd") and GO_LIVE.get(name, live_until) > live_until]

    rows = []
    for group, names in groups.items():
        for name in names:
            by_q = history[(group, name)]
            cur, b = by_q[quarter], by_q.get(prev)
            series = sorted(by_q)
            qoq_series = [pct(by_q[series[i]]["jd"], by_q[series[i - 1]]["jd"])
                          for i in range(1, len(series))]
            rows.append({"group": group, "feature": name, "jd": cur["jd"], "users": cur["users"],
                         "prev_jd": b["jd"] if b else 0, "qoq": pct(cur["jd"], b["jd"]) if b else None,
                         "users_qoq": pct(cur["users"], b["users"]) if b else None,
                         "jpu": cur["jd"] / cur["users"] if cur["users"] else None,
                         "prev_jpu": b["jd"] / b["users"] if b and b["users"] else None,
                         "streak": streak([v for v in qoq_series if v is not None])})
    by_group: dict[str, list] = {}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    group_jd = {g: sum(r["jd"] for r in rs) for g, rs in by_group.items()}
    group_prev = {g: sum(r["prev_jd"] for r in rs) for g, rs in by_group.items()}

    print(f"\n{'=' * 80}\nBY PRODUCT DOMAIN GROUP ({quarter} vs {prev})\n{'=' * 80}")
    print("  Every group below gets its block, and every feature its line in it, in this order.")
    for g in sorted(by_group, key=lambda g: -group_jd[g]):
        print(f"\n  [{g}]  {fmt_level(group_jd[g])} JD, {fmt_change(pct(group_jd[g], group_prev[g]))} QoQ, "
              f"{group_jd[g] / total_jd * 100:.1f}% of all Jobs Done")
        print("    Top 3 companies of the group (these go in the article):")
        for c in group_companies.get(g, [])[:3]:
            slug = f" ({c['Slug']})" if c["Slug"] else ""
            print(f"      ({c['Rank']}) {c['Company']}{slug}, {fmt_level(num(c['Jobs Done']))} "
                  f"({num(c['Jobs Done']) / group_jd[g] * 100:.1f}% of {g} Jobs Done)")
        print("    Features (top 3 companies of each, for the 💡 line only):")
        for r in sorted(by_group[g], key=lambda r: -r["jd"]):
            users = (f"{fmt_level(r['users'])} users ({fmt_change(r['users_qoq'])})" if r["users"]
                     else "users not tracked")
            jpu = (f"Jobs per User {r['jpu']:.1f} ← {r['prev_jpu']:.1f}"
                   if r["jpu"] and r["prev_jpu"] else "")
            print(f"    {r['feature']}: {fmt_level(r['jd'])} JD ({fmt_change(r['qoq'])} QoQ), "
                  f"{fmt_share(r['jd'] / group_jd[g] * 100)}% of the tribe, {users}  {jpu}  "
                  f"{r['streak']}".rstrip())
            for c in companies.get((g, r["feature"]), [])[:3]:
                slug = f" ({c['Slug']})" if c["Slug"] else ""
                print(f"        ({c['Rank']}) {c['Company']}{slug}, {fmt_level(num(c['Jobs Done']))} "
                      f"({num(c['Jobs Done']) / r['jd'] * 100:.1f}% of {r['feature']} JD)")
    if held_back:
        print("\n  NOT LIVE IN THIS QUARTER (leave out of the article):")
        for h in held_back:
            print(f"    - {h}")

    anomalies, weekly = weekly_anomalies(quarter)
    drivers_path = data_file("anomaly_drivers", quarter)
    drivers = _read(drivers_path) if drivers_path.exists() else []
    live = {r["feature"] for r in rows}
    found = []
    for f, a in anomalies.items():
        if f not in live:
            continue
        lead = [d for d in drivers if d["Feature"] == f]
        top = num(lead[0]["Share of change"]) if lead else 0
        found.append({"feature": f, "anomaly": a, "review": anomaly_review(f, a),
                      "drivers": lead, "weeks": sorted(weekly[f]),
                      "hint": ("one company explains it" if top >= 50 else
                               "spread over many companies: look for a tracking or product change")})
    if found:
        print("\n  STEPS AND SPIKES IN WEEKLY JOBS DONE:")
        for x in found:
            a = x["anomaly"]
            state = (f"reviewed as {x['review'][0]}: {x['review'][1]}" if x["review"]
                     else "⚠️ NOT REVIEWED, see ANOMALIES TO REVIEW")
            print(f"    - {x['feature']}: a {a['kind']} of {a['change']:+.0f}% in the week of "
                  f"{a['week']} ({state})")

    caveat_window = (f"{quarter_start(prev):%Y-%m-%d}", f"{quarter_start(shift_quarter(quarter, 1)):%Y-%m-%d}")
    for r in rows:
        r["share"] = r["jd"] / group_jd[r["group"]] * 100
        a = anomalies.get(r["feature"])
        r["caveat"] = (comparison_caveat(r["feature"], *caveat_window)
                       or anomaly_caveat(r["feature"], a))
        r["unreviewed"] = bool(a) and not anomaly_review(r["feature"], a)
    ANOMALIES.extend(x for x in found if not x["review"])
    ISSUES.extend(integrity_warnings(quarter))
    return rows


ISSUES: list[str] = []       # company directory problems
ANOMALIES: list[dict] = []   # unreviewed steps and spikes


def integrity_warnings(quarter: str) -> list[str]:
    """Problems in the company directory found at fetch time, as sentences."""
    path = data_file("integrity", quarter)
    if not path.exists():
        return [f"no integrity check on file for {quarter}: re-run without --no-fetch"]
    out = []
    for r in _read(path):
        value, expected = num(r["Value"]), num(r["Expected"])
        if r["Check"] == "company join total" and value > expected:
            out.append(f"the company join inflates Jobs Done by {pct(value, expected):+.2f}% "
                       f"({fmt_level(value)} against {fmt_level(expected)}): the company "
                       f"directory holds duplicate rows. The figures here are unaffected "
                       f"(ranked on organization_id); report it upstream.")
        elif r["Check"] == "unnamed organization in a top 3":
            out.append(f"organization {r['Organization']} ({fmt_level(value)} {r['Feature']} JD) "
                       f"has no account name, so it is left out of the {r['Feature']} top 3. "
                       f"Find out why.")
        elif r["Check"] == "catch-all account in a top 3":
            out.append(f"organization {r['Organization']} ({fmt_level(value)} {r['Feature']} JD) "
                       f"is in the {r['Feature']} top 3 under the Salesforce account "
                       f"'{CATCH_ALL_ACCOUNT}', which is not its own name. Report it upstream "
                       f"and tell the analyst before the article names it.")
    return out


def print_anomalies_to_review() -> None:
    """Everything needed to push the investigation of each unreviewed anomaly."""
    if not ANOMALIES:
        return
    print(f"\n{'!' * 80}\n⚠️  ANOMALIES TO REVIEW BEFORE WRITING ({len(ANOMALIES)})\n{'!' * 80}")
    print("  The detection does not decide. For each one: investigate (which companies,\n"
          "  which events), decide with the analyst whether its QoQ is misleading or a real\n"
          "  change in usage, and record the verdict in ANOMALY_REVIEWS in\n"
          "  jobs_done_common.py. check_quarterly_article.py fails until then.")
    for x in ANOMALIES:
        a = x["anomaly"]
        print(f"\n  {x['feature']}: a {a['kind']} of {a['change']:+.0f}% "
              f"in the week of {a['week']} ({month_label(a['week'])})")
        print("    weekly Jobs Done: " + "  ".join(f"{w[5:]}:{fmt_level(v)}" for w, v in x["weeks"]))
        for d in x["drivers"]:
            slug = f" ({d['Slug']})" if d["Slug"] else ""
            print(f"    {d['Company']}{slug}: {num(d['Share of change']):.0f}% of the change")
        print(f"    → {x['hint']}")
        print(f"    record: (\"{x['feature']}\", \"{a['week']}\"): "
              f"(\"misleading\" or \"real\", \"<what the investigation found>\")")


def volume_alerts(quarter: str) -> list[dict]:
    """Volume alert episodes over volume_period(quarter)."""
    found = read_volume_episodes(data_file("daily_volume", quarter), *volume_period(quarter))
    if found is None:
        print(f"⚠️ no daily volume on file for {quarter}: re-run without --no-fetch", file=sys.stderr)
    return found or []


def print_highlights(rows: list[dict]) -> None:
    """Candidates for "Which features grew the most?" and "... declined?".

    Every feature in one list, ranked on QoQ. A feature whose comparison is not like
    for like (joined this quarter, tracking change, reviewed step or spike) is set
    aside with the reason.
    """
    ok = [r for r in rows if r["qoq"] is not None and not r["caveat"]]
    print(f"\n{'=' * 80}\nHIGHLIGHTS — ranked on QoQ\n{'=' * 80}")
    print(f"  Pick 2 or 3 per list. 'small' = under {SMALL_SHARE:.0f}% of its group: say its "
          f"share if you pick it.")
    for title, pick in (("GREW THE MOST", sorted([r for r in ok if r["qoq"] > 0], key=lambda r: -r["qoq"])),
                        ("DECLINED", sorted([r for r in ok if r["qoq"] < 0], key=lambda r: r["qoq"]))):
        print(f"\n  {title}")
        for r in pick[:6]:
            small = "  small" if r["share"] < SMALL_SHARE else ""
            small += "  ⚠️ unreviewed step or spike" if r.get("unreviewed") else ""
            users = f"users {fmt_change(r['users_qoq'])}" if r["users"] else "users not tracked"
            print(f"    {r['feature']} {fmt_change(r['qoq'])} QoQ, {fmt_share(r['share'])}% of "
                  f"{r['group']}, {users}  {r['streak']}{small}".rstrip())
    set_aside = [r for r in rows if r["caveat"]]
    if set_aside:
        print("\n  SET ASIDE (their QoQ is not like for like, never list them):")
        for r in set_aside:
            print(f"    {r['feature']} {fmt_change(r['qoq'])}: {r['caveat']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", default="",
                        help="Report quarter YYYY-QN (defaults to the last complete quarter)")
    parser.add_argument("--fetch", action="store_true",
                        help="Kept for compatibility: fetching is the default")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Re-read data/quarterly/ without querying Looker. For work on "
                             "the script only: an article must be written on fresh data")
    parser.add_argument("--note", default="", metavar="TEXT",
                        help="Editorial context to surface at the top of the report")
    args = parser.parse_args()
    quarter = args.quarter or default_quarter()
    parse_quarter(quarter)

    if quarter_start(shift_quarter(quarter, 1)) > date.today():
        print(f"⚠️ {quarter} is not over yet: its figures are partial.", file=sys.stderr)
    if args.no_fetch:
        print("⚠️ --no-fetch: reading data/quarterly/ as it is. Not for an article.",
              file=sys.stderr)
    else:
        fetch(quarter)

    print(f"{'=' * 80}")
    print(f"QUARTERLY JOBS DONE ANALYTICS — {quarter} (compared with {shift_quarter(quarter, -1)}), "
          f"LumApps and Beekeeper combined")
    print("As on the Overview tab of the dashboard: Jobs Done and Users with a Job Done over")
    print("  the calendar quarter; MAU over the 28 days that end it; Reach = Users with a Job")
    print("  Done over those 28 days / MAU.")
    print(f"{'=' * 80}")
    if args.note:
        print(f"\nEDITORIAL NOTE FROM THE ANALYST — take this into account when writing\n  {args.note}")
    rows = analyse(quarter)
    print_highlights(rows)
    print_anomalies_to_review()
    print_volume_alerts(volume_alerts(quarter))
    if ISSUES:
        print(f"\n{'!' * 80}\n⚠️  COMPANY DIRECTORY ISSUES ({len(ISSUES)})\n{'!' * 80}")
        for w in ISSUES:
            print(f"  {w}")
        print(f"\n⚠️ {len(ISSUES)} company directory issue(s): see above.", file=sys.stderr)
    if ANOMALIES:
        print(f"\n⚠️ {len(ANOMALIES)} anomaly(ies) to review before writing: see above.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
