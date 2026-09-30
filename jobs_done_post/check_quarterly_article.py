#!/usr/bin/env python3
"""Check a quarterly Jobs Done article against the data and the editorial rules.

    python3 check_quarterly_article.py articles/quarterly_2026-Q2.md

Reads the files prepare_quarterly.py writes to data/quarterly/ for that quarter.

  NUMBERS  every M/K/% figure must trace back to the data, with its sign.
  SHAPE    fixed lines, one ### section per domain group of the scope, one block per
           feature of the scope, the right emoji and arrow, the top 3 companies in
           the script's order.
  RULES    the shared wording rules (jobs_done_common.py), and no year-over-year.

Exit codes: 0 clean, 1 failures. Warnings never fail the run.
"""

import csv
import re
import sys
from pathlib import Path

from jobs_done_common import (EMOJI, GO_LIVE, SCOPE, SCOPE_GROUP, SMALL_SHARE, YOY,
                              FRESH_HOURS, anomaly_caveat, anomaly_review, check_numbers,
                              check_wording, comparison_caveat, month_label, num, pct, stale,
                              weekly_anomaly)

DATA_DIR = Path(__file__).resolve().parent / "data" / "quarterly"

GREW = "### Which product domains grew the most?"
DECLINED = "### Which product domains declined?"
HIGHLIGHT = re.compile(r"^- (\S+)\s+\*\*([^*]+)\*\*\s+\((LumApps|Beekeeper)\)\s+([+-]\d+(?:\.\d+)?)% QoQ", re.M)
ARROWS = {"⬆️": "up", "⬇️": "down", "➡️": "flat"}
HEADING = re.compile(r"^(⬆️|⬇️|➡️)\s*(\S+)\s+\*\*([^*]+)\*\*", re.M)
GROUP = re.compile(r"^### (.+?)\s*$", re.M)
FIXED = [
    ("*Don't you know what \"Jobs Done\" metrics are?", "italicised intro link"),
    ("*Full breakdown available in the [LumApps Jobs Done dashboard]", "italicised LumApps dashboard link"),
    ("*Full breakdown available in the [Beekeeper Jobs Done dashboard]", "italicised Beekeeper dashboard link"),
    ("## High level overview", "overview heading"),
]


def shift(q, d):
    y, n = int(q[:4]), int(q[-1])
    i = y * 4 + n - 1 + d
    return f"{i // 4}-Q{i % 4 + 1}"


READ = set()   # data files the check read, for the freshness check


def read(platform, kind, quarter):
    path = DATA_DIR / f"{platform}_{kind}_{quarter}.csv"
    if not path.exists():
        sys.exit(f"[check_quarterly] {path} not found. Run: "
                 f"python3 prepare_quarterly.py --quarter {quarter}")
    READ.add(path)
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def anomalies(platform, quarter):
    """{feature: step or spike} from the weekly Jobs Done of this quarter and the one before."""
    weekly = {}
    for r in read(platform, "feature_weeks", quarter):
        weekly.setdefault(r["Feature"], []).append((r["Week"], num(r["Jobs Done"])))
    return {f: a for f, a in ((f, weekly_anomaly(v)) for f, v in weekly.items()) if a}


def load(platform, quarter):
    totals = {r["Quarter"]: r for r in read(platform, "totals", quarter)}
    feats = {}
    for r in read(platform, "features", quarter):
        feats.setdefault(r["Feature"], {})[r["Quarter"]] = r
    companies = {}
    for r in read(platform, "companies", quarter):
        companies.setdefault(r["Feature"], []).append(r)
    return totals, feats, companies


def scope(feats, quarter):
    """{group: [features, largest first]} live and non-zero in the quarter."""
    last_month = f"{quarter[:4]}-{3 * int(quarter[-1]):02d}"
    out = {}
    for name, by_q in feats.items():
        row = by_q.get(quarter)
        if row and num(row["Jobs Done"]) and GO_LIVE.get(name, last_month) <= last_month:
            out.setdefault(row["Product Domain Group"], []).append((num(row["Jobs Done"]), name))
    return {g: [n for _, n in sorted(v, reverse=True)] for g, v in out.items()}


def scaled(v):
    """A level (volume, users, share): never matches a signed figure."""
    return [("M", v / 1e6, False), ("K", v / 1e3, False)]


def share(v):
    return [("%", v, False)]


def change(v):
    return [("%", v, True)] if v is not None else []


