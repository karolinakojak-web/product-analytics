# Jobs Done: data and metrics

This folder produces the monthly and the quarterly Jobs Done articles. **To write one,
use its skill**: `/monthly-jobs-done-article` or `/quarterly-jobs-done-article`
(`.claude/skills/`). Each holds its step-by-step and its own rules; `writing-rules.md`
here holds the rules they share, and `jobs_done_common.py` the Looker config and
constants both scripts import. This file keeps what is true whatever you are doing here,
writing an article or changing the scripts: where the data comes from, what the metrics
mean, and how to read them.

---

## Automatic quality check

`check_article.py` verifies a written monthly article, `check_quarterly_article.py` a
quarterly one. A **Claude Code hook runs the right one on every save** of
`articles/article_*.md` or `articles/quarterly_*.md`, configured in `.claude/settings.json`
at the repo root. What follows describes the monthly check; the quarterly one adds the
shape of the article (one section per domain group, one block per feature, arrows, top 3
companies in order). Nothing
to remember and nothing to launch: write the article, the check runs, failures come back
as an error. It can also be run by hand:

```bash
python3 check_article.py articles/article_2026-08.md
```

**What it verifies**

| | |
|---|---|
| Figures | Every `M`, `K` and `%` in the article must trace back to the CSVs in `data/`. A figure written with an explicit sign must carry the sign the data has. A figure introduced by "about", "roughly" or "nearly" is matched with a tolerance. |
| Structure | Title shape, opening sentence, intro link, both dashboard links, all italicised where they should be. |
| Scope | Each platform's scope sentence lists exactly the domain groups and features tracked in the report month (from September 2026). |
| Wording | Em dashes, superlative rankings, recovery verbs, analyst vocabulary. |
| Selection | At most 3 feature paragraphs per platform, correct emoji per feature, no year-over-year inside a feature paragraph. |
| Warnings | Quantity words ("most", "half", "a third") are listed, never blocking. The script cannot judge them; a human confirms them against the figures. |

**What it cannot do**

- It only fires on writes made **by Claude**. Editing the article by hand in an editor
  triggers nothing, so run the command above after a manual edit.
- Warnings are not failures. The August 2026 issue shipped a wrong "most of July's drop"
  that only a human could catch, which is exactly why quantity words are surfaced.
- A failure can mean the data is stale rather than the article being wrong. Re-run
  `python3 prepare_data.py` before assuming the prose is at fault.
- If the hook seems not to run, open `/hooks` once or restart the session. It needs `jq`
  and `python3` on the PATH.

**One-time setup:** see `README.md` (dependencies and Looker API key).

**Options:**
- Every run fetches fresh CSVs from Looker; the checks refuse data more than 24 hours old.
  `--no-fetch` re-reads `data/` for work on the script only, never for an article.
- `--month 2026-04` target a specific report month. Defaults to the last complete calendar month.
- `--note "<text>"` pass editorial context for the month (a new feature, a known incident, an angle to take).

---

## Where the data comes from

Each run queries the Looker API directly. There is no manual CSV export step any more.

