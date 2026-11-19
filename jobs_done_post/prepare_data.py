#!/usr/bin/env python3
"""Prepare the monthly Jobs Done analytics, LumApps and Beekeeper combined.

Pulls from the explore behind the consolidated dashboard (see LOOKER in
jobs_done_common.py) into the data/ subfolder:
  - totals_YYYY-MM.csv         both platforms together, per month: Jobs Done, Users with
                               a Job Done, MAU
  - features_YYYY-MM.csv       the same per domain group x feature, a feature name
                               adding up both platforms
  - daily_volume_YYYY-MM.csv   daily Jobs Done per cell, to catch broken data (see
                               "Data volume" in jobs_done_common.py)
  - agents_YYYY-MM.csv         per-agent detail of the Agents domain, empty until
                               AI & Search reaches the explore

As on the Overview tab of the dashboard (Time Frame "1 month ago for 1 month"):
Jobs Done and Users with a Job Done cover the calendar month, day by day; MAU and the
28-day users behind Reach are read on the last day of the month.

Outputs structured analytics to stdout.

Usage:
    python3 prepare_data.py                      pull fresh CSVs from Looker, then analyse
    python3 prepare_data.py --month 2026-05      target a specific report month
    python3 prepare_data.py --no-fetch           re-read data/ (script work only, never
                                                 for an article: articles need fresh data)
"""

import argparse
import csv
import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, stdev

from jobs_done_common import (LOOKER, VOLUME_HEADERS, fetch_daily_volume, fmt_change, fmt_level,
                              kpis, looker_sdk_or_exit, num, overview_lines, print_volume_alerts,
                              read_volume_episodes, run_features, run_query)

DATA_DIR = Path(__file__).parent / "data"

P = LOOKER["prefix"]
# Calendar month: the daily Jobs Done summed, the users counted once over the month.
JD, USERS = f"{P}.jobs_done", f"{P}.active_users"
# Last day of the month: the 28-day users (for Reach) and MAU, both 28-day figures.
USERS_28D, MAU = f"{P}.active_users_28d", LOOKER["mau_field"]
ORGS = f"{P}.active_organizations"
MONTH, GROUP, FEATURE = f"{P}.calendar_month", f"{P}.product_domain_group", f"{P}.feature"

TOTAL_HEADERS = ["Calendar Month", "Jobs Done", "Jobs Done Users", "Jobs Done Users 28d", "MAU"]
FEATURE_HEADERS = ["Calendar Month", "Product Domain Group", "Feature", "Jobs Done",
                   "Jobs Done Users", "Jobs Done Users 28d", "MAU"]
AGENT_HEADERS = ["Calendar Month", "Agent", "Jobs Done", "Jobs Done Users", "Organizations"]

# 6 months are reported, the report month and the five before it (two quarters), and
# one more is fetched so the first of them has its MoM. No YoY, so no longer window.
TIME_FRAME = "7 month ago for 7 month"
REPORTED_MONTHS = 6


def data_file(kind: str, month: str) -> Path:
    return DATA_DIR / f"{kind}_{month}.csv"


# ---------------------------------------------------------------------------
# Months
# ---------------------------------------------------------------------------

def adj_month(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m += delta
    while m > 12: m -= 12; y += 1
    while m < 1:  m += 12; y -= 1
    return f"{y}-{m:02d}"


def month_end(ym: str) -> date:
    y, m = int(ym[:4]), int(ym[5:7])
    return date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)


def month_start(ym: str) -> date:
    return date(int(ym[:4]), int(ym[5:7]), 1)


def default_report_month() -> str:
    """Last complete calendar month."""
    t = date.today()
    return adj_month(f"{t.year}-{t.month:02d}", -1)


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


def _calendar() -> dict:
    """Every day of the months: Jobs Done and users over the calendar month."""
    return {f"{P}.calendar_date": TIME_FRAME, f"{P}.day_selection": "any^_day"}


def _month_ends() -> dict:
    """The last day of each month only: the 28-day figures (MAU, Reach)."""
    return {f"{P}.calendar_date": TIME_FRAME, f"{P}.day_selection": "last^_day^_of^_month"}


