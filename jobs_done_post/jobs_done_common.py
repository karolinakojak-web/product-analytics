"""What the monthly and quarterly Jobs Done articles share.

    Looker    where each platform's data lives and how to query it
    Features  the authoritative emoji per feature, and go-live months
    Checks    the wording rules and the figure matching both article checks use

The writing rules these constants enforce live in
jobs_done_post/writing-rules.md.
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Looker
# ---------------------------------------------------------------------------
# Credentials come from the standard Looker SDK environment variables:
#   LOOKERSDK_BASE_URL / LOOKERSDK_CLIENT_ID / LOOKERSDK_CLIENT_SECRET
#
# `filters` holds only the scoping every query needs. Each script adds its own
# time frame and day selection on top.

LOOKER_PLATFORMS = {
    "lumapps": {
        "dashboard": "base::jobs_done",
        "model": "base",
        "view": "fct_jobs_done__bi",
        "prefix": "fct_jobs_done__bi",
        "mau_field": "fct_user_metrics__bi.total_mau",
        "daily_jd_field": "fct_jobs_done__bi.jobs_done_count",
        # Company names come from the Salesforce-matched directory only, never
        # dim_organizations, which also lists internal and non-customer orgs.
        "company_fields": ["dim_lumapps_x_sf_organizations.lumapps_name",
                           "dim_lumapps_x_sf_organizations.slug"],
        "filters": {},
        # AI & Search puts the agent's name in `feature`, one row per agent, and
        # some of those names are customer names. The article stays at product
        # domain level there (Agents, Search, Ask AI), so these groups are fetched
        # with product_domain standing in for feature. A separate query rather than
        # a sum over agents, since users do not add up across them.
        "domain_level_groups": ["AI & Search"],
        # The one domain the monthly article also looks at per agent (experimental,
        # from September 2026). Kept in its own file so the feature data stays at
        # domain level.
        "per_agent_domain": "Agents",
    },
    "beekeeper": {
        "dashboard": "product_bi::jobs_done",
        "model": "product_bi",
        "view": "jobs_done",
        "prefix": "jobs_done",
        "mau_field": "user_metrics.mau",
        "daily_jd_field": "jobs_done.jobs_done",
        "company_fields": ["tenants.name", "tenants.subdomain"],
        # Beekeeper tiles carry tenant scoping that LumApps does not have.
        # Dropping these would silently change every number. The tab tiles leave
        # tenants.is_customer empty, so we do too.
        "filters": {
            "jobs_done.jobs_done_version_param": "2026.1",
            "tenants.account_selection": "commercial^_all",
        },
    },
}


def looker_sdk_or_exit():
    """An authenticated Looker SDK, or a clear exit when it cannot be built."""
    try:
        import looker_sdk
    except ImportError:
        sys.exit("Error: looker-sdk is not installed.  pip install -r requirements.txt")
    for var in ("LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET"):
        if not os.environ.get(var):
            sys.exit(f"Error: {var} is not set. See .env.example.")
    print(f"[looker] {os.environ['LOOKERSDK_BASE_URL']}", file=sys.stderr)
    return looker_sdk.init40()


def run_query(sdk, cfg: dict, dims: list[str], measures: list[str],
              filters: dict, limit: str = "5000") -> list[dict]:
    """Run one unpivoted inline query and return its JSON rows.

    Sorted on the first dimension descending (the period), then the others.
    """
    from looker_sdk import models40

    query = models40.WriteQuery(
        model=cfg["model"],
        view=cfg["view"],
        fields=dims + measures,
        filters={**cfg["filters"], **filters},
        sorts=[f"{dims[0]} desc"] + dims[1:],
        limit=limit,
    )
    return json.loads(sdk.run_inline_query(result_format="json", body=query))


def run_features(sdk, cfg: dict, period_dim: str, measures: list[str], filters: dict,
                 extra_dims: tuple = (), limit: str = "5000") -> list[dict]:
    """Breakdown by domain group x feature, with product_domain as the feature for
    domain-level groups.

    Rows come back keyed on <prefix>.feature either way, so the caller never
    sees the difference.
    """
    p = cfg["prefix"]
    group, feature, domain = (f"{p}.product_domain_group", f"{p}.feature",
                              f"{p}.product_domain")
    extra = list(extra_dims)
    groups = cfg.get("domain_level_groups", [])
    if not groups:
        return run_query(sdk, cfg, [period_dim, group, feature] + extra, measures,
                         filters, limit)

    rows = run_query(sdk, cfg, [period_dim, group, feature] + extra, measures,
                     {**filters, group: ",".join(f"-{g}" for g in groups)}, limit)
    for r in run_query(sdk, cfg, [period_dim, group, domain] + extra, measures,
                       {**filters, group: ",".join(groups)}, limit):
        r[feature] = r.pop(domain)
        rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

# Authoritative emoji per feature, mirroring the list in the shared writing rules.
EMOJI = {
    "Content": "\U0001f4c4", "Chats": "\U0001f4ac", "Streams": "\U0001f4e1",
    "Spaces": "\U0001f3e0", "Posts": "\U0001f4dd", "Videos": "\U0001f3ac",
    "Reactions": "\U0001f44d", "Surveys": "\U0001f4ca", "Tasks": "☑️",
    "Shifts": "\U0001f4c5", "Forms": "\U0001f5c2️", "Shortcuts": "\U0001f517",
    "Campaigns": "\U0001f4e2", "Company Events": "\U0001f4c6", "Workflows": "⚙️",
    "Comments": "\U0001f5e8️", "Documents": "\U0001f4c1", "Referrals": "\U0001f91d",
    "Agents": "\U0001f916", "Search": "\U0001f50d",
}

# Features whose data is backfilled before they joined Jobs Done. They stay out of
# the scope sentence, and out of the article, until their go-live month. A quarter
# includes a feature whose go-live month falls inside it.
GO_LIVE = {"Agents": "2026-09", "Search": "2026-09"}

# Tenants left out of the quarterly article, by platform, as {tenant_gid: reason}.
# Empty: every customer is kept. The LumApps internal tenant (5769928858664960) was
# excluded for a while, then kept on 8 October 2026 pending a decision with Karolina.
QUARTERLY_EXCLUDED_TENANTS: dict = {}


def without_excluded_tenants(platform, cfg, excluded):
    """cfg with a filter that leaves out the platform's excluded tenants."""
    ids = excluded.get(platform, {})
    if not ids:
        return cfg
    return {**cfg, "filters": {**cfg["filters"],
                               f"{cfg['prefix']}.tenant_gid": ",".join(f"-{t}" for t in ids)}}

