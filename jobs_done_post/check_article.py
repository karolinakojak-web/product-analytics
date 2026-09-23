#!/usr/bin/env python3
"""Check a Jobs Done article against the data and the editorial rules.

    python3 check_article.py articles/article_2026-08.md

Two families of checks:

  NUMBERS  every figure in the article must trace back to the CSVs in data/.
           A figure written with an explicit sign must carry the sign the data
           has: the July 2026 issue stated Content at -0.5% MoM when it had in
           fact grown +0.5%, which is the class of error this catches.

  RULES    the editorial conventions recorded in CLAUDE.md. Deterministic, so
           they never depend on anyone remembering them.

Exit codes: 0 clean, 1 failures, 2 the article or its data could not be read.
Warnings never fail the run; they ask a human to confirm a judgement the script
cannot make on its own.
"""

import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

# Authoritative emoji per feature, mirroring the list in CLAUDE.md.
EMOJI = {
    "Content": "\U0001f4c4", "Chats": "\U0001f4ac", "Streams": "\U0001f4e1",
    "Spaces": "\U0001f3e0", "Posts": "\U0001f4dd", "Videos": "\U0001f3ac",
    "Reactions": "\U0001f44d", "Surveys": "\U0001f4ca", "Tasks": "☑️",
    "Shifts": "\U0001f4c5", "Forms": "\U0001f5c2️", "Shortcuts": "\U0001f517",
    "Campaigns": "\U0001f4e2", "Company Events": "\U0001f4c6", "Workflows": "⚙️",
    "Comments": "\U0001f5e8️", "Documents": "\U0001f4c1", "Referrals": "\U0001f91d",
    "Agents": "\U0001f916",
}

BANNED = [
    (r"—",                          "em dash"),
    (r"\brecover(ed|s|ing)?\b",          "recovery verb (needs 3+ months of context)"),
    (r"\bbounced? back\b",               "recovery verb"),
    (r"\brebound(ed|s|ing)?\b",          "recovery verb"),
    (r"\b(second-)?best (month|KPI)\b",  "superlative ranking over time"),
    (r"\bstrongest\b.{0,30}\b(of|in) \d{4}\b", "superlative ranking over time"),
    (r"\bhighest ever\b|\brecord (high|month)\b", "superlative ranking over time"),
    (r"\baccounts? for (almost |nearly )?(all|the entire)\b", "analyst phrasing"),
    (r"\bswing\b",                       "analyst vocabulary"),
    (r"\bcontribution\b",                "analyst vocabulary"),
    (r"\bpenetration\b",                 "analyst vocabulary"),
]

# Quantity words are claims. The script cannot judge them, so it surfaces them.
QUANTITY = r"\b(most|nearly all|almost all|half|the bulk of|a third|two thirds|majority)\b"

YOY = r"(YoY|year[- ]over[- ]year|last (January|February|March|April|May|June|July|August|September|October|November|December)|over twelve months|versus \w+ \d{4}|compared to \w+ \d{4})"

NUM = re.compile(r"(?<![\w.])([+-]?)(\d[\d,]*(?:\.\d+)?)\s*(M|K|%)")


def fail(msg):
    print(f"  KO  {msg}")


def num(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def pct(a, b):
    return None if not b else (a - b) / b * 100


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
        sys.exit(f"[check_article] no data for {platform} in {DATA_DIR}. Run: python3 prepare_data.py --fetch")
    allr, feat = {}, {}
    with open(a_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            allr[r["Calendar Month"]] = r
    with open(f_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            feat.setdefault(r["Feature"], {})[r["Calendar Month"]] = r
    return allr, feat


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


APPROX = re.compile(r"\b(about|roughly|around|nearly|almost|some|close to|just over|just under)\s*$", re.I)


def check_numbers(block, allowed, label, failures):
    """Every M/K/% figure in `block` must trace to `allowed`.

    A figure introduced by an approximation word ("about 70%") is matched with a
    tolerance, because rounding 69.6 to 70 is honest writing, not a wrong number.
    """
    signed = {(u, round(v, 1)) for u, v in allowed}
    mags = {(u, round(abs(v), 1)) for u, v in allowed} | {(u, round(abs(v), 2)) for u, v in allowed}
    for match in NUM.finditer(block):
        sign, raw, unit = match.groups()
        val = float(raw.replace(",", ""))
        if APPROX.search(block[max(0, match.start() - 14):match.start()]):
            tol = max(1.0, abs(val) * 0.02)
            if any(u == unit and abs(abs(v) - abs(val)) <= tol for u, v in allowed):
                continue
            failures.append(f"{label}: approximate '{raw}{unit}' is not close to any figure in the data")
            continue
        if sign:
            want = val if sign == "+" else -val
            if (unit, round(want, 1)) in signed:
                continue
            if (unit, round(-want, 1)) in signed:
                failures.append(f"{label}: '{sign}{raw}{unit}' has the wrong sign "
                                f"(the data says {-want:+.1f}{unit})")
                continue
            failures.append(f"{label}: '{sign}{raw}{unit}' matches no figure in the data")
        elif (unit, round(val, 1)) not in mags and (unit, round(val, 2)) not in mags:
            failures.append(f"{label}: '{raw}{unit}' matches no figure in the data")


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

    # ---- banned wording --------------------------------------------------
    for pattern, why in BANNED:
        for hit in re.finditer(pattern, text, re.I):
            failures.append(f"{why}: {hit.group(0)!r}")

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

    for hit in re.finditer(QUANTITY, text, re.I):
        warnings.append(f"quantity word {hit.group(0)!r} - confirm it against the figures")

    # ---- figures ---------------------------------------------------------
    la_all, la_feat = load("lumapps")
    bk_all, bk_feat = load("beekeeper")
    check_numbers(overview, platform_values(la_all, month) + platform_values(bk_all, month),
                  "overview", failures)
    for plat, sec, (allr, feat) in (("lumapps", sections.get("lumapps", ""), (la_all, la_feat)),
                                    ("beekeeper", sections.get("beekeeper", ""), (bk_all, bk_feat))):
        if not sec:
            continue
        allowed = platform_values(allr, month)
        for p in sec.split("\n\n"):
            fm = re.search(r"\*\*([A-Z][\w &]*?)\*\*", p)
            vals = feature_values(feat, fm.group(1), month, allr) if fm else None
            check_numbers(p, allowed + (vals or []), f"{plat}/{fm.group(1) if fm else 'intro'}",
                          failures)

    # ---- report ----------------------------------------------------------
    print(f"[check_article] {path.name} ({month})")
    for w in warnings:
        print(f"  !   {w}")
    for f in failures:
        fail(f)
    if failures:
        print(f"\n  {len(failures)} failure(s). Fix the article, or the data is stale: "
              f"python3 prepare_data.py --fetch")
        return 1
    print(f"  OK  no failures ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
