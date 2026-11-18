#!/usr/bin/env python3
"""Check a quarterly Jobs Done article against the data and the editorial rules.

    python3 check_quarterly_article.py data/drafts/quarterly_2026-Q3.md

Reads the files prepare_quarterly.py writes to data/quarterly/ for that quarter. The
article reports LumApps and Beekeeper combined.

  OVERVIEW the five KPI lines, to the digit, as prepare_quarterly.py prints them: they
           are the figures of the dashboard's Overview tab for the quarter.
  NUMBERS  every other M/K/% figure must trace back to the data, with its sign.
  SHAPE    fixed lines, the two highlight sections, one ### block per domain group of
           the scope with its Jobs Done line, one line per feature of the group
           (largest first, right emoji), the group's top 3 companies in the script's
           order and one 💡 line.
  RULES    the shared wording rules (jobs_done_common.py), and no year-over-year.
  VOLUME   no daily volume alert left without a verdict, and a "*Data warning: ...*"
           line when a data incident is on record for the period.

Exit codes: 0 clean, 1 failures. Warnings never fail the run.
"""

import re
import sys
from pathlib import Path

import prepare_quarterly as pq
from jobs_done_common import (EMOJI, FRESH_HOURS, KPI_LABELS, SCOPE, SCOPE_GROUP, SMALL_SHARE, YOY,
                              anomaly_caveat, anomaly_review, check_numbers, check_overview,
                              check_volume, check_wording, comparison_caveat, dashboard_line,
                              month_label, num, pct, stale)

GREW = "### Which features grew the most?"
DECLINED = "### Which features declined?"
DOMAINS_SECTION = "## By tribe"
HIGHLIGHT = re.compile(r"^- (\S+)\s+\*\*([^*]+)\*\*\s+([+-]\d+(?:\.\d+)?)% QoQ", re.M)
GROUP = re.compile(r"^### (.+?)\s*$", re.M)
GROUP_LINE = re.compile(r"^- Jobs Done: \S+ \((?:[+-][\d.]+%|flat) QoQ\), [\d.]+% of all Jobs Done$", re.M)
FEATURES_LABEL = "Features by Jobs Done:"
FEATURE_LINE = re.compile(r"^- (\S+)\s+\*\*([^*]+)\*\*: \S+ \(([^)]*)\), [\d.]+% of the tribe$", re.M)
COMPANIES_LABEL = "Top 3 companies by Jobs Done:"


def scaled(v):
    """A level (volume, users, share): never matches a signed figure."""
    return [("M", v / 1e6, False), ("K", v / 1e3, False)]


def share(v):
    return [("%", v, False)]


def change(v):
    return [("%", v, True)] if v is not None else []


def total_values(totals, quarter):
    """The figures of the overview, as a prose sentence may quote them."""
    cur, prev = pq.quarter_kpis(totals, quarter), pq.quarter_kpis(totals, pq.shift_quarter(quarter, -1))
    out = []
    for k in ("jd", "users", "mau"):
        out += scaled(cur[k])
        if prev:
            out += scaled(prev[k]) + change(pct(cur[k], prev[k]))
    out += share(cur["reach"]) + (change(pct(cur["jpu"], prev["jpu"])) if prev else [])
    return out


def group_values(history, groups, quarter, total_jd):
    prev = pq.shift_quarter(quarter, -1)
    out = []
    for g, names in groups.items():
        jd = sum(history[(g, n)][quarter]["jd"] for n in names)
        pjd = sum(history[(g, n)].get(prev, {}).get("jd", 0) for n in names)
        out += scaled(jd) + scaled(pjd) + change(pct(jd, pjd)) + share(jd / total_jd * 100)
    return out


def feature_values(history, companies, group, name, group_jd, total_jd, quarter):
    by_q = history[(group, name)]
    cur, prev = by_q[quarter], by_q.get(pq.shift_quarter(quarter, -1))
    jd, us = cur["jd"], cur["users"]
    out = scaled(jd) + scaled(us) + share(jd / group_jd * 100) + share(jd / total_jd * 100)
    if prev:
        out += scaled(prev["jd"]) + scaled(prev["users"]) + change(pct(jd, prev["jd"]))
        out += change(pct(us, prev["users"]))
        if us and prev["users"]:
            out += change(pct(jd / us, prev["jd"] / prev["users"]))
    top3 = 0.0
    for c in companies.get((group, name), []):
        cj = num(c["Jobs Done"])
        out += scaled(cj) + share(cj / jd * 100)
        if int(c["Rank"]) <= 3:
            top3 += cj
    out += share(top3 / jd * 100)    # "the top 3 companies complete half of it"
    return out