# Under this share of its domain group's Jobs Done, a feature is small: its moves are
# large in % and tiny in volume, so a highlight quoting it must say its share.
SMALL_SHARE = 1.0

# Days on which what a feature counts changed. A comparison across that day measures
# the change, not usage. See "Known permanent data limitations" in CLAUDE.md.
TRACKING_CHANGES = {
    "Search": ("2026-08-06", "clicks on search suggestions are counted from this day"),
}


# Two shapes in a feature's weekly Jobs Done make its QoQ misleading:
#   step   a jump to a new level that stays, as Search did when suggestion clicks
#          started being counted (6 August 2026). Median of the STEP_WEEKS weeks
#          before a week against the median of the STEP_WEEKS weeks from it: medians
#          over six weeks, so a one- or two-week spike does not read as a step.
#   spike  a single week far off its neighbours, as Workflows in the weeks of
#          23 February and 2 March 2026 (about three times its usual level), which
#          inflated Q1 and made Q2 look like a drop.
STEP_WEEKS = 6
STEP_MIN_CHANGE = 40.0      # % between the two medians
SPIKE_NEIGHBOURS = 4        # weeks on each side
SPIKE_RATIO = 2.0           # a week at least twice, or at most half, its neighbours
MIN_WEEKLY = 5_000          # Jobs Done a week; below, a doubling is a few thousand
                            # jobs, noise for the article (Agents at 1-5K in Q3 2026)

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def month_label(ym):
    """'2026-08' or '2026-08-10' as 'August 2026'."""
    return f"{MONTHS[int(ym[5:7]) - 1]} {ym[:4]}"