def _merge(calendar: list[dict], snapshot: list[dict], key) -> list[dict]:
    """The calendar rows, with the month-end 28-day users and MAU of the same key."""
    ends = {key(r): r for r in snapshot}
    return [{**r, USERS_28D: ends.get(key(r), {}).get(USERS_28D),
             MAU: ends.get(key(r), {}).get(MAU)} for r in calendar]


def fetch_from_looker(month: str) -> None:
    """Pull the totals, the feature breakdown, the daily volume and the agents.

    Two queries each time, as the dashboard's Overview tab reads them: the calendar
    month for Jobs Done and users, its last day for the 28-day users and MAU. They stay
    apart because MAU joins another table, which a daily sum must not go through.
    """
    sdk = looker_sdk_or_exit()

    totals = _merge(run_query(sdk, [MONTH], [JD, USERS], _calendar()),
                    run_query(sdk, [MONTH], [USERS_28D, MAU], _month_ends()),
                    key=lambda r: r[MONTH])
    _write(data_file("totals", month), TOTAL_HEADERS,
           [{"Calendar Month": r[MONTH], "Jobs Done": r[JD], "Jobs Done Users": r[USERS],
             "Jobs Done Users 28d": r[USERS_28D], "MAU": r[MAU]} for r in totals])

    features = _merge(run_features(sdk, MONTH, [JD, USERS], _calendar()),
                      run_features(sdk, MONTH, [USERS_28D, MAU], _month_ends()),
                      key=lambda r: (r[MONTH], r[GROUP], r[FEATURE]))
    _write(data_file("features", month), FEATURE_HEADERS,
           [{"Calendar Month": r[MONTH], "Product Domain Group": r[GROUP], "Feature": r[FEATURE],
             "Jobs Done": r[JD], "Jobs Done Users": r[USERS],
             "Jobs Done Users 28d": r[USERS_28D], "MAU": r[MAU]} for r in features])

    # Daily volume over the two months the article compares, with four weeks ahead
    # for the baseline (see volume_alerts).
    _write(data_file("daily_volume", month), VOLUME_HEADERS, fetch_daily_volume(
        sdk, month_start(adj_month(month, -1)) - timedelta(weeks=4),
        month_end(month) + timedelta(days=1)))

    agents = run_query(sdk, [MONTH, FEATURE], [JD, USERS, ORGS],
                       {**_calendar(), f"{P}.product_domain": LOOKER["per_agent_domain"]})
    _write(data_file("agents", month), AGENT_HEADERS,
           [{"Calendar Month": r[MONTH], "Agent": r[FEATURE], "Jobs Done": r[JD],
             "Jobs Done Users": r[USERS], "Organizations": r[ORGS]} for r in agents])

    print(f"[looker] {len(totals)} months, {len(features)} feature rows, "
          f"{len(agents)} agent rows -> {DATA_DIR}\n", file=sys.stderr)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _read(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Error: {path} not found. Run without --no-fetch to pull it from Looker.")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_totals(month: str) -> dict[str, dict]:
    """month -> {jd, users, users_28d, mau}, months without Jobs Done left out."""
    out = {}
    for r in _read(data_file("totals", month)):
        if num(r["Jobs Done"]):
            out[r["Calendar Month"][:7]] = {"jd": num(r["Jobs Done"]),
                                            "users": num(r["Jobs Done Users"]),
                                            "users_28d": num(r["Jobs Done Users 28d"]),
                                            "mau": num(r["MAU"])}
    return out


def read_features(month: str) -> dict[tuple, dict]:
    """(domain group, feature) -> {month: {jd, users, users_28d, mau}}."""
    out: dict[tuple, dict] = {}
    for r in _read(data_file("features", month)):
        out.setdefault((r["Product Domain Group"], r["Feature"]), {})[r["Calendar Month"][:7]] = {
            "jd": num(r["Jobs Done"]), "users": num(r["Jobs Done Users"]),
            "users_28d": num(r["Jobs Done Users 28d"]), "mau": num(r["MAU"])}
    return out


def month_kpis(totals: dict, month: str) -> dict | None:
    """The overview KPIs of a month: Reach divides the 28-day users of its last day."""
    t = totals.get(month)
    return kpis(t["jd"], t["users"], t["mau"], t["users_28d"]) if t else None


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def pct(a, b) -> float | None:
    return (a - b) / b * 100 if b else None


def trend_label(mom_series: list[float]) -> str:
    """Classify a feature's trend from its MoM % series."""
    if len(mom_series) < 3:
        return "insufficient data"
    sd = stdev(mom_series) if len(mom_series) > 1 else 0
    avg = mean(mom_series)
    if sd > 30:
        return "volatile"
    if avg >= 3:
        return "growing"
    if avg <= -3:
        return "declining"
    return "stable"


def consecutive_direction(mom_series: list[float]) -> str:
    """How many consecutive months of growth/decline at the end of the series."""
    if not mom_series:
        return ""
    direction = "up" if mom_series[-1] > 0 else "down"
    count = 0
    for v in reversed(mom_series):
        if (v > 0) == (direction == "up"):
            count += 1
        else:
            break
    label = "growing" if direction == "up" else "declining"
    return f"{count} consecutive months {label}" if count > 1 else ""


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def print_overview(totals: dict, month: str) -> None:
    cur, prev = month_kpis(totals, month), month_kpis(totals, adj_month(month, -1))
    if not cur:
        sys.exit(f"Error: {month} missing from the data. Re-run without --no-fetch.")
    print(f"\n{'=' * 80}\nHIGH LEVEL OVERVIEW — copy these five lines as they are\n{'=' * 80}")
    for line in overview_lines(cur, prev, "MoM"):
        print(f"  {line}")

    print(f"\n{'=' * 80}\nBOTH PLATFORMS — 6-MONTH TREND\n{'=' * 80}")
    print(f"  {'Month':<9} {'Jobs Done':>10} {'MoM':>7} {'Users':>9} {'MoM':>7} "
          f"{'Jobs/User':>9} {'MAU':>9} {'MoM':>7} {'Reach':>7}")
    for m in sorted(totals)[-REPORTED_MONTHS:]:
        k, b = month_kpis(totals, m), month_kpis(totals, adj_month(m, -1))
        chg = (lambda key: fmt_change(pct(k[key], b[key])) if b else "n/a")
        mark = " ◄ report month" if m == month else ""
        print(f"  {m:<9} {fmt_level(k['jd']):>10} {chg('jd'):>7} {fmt_level(k['users']):>9} "
              f"{chg('users'):>7} {k['jpu']:>9.1f} {fmt_level(k['mau']):>9} {chg('mau'):>7} "
              f"{k['reach']:>6.1f}%{mark}")
    months = sorted(totals)[-REPORTED_MONTHS:]
    moms = [v for v in (pct(totals[months[i]]["jd"], totals[months[i - 1]]["jd"])
                        for i in range(1, len(months))) if v is not None]
    if moms:
        print(f"\n  Jobs Done trend: {trend_label(moms)}  |  Avg MoM: {mean(moms):+.1f}%  |  "
              f"{consecutive_direction(moms)}")


# ---------------------------------------------------------------------------
# Feature-level analytics
# ---------------------------------------------------------------------------

def feature_analytics(history: dict, report_month: str) -> list[dict]:
    """Each feature against its own previous month: in % and in Jobs Done."""
    prev_month = adj_month(report_month, -1)
    results = []
    for (group, feature), by_month in history.items():
        cur = by_month.get(report_month)
        if not cur or not cur["jd"]:
            continue
        prev = by_month.get(prev_month)
        recent = sorted(by_month)[-REPORTED_MONTHS:]
        jd_series = [by_month[m]["jd"] for m in recent]
        mom_series = [v for v in (pct(jd_series[i], jd_series[i - 1])
                                  for i in range(1, len(jd_series))) if v is not None]
        jpu = cur["jd"] / cur["users"] if cur["users"] else None
        prev_jpu = prev["jd"] / prev["users"] if prev and prev["users"] else None
        results.append({
            "domain_group": group,
            "feature": feature,
            "jd": cur["jd"],
            "users": cur["users"],
            "jpu": jpu,
            # Reach, as on the dashboard with the Feature filter: the feature's 28-day users
            # on the last day of the month, over the MAU of the organizations that have it.
            "reach": cur["users_28d"] / cur["mau"] * 100 if cur["mau"] else None,
            "mom_pct": pct(cur["jd"], prev["jd"]) if prev else None,
            "users_mom": pct(cur["users"], prev["users"]) if prev else None,
            "jpu_mom": pct(jpu, prev_jpu) if jpu and prev_jpu else None,
            # The feature's own change in Jobs Done: what ranks the features of the month.
            "abs_mom": cur["jd"] - prev["jd"] if prev else None,
            "prev_jpu": prev_jpu,
            "trend": trend_label(mom_series),
            "consecutive": consecutive_direction(mom_series),
            "avg_mom": round(mean(mom_series), 1) if mom_series else None,
            "months_tracked": len(by_month),
            "peak_month": max(recent, key=lambda m: by_month[m]["jd"]),
        })
    return sorted(results, key=lambda r: r["jd"], reverse=True)


def print_feature_section(features: list[dict], total_jd: float) -> None:
    print(f"\n{'=' * 80}\nFEATURE BREAKDOWN — both platforms, by domain group\n{'=' * 80}")
    groups: dict[str, list] = {}
    for r in features:
        groups.setdefault(r["domain_group"], []).append(r)
    for grp in sorted(groups, key=lambda g: -sum(r["jd"] for r in groups[g])):
        rows = groups[grp]
        grp_total = sum(r["jd"] for r in rows)
        print(f"\n  [{grp}]  {fmt_level(grp_total)} Jobs Done, "
              f"{grp_total / total_jd * 100:.1f}% of all Jobs Done")
        print(f"  {'Feature':<18} {'Jobs Done':>10} {'MoM':>7} {'Users':>9} {'MoM':>7} "
              f"{'Jobs/User':>9} {'MoM':>7} {'Reach':>7}  {'Trend':<12} Consecutive")
        print("  " + "-" * 110)
        for r in rows:
            reach = f"{r['reach']:.1f}%" if r["reach"] is not None else "n/a"
            jpu = f"{r['jpu']:.1f}" if r["jpu"] else "n/a"
            users = fmt_level(r["users"]) if r["users"] else "not tracked"
            print(f"  {r['feature']:<18} {fmt_level(r['jd']):>10} {fmt_change(r['mom_pct']):>7} "
                  f"{users:>9} {fmt_change(r['users_mom']):>7} {jpu:>9} "
                  f"{fmt_change(r['jpu_mom']):>7} {reach:>7}  {r['trend']:<12} {r['consecutive']}")


def print_movers(features: list[dict], total_jd: float = 0.0, total_change: float = 0.0) -> None:
    """Rank what to write about, each feature against its own previous month.

    BIGGEST MOVES ranks on the feature's own change in Jobs Done (October 2026: Content
    -1.68M, Spaces +714K, Posts +379K). Not on its MoM %: that alone promotes small
    features, and in August 2026 it put Videos (-26.7%, about -110K Jobs Done) above
    Content (-7.1%, -8.51M). Not on a share of the total's change either: when ups and
    downs offset, the total barely moves and such a share runs far above 100% (Content
    was "306% of the change" in October 2026, a total of -548K).

    The relative list keeps small-but-loud signals from disappearing.
    """
    DRIVER_ABS_MIN = max(5_000, total_jd * 0.0005)      # 0.05% of the total volume
    DRIVERS_SHOWN = 5
    RELATIVE_MOM_MIN = 10.0                             # %
    RELATIVE_ABS_MIN = max(5_000, total_jd * 0.0001)    # 0.01% of the total volume

    # at least DRIVERS_SHOWN features, so the article always has five candidates
    moved = sorted((r for r in features if r["abs_mom"] is not None), key=lambda x: -abs(x["abs_mom"]))
    drivers = [r for i, r in enumerate(moved) if i < DRIVERS_SHOWN or abs(r["abs_mom"]) >= DRIVER_ABS_MIN]
    if drivers:
        print(f"\nBIGGEST MOVES OF THE MONTH (each feature against its previous month, "
              f"|change| ≥ {fmt_level(DRIVER_ABS_MIN)} Jobs Done, top {DRIVERS_SHOWN} at least)")
        print("-" * 80)
        print(f"  Ranked by the change in Jobs Done. The total moved {total_change:+,.0f}.")
        for r in sorted(drivers, key=lambda x: -abs(x["abs_mom"])):
            # A feature moving against the total is worth saying out loud
            # ("everything grew except X").
            against = ("  <- moved AGAINST the total"
                       if total_change and (r["abs_mom"] > 0) != (total_change > 0) else "")
            print(f"  [{r['domain_group']}] {r['feature']}: {r['abs_mom']:+,.0f} Jobs Done "
                  f"({fmt_change(r['mom_pct'])} MoM), now {fmt_level(r['jd'])}{against}")

    relative = [r for r in features
                if r["mom_pct"] is not None and abs(r["mom_pct"]) >= RELATIVE_MOM_MIN
                and abs(r["abs_mom"] or 0) >= RELATIVE_ABS_MIN
                and r not in drivers]
    if relative:
        print(f"\nSTRONGEST RELATIVE MOVES (|MoM| ≥ {RELATIVE_MOM_MIN:.0f}%, abs ≥ {fmt_level(RELATIVE_ABS_MIN)})")
        print("-" * 80)
        print("  Not top moves by volume: cover at most two of these, and only if they tell a story.")
        for r in sorted(relative, key=lambda x: -abs(x["mom_pct"])):
            jpu = (f"  Jobs per User {r['jpu']:.1f} ← {r['prev_jpu']:.1f}"
                   if r.get("jpu") and r.get("prev_jpu") else "")
            print(f"  · [{r['domain_group']}] {r['feature']}: {fmt_change(r['mom_pct'])} MoM "
                  f"({r['abs_mom']:+,.0f} Jobs Done), now {fmt_level(r['jd'])}{jpu}")

    # A feature tracked for less than the full window is new to the metric. It will
    # never rank on volume, but "we started measuring this" is itself news.
    newly = [r for r in features if r["months_tracked"] < REPORTED_MONTHS]
    if newly:
        print("\nNEWLY TRACKED FEATURES (shorter history than the reporting window)")
        print("-" * 80)
        print("  Too small to rank on volume. Worth a line the first time they appear.")
        for r in sorted(newly, key=lambda x: x["months_tracked"]):
            print(f"  * [{r['domain_group']}] {r['feature']}: {fmt_level(r['jd'])} JD, "
                  f"{fmt_level(r['users'])} users, {r['months_tracked']} months tracked, "
                  f"{fmt_change(r['mom_pct'])} MoM")


def print_agents_section(month: str, features: list[dict]) -> None:
    """Per-agent detail for the Agents paragraph (experimental).

    The paragraph gives the Agents total, then one or two agents picked from three
    lists: the largest, the biggest absolute growth, and the widest adoption across
    organizations. Growth is ranked on the absolute change, because at a few hundred
    Jobs Done per agent a percentage swings wildly. Prints nothing while the explore
    has no Agents data.
    """
    TOP = 3
    path = data_file("agents", month)
    if not path.exists():
        return
    prev_month = adj_month(month, -1)
    by_agent: dict[str, dict] = {}
    for r in _read(path):
        by_agent.setdefault(r["Agent"], {})[r["Calendar Month"][:7]] = {
            "jd": num(r["Jobs Done"]), "users": num(r["Jobs Done Users"]),
            "orgs": num(r["Organizations"])}
    rows = []
    for name, months in by_agent.items():
        cur = months.get(month)
        if not cur or not cur["jd"]:
            continue
        prev = months.get(prev_month)
        rows.append({"agent": name, **cur,
                     "prev_jd": prev["jd"] if prev else 0,
                     "abs_mom": cur["jd"] - (prev["jd"] if prev else 0),
                     "mom_pct": pct(cur["jd"], prev["jd"]) if prev else None})
    if not rows:
        return

    total = next((f for f in features if f["feature"] == "Agents"), None)
    agents_jd = sum(r["jd"] for r in rows)
    print(f"\n{'=' * 80}\nAGENTS DETAIL (experimental)\n{'=' * 80}")
    if total:
        print(f"  Agents total: {fmt_level(total['jd'])} JD ({int(total['jd']):,}), "
              f"{fmt_change(total['mom_pct'])} MoM, {fmt_level(total['users'])} users, "
              f"{len(rows)} agents used this month")
    print("  Names are free text set by each customer, and several carry a customer name.")

    def line(r):
        new = "  (new this month)" if not r["prev_jd"] else ""
        return (f"  - {r['agent']}: {int(r['jd']):,} JD ({r['jd'] / agents_jd * 100:.1f}% of Agents), "
                f"{int(r['users']):,} users, {int(r['orgs'])} organization(s), "
                f"{r['abs_mom']:+,.0f} JD vs last month ({fmt_change(r['mom_pct'])}){new}")

    for title, key in (("LARGEST", lambda r: (-r["jd"],)),
                       ("BIGGEST GROWTH (absolute)", lambda r: (-r["abs_mom"], -r["jd"])),
                       ("WIDEST ADOPTION (organizations)", lambda r: (-r["orgs"], -r["jd"]))):
        picks = sorted(rows, key=key)[:TOP]
        if title.startswith("BIGGEST"):
            picks = [r for r in picks if r["abs_mom"] > 0]
        print(f"\n  {title}")
        for r in picks:
            print(line(r))


def print_trends(features: list[dict]) -> None:
    """Summary of the 6-month trajectory per feature."""
    print(f"\n{'=' * 80}\n6-MONTH TRENDS\n{'=' * 80}")
    print(f"  {'Feature':<18} {'Group':<32} {'Trend':<12} {'Avg MoM':>8} {'Peak month':<10} Consecutive")
    print("  " + "-" * 100)
    for r in features:
        print(f"  {r['feature']:<18} {r['domain_group']:<32} {r['trend']:<12} "
              f"{fmt_change(r['avg_mom']):>8} {r['peak_month']:<10} {r['consecutive']}")


# ---------------------------------------------------------------------------
# Data volume
# ---------------------------------------------------------------------------

def volume_alerts(report_month: str) -> list[dict]:
    """Volume alerts for the report month: every day of the two months the article
    compares (the previous month and this one), per cell.

    Jobs Done is the sum of these days, so a broken day moves the figure itself.
    """
    vol = data_file("daily_volume", report_month)
    episodes = read_volume_episodes(vol, month_start(adj_month(report_month, -1)),
                                    month_end(report_month))
    if episodes is None:
        print(f"⚠️ no daily volume on file for {report_month}: re-run without --no-fetch",
              file=sys.stderr)
        return []
    return episodes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="",
                        help="Report month YYYY-MM (defaults to the last complete month)")
    parser.add_argument("--fetch", action="store_true",
                        help="Kept for compatibility: fetching is the default")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Re-read data/ without querying Looker. For work on the script "
                             "only: an article must be written on freshly fetched data")
    parser.add_argument("--note", default="", metavar="TEXT",
                        help="Editorial context to surface at the top of the report, e.g. "
                             "\"the Agents feature was added this month, worth a mention\"")
    args = parser.parse_args()
    month = args.month or default_report_month()

    if args.no_fetch:
        print("⚠️ --no-fetch: reading data/ as it is. Not for an article.", file=sys.stderr)
    else:
        fetch_from_looker(month)
    print(f"[Report month] {month}\n", file=sys.stderr)

    totals = read_totals(month)
    history = read_features(month)

    print(f"{'=' * 80}")
    print(f"JOBS DONE ANALYTICS — {month}, LumApps and Beekeeper combined")
    print("Methodology, as on the Overview tab of the dashboard: Jobs Done and Users with a")
    print("Job Done over the calendar month; Jobs per User = Jobs Done / Users with a Job Done.")
    print("MAU and Reach are 28-day figures on the last day of the month:")
    print("Reach = Users with a Job Done over those 28 days / MAU.")
    print(f"{'=' * 80}")

    if args.note:
        print(f"\n{'=' * 80}")
        print("EDITORIAL NOTE FROM THE ANALYST — take this into account when writing")
        print(f"{'=' * 80}")
        print(f"  {args.note}")

    print_overview(totals, month)

    cur, prev = totals.get(month, {}), totals.get(adj_month(month, -1), {})
    total_jd = cur.get("jd", 0)
    features = feature_analytics(history, month)
    print_feature_section(features, total_jd)
    print_movers(features, total_jd, total_jd - prev.get("jd", 0))
    print_agents_section(month, features)
    print_trends(features)

    print_volume_alerts(volume_alerts(month))


if __name__ == "__main__":
    main()