def platform_values(totals, quarter):
    cur, prev = totals.get(quarter), totals.get(shift(quarter, -1))
    if not cur:
        sys.exit(f"[check_quarterly] {quarter} missing from the data")
    out = []
    for col in ("Jobs Done", "Jobs Done Users"):
        v = num(cur.get(col))
        out += scaled(v)
        if prev:
            out += scaled(num(prev.get(col))) + change(pct(v, num(prev.get(col))))
    return out


def group_values(feats, groups, quarter, platform_jd):
    prev = shift(quarter, -1)
    out = []
    for g, names in groups.items():
        jd = sum(num(feats[n][quarter]["Jobs Done"]) for n in names)
        pjd = sum(num(feats[n].get(prev, {}).get("Jobs Done")) for n in names)
        out += scaled(jd) + scaled(pjd) + change(pct(jd, pjd)) + share(jd / platform_jd * 100)
    return out


def feature_values(feats, companies, name, group_jd, platform_jd, quarter):
    cur, prev = feats[name][quarter], feats[name].get(shift(quarter, -1))
    jd, us = num(cur["Jobs Done"]), num(cur["Jobs Done Users"])
    out = scaled(jd) + scaled(us) + share(jd / group_jd * 100) + share(jd / platform_jd * 100)
    if prev:
        pjd, pus = num(prev["Jobs Done"]), num(prev["Jobs Done Users"])
        out += scaled(pjd) + scaled(pus) + change(pct(jd, pjd)) + change(pct(us, pus))
        if us and pus:
            out += change(pct(jd / us, pjd / pus))
    top3 = 0.0
    for c in companies.get(name, []):
        cj = num(c["Jobs Done"])
        out += scaled(cj) + share(cj / jd * 100)
        if int(c["Rank"]) <= 3:
            top3 += cj
    out += share(top3 / jd * 100)    # "the top 3 companies complete half of it"
    return out


def check_highlights(text, data, quarter, failures):
    """The two highlight sections: 2 or 3 points each, both platforms, like for like."""
    prev = shift(quarter, -1)
    window = (f"{prev[:4]}-{3 * int(prev[-1]) - 2:02d}-01",
              f"{shift(quarter, 1)[:4]}-{3 * int(shift(quarter, 1)[-1]) - 2:02d}-01")
    plat_of = {"LumApps": "lumapps", "Beekeeper": "beekeeper"}
    weekly = {p: anomalies(p, quarter) for p in plat_of.values()}
    for title, want_up in ((GREW, True), (DECLINED, False)):
        if title not in text:
            failures.append(f"missing the '{title[4:]}' section")
            continue
        body = text.split(title, 1)[1]
        body = re.split(r"^#{2,3} |^Continue reading", body, maxsplit=1, flags=re.M)[0]
        points = [l for l in body.splitlines() if l.startswith("- ")]
        label = "highlights/" + ("grew" if want_up else "declined")
        if not 2 <= len(points) <= 3:
            failures.append(f"{label}: {len(points)} points, write 2 or 3")
        seen, candidates = set(), set()
        for plat in plat_of.values():
            totals, feats, _ = data[plat]
            for g, names in scope(feats, quarter).items():
                for n in names:
                    p = feats[n].get(prev)
                    q = pct(num(feats[n][quarter]["Jobs Done"]), num(p["Jobs Done"])) if p else None
                    if (q and (q > 0) == want_up and not comparison_caveat(n, *window)
                            and not anomaly_caveat(plat, n, weekly[plat].get(n))):
                        candidates.add(plat)
        for line in points:
            m = HIGHLIGHT.match(line)
            if not m:
                failures.append(f"{label}: write '- <emoji> **Feature** (Platform) +x.x% QoQ: ...', got {line[:60]!r}")
                continue
            emoji, name, platform, written = m.group(1), m.group(2).strip(), m.group(3), float(m.group(4))
            plat = plat_of[platform]
            totals, feats, companies = data[plat]
            groups = scope(feats, quarter)
            group = next((g for g, ns in groups.items() if name in ns), None)
            if not group:
                failures.append(f"{label}: {name} is not a live {platform} feature in {quarter}")
                continue
            seen.add(plat)
            if EMOJI.get(name) and emoji != EMOJI[name]:
                failures.append(f"{label}: {name} should use {EMOJI[name]}, not {emoji}")
            caveat = comparison_caveat(name, *window) or anomaly_caveat(plat, name, weekly[plat].get(name))
            if caveat:
                failures.append(f"{label}: {name} cannot be a highlight, its QoQ is not like for like ({caveat})")
            if (written > 0) != want_up:
                failures.append(f"{label}: {name} {written:+.1f}% belongs in the other section")
            group_jd = sum(num(feats[n][quarter]["Jobs Done"]) for n in groups[group])
            platform_jd = num(totals[quarter]["Jobs Done"])
            if num(feats[name][quarter]["Jobs Done"]) / group_jd * 100 < SMALL_SHARE and "% of " not in line:
                failures.append(f"{label}: {name} is under {SMALL_SHARE:.0f}% of {group}, say its share")
            check_numbers(line, platform_values(totals, quarter)
                          + group_values(feats, groups, quarter, platform_jd)
                          + feature_values(feats, companies, name, group_jd, platform_jd, quarter),
                          f"{label}/{name}", failures)
        for plat in sorted(candidates - seen):
            failures.append(f"{label}: no {plat} point, while it has candidates; mix both platforms")


