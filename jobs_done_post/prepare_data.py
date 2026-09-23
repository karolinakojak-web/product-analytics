#!/usr/bin/env python3
"""Prepare Jobs Done analytics for Claude Code analysis.

Reads four CSV files from the data/ subfolder:
  - lumapps_all_YYYY-MM.csv           platform totals + MAU (Lumapps)
  - beekeeper_all_YYYY-MM.csv         platform totals + MAU (Beekeeper)
  - lumapps_features_YYYY-MM.csv      feature-level breakdown (Lumapps)
  - beekeeper_features_YYYY-MM.csv    feature-level breakdown (Beekeeper)

Outputs structured analytics to stdout.

Usage:
    python3 prepare_data.py                      analyse the CSVs already in data/
    python3 prepare_data.py --fetch              pull fresh CSVs from Looker, then analyse
    python3 prepare_data.py --month 2026-05      target a specific report month
"""

import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from statistics import mean, stdev

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def detect_delimiter(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        line = f.readline()
    return ";" if line.count(";") > line.count(",") else ","


def clean_header(raw: str) -> str:
    h = re.sub(r"[^\x00-\x7F]+", "", raw)   # strip emojis
    h = re.sub(r"\s+", " ", h).strip().lower()
    h = re.sub(r"date selection\s*", "", h)  # strip "date selection" prefix
    return h.strip()


def identify_feature_column(raw: str) -> str:
    h = clean_header(raw)
    if "calendar date" in h or h == "date":
        return "date"
    if "calendar month" in h or h == "month":
        return "month"
    if "domain group" in h:
        return "domain_group"
    if re.search(r"\bfeature$", h):
        return "feature"
    if "jobs done users" in h:
        return "jd_users"
    if "jobs done" in h and not any(w in h for w in ("users", "domain", "feature", "group")):
        return "jd"
    return h


def identify_all_column(raw: str) -> str:
    h = clean_header(raw)
    if "calendar date" in h or h == "date":
        return "date"
    if "calendar month" in h or h == "month":
        return "month"
    if "mau" in h:
        return "mau"
    if "jobs done users" in h:
        return "jd_users"
    if "jobs done" in h and "users" not in h:
        return "jd"
    return h


def _parse_num(v: str) -> float:
    try:
        return float(v.replace(",", "").strip())
    except ValueError:
        return 0.0


def read_feature_csv(path: str, company: str) -> list[dict]:
    delimiter = detect_delimiter(path)
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        col_map = {h: identify_feature_column(h) for h in (reader.fieldnames or [])}
        for raw in reader:
            r = {col_map[k]: v.strip() for k, v in raw.items()}
            r["company"] = company
            jd = int(_parse_num(r.get("jd", "0")))
            users = int(_parse_num(r.get("jd_users", "0")))
            mau = _parse_num(r.get("mau", "0"))
            r["jd"] = jd
            r["jd_users"] = users
            r["mau"] = mau
            r["frequency"] = round(jd / users, 2) if users > 0 else 0.0
            # Share of the active user base that used this feature. MAU is
            # platform-wide, so this is reach, not a within-domain ratio.
            r["ucj_mau_pct"] = round(users / mau * 100, 1) if mau else None
            if r.get("month") and len(r["month"]) == 7:
                rows.append(r)
    return rows


def read_all_csv(path: str) -> list[dict]:
    """Read platform-total file (with MAU). Filters rows with MAU=0 (noise)."""
    delimiter = detect_delimiter(path)
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        col_map = {h: identify_all_column(h) for h in (reader.fieldnames or [])}
        for raw in reader:
            r = {col_map[k]: v.strip() for k, v in raw.items()}
            mau = _parse_num(r.get("mau", "0"))
            if mau == 0:
                continue  # filter noise rows (Lumapps has some 0-MAU artifact rows)
            r["jd"] = int(_parse_num(r.get("jd", "0")))
            r["jd_users"] = int(_parse_num(r.get("jd_users", "0")))
            r["mau"] = mau
            if r.get("month") and len(r["month"]) == 7:
                rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_files() -> dict[str, str]:
    d = str(DATA_DIR)
    def latest(pattern: str) -> str:
        matches = sorted(glob.glob(f"{d}/{pattern}"))
        return matches[-1] if matches else ""

    return {
        "lumapps_all":     latest("lumapps_all*.csv"),
        "beekeeper_all":   latest("beekeeper_all*.csv"),
        "lumapps_feat":    latest("lumapps_features_*.csv"),
        "beekeeper_feat":  latest("beekeeper_features*.csv"),
    }


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------

def adj_month(ym: str, delta: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m += delta
    while m > 12: m -= 12; y += 1
    while m < 1:  m += 12; y -= 1
    return f"{y}-{m:02d}"


def sorted_months(rows: list[dict]) -> list[str]:
    return sorted({r["month"] for r in rows if r.get("month")})


def pct(a, b) -> float | None:
    return round((a - b) / b * 100, 1) if b else None


def fmt_pct(v) -> str:
    return f"{v:+.1f}%" if v is not None else "n/a"


def fmt_m(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}K"
    return str(int(v))


def trend_label(mom_series: list[float]) -> str:
    """Classify a feature's trend from its MoM % series."""
    if len(mom_series) < 3:
        return "insufficient data"
    avg = mean(mom_series)
    if len(mom_series) >= 3:
        sd = stdev(mom_series) if len(mom_series) > 1 else 0
    else:
        sd = 0
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
# Platform total trends (from all-files with MAU)
# ---------------------------------------------------------------------------

def build_platform_trends(all_rows: list[dict]) -> dict[str, dict]:
    """month -> {jd, jd_users, mau, ucj_pct}"""
    by_month = {}
    for r in all_rows:
        m = r["month"]
        by_month[m] = {
            "jd": r["jd"],
            "jd_users": r["jd_users"],
            "mau": r["mau"],
            "ucj_pct": round(r["jd_users"] / r["mau"] * 100, 1) if r["mau"] else None,
        }
    return by_month


def print_platform_section(company: str, trends: dict[str, dict], report_month: str) -> None:
    # Older months are fetched only to back the YoY column; don't print them.
    months = sorted(trends)[-REPORTED_MONTHS:]
    print(f"\n{'='*80}")
    print(f"{company.upper()} — PLATFORM TOTALS (13-month trend)")
    print(f"{'='*80}")
    print(f"{'Month':<10} {'Jobs Done':>14} {'MoM%':>7} {'YoY%':>7} {'Users Compl.':>14} {'MAU':>12} {'UCJ/MAU':>9}")
    print("-" * 80)
    for m in months:
        d = trends[m]
        prev = trends.get(adj_month(m, -1), {})
        yoy  = trends.get(adj_month(m, -12), {})
        mom  = fmt_pct(pct(d["jd"], prev["jd"])) if prev else " n/a"
        yoy_s= fmt_pct(pct(d["jd"], yoy["jd"]))  if yoy  else " n/a"
        ucj  = f"{d['ucj_pct']:.1f}%" if d.get("ucj_pct") else "n/a"
        marker = " ◄ report month" if m == report_month else ""
        print(f"{m:<10} {fmt_m(d['jd']):>14} {mom:>7} {yoy_s:>7} {fmt_m(d['jd_users']):>14} {fmt_m(d['mau']):>12} {ucj:>9}{marker}")

    # Summary of trend
    jd_series = [trends[m]["jd"] for m in months]
    mom_series = [pct(jd_series[i], jd_series[i-1]) for i in range(1, len(jd_series)) if jd_series[i-1]]
    mom_series = [v for v in mom_series if v is not None]
    consec = consecutive_direction(mom_series)
    print(f"\n  Trend: {trend_label(mom_series)}  |  Avg MoM: {mean(mom_series):+.1f}%  |  {consec}")


# ---------------------------------------------------------------------------
# Feature-level analytics
# ---------------------------------------------------------------------------

def build_feature_history(rows: list[dict], company: str) -> dict:
    """Returns {fkey: {month: row}} for all features of a company."""
    history: dict[tuple, dict] = {}
    for r in rows:
        if r["company"] != company:
            continue
        k = (r.get("domain_group", ""), r.get("feature", ""))
        history.setdefault(k, {})[r["month"]] = r
    return history


def feature_analytics(history: dict, report_month: str, platform_change: float = 0.0) -> list[dict]:
    """platform_change: the platform's own MoM change in Jobs Done, used to express
    each feature's contribution to it."""
    prev_month = adj_month(report_month, -1)
    yoy_month  = adj_month(report_month, -12)
    results = []

    for fkey, by_month in history.items():
        cur  = by_month.get(report_month)
        if cur is None:
            continue
        prev = by_month.get(prev_month, {})
        yoy  = by_month.get(yoy_month, {})
        months_present = sorted(by_month)
        recent = months_present[-REPORTED_MONTHS:]

        # MoM series over the reported window (older months only back the YoY column)
        jd_series = [(m, by_month[m]["jd"]) for m in recent]
        mom_series = [
            pct(jd_series[i][1], jd_series[i-1][1])
            for i in range(1, len(jd_series))
            if jd_series[i-1][1]
        ]
        mom_series = [v for v in mom_series if v is not None]

        results.append({
            "domain_group": fkey[0],
            "feature":      fkey[1],
            "jd":           cur["jd"],
            "jd_users":     cur["jd_users"],
            "frequency":    cur["frequency"],
            "ucj_mau_pct":  cur.get("ucj_mau_pct"),
            "mom_pct":      pct(cur["jd"], prev.get("jd", 0)) if prev else None,
            "yoy_pct":      pct(cur["jd"], yoy.get("jd", 0))  if yoy  else None,
            "abs_mom":      cur["jd"] - prev.get("jd", 0)     if prev else None,
            # This feature's contribution to the platform's MoM change. This is
            # what "biggest influence on the overall result" actually means.
            "contribution_pct":  (round((cur["jd"] - prev.get("jd", 0)) / platform_change * 100, 1)
                             if prev and platform_change else None),
            "prev_jd":      prev.get("jd", 0),
            "prev_freq":    prev.get("frequency"),
            "trend":        trend_label(mom_series),
            "consecutive":  consecutive_direction(mom_series),
            "avg_mom":      round(mean(mom_series), 1) if mom_series else None,
            "months_tracked": len(months_present),
            "jd_12m_peak":  max(by_month[m]["jd"] for m in recent),
            "jd_12m_peak_month": max(recent, key=lambda m: by_month[m]["jd"]),
        })

    return sorted(results, key=lambda r: r["jd"], reverse=True)


def print_feature_section(company: str, features: list[dict], report_month: str) -> None:
    print(f"\n{'='*80}")
    print(f"{company.upper()} — FEATURE BREAKDOWN")
    print(f"{'='*80}")

    # Group by domain group
    groups = {}
    for r in features:
        groups.setdefault(r["domain_group"], []).append(r)

    # Sort groups by total JD in report month
    for grp in sorted(groups, key=lambda g: sum(r["jd"] for r in groups[g]), reverse=True):
        rows = groups[grp]
        grp_total = sum(r["jd"] for r in rows)
        print(f"\n  [{grp}]  —  {fmt_m(grp_total)} total JD")
        print(f"  {'Feature':<22} {'Jobs Done':>12} {'Users':>10} {'UCJ/MAU':>8} {'Freq':>6} {'MoM%':>8} {'YoY%':>8} {'Trend':<12} {'Consecutive'}")
        print("  " + "-"*105)
        for r in rows:
            mom  = fmt_pct(r["mom_pct"])
            yoy  = fmt_pct(r["yoy_pct"])
            freq = f"{r['frequency']:.1f}x"
            reach = f"{r['ucj_mau_pct']:.1f}%" if r.get("ucj_mau_pct") is not None else "n/a"
            print(f"  {r['feature']:<22} {fmt_m(r['jd']):>12} {fmt_m(r['jd_users']):>10} {reach:>8} {freq:>6} {mom:>8} {yoy:>8} {r['trend']:<12} {r['consecutive']}")


def print_movers(features: list[dict], platform_jd: float = 0.0) -> None:
    """Rank what to write about.

    A feature's CONTRIBUTION is its own absolute MoM change over the platform's, i.e.
    how much of the month it explains. For LumApps in August 2026 the platform went
    127.99M -> 118.04M (-9.95M) and Content alone moved -8.51M, so Content contributed
    85.5% of the month. Jobs Done is additive across features, so contributions sum to
    100%. A contribution is negative when the feature moved against its platform.

    Two lists, deliberately. Sorting by MoM% alone systematically promotes small
    features: in August 2026 it put Videos (-26.7%, 1.1% of the change) above Content
    (-7.1%, 85.5% of it). Ranking by contribution answers "what happened this month";
    the relative list keeps small-but-loud signals from disappearing.
    """
    DRIVER_SHARE_MIN = 2.0      # % of the platform's monthly change
    RELATIVE_MOM_MIN = 10.0     # %
    RELATIVE_ABS_MIN = max(5_000, platform_jd * 0.0005)   # 0.05% of platform volume

    drivers = [r for r in features
               if r.get("contribution_pct") is not None and abs(r["contribution_pct"]) >= DRIVER_SHARE_MIN]
    if drivers:
        print(f"\nBIGGEST DRIVERS OF THE MONTH (≥ {DRIVER_SHARE_MIN:.0f}% of the platform's monthly change)")
        print("-"*80)
        print("  Ranked by how much of this month's movement each feature explains.")
        for r in sorted(drivers, key=lambda x: -abs(x["contribution_pct"])):
            sign = "+" if (r["abs_mom"] or 0) >= 0 else "-"
            # A negative share means the feature moved against its platform — worth
            # saying out loud ("everything grew except X"), not hiding behind abs().
            against = "  <- moved AGAINST the platform" if r["contribution_pct"] < 0 else ""
            print(f"  {sign} [{r['domain_group']}] {r['feature']}: "
                  f"{abs(r['contribution_pct']):.1f}% of the monthly change  |  {fmt_m(r['jd'])} JD  "
                  f"{fmt_pct(r['mom_pct'])} MoM  ({r['abs_mom']:+,} abs){against}")

    relative = [r for r in features
                if r["mom_pct"] is not None and abs(r["mom_pct"]) >= RELATIVE_MOM_MIN
                and abs(r["abs_mom"] or 0) >= RELATIVE_ABS_MIN
                and r not in drivers]
    if relative:
        print(f"\nSTRONGEST RELATIVE MOVES (|MoM| ≥ {RELATIVE_MOM_MIN:.0f}%, abs ≥ {fmt_m(RELATIVE_ABS_MIN)})")
        print("-"*80)
        print("  Not top drivers by volume — cover at most one of these, and only if it tells a story.")
        for r in sorted(relative, key=lambda x: -abs(x["mom_pct"])):
            freq_chg = f"  freq {r['frequency']:.1f}x ← {r['prev_freq']:.1f}x" if r.get("prev_freq") else ""
            if r.get("contribution_pct") is None:
                share = "n/a"
            elif r["contribution_pct"] < 0:
                share = f"{abs(r['contribution_pct']):.1f}% of the monthly change, against the platform"
            else:
                share = f"{abs(r['contribution_pct']):.1f}% of the monthly change"
            print(f"  · [{r['domain_group']}] {r['feature']}: {fmt_m(r['jd'])} JD  "
                  f"{fmt_pct(r['mom_pct'])} MoM  ({share}){freq_chg}")

    # A feature tracked for less than the full window is new to the metric. It will
    # never rank on volume, but "we started measuring this" is itself news.
    newly = [r for r in features if r["months_tracked"] < REPORTED_MONTHS]
    if newly:
        print("\nNEWLY TRACKED FEATURES (shorter history than the reporting window)")
        print("-"*80)
        print("  Too small to rank on volume. Worth a line the first time they appear.")
        for r in sorted(newly, key=lambda x: x["months_tracked"]):
            print(f"  * [{r['domain_group']}] {r['feature']}: {fmt_m(r['jd'])} JD, "
                  f"{fmt_m(r['jd_users'])} users, {r['months_tracked']} months tracked, "
                  f"{fmt_pct(r['mom_pct'])} MoM")


def print_yearly_trends(company: str, features: list[dict]) -> None:
    """Summary of 12-month trajectory per feature."""
    print(f"\n{'='*80}")
    print(f"{company.upper()} — YEARLY TRENDS (12-month trajectory)")
    print(f"{'='*80}")
    print(f"  {'Feature':<22} {'Group':<35} {'Trend':<12} {'Avg MoM':>8} {'YoY%':>8} {'Peak month':<10} {'Consecutive'}")
    print("  " + "-"*110)
    for r in features:
        print(f"  {r['feature']:<22} {r['domain_group']:<35} {r['trend']:<12} "
              f"{fmt_pct(r['avg_mom']):>8} {fmt_pct(r['yoy_pct']):>8} "
              f"{r['jd_12m_peak_month']:<10} {r['consecutive']}")


# ---------------------------------------------------------------------------
# Looker API fetch  (--fetch)
# ---------------------------------------------------------------------------
# Replaces the manual CSV export from the two LookML "Jobs Done" dashboards:
#   LumApps    https://bi.lumapps.com/dashboards/base%3A%3Ajobs_done
#   Beekeeper  https://bi.lumapps.com/dashboards/product_bi%3A%3Ajobs_done
#
# Three of the four dashboard tabs are pulled ("Month overview" is skipped —
# it is a 1-month snapshot, redundant with the 13-month series). Each tab is
# fetched at two scopes, "total" (platform-wide) and "features" (broken down
# by product domain group and feature), giving 6 queries per platform.
#
# The dashboard tiles pivot on feature; we request the same data unpivoted so
# it lands in long format, which is what the parsers above expect.
#
# Credentials come from the standard Looker SDK environment variables:
#   LOOKERSDK_BASE_URL / LOOKERSDK_CLIENT_ID / LOOKERSDK_CLIENT_SECRET

RAW_DIR = DATA_DIR / "raw"

# 25 months of history: 13 months are reported, and each of them needs the same
# month a year earlier to get a YoY figure. The dashboards default to 13 months,
# which only yields YoY for the report month itself.
TIME_FRAME = "25 month ago for 25 month"
REPORTED_MONTHS = 13

LOOKER_PLATFORMS = {
    "lumapps": {
        "dashboard": "base::jobs_done",
        "model": "base",
        "view": "fct_jobs_done__bi",
        "prefix": "fct_jobs_done__bi",
        "mau_field": "fct_user_metrics__bi.total_mau",
        "filters": {
            "fct_jobs_done__bi.calendar_date": TIME_FRAME,
            "fct_jobs_done__bi.day_selection": "last^_day^_of^_month",
        },
    },
    "beekeeper": {
        "dashboard": "product_bi::jobs_done",
        "model": "product_bi",
        "view": "jobs_done",
        "prefix": "jobs_done",
        "mau_field": "user_metrics.mau",
        # Beekeeper tiles carry tenant scoping that LumApps does not have.
        # Dropping these would silently change every number. The tab tiles leave
        # tenants.is_customer empty, so we do too.
        "filters": {
            "jobs_done.calendar_date": TIME_FRAME,
            "jobs_done.day_selection": "last^_day^_of^_month",
            "jobs_done.jobs_done_version_param": "2026.1",
            "tenants.account_selection": "commercial^_all",
        },
    },
}

# tab name -> measures to pull for it
LOOKER_TABS = {
    "jobs_done": lambda cfg: [f"{cfg['prefix']}.jobs_done_28d"],
    "ucj":       lambda cfg: [f"{cfg['prefix']}.active_users_28d", cfg["mau_field"]],
    "frequency": lambda cfg: [f"{cfg['prefix']}.jobs_done_per_user_28d"],
}

# Looker field -> canonical CSV header written out for the parsers above.
HEADER_FOR = {
    "calendar_month":        "Calendar Month",
    "product_domain_group":  "Product Domain Group",
    "feature":               "Feature",
    "jobs_done_28d":         "Jobs Done",
    "active_users_28d":      "Jobs Done Users",
    "jobs_done_per_user_28d": "Frequency",
    "total_mau":             "MAU",
    "mau":                   "MAU",
}


def _header_for(field: str) -> str:
    return HEADER_FOR.get(field.split(".", 1)[-1], field)


def _run(sdk, cfg: dict, measures: list[str], breakdown: bool) -> list[dict]:
    """Run one unpivoted inline query and return its JSON rows."""
    from looker_sdk import models40

    dims = [f"{cfg['prefix']}.calendar_month"]
    if breakdown:
        dims += [f"{cfg['prefix']}.product_domain_group", f"{cfg['prefix']}.feature"]

    query = models40.WriteQuery(
        model=cfg["model"],
        view=cfg["view"],
        fields=dims + measures,
        filters=dict(cfg["filters"]),
        sorts=[f"{cfg['prefix']}.calendar_month desc"] + dims[1:],
        limit="5000",
    )
    return json.loads(sdk.run_inline_query(result_format="json", body=query))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([_header_for(x) for x in fields])
        for r in rows:
            w.writerow(["" if r.get(x) is None else r[x] for x in fields])


def fetch_from_looker(report_month: str = "") -> str:
    """Pull the three dashboard tabs for both platforms and write the CSVs.

    Writes the per-tab responses to data/raw/ as an audit trail, then merges
    them into the four data/ files the analytics below read.
    Returns the month stamp used in the filenames.
    """
    try:
        import looker_sdk
    except ImportError:
        sys.exit("Error: looker-sdk is not installed.  pip install -r requirements.txt")

    for var in ("LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET"):
        if not os.environ.get(var):
            sys.exit(f"Error: {var} is not set. See .env.example.")

    sdk = looker_sdk.init40()
    print(f"[looker] {os.environ['LOOKERSDK_BASE_URL']}", file=sys.stderr)

    stamp = report_month
    written = []

    for platform, cfg in LOOKER_PLATFORMS.items():
        # key -> merged row, so the three tabs line up on the same grain
        totals: dict[str, dict] = {}
        features: dict[tuple, dict] = {}

        for tab, measures_for in LOOKER_TABS.items():
            measures = measures_for(cfg)

            for scope, breakdown in (("total", False), ("features", True)):
                rows = _run(sdk, cfg, measures, breakdown)
                dims = [f"{cfg['prefix']}.calendar_month"]
                if breakdown:
                    dims += [f"{cfg['prefix']}.product_domain_group", f"{cfg['prefix']}.feature"]

                raw_path = RAW_DIR / f"{platform}_{tab}_{scope}_{stamp}.csv"
                _write_csv(raw_path, dims + measures, rows)
                written.append(raw_path)
                print(f"  [{platform}] {tab}/{scope}: {len(rows)} rows -> {raw_path.name}",
                      file=sys.stderr)

                target = features if breakdown else totals
                for r in rows:
                    month = r.get(f"{cfg['prefix']}.calendar_month")
                    if not month:
                        continue
                    if breakdown:
                        key = (month,
                               r.get(f"{cfg['prefix']}.product_domain_group") or "",
                               r.get(f"{cfg['prefix']}.feature") or "")
                    else:
                        key = month
                    slot = target.setdefault(key, {})
                    for m in measures:
                        slot[_header_for(m)] = r.get(m)

        # --- merged files, matching the historical manual-export layout ---
        all_path = DATA_DIR / f"{platform}_all_{stamp}.csv"
        _merge_csv(all_path,
                   ["Calendar Month", "Jobs Done", "Jobs Done Users", "MAU", "Frequency"],
                   [{"Calendar Month": m, **v} for m, v in sorted(totals.items(), reverse=True)])
        written.append(all_path)

        feat_path = DATA_DIR / f"{platform}_features_{stamp}.csv"
        _merge_csv(feat_path,
                   ["Calendar Month", "Product Domain Group", "Feature",
                    "Jobs Done", "Jobs Done Users", "MAU", "Frequency"],
                   [{"Calendar Month": k[0], "Product Domain Group": k[1], "Feature": k[2], **v}
                    for k, v in sorted(features.items(), reverse=True)])
        written.append(feat_path)

        print(f"  [{platform}] merged -> {all_path.name}, {feat_path.name}", file=sys.stderr)

    print(f"[looker] {len(written)} files written\n", file=sys.stderr)
    return stamp


def _merge_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({h: r.get(h, "") for h in headers})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def default_report_month() -> str:
    """Last complete calendar month."""
    t = date.today()
    return adj_month(f"{t.year}-{t.month:02d}", -1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="",
                        help="Report month YYYY-MM (defaults to the last complete month)")
    parser.add_argument("--fetch", action="store_true",
                        help="Pull fresh CSVs from the Looker dashboards before analysing")
    parser.add_argument("--note", default="", metavar="TEXT",
                        help="Editorial context to surface at the top of the report, e.g. "
                             "\"the Agents feature was added this month, worth a mention\"")
    args = parser.parse_args()

    if args.fetch:
        fetch_from_looker(args.month or default_report_month())

    files = find_files()
    missing = [k for k, v in files.items() if not v]
    if missing:
        sys.exit(f"Error: could not find files for: {missing}\nLooked in: {DATA_DIR}\n"
                 f"Run with --fetch to pull them from Looker.")

    print(f"[Files]", file=sys.stderr)
    for k, v in files.items():
        print(f"  {k}: {Path(v).name}", file=sys.stderr)

    # Load data
    luma_all_rows  = read_all_csv(files["lumapps_all"])
    beek_all_rows  = read_all_csv(files["beekeeper_all"])
    luma_feat_rows = read_feature_csv(files["lumapps_feat"], "Lumapps")
    beek_feat_rows = read_feature_csv(files["beekeeper_feat"], "Beekeeper")

    # Determine report month
    all_months = sorted_months(luma_feat_rows + beek_feat_rows)
    report_month = args.month or (all_months[-1] if all_months else "")
    if not report_month:
        sys.exit("Error: no month data found.")

    print(f"[Report month] {report_month}\n", file=sys.stderr)

    # Platform trends
    luma_platform = build_platform_trends(luma_all_rows)
    beek_platform = build_platform_trends(beek_all_rows)

    print(f"{'='*80}")
    print(f"JOBS DONE ANALYTICS — {report_month}")
    print(f"Methodology: 28-day rolling window ending on the last day of each month.")
    print(f"Frequency = Jobs Done / Users Completing Jobs.")
    print(f"UCJ/MAU = Users Completing Jobs as % of Monthly Active Users.")
    print(f"{'='*80}")

    if args.note:
        print(f"\n{'='*80}")
        print("EDITORIAL NOTE FROM THE ANALYST — take this into account when writing")
        print(f"{'='*80}")
        print(f"  {args.note}")

    print_platform_section("Lumapps", luma_platform, report_month)
    print_platform_section("Beekeeper", beek_platform, report_month)

    # Feature analytics. Each feature is scored against its own platform's monthly
    # change, so "influence on the overall result" is computed rather than eyeballed.
    def monthly_change(trends: dict) -> tuple[float, float]:
        cur = trends.get(report_month, {})
        prev = trends.get(adj_month(report_month, -1), {})
        return cur.get("jd", 0) - prev.get("jd", 0), cur.get("jd", 0)

    luma_change, luma_jd = monthly_change(luma_platform)
    beek_change, beek_jd = monthly_change(beek_platform)

    luma_features = feature_analytics(build_feature_history(luma_feat_rows, "Lumapps"),
                                      report_month, luma_change)
    beek_features = feature_analytics(build_feature_history(beek_feat_rows, "Beekeeper"),
                                      report_month, beek_change)

    print_feature_section("Lumapps", luma_features, report_month)
    print_movers(luma_features, luma_jd)
    print_yearly_trends("Lumapps", luma_features)

    print_feature_section("Beekeeper", beek_features, report_month)
    print_movers(beek_features, beek_jd)
    print_yearly_trends("Beekeeper", beek_features)


if __name__ == "__main__":
    main()