def weekly_anomaly(weekly):
    """A step or a spike in [(week 'YYYY-MM-DD', jobs done)], or None.

    The first and last weeks are dropped: the fetch window cuts them, so they are
    partial. A step wins over a spike. Returns {"kind", "week", "change"}, `change`
    in % against the usual level.
    """
    from statistics import median

    pairs = sorted(weekly)[1:-1]
    weeks, series = [w for w, _ in pairs], [v for _, v in pairs]
    step = None
    for i in range(STEP_WEEKS, len(series) - STEP_WEEKS + 1):
        before, after = median(series[i - STEP_WEEKS:i]), median(series[i:i + STEP_WEEKS])
        if min(before, after) < MIN_WEEKLY:
            continue
        change = (after - before) / before * 100
        if abs(change) >= STEP_MIN_CHANGE and (step is None or abs(change) > abs(step["change"])):
            step = {"kind": "step", "week": weeks[i], "change": change}
    if step:
        return step
    spike = None
    for i, v in enumerate(series):
        around = series[max(0, i - SPIKE_NEIGHBOURS):i] + series[i + 1:i + 1 + SPIKE_NEIGHBOURS]
        if len(around) < SPIKE_NEIGHBOURS:
            continue
        usual = median(around)
        if usual < MIN_WEEKLY:
            continue
        if v >= usual * SPIKE_RATIO or v <= usual / SPIKE_RATIO:
            change = (v - usual) / usual * 100
            if spike is None or abs(change) > abs(spike["change"]):
                spike = {"kind": "spike", "week": weeks[i], "change": change}
    return spike


def comparison_caveat(feature, prev_start, end):
    """Why comparing [prev_start, end) with the period before is not like for like.

    Dates are 'YYYY-MM-DD', `end` exclusive; `prev_start` opens the earlier period.
    Returns None when the comparison is sound.
    """
    go = GO_LIVE.get(feature)
    if go and prev_start[:7] < go < end[:7]:
        return f"joined Jobs Done in {go}: the earlier period is backfill"
    change = TRACKING_CHANGES.get(feature)
    if change and prev_start < change[0] < end:
        return f"tracking change on {change[0]}: {change[1]}"
    return None


# Every step or spike the detection finds is reviewed by a person before an article
# uses it, and the verdict is recorded here, keyed on (platform, feature, week):
#   "misleading"  the QoQ does not measure usage: the feature is set aside from the
#                 highlights, and its 💡 line must explain the anomaly with its month
#   "real"        a genuine change in usage: the feature stays a normal candidate
# The detection never decides on its own; an unreviewed anomaly fails the check.
ANOMALY_REVIEWS = {
    ("beekeeper", "Workflows", "2026-02-23"): (
        "misleading", "two weeks at about three times the usual level, 98% from a single "
                      "customer; inflates Q1 2026"),
    ("lumapps", "Search", "2026-08-10"): (
        "misleading", "suggestion clicks counted from 6 August 2026, spread over many "
                      "companies (see TRACKING_CHANGES)"),
}


def anomaly_review(platform, feature, anomaly):
    """(verdict, reason) recorded for this anomaly, or None while it is unreviewed."""
    return ANOMALY_REVIEWS.get((platform, feature, anomaly["week"])) if anomaly else None


def anomaly_caveat(platform, feature, anomaly):
    """Why a reviewed-misleading anomaly sets the feature aside, or None."""
    review = anomaly_review(platform, feature, anomaly)
    if review and review[0] == "misleading":
        return f"reviewed {anomaly['kind']} in the week of {anomaly['week']}: {review[1]}"
    return None


