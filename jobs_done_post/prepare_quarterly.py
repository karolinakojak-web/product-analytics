#!/usr/bin/env python3
"""Prepare quarterly Jobs Done analytics for the quarterly article.

Unlike the monthly article, which reads a 28-day window, a quarter is measured over
every day it contains:

  Jobs Done               daily Jobs Done summed over the quarter
  Users Completing Jobs   unique users over the whole quarter (not additive)

Writes to data/quarterly/, one file per platform and kind:
  <platform>_totals_YYYY-QN.csv      platform totals, last QUARTERS quarters
  <platform>_features_YYYY-QN.csv    domain group x feature, same quarters
  <platform>_companies_YYYY-QN.csv   top companies per feature, report quarter only
  <platform>_feature_weeks_YYYY-QN.csv  weekly Jobs Done per feature, report quarter and
                                        the one before, to catch steps and spikes
  <platform>_anomaly_drivers_YYYY-QN.csv  the companies behind each step or spike
  <platform>_integrity_YYYY-QN.csv   checks on the company directory (see below)
  <platform>_daily_volume_YYYY-QN.csv  daily Jobs Done per cell (LumApps) or for the
                                        platform (Beekeeper), to catch broken data

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
from statistics import median
from pathlib import Path

from jobs_done_common import (GO_LIVE, LOOKER_PLATFORMS, QUARTERLY_EXCLUDED_TENANTS,
                              SMALL_SHARE, comparison_caveat, without_excluded_tenants,
                              STEP_WEEKS, anomaly_caveat, anomaly_review, fmt_change,
                              VOLUME_HEADERS, fetch_daily_volume, looker_sdk_or_exit,
                              print_volume_alerts, read_volume_episodes,
                              month_label, run_features, run_query, weekly_anomaly)

DATA_DIR = Path(__file__).parent / "data" / "quarterly"

QUARTERS = 5          # the report quarter and the four before it
TOP_COMPANIES = 5     # kept per feature; the article quotes the top 3

TOTAL_HEADERS = ["Quarter", "Jobs Done", "Jobs Done Users"]
FEATURE_HEADERS = ["Quarter", "Product Domain Group", "Feature", "Jobs Done", "Jobs Done Users"]
COMPANY_HEADERS = ["Product Domain Group", "Feature", "Rank", "Company", "Slug", "Jobs Done"]
WEEK_HEADERS = ["Week", "Product Domain Group", "Feature", "Jobs Done"]
INTEGRITY_HEADERS = ["Check", "Feature", "Tenant", "Value", "Expected"]
DRIVER_HEADERS = ["Feature", "Kind", "Week", "Rank", "Company", "Slug", "Change", "Share of change"]


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


def quarter_last_month(q: str) -> str:
    y, n = parse_quarter(q)
    return f"{y}-{3 * n:02d}"


def volume_period(q: str) -> tuple[date, date]:
    """The days the volume check covers: the quarter before and this one."""
    return quarter_start(shift_quarter(q, -1)), quarter_start(shift_quarter(q, 1)) - timedelta(days=1)


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
    end = quarter_start(shift_quarter(last, 1))
    return f"{quarter_start(first):%Y/%m/%d} to {end:%Y/%m/%d}"


# ---------------------------------------------------------------------------
# Looker fetch  (--fetch)
# ---------------------------------------------------------------------------

def _write(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({h: ("" if r.get(h) is None else r[h]) for h in headers})


def _company_names(sdk, cfg: dict, filters: dict, tenants: set) -> dict[str, tuple]:
    """tenant_gid -> (name, slug) from the platform's company directory.

    Dimensions only, no measure, so the join cannot inflate anything.
    """
    if not tenants:
        return {}
    p = cfg["prefix"]
    name_f, slug_f = cfg["company_fields"]
    rows = run_query(sdk, cfg, [f"{p}.tenant_gid", name_f, slug_f], [],
                     {**filters, f"{p}.tenant_gid": ",".join(sorted(tenants))})
    return {r[f"{p}.tenant_gid"]: (r[name_f].strip(), (r[slug_f] or "").strip())
            for r in rows if r.get(name_f) and r[name_f].strip()}


def _anomaly_drivers(sdk, cfg: dict, weeks: list[dict]) -> list[dict]:
    """For each step or spike, the companies whose own weekly Jobs Done moved the most.

    A spike: each company's spike week against the median of its neighbouring weeks.
    A step: each company's median after against its median before. One company
    explaining most of it points to that customer; a change spread over many points
    to what is counted (a tracking or product change), as with Search in August 2026.
    """
    p = cfg["prefix"]
    wdim, tenant, jd = f"{p}.calendar_week", f"{p}.tenant_gid", cfg["daily_jd_field"]
    series: dict[tuple, list] = {}
    for w in weeks:
        series.setdefault((w["Product Domain Group"], w["Feature"]), []).append(
            (w["Week"], _num(w["Jobs Done"])))
    out = []
    for (group, feature), s in series.items():
        a = weekly_anomaly(s)
        if not a:
            continue
        week = date.fromisoformat(a["week"])
        span = STEP_WEEKS if a["kind"] == "step" else 4
        level = (f"{p}.product_domain" if group in cfg.get("domain_level_groups", [])
                 else f"{p}.feature")
        rows = run_query(sdk, cfg, [wdim, tenant], [jd], {
            f"{p}.calendar_date": f"{week - timedelta(weeks=span):%Y/%m/%d} to "
                                  f"{week + timedelta(weeks=span + (a['kind'] == 'spike')):%Y/%m/%d}",
            f"{p}.day_selection": "any^_day",
            f"{p}.product_domain_group": group, level: feature}, limit="50000")
        by_tenant: dict[str, dict] = {}
        for r in rows:
            by_tenant.setdefault(r[tenant], {})[r[wdim]] = r[jd] or 0
        moves = {}
        for t, v in by_tenant.items():
            before = [x for w, x in v.items() if w < a["week"]] or [0]
            if a["kind"] == "spike":
                after = [x for w, x in v.items() if w > a["week"]] or [0]
                moves[t] = v.get(a["week"], 0) - median(before + after)
            else:
                moves[t] = median([x for w, x in v.items() if w >= a["week"]] or [0]) - median(before)
        total = sum(moves.values()) or 1
        lead = sorted(moves, key=lambda t: -moves[t] if a["change"] > 0 else moves[t])[:8]
        names = _company_names(sdk, cfg, {f"{p}.calendar_date": date_range_weeks(week, span),
                                          f"{p}.day_selection": "any^_day"}, set(lead))
        for i, t in enumerate([t for t in lead if t in names][:3], 1):
            out.append({"Feature": feature, "Kind": a["kind"], "Week": a["week"], "Rank": i,
                        "Company": names[t][0], "Slug": names[t][1], "Change": round(moves[t]),
                        "Share of change": round(moves[t] / total * 100, 1)})
    return out


def date_range_weeks(week: date, span: int) -> str:
    return f"{week - timedelta(weeks=span):%Y/%m/%d} to {week + timedelta(weeks=span + 1):%Y/%m/%d}"


def fetch(quarter: str) -> None:
    sdk = looker_sdk_or_exit()
    first = shift_quarter(quarter, -(QUARTERS - 1))

    for platform, cfg in LOOKER_PLATFORMS.items():
        # every query of this platform leaves the excluded tenants out
        cfg = without_excluded_tenants(platform, cfg, QUARTERLY_EXCLUDED_TENANTS)
        p = cfg["prefix"]
        qdim, jd, users = f"{p}.calendar_quarter", cfg["daily_jd_field"], f"{p}.active_users"
        every_day = {f"{p}.calendar_date": date_range(first, quarter),
                     f"{p}.day_selection": "any^_day"}

        totals = {looker_quarter(r[qdim]): {"Quarter": looker_quarter(r[qdim]),
                                            "Jobs Done": r[jd], "Jobs Done Users": r[users]}
                  for r in run_query(sdk, cfg, [qdim], [jd, users], every_day)}
        _write(DATA_DIR / f"{platform}_totals_{quarter}.csv", TOTAL_HEADERS,
               sorted(totals.values(), key=lambda r: r.get("Quarter", ""), reverse=True))

        features = [{"Quarter": looker_quarter(r[qdim]),
                     "Product Domain Group": r[f"{p}.product_domain_group"],
                     "Feature": r[f"{p}.feature"], "Jobs Done": r[jd], "Jobs Done Users": r[users]}
                    for r in run_features(sdk, cfg, qdim, [jd, users], every_day)]
        _write(DATA_DIR / f"{platform}_features_{quarter}.csv", FEATURE_HEADERS, features)

        # Companies are ranked on tenant_gid, straight from the fact table, and only
        # then named, so the figures stay right whatever the company directory holds.
        # In Q2 2026, summing through the LumApps company join doubled a large
        # customer's Videos JD (twice its real 583,683). The directory is checked
        # below instead, so a problem there is reported, not silently absorbed.
        tenant = f"{p}.tenant_gid"
        in_quarter = {f"{p}.calendar_date": date_range(quarter, quarter),
                      f"{p}.day_selection": "any^_day"}
        ranked: dict[tuple, list] = {}
        for r in run_features(sdk, cfg, qdim, [jd], in_quarter, (tenant,), limit="50000"):
            if r.get(jd):
                ranked.setdefault((r[f"{p}.product_domain_group"], r[f"{p}.feature"]), []).append(r)
        # a few spares per feature, in case some of the top tenants have no name
        shortlist = {k: sorted(rows, key=lambda x: -x[jd])[:TOP_COMPANIES + 5]
                     for k, rows in ranked.items()}
        names = _company_names(sdk, cfg, in_quarter,
                               {r[tenant] for rows in shortlist.values() for r in rows})
        companies, integrity = [], []
        for (group, feature), rows in shortlist.items():
            named = [r for r in rows if r[tenant] in names][:TOP_COMPANIES]
            for i, r in enumerate(named, 1):
                name, slug = names[r[tenant]]
                companies.append({"Product Domain Group": group, "Feature": feature, "Rank": i,
                                  "Company": name, "Slug": slug, "Jobs Done": r[jd]})
            # A tenant with no name ahead of the third named one would have been in
            # the top 3: say so rather than drop it quietly.
            cutoff = named[2][jd] if len(named) >= 3 else 0
            for r in rows:
                if r[tenant] not in names and r[jd] >= cutoff:
                    integrity.append({"Check": "unnamed tenant in a top 3", "Feature": feature,
                                      "Tenant": r[tenant], "Value": r[jd], "Expected": ""})
        _write(DATA_DIR / f"{platform}_companies_{quarter}.csv", COMPANY_HEADERS, companies)

        # The company join must not change the total: summed through it, the
        # quarter's Jobs Done must equal the plain total. More means the directory
        # holds several rows for some companies.
        plain = sum(r[jd] or 0 for r in run_query(sdk, cfg, [qdim], [jd], in_quarter))
        joined = sum(r[jd] or 0 for r in run_query(sdk, cfg, [qdim, cfg["company_fields"][0]],
                                                   [jd], in_quarter, limit="50000"))
        integrity.append({"Check": "company join total", "Feature": "", "Tenant": "",
                          "Value": joined, "Expected": plain})
        _write(DATA_DIR / f"{platform}_integrity_{quarter}.csv", INTEGRITY_HEADERS, integrity)

        # Weekly Jobs Done per feature over this quarter and the one before: a step
        # in it (a tracking change, a big launch) makes the QoQ misleading.
        wdim = f"{p}.calendar_week"
        two = {f"{p}.calendar_date": date_range(shift_quarter(quarter, -1), quarter),
               f"{p}.day_selection": "any^_day"}
        weeks = [{"Week": r[wdim], "Product Domain Group": r[f"{p}.product_domain_group"],
                  "Feature": r[f"{p}.feature"], "Jobs Done": r[jd]}
                 for r in run_features(sdk, cfg, wdim, [jd], two)]
        _write(DATA_DIR / f"{platform}_feature_weeks_{quarter}.csv", WEEK_HEADERS, weeks)
        _write(DATA_DIR / f"{platform}_anomaly_drivers_{quarter}.csv", DRIVER_HEADERS,
               _anomaly_drivers(sdk, cfg, weeks))

        # Daily volume over this quarter and the one before, with four weeks ahead
        # for the baseline: a day far off its usual level may be broken data.
        start, end = volume_period(quarter)
        _write(DATA_DIR / f"{platform}_daily_volume_{quarter}.csv", VOLUME_HEADERS,
               fetch_daily_volume(sdk, platform, cfg, start - timedelta(weeks=4),
                                  end + timedelta(days=1)))

        print(f"  [{platform}] {len(totals)} quarters, {len(features)} feature rows, "
              f"{len(companies)} company rows", file=sys.stderr)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def pct(a, b):
    return (a - b) / b * 100 if b else None


def fmt_pct(v) -> str:
    return fmt_change(v)


def fmt_n(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f}M" if v < 10_000_000 else f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{int(v)}"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Error: {path} not found. Run without --no-fetch: --quarter {path.stem[-7:]}")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def analyse(platform: str, quarter: str) -> list[dict]:
    prev = shift_quarter(quarter, -1)
    live_until = quarter_last_month(quarter)

    totals = {r["Quarter"]: r for r in _read(DATA_DIR / f"{platform}_totals_{quarter}.csv")}
    feats: dict[tuple, dict] = {}
    for r in _read(DATA_DIR / f"{platform}_features_{quarter}.csv"):
        feats.setdefault((r["Product Domain Group"], r["Feature"]), {})[r["Quarter"]] = r
    companies: dict[tuple, list] = {}
    for r in _read(DATA_DIR / f"{platform}_companies_{quarter}.csv"):
        companies.setdefault((r["Product Domain Group"], r["Feature"]), []).append(r)

    print(f"\n{'=' * 80}\n{platform.upper()} — PLATFORM TOTALS\n{'=' * 80}")
    print(f"  {'Quarter':<9} {'Jobs Done':>11} {'QoQ':>8} {'Users':>9} {'QoQ':>8}")
    order = sorted(totals)
    for i, q in enumerate(order):
        r, b = totals[q], totals.get(order[i - 1]) if i else None
        cols = []
        for c in ("Jobs Done", "Jobs Done Users"):
            v = _num(r.get(c))
            cols += [fmt_n(v), fmt_pct(pct(v, _num(b.get(c)))) if b else "n/a"]
        mark = " ◄ report quarter" if q == quarter else ""
        print(f"  {q:<9} {cols[0]:>11} {cols[1]:>8} {cols[2]:>9} {cols[3]:>8}{mark}")
    if quarter not in totals:
        sys.exit(f"Error: {quarter} missing from the {platform} data. Re-run without --no-fetch.")

    platform_jd = _num(totals[quarter]["Jobs Done"])
    rows, held_back = [], []
    for (group, feature), by_q in feats.items():
        cur = by_q.get(quarter)
        if not cur or not _num(cur["Jobs Done"]):
            continue
        if GO_LIVE.get(feature, live_until) > live_until:
            held_back.append(f"{feature} ({group}), live from {GO_LIVE[feature]}")
            continue
        b = by_q.get(prev)
        jd, us = _num(cur["Jobs Done"]), _num(cur["Jobs Done Users"])
        pjd, pus = (_num(b["Jobs Done"]), _num(b["Jobs Done Users"])) if b else (0, 0)
        series = sorted(by_q)
        qoq_series = [pct(_num(by_q[series[i]]["Jobs Done"]), _num(by_q[series[i - 1]]["Jobs Done"]))
                      for i in range(1, len(series))]
        rows.append({"group": group, "feature": feature, "jd": jd, "users": us,
                     "prev_jd": pjd, "prev_users": pus, "qoq": pct(jd, pjd),
                     "users_qoq": pct(us, pus),
                     "freq": jd / us if us else None, "prev_freq": pjd / pus if pus else None,
                     "streak": streak([v for v in qoq_series if v is not None])})

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(r)
    group_jd = {g: sum(r["jd"] for r in rs) for g, rs in groups.items()}
    group_prev = {g: sum(r["prev_jd"] for r in rs) for g, rs in groups.items()}

    print(f"\n{'=' * 80}\n{platform.upper()} — BY PRODUCT DOMAIN GROUP ({quarter} vs {prev})\n{'=' * 80}")
    print("  Every feature below gets its own block in the article.")
    for g in sorted(groups, key=lambda g: -group_jd[g]):
        print(f"\n  [{g}]  {fmt_n(group_jd[g])} JD, {fmt_pct(pct(group_jd[g], group_prev[g]))} QoQ, "
              f"{group_jd[g] / platform_jd * 100:.1f}% of the platform")
        for r in sorted(groups[g], key=lambda r: -r["jd"]):
            share = r["jd"] / group_jd[g] * 100
            users = (f"{fmt_n(r['users'])} users ({fmt_pct(r['users_qoq'])})" if r["users"]
                     else "users not tracked")
            freq = (f"freq {r['freq']:.1f}x ← {r['prev_freq']:.1f}x"
                    if r["freq"] and r["prev_freq"] else "")
            print(f"    {r['feature']}: {fmt_n(r['jd'])} JD ({fmt_pct(r['qoq'])} QoQ), "
                  f"{share:.1f}% of {g}, {users}  {freq}  {r['streak']}".rstrip())
            for c in companies.get((g, r["feature"]), [])[:3]:
                slug = f" ({c['Slug']})" if c["Slug"] else ""
                print(f"        ({c['Rank']}) {c['Company']}{slug}, {fmt_n(_num(c['Jobs Done']))} "
                      f"({_num(c['Jobs Done']) / r['jd'] * 100:.1f}% of {r['feature']} JD)")

    moved = [r for r in rows if r["qoq"] is not None]
    print(f"\n  LARGEST QoQ MOVES (share of their group in brackets; small shares move a lot)")
    for label, pick in (("up", sorted([r for r in moved if r["qoq"] > 0], key=lambda r: -r["qoq"])),
                        ("down", sorted([r for r in moved if r["qoq"] < 0], key=lambda r: r["qoq"]))):
        for r in pick[:4]:
            print(f"    {label:<5}{r['feature']} {fmt_pct(r['qoq'])} "
                  f"({r['jd'] / group_jd[r['group']] * 100:.1f}% of {r['group']})")
    if held_back:
        print("\n  NOT LIVE IN THIS QUARTER (leave out of the article):")
        for h in held_back:
            print(f"    - {h}")

    weekly: dict[str, list] = {}
    for w in _read(DATA_DIR / f"{platform}_feature_weeks_{quarter}.csv"):
        weekly.setdefault(w["Feature"], []).append((w["Week"], _num(w["Jobs Done"])))
    anomalies = {f: a for f, a in ((f, weekly_anomaly(v)) for f, v in weekly.items()) if a}
    drivers_path = DATA_DIR / f"{platform}_anomaly_drivers_{quarter}.csv"
    drivers = _read(drivers_path) if drivers_path.exists() else []
    live = {r["feature"] for r in rows}
    found = []
    for f, a in anomalies.items():
        if f not in live:
            continue
        review = anomaly_review(platform, f, a)
        lead = [d for d in drivers if d["Feature"] == f]
        top = _num(lead[0]["Share of change"]) if lead else 0
        found.append({"platform": platform, "feature": f, "anomaly": a, "review": review,
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
        r["platform"] = platform
        r["share"] = r["jd"] / group_jd[r["group"]] * 100
        r["caveat"] = (comparison_caveat(r["feature"], *caveat_window)
                       or anomaly_caveat(platform, r["feature"], anomalies.get(r["feature"])))
        a = anomalies.get(r["feature"])
        r["unreviewed"] = bool(a) and not anomaly_review(platform, r["feature"], a)
    ANOMALIES.extend(x for x in found if not x["review"])
    ISSUES.extend((platform, w) for w in integrity_warnings(platform, quarter))
    return rows


ISSUES: list[tuple] = []   # company directory problems, gathered across platforms


def integrity_warnings(platform: str, quarter: str) -> list[str]:
    """Problems in the company directory found at fetch time, as sentences."""
    path = DATA_DIR / f"{platform}_integrity_{quarter}.csv"
    if not path.exists():
        return [f"no integrity check on file for {quarter}: re-run without --no-fetch"]
    out = []
    for r in _read(path):
        value, expected = _num(r["Value"]), _num(r["Expected"])
        if r["Check"] == "company join total" and value > expected:
            out.append(f"the company join inflates Jobs Done by {pct(value, expected):+.2f}% "
                       f"({fmt_n(value)} against {fmt_n(expected)}): the company directory "
                       f"holds duplicate rows. The figures here are unaffected (ranked on "
                       f"tenant_gid); report it upstream.")
        elif r["Check"] == "unnamed tenant in a top 3":
            out.append(f"tenant {r['Tenant']} ({fmt_n(value)} {r['Feature']} JD) has no company "
                       f"name, so it is left out of the {r['Feature']} top 3. Find out why.")
    return out


ANOMALIES: list[dict] = []   # unreviewed steps and spikes, gathered across platforms


def print_anomalies_to_review(quarter: str) -> None:
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
        print(f"\n  {x['feature']} ({x['platform']}): a {a['kind']} of {a['change']:+.0f}% "
              f"in the week of {a['week']} ({month_label(a['week'])})")
        print("    weekly Jobs Done: " + "  ".join(f"{w[5:]}:{fmt_n(v)}" for w, v in x["weeks"]))
        for d in x["drivers"]:
            slug = f" ({d['Slug']})" if d["Slug"] else ""
            print(f"    {d['Company']}{slug}: {_num(d['Share of change']):.0f}% of the change")
        print(f"    → {x['hint']}")
        print(f"    record: (\"{x['platform']}\", \"{x['feature']}\", \"{a['week']}\"): "
              f"(\"misleading\" or \"real\", \"<what the investigation found>\")")


def volume_alerts(quarter: str) -> list[dict]:
    """Volume alert episodes of both platforms over volume_period(quarter)."""
    episodes = []
    for platform in LOOKER_PLATFORMS:
        found = read_volume_episodes(platform, DATA_DIR / f"{platform}_daily_volume_{quarter}.csv",
                                     *volume_period(quarter))
        if found is None:
            print(f"⚠️ [{platform}] no daily volume on file for {quarter}: re-run without --no-fetch",
                  file=sys.stderr)
        episodes += found or []
    return episodes


def print_highlights(rows: list[dict]) -> None:
    """Candidates for "Which product domains grew the most?" and "... declined?".

    Both platforms in one list, ranked on QoQ. A feature whose comparison is not like
    for like (joined this quarter, tracking change) is set aside with the reason.
    """
    name = {"lumapps": "LumApps", "beekeeper": "Beekeeper"}
    ok = [r for r in rows if r["qoq"] is not None and not r["caveat"]]
    print(f"\n{'=' * 80}\nHIGHLIGHTS — both platforms, ranked on QoQ\n{'=' * 80}")
    print("  Pick 2 or 3 per list, with both platforms in each. 'small' = under "
          f"{SMALL_SHARE:.0f}% of its group: say its share if you pick it.")
    for title, pick in (("GREW THE MOST", sorted([r for r in ok if r["qoq"] > 0], key=lambda r: -r["qoq"])),
                        ("DECLINED", sorted([r for r in ok if r["qoq"] < 0], key=lambda r: r["qoq"]))):
        print(f"\n  {title}")
        for r in pick[:6]:
            small = "  small" if r["share"] < SMALL_SHARE else ""
            small += "  ⚠️ unreviewed step or spike" if r.get("unreviewed") else ""
            users = f"users {fmt_pct(r['users_qoq'])}" if r["users"] else "users not tracked"
            share = f"{r['share']:.2f}" if r["share"] < 0.1 else f"{r['share']:.1f}"
            print(f"    {r['feature']} ({name[r['platform']]}) {fmt_pct(r['qoq'])} QoQ, "
                  f"{share}% of {r['group']}, {users}  {r['streak']}{small}".rstrip())
    set_aside = [r for r in rows if r["caveat"]]
    if set_aside:
        print("\n  SET ASIDE (their QoQ is not like for like, never list them):")
        for r in set_aside:
            print(f"    {r['feature']} ({name[r['platform']]}) {fmt_pct(r['qoq'])}: {r['caveat']}")


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
    print(f"QUARTERLY JOBS DONE ANALYTICS — {quarter} (compared with {shift_quarter(quarter, -1)})")
    print("Jobs Done: summed over every day of the quarter.")
    print("Users: unique users completing a job over the whole quarter (not additive).")
    print(f"{'=' * 80}")
    if args.note:
        print(f"\nEDITORIAL NOTE FROM THE ANALYST — take this into account when writing\n  {args.note}")
    rows = []
    for platform in LOOKER_PLATFORMS:
        rows += analyse(platform, quarter)
    print_highlights(rows)
    print_anomalies_to_review(quarter)
    print_volume_alerts(volume_alerts(quarter))
    if ISSUES:
        print(f"\n{'!' * 80}\n⚠️  COMPANY DIRECTORY ISSUES ({len(ISSUES)})\n{'!' * 80}")
        for platform, w in ISSUES:
            print(f"  [{platform}] {w}")
        print(f"\n⚠️ {len(ISSUES)} company directory issue(s): see above.", file=sys.stderr)
    if ANOMALIES:
        print(f"\n⚠️ {len(ANOMALIES)} anomaly(ies) to review before writing: see above.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