def group_company_values(rows, group_jd):
    out = []
    for c in rows:
        cj = num(c["Jobs Done"])
        out += scaled(cj) + share(cj / group_jd * 100)
    return out


def caveat(name, anomalies, quarter):
    prev = pq.shift_quarter(quarter, -1)
    window = (f"{pq.quarter_start(prev):%Y-%m-%d}",
              f"{pq.quarter_start(pq.shift_quarter(quarter, 1)):%Y-%m-%d}")
    return comparison_caveat(name, *window) or anomaly_caveat(name, anomalies.get(name))


def check_highlights(text, data, quarter, failures):
    """The two highlight sections: 2 or 3 points each, like for like."""
    totals, history, companies, _ = data
    prev = pq.shift_quarter(quarter, -1)
    groups = pq.scope(history, quarter)
    group_of = {n: g for g, ns in groups.items() for n in ns}
    anomalies, _ = pq.weekly_anomalies(quarter)
    total_jd = totals[quarter]["jd"]
    for title, want_up in ((GREW, True), (DECLINED, False)):
        if title not in text:
            failures.append(f"missing the '{title[4:]}' section")
            continue
        body = text.split(title, 1)[1]
        body = re.split(r"^#{2,3} ", body, maxsplit=1, flags=re.M)[0]
        points = [l for l in body.splitlines() if l.startswith("- ")]
        label = "highlights/" + ("grew" if want_up else "declined")
        if not 2 <= len(points) <= 3:
            failures.append(f"{label}: {len(points)} points, write 2 or 3")
        for line in points:
            m = HIGHLIGHT.match(line)
            if not m:
                failures.append(f"{label}: write '- <emoji> **Feature** +x.x% QoQ: ...', got {line[:60]!r}")
                continue
            emoji, name, written = m.group(1), m.group(2).strip(), float(m.group(3))
            group = group_of.get(name)
            if not group:
                failures.append(f"{label}: {name} is not a live feature in {quarter}")
                continue
            if EMOJI.get(name) and emoji != EMOJI[name]:
                failures.append(f"{label}: {name} should use {EMOJI[name]}, not {emoji}")
            why = caveat(name, anomalies, quarter)
            if why:
                failures.append(f"{label}: {name} cannot be a highlight, its QoQ is not like for like ({why})")
            if (written > 0) != want_up:
                failures.append(f"{label}: {name} {written:+.1f}% belongs in the other section")
            group_jd = sum(history[(group, n)][quarter]["jd"] for n in groups[group])
            if history[(group, name)][quarter]["jd"] / group_jd * 100 < SMALL_SHARE and "% of " not in line:
                failures.append(f"{label}: {name} is under {SMALL_SHARE:.0f}% of {group}, say its share")
            check_numbers(line, total_values(totals, quarter)
                          + group_values(history, groups, quarter, total_jd)
                          + feature_values(history, companies, group, name, group_jd, total_jd, quarter),
                          f"{label}/{name}", failures)


