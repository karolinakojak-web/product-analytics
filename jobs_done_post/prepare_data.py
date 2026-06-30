#!/usr/bin/env python3
"""Prepare Jobs Done analytics for Claude Code analysis.

Reads four CSV files from the data/ subfolder:
  - lumapps_all_YYYY-MM.csv           platform totals + MAU (Lumapps)
  - beekeeper_all_YYYY-MM.csv         platform totals + MAU (Beekeeper)
  - lumapps_features_YYYY-MM.csv      feature-level breakdown (Lumapps)
  - beekeeper_features_YYYY-MM.csv    feature-level breakdown (Beekeeper)

Outputs structured analytics to stdout.

Usage:
    python3 prepare_data.py
    python3 prepare_data.py --month 2026-05
"""

import argparse
import csv
import glob
import re
import sys
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
            r["jd"] = jd
            r["jd_users"] = users
            r["frequency"] = round(jd / users, 2) if users > 0 else 0.0
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
    months = sorted(trends)
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


def feature_analytics(history: dict, report_month: str) -> list[dict]:
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

        # MoM series over all available months
        jd_series = [(m, by_month[m]["jd"]) for m in months_present]
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
            "mom_pct":      pct(cur["jd"], prev.get("jd", 0)) if prev else None,
            "yoy_pct":      pct(cur["jd"], yoy.get("jd", 0))  if yoy  else None,
            "abs_mom":      cur["jd"] - prev.get("jd", 0)     if prev else None,
            "prev_jd":      prev.get("jd", 0),
            "prev_freq":    prev.get("frequency"),
            "trend":        trend_label(mom_series),
            "consecutive":  consecutive_direction(mom_series),
            "avg_mom":      round(mean(mom_series), 1) if mom_series else None,
            "months_tracked": len(months_present),
            "jd_12m_peak":  max(by_month[m]["jd"] for m in months_present),
            "jd_12m_peak_month": max(months_present, key=lambda m: by_month[m]["jd"]),
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
        print(f"  {'Feature':<22} {'Jobs Done':>12} {'Users':>10} {'Freq':>6} {'MoM%':>8} {'YoY%':>8} {'Trend':<12} {'Consecutive'}")
        print("  " + "-"*96)
        for r in rows:
            mom  = fmt_pct(r["mom_pct"])
            yoy  = fmt_pct(r["yoy_pct"])
            freq = f"{r['frequency']:.1f}x"
            print(f"  {r['feature']:<22} {fmt_m(r['jd']):>12} {fmt_m(r['jd_users']):>10} {freq:>6} {mom:>8} {yoy:>8} {r['trend']:<12} {r['consecutive']}")


def print_movers(features: list[dict]) -> None:
    threshold_pct = 5
    threshold_abs = 5_000

    growers  = [r for r in features if r["mom_pct"] is not None and r["mom_pct"] >= threshold_pct  and (r["abs_mom"] or 0) >= threshold_abs]
    decliners= [r for r in features if r["mom_pct"] is not None and r["mom_pct"] <= -threshold_pct and abs(r["abs_mom"] or 0) >= threshold_abs]
    new      = [r for r in features if r["prev_jd"] == 0]

    if growers:
        print("\nTOP GROWERS THIS MONTH (MoM ≥ +5%, abs ≥ 5K)")
        print("-"*80)
        for r in sorted(growers, key=lambda x: x["mom_pct"], reverse=True):
            freq_chg = f"  freq {r['frequency']:.1f}x ← {r['prev_freq']:.1f}x" if r.get("prev_freq") else ""
            print(f"  + [{r['domain_group']}] {r['feature']}: "
                  f"{fmt_m(r['jd'])} JD  {fmt_pct(r['mom_pct'])} MoM  ({r['abs_mom']:+,} abs){freq_chg}")

    if decliners:
        print("\nTOP DECLINERS THIS MONTH (MoM ≤ -5%, abs ≥ 5K)")
        print("-"*80)
        for r in sorted(decliners, key=lambda x: x["mom_pct"]):
            freq_chg = f"  freq {r['frequency']:.1f}x ← {r['prev_freq']:.1f}x" if r.get("prev_freq") else ""
            print(f"  - [{r['domain_group']}] {r['feature']}: "
                  f"{fmt_m(r['jd'])} JD  {fmt_pct(r['mom_pct'])} MoM  ({r['abs_mom']:+,} abs){freq_chg}")

    if new:
        print("\nNEW / FIRST-TIME TRACKED FEATURES")
        print("-"*80)
        for r in new:
            print(f"  * [{r['domain_group']}] {r['feature']}: {fmt_m(r['jd'])} JD, {fmt_m(r['jd_users'])} users")


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
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="", help="Report month YYYY-MM (defaults to latest)")
    args = parser.parse_args()

    files = find_files()
    missing = [k for k, v in files.items() if not v]
    if missing:
        sys.exit(f"Error: could not find files for: {missing}\nLooked in: {DATA_DIR}")

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

    print_platform_section("Lumapps", luma_platform, report_month)
    print_platform_section("Beekeeper", beek_platform, report_month)

    # Feature analytics
    luma_features = feature_analytics(build_feature_history(luma_feat_rows, "Lumapps"), report_month)
    beek_features = feature_analytics(build_feature_history(beek_feat_rows, "Beekeeper"), report_month)

    print_feature_section("Lumapps", luma_features, report_month)
    print_movers(luma_features)
    print_yearly_trends("Lumapps", luma_features)

    print_feature_section("Beekeeper", beek_features, report_month)
    print_movers(beek_features)
    print_yearly_trends("Beekeeper", beek_features)


if __name__ == "__main__":
    main()
