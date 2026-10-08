# Jobs Done articles

Generates the Jobs Done posts covering LumApps and Beekeeper: a monthly one and a
quarterly one.

| | Monthly | Quarterly |
|---|---|---|
| Skill | `/monthly-jobs-done-article` | `/quarterly-jobs-done-article` |
| Data and analysis | `prepare_data.py` | `prepare_quarterly.py` |
| Check | `check_article.py` | `check_quarterly_article.py` |
| Article | `articles/article_YYYY-MM.md` | `articles/quarterly_YYYY-QN.md` |
| Shape | 2 to 3 features per platform | every feature, with its top 3 companies |

Both read the same Looker explores and share their writing rules
(`writing-rules.md`) and their constants (`jobs_done_common.py`).

## Setup (once)

**1. Install the dependencies**

```bash
pip install -r requirements.txt
```

**2. Get a Looker API key**

In Looker, go to **Admin > Users**, select your user, and generate an API key. You get a
client ID and a client secret. The secret is shown once, so copy it straight away.

**3. Export the three variables**

```bash
export LOOKERSDK_BASE_URL="https://bi.lumapps.com:19999"
export LOOKERSDK_CLIENT_ID="your_client_id"
export LOOKERSDK_CLIENT_SECRET="your_client_secret"
```

Put them in your shell profile, or copy `.env.example` to `.env` and source it. `.env` is
gitignored. Never commit the secret.

> **Mind the base URL.** It needs the API port and no slash before it.
> `https://bi.lumapps.com:19999` works, `https://bi.lumapps.com/:19999` returns 403.

If your `~/.bashrc` exports these, note that it usually returns early for non-interactive
shells, so scripts launched outside a terminal may not see them.

## Generating a month

In Claude Code, from the repository root:

```
/monthly-jobs-done-article
/monthly-jobs-done-article 2026-09
/monthly-jobs-done-article 2026-09 Search and Agents joined Jobs Done this month, worth a mention
```

The skill runs the steps below, writes the article following its rules, and fixes
whatever the check reports. The arguments are optional: a month, then an editorial note.

### Running the script by hand

From this folder:

```bash
python3 prepare_data.py
```

That pulls fresh data into `data/` and prints the analysis:

- platform totals with MAU, over 13 months;
- the feature breakdown by product domain group;
- three ranked lists telling you what to write about: biggest drivers of the month,
  strongest relative moves, newly tracked features;
- for LumApps, the *AGENTS DETAIL* (experimental): the Agents total, then the largest
  agents, the biggest absolute growth and the widest adoption across tenants.

The writing rules live in the skill (see *Layout*). Save the article as
`articles/article_YYYY-MM.md`.

### Options

| Option | What it does |
|---|---|
| `--month 2026-08` | Target a specific report month. Defaults to the last complete calendar month. |
| `--note "<text>"` | Pass editorial context for the month, for example a feature that just launched or an incident worth mentioning. It is printed at the top of the analysis and outranks the automatic ranking. |

**Every run fetches fresh data from Looker**, and every article is written and checked
on it: history is revised from one month to the next, and upstream fixes land between
two runs. The checks fail when the data they read is more than 24 hours old.
`--no-fetch` re-reads `data/` as it is, for work on the scripts only, never for an
article. `--fetch` is still accepted and does nothing more.

The fetch always pulls the last 15 complete months counted from today, whatever
`--month` says. A report month must fall inside that window, and needs to be one of its
last 3 months to have a year-over-year figure.

Common combinations:

```bash
# the usual monthly run
python3 prepare_data.py

# a given month
python3 prepare_data.py --month 2026-08

# flag something the data alone cannot tell you
python3 prepare_data.py --note "Search and Agents joined Jobs Done this month, worth a mention"
```

## Generating a quarter

In Claude Code, from the repository root:

```
/quarterly-jobs-done-article
/quarterly-jobs-done-article 2026-Q3
```

The argument is optional and defaults to the last complete quarter. By hand, from this
folder:

```bash
python3 prepare_quarterly.py --quarter 2026-Q3
python3 check_quarterly_article.py articles/quarterly_2026-Q3.md
```

A quarter is measured over every day it contains: Jobs Done summed day by day, Users
Completing Jobs unique over the whole quarter. There is no MAU in the quarterly article. The script fetches the
report quarter and the four before it, and warns when the quarter is not over yet.
Wait a day or two after the quarter ends so its last day has landed in Looker.

The article names customers in each feature's top 3. It is meant for internal readers.

## Checking the article

```bash
python3 check_article.py articles/article_2026-08.md
```

It verifies that every figure in the article traces back to the CSVs, per-agent figures
in the Agents paragraph included, and that the editorial rules hold (structure, banned
wording, feature count, emoji, year-over-year placement). It also checks that the scope
sentence opening each platform section lists exactly the domains and features tracked
that month, leaving out features whose go-live month has not come yet (`GO_LIVE` in the
script: Agents and Search, September 2026). The scope grows over time, so this check
catches a sentence copied from last month. Figures written without a unit, such as
"164 Jobs Done" or "8 customers", are not checked.

