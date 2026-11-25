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
quarterly one. The article is written as a Markdown draft in `data/drafts/` (gitignored),
and only its HTML rendering in `articles/` is the deliverable. A **Claude Code hook runs
the right check on every save** of `data/drafts/article_*.md` or
`data/drafts/quarterly_*.md`, configured in `.claude/settings.json` at the repo root.
What follows describes the monthly check; the quarterly one adds the shape of the
article (two highlight lists, one block per domain group, one line per feature in size
order, the group's biggest movers by company as the script prints them). Once a check
passes, the hook renders the article as HTML: `render_monthly_html.py` for a monthly
one, `render_quarterly_html.py` for a quarterly one. Nothing to remember and nothing to
launch: write the article, the check runs, failures come back as an error. It can also
be run by hand:

```bash
python3 check_article.py data/drafts/article_2026-10.md
```

**What it verifies**

| | |
|---|---|
| Overview | The five KPI lines are the ones the script prints, to the digit: they are the figures of the dashboard's Overview tab. |
| Figures | Every other `M`, `K` and `%` in the article must trace back to the CSVs in `data/`. A figure written with an explicit sign must carry the sign the data has. A figure introduced by "about", "roughly" or "nearly" is matched with a tolerance. |
| Structure | Title shape, opening sentence, intro link, the dashboard line, all italicised where they should be. |
| Scope | The scope sentence lists exactly the domain groups and features tracked in the report month. |
| Wording | Em dashes, superlative rankings, recovery verbs, analyst vocabulary, year-over-year. |
| Selection | Exactly 5 feature paragraphs, correct emoji per feature. |
| Data volume | No daily volume alert left without a verdict in `VOLUME_REVIEWS`, and a `*Data warning: ...*` line when an incident is on record (see *Data volume checks* in `README.md`). |
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

Each run queries the Looker API directly. Since November 2026 one dashboard and one
explore cover LumApps and Beekeeper together, and **they are the source of truth for
both articles**:

| | |
|---|---|
| Dashboard | [`product_bi::platform_jobs_done`](https://bi.lumapps.com/dashboards/product_bi::platform_jobs_done), defined in the `looker` repo (PR #1232) |
| Explore | `product_bi` / `jobs_done` (view `facts_jobs_done_events_agg`, ClickHouse table `agg_jobs_done`) |

The articles report **both platforms combined**: no LumApps or Beekeeper figure, and no
share of one platform, appears in them. Articles up to October 2026 read two other
explores, one per platform (`base::fct_jobs_done__bi` for LumApps), over other windows.
The consolidated explore is a fresh baseline: its figures are not compared with those.

**The script never reads the dashboard.** It queries the explore with the scoping every
tile of the dashboard carries, reproduced in `LOOKER["filters"]` in
`jobs_done_common.py`:

| Filter | Value |
|---|---|
| `jobs_done.product_origin_selection` | `All` (both platforms; also selects the combined row of `user_metrics`) |
| `organizations.account_selection` | `commercial_all` |
| `organizations.is_active_customer` | `Yes` |
| `jobs_done.jobs_done_version_param` | `2026.1` |

Removing one of them silently changes every number, and the article would no longer
match the dashboard.

**The articles reproduce the dashboard's Overview tab.** Since 18 November 2026 (PR
#1232) it reads the calendar period set in its *Time Frame* filter: "1 month ago for 1
month" for the monthly article (the default), "1 quarter ago for 1 quarter" for the
quarterly one.

| KPI | Measure | Read over |
|---|---|---|
| Jobs Done | `jobs_done` (daily Jobs Done, summed) | the calendar month or quarter |
| Users with a Job Done | `active_users` (unique users) | the calendar month or quarter |
| Jobs per User | Jobs Done / Users with a Job Done | same |
| MAU | `user_metrics.mau` | the 28 days that end the period, on its last day |
| Reach | `active_users_28d` / MAU | the same 28 days, on the last day |

Only MAU and Reach stay rolling 28-day figures. The changes compare with the previous
period of the same length (MoM, QoQ); Reach changes in points. The scripts run two
queries for this, as the tab's `*_overview_cur` measures do: the calendar period for
Jobs Done and users, its last day (`day_selection` "last day of the month/quarter") for
the 28-day users and MAU. They are never in one query: MAU joins `user_metrics`, which a
daily sum must not go through. A single feature's figures are the KPI tiles with the
dashboard's *Feature* filter.

The trend tabs (Jobs Done, Users Completing Jobs, Frequency) also sum daily values over
the period. The MAU Reach tab reads MAU and 28-day users on the last day of each month.

**A feature is one name across both platforms.** Reactions adds up the reactions of
Beekeeper (Streams, Chats) and LumApps (Content, Posts, Articles, Videos, Events), as the
dashboard's *Feature* filter does. Users are queried at that grain, never added up.

---

## Data files — structure and naming

All CSV files live in the `data/` subfolder, which is **gitignored**: these exports
carry customer-level data and are regenerated on demand.

| File | Content |
|---|---|
| `totals_YYYY-MM.csv` | Both platforms, per month: Jobs Done, Users with a Job Done, MAU |
| `features_YYYY-MM.csv` | Domain group × feature, per month, with the MAU of the organizations that have the feature (for its Reach) |
| `agents_YYYY-MM.csv` | Agents per agent: Jobs Done, users, organizations. Agent names are free text set by customers |
| `daily_volume_YYYY-MM.csv` | Daily Jobs Done per cell, for the volume checks |
| `quarterly/*_YYYY-QN.csv` | The quarterly files, see the docstring of `prepare_quarterly.py` |

**Scope** (November 2026): Communication & Collaboration, Work & Automation, AI &
Search, Channels, People & Growth. **AI & Search** (Search, Agents, Ask AI) joined
LumApps Jobs Done in September 2026 and reached the consolidated explore in late
November 2026, with data from late July 2026 (Ask AI from 31 August).

**AI & Search is read at product domain level.** In the explore, `feature` holds one row
per agent, named after the agent, and some names are customer names. The scripts fetch
this group with `product_domain` in place of `feature`, so the data shows `Agents`,
`Search` and `Ask AI`. The per-agent rows are fetched separately into
`agents_YYYY-MM.csv`, only for the experimental agent detail of the monthly article.

Articles up to August 2026 carried a standing note saying LumApps Jobs Done covered only
Communication & Collaboration. **That note is retired.** Do not reinstate it. The scope
sentence of each article replaces it, written from the script output every time.

**Workflows (Beekeeper):** Users with a Job Done = 0 due to a technical tracking
limitation. Jobs Done volume is valid; the users metric is not.

---

## Business context

Two products in one company:
- **LumApps**: intranet and employee experience platform
- **Beekeeper**: frontline worker communication and operations platform

One consolidated dashboard tracks both, and one article per month and per quarter
reports them combined.

---

## Jobs Done — concept and metrics

Jobs Done focuses on moments when a user **gets the core value** of a feature. Each feature is measured by exactly one key action.

| Metric | Definition | What it signals |
|---|---|---|
| **Jobs Done** | Key actions over the calendar month or quarter | Feature traffic |
| **Users with a Job Done** | Unique users who performed that action over the same period | How many people |
| **Jobs per User** | Jobs Done / Users with a Job Done | Engagement depth per user |
| **MAU** | Unique users active over the last 28 days | Total active user base |
| **Reach** | Users with a Job Done over 28 days, as % of MAU | Share of the active base |

**Time methodology:** monthly = the calendar month; quarterly = the calendar quarter.
MAU and Reach alone are 28-day figures, read on the last day of the period. MoM and QoQ
compare with the previous month or quarter. A calendar month has 28 to 31 days, so a
month with more days, or more working days, has more Jobs Done for that reason alone:
say so when it explains a move. There is no YoY: the Overview tab shows none.

**Trend classification** (from the MoM series of the last 6 months):
- `growing` — avg MoM ≥ +3%
- `declining` — avg MoM ≤ -3%
- `stable` — avg MoM between -3% and +3%, low variance
- `volatile` — high variance regardless of direction

---

## Interpretation guidance
- **Volume up + Users up** → more people complete the job
- **Volume up + Users flat** → existing users engage more (Jobs per User rising)
- **Volume up + Users down** → fewer people doing more — intensity signal
- **Volume down + Jobs per User flat** → fewer users, same depth per user
- **Volume down + Jobs per User down** → most concerning — users leaving and disengaging
- **Reach > 85%** → the tracked action is performed by most of the MAU it is measured on
- **Reach < 30%** → the tracked action reaches a small share of that MAU

  Both read as adoption of the **one action Jobs Done measures**, not of the feature as a
  whole. Do not turn them into "widely adopted" or "niche feature" in the article. A
  feature's Reach divides by the MAU of the organizations that have the feature, as the
  dashboard does with its *Feature* filter.

---

## Known permanent data limitations

- **Customer-level breakdowns** are only fetched for the quarterly article: the top
  organizations per feature (`data/quarterly/companies_*.csv`, for the 💡 lines) and the
  biggest movers per domain group, the organizations whose Jobs Done rose and fell the
  most against the quarter before (`group_movers_*.csv`).
- **Companies are organizations, never Salesforce accounts.** `prepare_quarterly.py`
  ranks on `organization_id` and only then labels each organization with
  `organizations.account_name` and its slug. Grouping by account would be wrong: in Q3
  2026 the account named "LumApps" held 35 organizations with Jobs Done, many of them
  customers. The script reports an organization of a top 3 or of the movers that sits
  under that account, or that has no account name, as *COMPANY DIRECTORY ISSUES*. It
  also checks that the company join does not inflate the total (LumApps' old source
  doubled a large customer's Videos Jobs Done in Q2 2026 that way). Report such issues
  upstream.
- **Users and MAU cannot be summed across features or domain groups.** They count
  *unique* users, so a user active in two domains is counted once at total level but
  twice if the rows are added up. Totals are queried at total grain. Only Jobs Done
  volume is safely additive.
- **Historical figures can be revised.** Do not restate an old month from memory;
  re-read it from the current output.
- **Workflows (Beekeeper) users metric** always 0 — do not report it. Volume is valid.
- **Workflows (Beekeeper) spiked at the end of February 2026**: the weeks of 23 February
  and 2 March hold about three times the usual weekly Jobs Done, 98% of it from a single
  customer. `prepare_quarterly.py` detects such steps and spikes (see `weekly_anomaly`
  in `jobs_done_common.py`) and names the companies behind them.
- **Search counts suggestion clicks only from 6 August 2026.** A Search Job Done is a
  search session with at least one click, and `SearchClickSuggestionAction` first appears
  in `fct_user_actions` on that day (690,608 events in 64 organizations of one cell by the
  end of August, none before). Search Jobs Done stepped from about 530K to about 930K a
  week at that point, while result clicks stayed flat. Any comparison across that date
  mostly measures the new event, not more searching: say so rather than reading it as
  growth.
- **Daily data can break without any check failing.** In September 2026 a dbt change
  (dataplatform PR #1503) left partial days in LumApps' old source. On the consolidated
  explore, the first runs (18 November 2026) found days with almost no Jobs Done:
  12 September 2026 in every cell large enough to be checked (no daily row at all), and
  9 and 10 October 2026 in the LumApps go cells.
  Both scripts check daily volume per cell and print *DATA VOLUME ALERTS*; the article
  checks fail until each has a verdict in `VOLUME_REVIEWS` (see *Data volume checks* in
  `README.md`). An `incident` verdict means the article opens on a
  `*Data warning: ...*` line.
- **MAU and Reach are 28-day figures**, as on the dashboard. Users with a Job Done cover
  the whole month or quarter and can be larger than MAU: never divide them by MAU. Reach
  divides the 28-day users of the period's last day.

---