| Platform | LookML dashboard | Explore |
|---|---|---|
| LumApps | [`base::jobs_done`](https://bi.lumapps.com/dashboards/base%3A%3Ajobs_done) — defined in the `internal/bi` repo | `base` / `fct_jobs_done__bi` |
| Beekeeper | [`product_bi::jobs_done`](https://bi.lumapps.com/dashboards/product_bi%3A%3Ajobs_done) — defined in the `looker` repo | `product_bi` / `jobs_done` |

**The script never reads the dashboards.** It queries the explores directly, so a change
to a dashboard's layout does not affect it; a change to the explore or its dbt model does.

Both dashboards have four tabs. The script pulls the measures of three of them,
**Jobs Done**, **Users Completing Jobs** and **Frequency**. The fourth, *Month overview*,
is a one-month snapshot already contained in the 13-month series. Each tab is fetched at
two scopes (platform total, and broken down by domain group + feature), so 6 queries per
platform, plus one per scope for the AI & Search domain level (see *Data files*).

The data arrives in long format, one row per month × domain × feature. Since September
2026 the LumApps dashboard has no per-feature tiles any more: each tab shows the total,
and a single feature is viewed with the *Feature* filter. Its *Product Domain Group*
filter is required and defaults to Communication & Collaboration, so the default view
shows a lower LumApps total than the article, which covers every domain.

The *Users Completing Jobs* tab holds two measures (`active_users_28d`, MAU). Everything else on the tabs (`MoM %`, `Users Completing Jobs / MAU`) is a
Looker **table calculation**, computed at render time and never stored, so the script
recomputes those itself. MAU is carried down to feature grain, which is what gives the
UCJ/MAU reach figure per feature.

**Beekeeper carries tenant scoping that LumApps does not** — `account_selection =
commercial_all` and `jobs_done_version_param = 2026.1`. These are reproduced in
`LOOKER_PLATFORMS` in `prepare_data.py`. Removing them silently changes every number.

---

## Data files — structure and naming

All CSV files live in the `data/` subfolder, which is **gitignored** — these exports
carry customer-level data and are regenerated on demand.

| File pattern | Content |
|---|---|
| `lumapps_all_YYYY-MM.csv` | Lumapps platform totals: Jobs Done, Users Completing Jobs, MAU, Frequency |
| `beekeeper_all_YYYY-MM.csv` | Beekeeper platform totals: same columns |
| `lumapps_features_YYYY-MM.csv` | Lumapps breakdown by domain group × feature, incl. MAU |
| `beekeeper_features_YYYY-MM.csv` | Beekeeper breakdown by domain group × feature, incl. MAU |
| `lumapps_agents_YYYY-MM.csv` | LumApps Agents per agent: Jobs Done, users, tenants. Agent names are free text set by customers |

`data/raw/` holds the twelve per-tab responses (`<platform>_<tab>_<scope>_YYYY-MM.csv`) as an
audit trail. They are the Looker rows as returned, except that for AI & Search the
`product_domain` value is written in the feature column (see above). The `all` and
`features` files are merged from them and are what the analytics read; the agents file
comes from its own query.

**Lumapps scope:** the list of product domain groups is growing. Communication &
Collaboration was the only one for a long time; **AI & Search** was added to Jobs Done in
**September 2026** with two features, Search and Agents (earlier data is backfill), and
a third domain is on the way.

**AI & Search is read at product domain level.** In the explore, `feature` holds one row
per agent, named after the agent, and some names are customer names. `prepare_data.py`
fetches this group with `product_domain` in place of `feature`, so the data shows
`Agents`, `Search` and, once it has data, `Ask AI`. The per-agent rows are fetched
separately into `lumapps_agents_YYYY-MM.csv`, only for the experimental agent detail of the
article. The other groups keep `feature`: for Communication & Collaboration,
`product_domain` does not match the feature (Comments and Reactions span several domains).

Articles up to August 2026 carried a standing note saying LumApps Jobs Done covered only
Communication & Collaboration. **That note is retired** — it stopped being true. Do not
reinstate it. It is replaced by the scope sentence that opens each platform section
(see *Scope sentence* in `.claude/skills/monthly-jobs-done-article/references/writing-rules.md`), written from the script output every month.

**Beekeeper scope:** all four domain groups — Communication & Collaboration,
Work & Automation, Channels, People & Growth.

**Known quirk:** the Lumapps `all` file can contain noise rows (MAU = 0) — filtered automatically by the script.

**Workflows (Beekeeper):** Users Completing Jobs = 0 due to a technical tracking limitation. Jobs Done volume is valid; the users metric is not.

---

## Business context

Two separate products in one company:
- **Lumapps** — intranet and employee experience platform
- **Beekeeper** — frontline worker communication and operations platform

Both tracked independently with separate Looker dashboards. We publish one unified monthly article covering both.

---

## Jobs Done — concept and metrics

Jobs Done focuses on moments when a user **gets the core value** of a feature. Each feature is measured by exactly one key action.

| Metric | Definition | What it signals |
|---|---|---|
| **Jobs Done (Volume)** | Total events in the 28-day window | Feature traffic |
| **Users Completing Jobs (UCJ)** | Unique users who performed that action | Reach |
| **MAU** | Monthly Active Users (28-day average) | Total active user base |
| **UCJ / MAU** | UCJ as % of MAU | Penetration across the active base |
| **Frequency** | Volume / UCJ | Engagement depth per user |

**Time methodology:** monthly = last 28 days ending on the last day of the calendar month. MoM and YoY use the same window.

**Trend classification** (from 12-month MoM series):
- `growing` — avg MoM ≥ +3%
- `declining` — avg MoM ≤ -3%
- `stable` — avg MoM between -3% and +3%, low variance
- `volatile` — high variance regardless of direction

---

## Interpretation guidance
- **Volume up + Users up** → growing reach
- **Volume up + Users flat** → existing users engage more (frequency rising)
- **Volume up + Users down** → fewer people doing more — intensity signal
- **Volume down + Frequency flat** → reach problem (fewer users, same depth per user)
- **Volume down + Frequency down** → most concerning — users leaving and disengaging
- **UCJ/MAU > 85%** → the tracked action is performed by most of the active user base
- **UCJ/MAU < 30%** → the tracked action reaches a small share of active users

  Both read as adoption of the **one action Jobs Done measures**, not of the feature as a
  whole. Do not turn them into "widely adopted" or "niche feature" in the article.

---

## Known permanent data limitations

- **Customer-level breakdowns** are only fetched for the quarterly top 3 companies
  (`data/quarterly/<platform>_companies_*.csv`).
- **Never sum Jobs Done through the LumApps company join.** Grouping
  `fct_jobs_done__bi` by a `dim_lumapps_x_sf_organizations` field inflates the sums: in
  Q2 2026 it doubled a large customer's Videos Jobs Done, and inflated LumApps' whole
  quarter by +78% (687.9M against 385.8M). The join is declared `many_to_one` but the
  table holds several rows per organization (one per Salesforce platform, since
  23 September 2026; a fix was merged on 28 September). `prepare_quarterly.py` ranks on
  `tenant_gid` and only then looks the names up, so its figures stay right either way,
  and it measures the problem on every fetch: the join total must equal the plain total,
  and a tenant with no name that would have made a top 3 is reported. Both surface as
  *COMPANY DIRECTORY ISSUES* and as warnings in the check. Company names come from
  `dim_lumapps_x_sf_organizations` only, never `dim_organizations`.
- **Users and MAU cannot be summed across domain groups.** They count *unique* users, so a
  user active in two domains is counted once at platform level but twice if the rows are
  added up. This is why the `all` files have no domain column: platform totals are queried
  at platform grain. Only Jobs Done volume is safely additive.
- **Historical figures can be revised.** The Beekeeper total published for April 2026
  (32.9M) no longer reproduces — the explore now returns 34.3M for that month. Do not
  restate an old month from memory; re-read it from the current output.
- **Workflows (Beekeeper) users metric** always 0 — do not report it. Volume is valid.
- **Workflows (Beekeeper) spiked at the end of February 2026**: the weeks of 23 February
  and 2 March hold about three times the usual weekly Jobs Done, 98% of it from a single
  customer. It inflates Q1 2026, so Q2 2026 reads as a -13.5% drop while the
  usual weekly level rose. `prepare_quarterly.py` detects such steps and spikes (see
  `weekly_anomaly` in `jobs_done_common.py`) and names the companies behind them.
- **Search counts suggestion clicks only from 6 August 2026.** A Search Job Done is a
  search session with at least one click, and `SearchClickSuggestionAction` first appears
  in `fct_user_actions` on that day (checked in `hm-prod-go-cell-001`: 690,608 events in
  64 organizations by the end of August, none before). Search Jobs Done stepped from
  about 530K to about 930K a week at that point, while result clicks stayed flat. Any
  comparison across that date (August 2026 MoM, Q3 2026 QoQ) mostly measures the new
  event, not more searching: say so rather than reading it as growth.
- **MAU** comes from the `_all_` files. If those files are missing, note MAU is unavailable.

---