A hook in `.claude/settings.json` runs it automatically whenever Claude saves an article,
so you only need the command above after editing one by hand.

Warnings are not failures. Quantity words like "most" or "half" are listed for you to
confirm, because the script cannot judge them. That is deliberate: the August 2026 draft
claimed a month made up "most" of the previous drop when it was about a third.

## Data volume checks

Every check above can pass on broken data. In September 2026 a dbt change
(dataplatform PR #1503) overwrote LumApps daily Jobs Done with partial days, from
20 September in some cells: the article's figures traced to the data, and the data was
wrong. So both scripts also check the data itself, and both article checks fail until
a person has looked at what they find.

| Check | What raises an alert |
|---|---|
| Daily volume | A day under half, or over twice, the median of the same weekday over the 4 weeks before. Read per LumApps cell (`haussmann_cell`), since cells break separately, and for Beekeeper as a whole. Units under 50,000 Jobs Done a day are not checked. |
| 28-day window (monthly) | The month's 28-day Jobs Done against the sum of its 28 daily values. For LumApps the window runs about 2% above the sum even in healthy months, so the check alerts when that gap moves more than 0.5 point from the two month ends before. |

The days checked are the ones the article compares: the report month's window and the
one before (monthly), the report quarter and the one before (quarterly). Alert days of
one unit close together form one episode, so an incident is reviewed once.

**The scripts do not decide.** Both print *DATA VOLUME ALERTS*, with the verdicts on
record. For each new one, investigate (a public holiday in the cell's region, an
incident upstream), then record the verdict in `VOLUME_REVIEWS` in
`jobs_done_common.py`:

- `"expected"`: a real dip or peak, such as a public holiday. Nothing else to do.
- `"incident"`: the data is wrong. Report it upstream, and open the article on a line
  `*Data warning: <what is affected, and that a corrected version will follow>.*`.
  The check fails without it.

A verdict stays on record, so a holiday reviewed for one article is not asked again for
the next one that covers it. The daily data is in
`data/<platform>_daily_volume_YYYY-MM.csv` and
`data/quarterly/<platform>_daily_volume_YYYY-QN.csv`.

## Layout

```
jobs_done_post/
├── README.md           this file
├── CLAUDE.md           data sources, metric definitions, data limitations
├── writing-rules.md            writing rules shared by both articles
├── jobs_done_common.py         Looker config, emoji, go-live, reviews, shared checks
├── prepare_data.py             monthly: Looker fetch + analysis
├── check_article.py            monthly: article verification
├── prepare_quarterly.py        quarterly: Looker fetch + analysis
├── check_quarterly_article.py  quarterly: article verification
├── requirements.txt
├── .env.example
├── articles/           article_YYYY-MM.md and quarterly_YYYY-QN.md
└── data/               gitignored, regenerated on every run
    ├── <platform>_all_YYYY-MM.csv        platform totals
    ├── <platform>_features_YYYY-MM.csv   domain group x feature
    ├── lumapps_agents_YYYY-MM.csv        LumApps Agents, per agent
    ├── <platform>_daily_volume_YYYY-MM.csv  daily Jobs Done per cell, for the volume checks
    ├── raw/            per-tab responses, kept as an audit trail
    └── quarterly/      <platform>_{totals,features,companies,daily_volume,...}_YYYY-QN.csv

.claude/skills/monthly-jobs-done-article/
├── SKILL.md                    the steps Claude follows
└── references/
    ├── writing-rules.md        the monthly rules
    └── example-article.md      August 2026 article, figures removed

.claude/skills/quarterly-jobs-done-article/
├── SKILL.md
└── references/
    └── writing-rules.md        the quarterly structure and feature block
```

`data/` and `articles/` are gitignored on purpose: the exports carry customer-level data,
and the articles name customers, while this repository is public. Regenerate the data
by running the script rather than sharing files, and share articles through internal channels.
Keep customer names out of the code and the docs too.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `403` on login | Base URL is wrong. Check the port and the missing slash. |
| `LOOKERSDK_... is not set` | The variables are not exported in this shell. |
| `no data for lumapps in .../data` | Run the script without `--no-fetch`. |
| `month YYYY-MM missing from the data` | The month is outside the fetched window. |
| `data is Nh old` in a check | The data is more than 24 hours old. Re-run the script, then the check. |
| The hook never runs | Open `/hooks` once or restart the session. It needs `jq` and `python3` on the PATH. |
| `... is not over yet: its figures are partial` | The quarter is still running, or its last day has not landed. Wait, then re-run. |
| Figures do not match an old published article | Expected. Looker revises history, and a newly tracked feature comes with backfilled history: Search added 3.4M to LumApps' August 2026 total after that article was published. Do not restate an old month from memory. |