def check_domains(sec, data, quarter, failures):
    totals, history, companies, group_companies = data
    total_jd = totals[quarter]["jd"]
    want = pq.scope(history, quarter)
    anomalies, _ = pq.weekly_anomalies(quarter)

    m = SCOPE.search(sec)
    if not m:
        failures.append("domains: open on the scope sentence 'Jobs Done covers <Domain> (<Feature>, ...)'")
    else:
        written = {d: {f.strip() for f in fs.split(",") if f.strip()}
                   for d, fs in SCOPE_GROUP.findall(m.group(1))}
        for d in sorted(set(want) | set(written)):
            miss, extra = set(want.get(d, [])) - written.get(d, set()), written.get(d, set()) - set(want.get(d, []))
            if miss:
                failures.append(f"scope sentence misses {', '.join(sorted(miss))} ({d})")
            if extra:
                failures.append(f"scope sentence lists {', '.join(sorted(extra))} ({d}), "
                                f"not tracked or not live in {quarter}")

    allowed = total_values(totals, quarter) + group_values(history, want, quarter, total_jd)
    heads = list(GROUP.finditer(sec))
    check_numbers(sec[:heads[0].start()] if heads else sec, allowed, "domains/intro", failures)

    seen_groups = [h.group(1) for h in heads]
    for g in want:
        if g not in seen_groups:
            failures.append(f"no '### {g}' block")
    for g in seen_groups:
        if g not in want:
            failures.append(f"'### {g}' is not a domain group of the {quarter} scope")
    order = sorted(want, key=lambda g: -sum(history[(g, n)][quarter]["jd"] for n in want[g]))
    if [g for g in seen_groups if g in want] != [g for g in order if g in seen_groups]:
        failures.append(f"order the domain blocks from largest to smallest: {', '.join(order)}")

    for i, h in enumerate(heads):
        g = h.group(1)
        body = sec[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(sec)]
        body = body.split("*Full breakdown available")[0]
        names = want.get(g, [])
        if not names:
            continue
        label = f"domains/{g}"
        group_jd = sum(history[(g, n)][quarter]["jd"] for n in names) or 1
        values = (allowed + group_company_values(group_companies.get(g, []), group_jd)
                  + [v for n in names for v in feature_values(history, companies, g, n, group_jd,
                                                              total_jd, quarter)])

        if not GROUP_LINE.search(body):
            failures.append(f"{label}: open the block on '- Jobs Done: <JD> (<QoQ> QoQ), "
                            f"<share>% of all Jobs Done'")

        # every feature of the group, largest first, with its emoji
        if FEATURES_LABEL not in body:
            failures.append(f"{label}: missing the '{FEATURES_LABEL}' list")
        listing = re.split(rf"^{re.escape(COMPANIES_LABEL)}|^💡", body.partition(FEATURES_LABEL)[2],
                           maxsplit=1, flags=re.M)[0]
        for raw in listing.splitlines():
            if raw.startswith("- ") and not FEATURE_LINE.match(raw):
                failures.append(f"{label}: write '- <emoji> **Feature**: <JD> (<QoQ> QoQ), "
                                f"<share>% of the tribe', got {raw[:60]!r}")
        lines = list(FEATURE_LINE.finditer(listing))
        written = [m.group(2).strip() for m in lines]
        for n in names:
            if n not in written:
                failures.append(f"{label}: no line for {n} in '{FEATURES_LABEL}'")
        for m in lines:
            emoji, name = m.group(1), m.group(2).strip()
            if name not in names:
                failures.append(f"{label}: {name} is not a live feature of {g} in {quarter}")
            elif EMOJI.get(name) and emoji != EMOJI[name]:
                failures.append(f"{label}: {name} should use {EMOJI[name]}, not {emoji}")
        listed = [n for n in written if n in names]
        if listed != [n for n in names if n in listed]:
            failures.append(f"{label}: list the features from largest to smallest Jobs Done: "
                            f"{', '.join(names)}")

        # the group's top 3 companies, as the script ranks them
        top = [f"{c['Company']} ({c['Slug']})" if c["Slug"] else c["Company"]
               for c in group_companies.get(g, [])[:3]]
        if top and COMPANIES_LABEL not in body:
            failures.append(f"{label}: missing the '{COMPANIES_LABEL}' list")
        positions = []
        for c in top:
            hit = re.search(rf"^\s*\d\.\s+{re.escape(c)}, ", body, re.M)
            positions.append(hit.start() if hit else -1)
        if top and -1 in positions:
            missing = [c for c, p in zip(top, positions) if p == -1]
            failures.append(f"{label}: top 3 companies should list {', '.join(missing)}")
        elif positions != sorted(positions):
            failures.append(f"{label}: top 3 companies are not in the script's order")

        insights = [l for l in body.splitlines() if l.startswith("💡")]
        if len(insights) != 1:
            failures.append(f"{label}: write one 💡 line, found {len(insights)}")
        for n in names:
            odd = anomalies.get(n)
            if odd and anomaly_caveat(n, odd) and month_label(odd["week"]) not in body:
                failures.append(f"{label}: {n} was reviewed as misleading ({odd['kind']} in the "
                                f"week of {odd['week']}); the 💡 line must explain it and name "
                                f"{month_label(odd['week'])}")
        check_numbers(body, values, label, failures)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_quarterly_article.py data/drafts/quarterly_YYYY-QN.md")
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"[check_quarterly] no such file: {path}")
    m = re.search(r"quarterly_(\d{4}-Q[1-4])\.md$", path.name)
    if not m:
        sys.exit(f"[check_quarterly] filename must be quarterly_YYYY-QN.md, got {path.name}")
    quarter = m.group(1)
    prev = pq.shift_quarter(quarter, -1)
    q_label, prev_label = f"Q{quarter[-1]} {quarter[:4]}", f"Q{prev[-1]} {prev[:4]}"
    text = path.read_text(encoding="utf-8")
    failures, warnings = [], []

    totals = pq.read_totals(quarter)
    if quarter not in totals:
        sys.exit(f"[check_quarterly] {quarter} missing from the data. Run: "
                 f"python3 prepare_quarterly.py --quarter {quarter}")
    data = (totals, pq.read_features(quarter), *pq.read_companies(quarter))

    if not re.search(rf"^# Jobs Done - {q_label} Product Performance$", text, re.M):
        failures.append(f"title must read '# Jobs Done - {q_label} Product Performance'")
    opening = (f"Hi Team, here is how our key product usage KPI, Jobs Done, performed in "
               f"{q_label} across LumApps and Beekeeper. Every change compares with {prev_label}.")
    # QoQ is defined in the glossary the render adds, not in the article.
    for needle, what in ((opening, "standard opening"),
                         ("## High level overview", "overview heading"),
                         (DOMAINS_SECTION, f"'{DOMAINS_SECTION}' section"),
                         (dashboard_line("quarter"), "italicised dashboard line, copied as it is")):
        if needle not in text:
            failures.append(f"missing {what}")
    # MAU covers 28 days and the users the whole quarter: outside its overview line,
    # "active users" would blur the two.
    kpi_lines = "\n".join(l for l in text.splitlines() if l.startswith(tuple(KPI_LABELS)))
    for hit in re.finditer(r"\bactive users?\b", text.replace(kpi_lines, ""), re.I):
        failures.append(f"'{hit.group(0)}': MAU belongs in the overview only, write 'Users with a Job Done'")
    # the fixed section titles hold "the most", which is not a claim
    check_wording(text.replace(GREW, "").replace(DECLINED, ""), failures, warnings)
    for hit in re.finditer(YOY, text, re.I):
        failures.append(f"the quarterly compares QoQ only: {hit.group(0)!r}")

    head, _, body = text.partition(DOMAINS_SECTION)
    overview, _, highlights = head.partition(GREW)
    check_overview(overview, pq.overview_lines(pq.quarter_kpis(totals, quarter),
                                               pq.quarter_kpis(totals, prev), "QoQ"), failures)
    history = data[1]
    allowed = total_values(totals, quarter) + group_values(
        history, pq.scope(history, quarter), quarter, totals[quarter]["jd"])

    def story(block):
        """The prose paragraphs of a block: no heading, KPI line, list item or rule."""
        return [p.strip() for p in block.split("\n\n") if p.strip()
                and not p.strip().startswith(("---", "#", "- ") + tuple(KPI_LABELS))]

    # Two or three sentences close the overview, after the two highlight lists: the
    # quarter as a whole, then the tribes behind it. They may quote the totals and the
    # figures of each tribe.
    if story(overview.partition("## High level overview")[2]):
        failures.append("overview: the introduction goes at the end of the overview, after "
                        f"'{DECLINED[4:]}', not between the KPI lines and the highlights")
    closing = story(highlights.partition(DECLINED)[2])
    if not closing:
        failures.append("overview: close it with two or three sentences on the quarter as a "
                        f"whole and the tribes behind it, after the '{DECLINED[4:]}' list")
    check_numbers("\n\n".join(story(overview.partition("## High level overview")[2]) + closing),
                  allowed, "overview", failures)
    if highlights:
        check_highlights(GREW + highlights, data, quarter, failures)
    else:
        failures.append(f"missing the '{GREW[4:]}' section")
    if body:
        check_domains(body, data, quarter, failures)

    # No article passes while a step or a spike waits for a person's verdict.
    live = {n for names in pq.scope(data[1], quarter).values() for n in names}
    for name, odd in pq.weekly_anomalies(quarter)[0].items():
        if name in live and not anomaly_review(name, odd):
            failures.append(f"{name}: unreviewed {odd['kind']} ({odd['change']:+.0f}% in the week "
                            f"of {odd['week']}); investigate it, then record 'misleading' or "
                            f"'real' in ANOMALY_REVIEWS (jobs_done_common.py)")

    # Company directory issues found at fetch time: warnings, since the article's
    # figures are ranked on organization_id and stay right; they still must be reported.
    for w in pq.integrity_warnings(quarter):
        warnings.append(f"company directory: {w}")

    # Daily volume: a broken pipeline leaves the figures traceable but wrong.
    check_volume(pq.volume_alerts(quarter), text, failures)
    read = [pq.data_file(k, quarter) for k in ("totals", "features", "companies", "group_companies",
                                               "feature_weeks", "daily_volume")]
    for p in read:
        if not p.exists():
            failures.append(f"no {p.name} on file: re-run python3 prepare_quarterly.py "
                            f"--quarter {quarter}")
    for p, hours in stale([p for p in read if p.exists()]):
        failures.append(f"data is {hours:.0f}h old ({p.name}): an article is checked on data "
                        f"fetched within {FRESH_HOURS}h. Re-run python3 prepare_quarterly.py "
                        f"--quarter {quarter}")

    print(f"[check_quarterly] {path.name} ({quarter})")
    for w in warnings:
        print(f"  !   {w}")
    for f in failures:
        print(f"  KO  {f}")
    if failures:
        print(f"\n  {len(failures)} failure(s). Fix the article, or the data is stale: "
              f"python3 prepare_quarterly.py --quarter {quarter}")
        return 1
    print(f"  OK  no failures ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