def check_platform(plat, sec, data, quarter, failures):
    totals, feats, companies = data
    platform_jd = num(totals[quarter]["Jobs Done"])
    want = scope(feats, quarter)
    weekly = anomalies(plat, quarter)

    m = SCOPE.search(sec)
    if not m:
        failures.append(f"{plat}: missing the scope sentence 'Jobs Done covers <Domain> (<Feature>, ...)'")
    else:
        written = {d: {f.strip() for f in fs.split(",") if f.strip()}
                   for d, fs in SCOPE_GROUP.findall(m.group(1))}
        for d in sorted(set(want) | set(written)):
            miss, extra = set(want.get(d, [])) - written.get(d, set()), written.get(d, set()) - set(want.get(d, []))
            if miss:
                failures.append(f"{plat}: scope sentence misses {', '.join(sorted(miss))} ({d})")
            if extra:
                failures.append(f"{plat}: scope sentence lists {', '.join(sorted(extra))} ({d}), "
                                f"not tracked or not live in {quarter}")

    allowed = platform_values(totals, quarter) + group_values(feats, want, quarter, platform_jd)
    heads = list(GROUP.finditer(sec))
    check_numbers(sec[:heads[0].start()] if heads else sec, allowed, f"{plat}/intro", failures)

    seen_groups = [h.group(1) for h in heads]
    for g in want:
        if g not in seen_groups:
            failures.append(f"{plat}: no '### {g}' section")
    for g in seen_groups:
        if g not in want:
            failures.append(f"{plat}: '### {g}' is not a domain group of the {quarter} scope")

    for i, h in enumerate(heads):
        g = h.group(1)
        body = sec[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(sec)]
        body = body.split("*Full breakdown available")[0]
        names = want.get(g, [])
        group_jd = sum(num(feats[n][quarter]["Jobs Done"]) for n in names) or 1
        blocks = list(HEADING.finditer(body))
        check_numbers(body[:blocks[0].start()] if blocks else body, allowed, f"{plat}/{g}", failures)

        written = [b.group(3).strip() for b in blocks]
        for n in names:
            if n not in written:
                failures.append(f"{plat}/{g}: no block for {n}")
        for j, b in enumerate(blocks):
            arrow, emoji, name = b.group(1), b.group(2), b.group(3).strip()
            text = body[b.start():blocks[j + 1].start() if j + 1 < len(blocks) else len(body)]
            label = f"{plat}/{name}"
            if name not in names:
                failures.append(f"{label}: not a live feature of {g} in {quarter}")
                continue
            if EMOJI.get(name) and emoji != EMOJI[name]:
                failures.append(f"{label}: should use {EMOJI[name]}, not {emoji}")
            prev = feats[name].get(shift(quarter, -1))
            qoq = pct(num(feats[name][quarter]["Jobs Done"]), num(prev["Jobs Done"])) if prev else None
            if qoq is not None:
                direction = "flat" if round(qoq, 1) == 0 else ("up" if qoq > 0 else "down")
                if ARROWS[arrow] != direction:
                    failures.append(f"{label}: arrow {arrow} but Jobs Done moved {qoq:+.1f}% QoQ")
            for hit in re.finditer(YOY, text, re.I):
                failures.append(f"{label}: year-over-year in a feature block: {hit.group(0)!r}")
            odd = weekly.get(name)
            if odd and anomaly_caveat(plat, name, odd) and month_label(odd["week"]) not in text:
                failures.append(f"{label}: reviewed as misleading ({odd['kind']} in the week of "
                                f"{odd['week']}); its 💡 line must explain it and name "
                                f"{month_label(odd['week'])}")
            # name and slug together: two tenants can share a name ("Beekeeper")
            top = [f"{c['Company']} ({c['Slug']})" if c["Slug"] else c["Company"]
                   for c in companies.get(name, [])[:3]]
            positions = []
            for c in top:
                hit = re.search(rf"^\s*\d\.\s+{re.escape(c)}", text, re.M)
                positions.append(hit.start() if hit else -1)
            if top and -1 in positions:
                missing = [c for c, p in zip(top, positions) if p == -1]
                failures.append(f"{label}: top 3 companies should list {', '.join(missing)}")
            elif positions != sorted(positions):
                failures.append(f"{label}: top 3 companies are not in the script's order")
            if (not num(feats[name][quarter]["Jobs Done Users"])
                    and "- Users Completing Jobs: not tracked" not in text):
                failures.append(f"{label}: users are not tracked, write 'Users Completing Jobs: not tracked'")
            check_numbers(text, allowed + feature_values(feats, companies, name, group_jd,
                                                         platform_jd, quarter), label, failures)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_quarterly_article.py articles/quarterly_YYYY-QN.md")
    path = Path(sys.argv[1])
    if not path.exists():
        sys.exit(f"[check_quarterly] no such file: {path}")
    m = re.search(r"quarterly_(\d{4}-Q[1-4])\.md$", path.name)
    if not m:
        sys.exit(f"[check_quarterly] filename must be quarterly_YYYY-QN.md, got {path.name}")
    quarter = m.group(1)
    q_label, prev_label = f"Q{quarter[-1]} {quarter[:4]}", f"Q{shift(quarter, -1)[-1]} {shift(quarter, -1)[:4]}"
    text = path.read_text(encoding="utf-8")
    failures, warnings = [], []

    if not re.search(rf"^# Jobs Done - {q_label} Product Performance$", text, re.M):
        failures.append(f"title must read '# Jobs Done - {q_label} Product Performance'")
    opening = (f"Hi Team, here is how our key product usage KPI, Jobs Done, performed in "
               f"{q_label} across two platforms. Every change compares with {prev_label}.")
    for needle, what in [(opening, "standard opening")] + FIXED:
        if needle not in text:
            failures.append(f"missing {what}")
    # No MAU in the quarterly: "active users" would read as the whole active base.
    for hit in re.finditer(r"\bactive users?\b", text, re.I):
        failures.append(f"'{hit.group(0)}': the quarterly has no MAU, write 'Users Completing Jobs'")
    # the fixed section titles hold "the most", which is not a claim
    check_wording(text.replace(GREW, "").replace(DECLINED, ""), failures, warnings)

    data = {p: load(p, quarter) for p in ("lumapps", "beekeeper")}
    head = text.split("## LumApps")[0]
    overview, _, highlights = head.partition(GREW)
    check_highlights(GREW + highlights, data, quarter, failures) if highlights else \
        failures.append(f"missing the '{GREW[4:]}' section")
    body = text.split("## LumApps", 1)[1] if "## LumApps" in text else ""
    la, _, bk = body.partition("## Beekeeper")
    if not body or not bk:
        failures.append("the article needs a '## LumApps' then a '## Beekeeper' section")
    check_numbers(overview, platform_values(data["lumapps"][0], quarter)
                  + platform_values(data["beekeeper"][0], quarter), "overview", failures)
    for hit in re.finditer(YOY, overview, re.I):
        failures.append(f"overview: the quarterly compares QoQ only: {hit.group(0)!r}")
    for plat, sec in (("lumapps", la), ("beekeeper", bk)):
        if sec:
            check_platform(plat, sec, data[plat], quarter, failures)
    # No article passes while a step or a spike waits for a person's verdict.
    for plat in ("lumapps", "beekeeper"):
        live = {n for names in scope(data[plat][1], quarter).values() for n in names}
        for name, odd in anomalies(plat, quarter).items():
            if name in live and not anomaly_review(plat, name, odd):
                failures.append(f"{plat}/{name}: unreviewed {odd['kind']} ({odd['change']:+.0f}% "
                                f"in the week of {odd['week']}); investigate it, then record "
                                f"'misleading' or 'real' in ANOMALY_REVIEWS (jobs_done_common.py)")

    # Company directory issues found at fetch time: warnings, since the article's
    # figures are ranked on tenant_gid and stay right; they still must be reported.
    import prepare_quarterly
    for plat in ("lumapps", "beekeeper"):
        for w in prepare_quarterly.integrity_warnings(plat, quarter):
            warnings.append(f"company directory ({plat}): {w}")

    for p, hours in stale(sorted(READ)):
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