# ---------------------------------------------------------------------------
# Data volume
# ---------------------------------------------------------------------------
# A broken pipeline can leave every check above green: in September 2026 an
# incremental-filter change (dataplatform PR #1503) overwrote LumApps daily Jobs
# Done with a few hours of each day, from 20 September, and the articles' figures
# still traced to the data. These checks look at the data itself, day by day,
# before an article is written. They never decide: an alert waits for a person's
# verdict in VOLUME_REVIEWS, and both article checks fail until then.

# What a day is split by: LumApps runs on separate cells that break separately.
VOLUME_UNIT_DIM = {"lumapps": "haussmann_cell", "beekeeper": None}
VOLUME_BASELINE_WEEKS = 4      # same weekday, the 4 weeks before
VOLUME_LOW, VOLUME_HIGH = 0.5, 2.0
VOLUME_MIN_BASELINE = 50_000   # Jobs Done a day; a smaller unit is noise
VOLUME_EPISODE_GAP = 3         # alert days at most this far apart form one episode
WINDOW_GAP_DRIFT = 0.5         # points of % (see window_alerts)

# Verdicts on volume alerts, keyed on (platform, unit, first day of the episode):
#   "expected"  a real dip or peak (a public holiday): nothing to do
#   "incident"  the data is wrong: the article opens on a "*Data warning: ...*" line
VOLUME_REVIEWS = {
    # public holidays
    ("lumapps", "hm-prod-go-cell-003", "2026-04-06"): ("expected", "Easter Monday"),
    ("lumapps", "hm-prod-go-cell-005", "2026-04-06"): ("expected", "Easter Monday"),
    ("lumapps", "hm-prod-ms-cell-001", "2026-04-06"): ("expected", "Easter Monday"),
    ("lumapps", "hm-prod-go-cell-003", "2026-05-01"): ("expected", "Labour Day, 1 May"),
    ("lumapps", "hm-prod-go-cell-005", "2026-05-01"): ("expected", "Labour Day, 1 May"),
    ("lumapps", "hm-prod-go-cell-600", "2026-05-01"): ("expected", "Labour Day, 1 May"),
    ("lumapps", "hm-prod-ms-cell-001", "2026-05-01"): ("expected", "Labour Day, 1 May"),
    ("lumapps", "hm-prod-go-cell-003", "2026-05-14"): ("expected", "Ascension Day"),
    ("lumapps", "hm-prod-go-cell-002", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    ("lumapps", "hm-prod-go-cell-003", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    ("lumapps", "hm-prod-go-cell-005", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    ("lumapps", "hm-prod-go-cell-600", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    ("lumapps", "hm-prod-ms-cell-001", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    ("lumapps", "hm-prod-go-cell-003", "2026-07-14"): ("expected", "Bastille Day, French public holiday"),
    ("lumapps", "hm-prod-go-cell-002", "2026-09-07"): ("expected", "Labor Day, US public holiday"),
    ("beekeeper", "all", "2026-05-25"): ("expected", "Whit Monday in Europe, Memorial Day in the US"),
    # fct_jobs_done_1d overwritten with partial days since dataplatform PR #1503
    # (merged 22 September 2026); a fix is under way
    ("lumapps", "hm-prod-ms-cell-001", "2026-09-20"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-ms-cell-002", "2026-09-20"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-go-cell-600", "2026-09-21"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-go-cell-001", "2026-09-26"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-go-cell-002", "2026-09-26"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-go-cell-003", "2026-09-26"): ("incident", "partial days after dataplatform PR #1503"),
    ("lumapps", "hm-prod-go-cell-005", "2026-09-26"): ("incident", "partial days after dataplatform PR #1503"),
}


def fetch_daily_volume(sdk, platform, cfg, first, end):
    """Daily Jobs Done per unit (cell, or the whole platform) from `first` to `end`
    (dates, `end` excluded): [{"Day", "Unit", "Jobs Done"}]."""
    p, jd = cfg["prefix"], cfg["daily_jd_field"]
    unit = VOLUME_UNIT_DIM.get(platform)
    dims = [f"{p}.calendar_date"] + ([f"{p}.{unit}"] if unit else [])
    rows = run_query(sdk, cfg, dims, [jd], {
        f"{p}.calendar_date": f"{first:%Y/%m/%d} to {end:%Y/%m/%d}",
        f"{p}.day_selection": "any^_day"}, limit="50000")
    return [{"Day": r[f"{p}.calendar_date"], "Unit": (r.get(f"{p}.{unit}") if unit else "all") or "none",
             "Jobs Done": r[jd] or 0} for r in rows]


def volume_episodes(platform, rows, period_start, period_end):
    """Alert episodes in [period_start, period_end] (dates, both included).

    Each day is compared with the median of the same weekday over the
    VOLUME_BASELINE_WEEKS weeks before it. A day under VOLUME_LOW or over
    VOLUME_HIGH times that baseline is an alert; alert days of one unit close
    together form an episode, reviewed once.
    """
    import datetime as dt
    from statistics import median

    series = {}
    for r in rows:
        series.setdefault(r["Unit"], {})[dt.date.fromisoformat(r["Day"])] = num(r["Jobs Done"])
    episodes = []
    for unit, s in sorted(series.items()):
        alerts, day = [], period_start
        while day <= period_end:
            ref = [s[day - dt.timedelta(weeks=k)] for k in range(1, VOLUME_BASELINE_WEEKS + 1)
                   if day - dt.timedelta(weeks=k) in s]
            if len(ref) >= VOLUME_BASELINE_WEEKS - 1:
                base, value = median(ref), s.get(day, 0)
                if base >= VOLUME_MIN_BASELINE and not VOLUME_LOW <= value / base <= VOLUME_HIGH:
                    alerts.append((day, value, base))
            day += dt.timedelta(days=1)
        for a in alerts:
            if episodes and episodes[-1]["unit"] == unit and (a[0] - episodes[-1]["last"]).days <= VOLUME_EPISODE_GAP:
                episodes[-1]["days"].append(a)
                episodes[-1]["last"] = a[0]
            else:
                episodes.append({"platform": platform, "unit": unit, "first": a[0], "last": a[0], "days": [a]})
    for e in episodes:
        e["review"] = VOLUME_REVIEWS.get((platform, e["unit"], f"{e['first']:%Y-%m-%d}"))
    return episodes


def window_alerts(platform, rows):
    """The 28-day window against the sum of its 28 daily values, at month ends.

    rows: [{"Day", "Window", "Daily sum"}], the report month end last. For LumApps
    the window runs about 2% above the daily sum even in healthy months (seen in
    July and August 2026), so the check alerts on a drift of that gap, not on
    the gap itself: more than WINDOW_GAP_DRIFT points from the earlier month ends.
    """
    from statistics import median

    gaps = [(r["Day"], pct(num(r["Window"]), num(r["Daily sum"]))) for r in rows]
    gaps = [(d, g) for d, g in gaps if g is not None]
    if len(gaps) < 2:
        return []
    day, gap = gaps[-1]
    usual = median(g for _, g in gaps[:-1])
    if abs(gap - usual) <= WINDOW_GAP_DRIFT:
        return []
    review = VOLUME_REVIEWS.get((platform, "28-day window", day))
    return [{"platform": platform, "unit": "28-day window", "first": day, "gap": gap,
             "usual": usual, "review": review}]


def describe_volume_alert(e):
    """One line for an episode or a window alert."""
    if e["unit"] == "28-day window":
        return (f"{e['platform']} 28-day window on {e['first']}: {e['gap']:+.1f}% against the sum of its "
                f"daily values, usually {e['usual']:+.1f}%")
    worst = max(e["days"], key=lambda d: abs(d[1] / d[2] - 1))
    return (f"{e['platform']} {e['unit']}: {len(e['days'])} day(s) from {e['first']:%d %b} to "
            f"{e['last']:%d %b %Y}, e.g. {worst[0]:%a %d %b}: {worst[1]:,.0f} Jobs Done against "
            f"{worst[2]:,.0f} usually ({worst[1] / worst[2] * 100:.0f}%)")


VOLUME_HEADERS = ["Day", "Unit", "Jobs Done"]


def read_volume_episodes(platform, path, period_start, period_end):
    """volume_episodes on a daily volume CSV; a missing file is itself an alert."""
    import csv
    from pathlib import Path

    if not Path(path).exists():
        return None
    with open(path, newline="", encoding="utf-8") as f:
        return volume_episodes(platform, list(csv.DictReader(f)), period_start, period_end)


def print_volume_alerts(episodes):
    """The DATA VOLUME ALERTS block, with the verdicts on record."""
    if not episodes:
        return
    open_ = [e for e in episodes if not e["review"]]
    print(f"\n{'!' * 80}\n⚠️  DATA VOLUME ALERTS ({len(episodes)}, {len(open_)} not reviewed)\n{'!' * 80}")
    print("  Days far from the usual volume of the same weekday. A holiday explains some;\n"
          "  a broken pipeline explains others. The script does not decide: investigate each\n"
          "  new one with the analyst, then record the verdict in VOLUME_REVIEWS in\n"
          "  jobs_done_common.py. The article check fails until then.")
    for e in episodes:
        state = (f"{e['review'][0]}: {e['review'][1]}" if e["review"] else "⚠️ NOT REVIEWED")
        print(f"\n  {describe_volume_alert(e)}\n    → {state}")
        if not e["review"]:
            print(f'    record: ("{e["platform"]}", "{e["unit"]}", "{str(e["first"])[:10]}"): '
                  f'("expected" or "incident", "<what the investigation found>")')
    if open_:
        sys.stdout.flush()
        print(f"\n⚠️ {len(open_)} data volume alert(s) to review before writing: see above.",
              file=sys.stderr)


DATA_WARNING = re.compile(r"^\*Data warning: .+\*$", re.M)


def check_volume(episodes, text, failures):
    """No unreviewed alert; an incident must be announced at the top of the article."""
    for e in episodes:
        if not e["review"]:
            key = f'("{e["platform"]}", "{e["unit"]}", "{str(e["first"])[:10]}")'
            failures.append(f"unreviewed data volume alert: {describe_volume_alert(e)}. Investigate, then record "
                            f"{key}: (\"expected\" or \"incident\", \"<why>\") in VOLUME_REVIEWS")
    if any(e["review"] and e["review"][0] == "incident" for e in episodes) and not DATA_WARNING.search(text):
        failures.append("a data incident is recorded for this period: open the article on a "
                        "'*Data warning: ...*' line")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

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
    # Jobs Done covers one action on a subset of features, so these phrasings claim
    # more than the data supports. See "Claims must stay inside the metric".
    (r"\b(biggest|largest|most[- ]used) feature\b",
     "platform-wide ranking; write 'the largest of the features we track'"),
    (r"\bused by \*{0,2}\d",
     "'used by X%' implies general feature usage; write 'X% of active users completed a <feature> job'"),
]

# Quantity words are claims. The script cannot judge them, so it surfaces them.
# "a third quarter in a row" is an ordinal, not a share.
QUANTITY = r"\b(most|nearly all|almost all|half|the bulk of|a third(?! quarter)|two thirds|majority)\b"

YOY = r"(YoY|year[- ]over[- ]year|last (January|February|March|April|May|June|July|August|September|October|November|December)|over twelve months|versus \w+ \d{4}|compared to \w+ \d{4})"

# The unit must end the token: "2 March" is a date, not 2M.
NUM = re.compile(r"(?<![\w.])([+-]?)(\d[\d,]*(?:\.\d+)?)\s*(M|K|%)(?![A-Za-z])")

# Each platform section opens on a sentence listing what Jobs Done covers:
#   Jobs Done covers <Domain> (<Feature>, <Feature>) and <Domain> (<Feature>).
SCOPE = re.compile(r"^Jobs Done covers (.+)$", re.M)
SCOPE_GROUP = re.compile(r"([A-Z][\w &]*?) \(([^)]*)\)")

APPROX = re.compile(r"\b(about|roughly|around|nearly|almost|some|close to|just over|just under)\s*$", re.I)


# Every article is written, and checked, on data fetched fresh from Looker: history is
# revised from one month to the next, and upstream fixes land between two runs.
FRESH_HOURS = 24


def stale(paths):
    """[(path, age in hours)] for the data files fetched more than FRESH_HOURS ago."""
    import time
    now = time.time()
    ages = [(p, (now - p.stat().st_mtime) / 3600) for p in paths]
    return [(p, h) for p, h in ages if h > FRESH_HOURS]


def fmt_change(v):
    """A % change as the article writes it.

    One decimal, except near zero, where one decimal would print "-0.0%": two decimals
    under 0.05%, and "flat" when even two decimals round to zero (Beekeeper users in
    Q3 2026 moved by -0.033%, Forms users by -0.003%).
    """
    if v is None:
        return "n/a"
    if abs(v) >= 0.05:
        return f"{v:+.1f}%"
    if round(v, 2) != 0:
        return f"{v:+.2f}%"
    return "flat"


def num(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def pct(a, b):
    return None if not b else (a - b) / b * 100


def check_numbers(block, allowed, label, failures):
    """Every M/K/% figure in `block` must trace to `allowed`.

    A figure introduced by an approximation word ("about 70%") is matched with a
    tolerance, because rounding 69.6 to 70 is honest writing, not a wrong number.

    `allowed` holds (unit, value) pairs, or (unit, value, is_change) triples. A figure
    written with a sign only matches a change: a +2.5% must not pass because some
    share happens to be 2.5%. Pairs count as changes, which keeps the monthly check
    as it was.
    """
    changes = [(a[0], a[1]) for a in allowed if len(a) == 2 or a[2]]
    signed = {(u, round(v, 1)) for u, v in changes}
    signed2 = {(u, round(v, 2)) for u, v in changes}    # "-0.03%" is checked at 2 decimals
    allowed = [(a[0], a[1]) for a in allowed]
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
            places = len(raw.split(".")[1]) if "." in raw else 0
            pool, nd = (signed2, 2) if places >= 2 else (signed, 1)
            if (unit, round(want, nd)) in pool:
                continue
            if (unit, round(-want, nd)) in pool:
                failures.append(f"{label}: '{sign}{raw}{unit}' has the wrong sign "
                                f"(the data says {-want:+.{nd}f}{unit})")
                continue
            failures.append(f"{label}: '{sign}{raw}{unit}' matches no figure in the data")
        elif (unit, round(val, 1)) not in mags and (unit, round(val, 2)) not in mags:
            failures.append(f"{label}: '{raw}{unit}' matches no figure in the data")


def check_wording(text, failures, warnings):
    """Banned wording fails; quantity words are surfaced for a human to confirm."""
    for pattern, why in BANNED:
        for hit in re.finditer(pattern, text, re.I):
            failures.append(f"{why}: {hit.group(0)!r}")
    for hit in re.finditer(QUANTITY, text, re.I):
        warnings.append(f"quantity word {hit.group(0)!r} - confirm it against the figures")
    # "+0.0%" or "-0.0%" hides a real, tiny move: write two decimals, or "flat".
    for hit in re.finditer(r"[+-]0\.0%", text):
        failures.append(f"'{hit.group(0)}': write a change under 0.05% with two decimals, or "
                        f"'flat' when it rounds to 0.00%")
