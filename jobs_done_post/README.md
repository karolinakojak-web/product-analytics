# Jobs Done articles

Generates the Jobs Done posts covering LumApps and Beekeeper, combined: a monthly one and
a quarterly one. Both reproduce the figures of the consolidated Jobs Done dashboard
(`product_bi::platform_jobs_done`, its Overview tab), and read the explore behind it.

| | Monthly | Quarterly |
|---|---|---|
| Skill | `/monthly-jobs-done-article` | `/quarterly-jobs-done-article` |
| Data and analysis | `prepare_data.py` | `prepare_quarterly.py` |
| Check | `check_article.py` | `check_quarterly_article.py` |
| Draft (checked, not handed over) | `data/drafts/article_YYYY-MM.md` | `data/drafts/quarterly_YYYY-QN.md` |
| Deliverable | `articles/article_YYYY-MM.html`, by `render_monthly_html.py` | `articles/quarterly_YYYY-QN.html`, by `render_quarterly_html.py` |
| Period | the calendar month (MAU and Reach: the 28 days that end it) | the calendar quarter (MAU and Reach: the 28 days that end it) |
| Shape | the five overview KPIs, then 5 features of the month | the five overview KPIs, two highlight lists, then one block per domain group: every feature, and the group's biggest movers by company |

Both read the same Looker explore and share their writing rules
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
/monthly-jobs-done-article 2026-10 Campaigns had a big launch this month, worth a mention
```

The skill runs the steps below, writes the article following its rules, and fixes
whatever the check reports. The arguments are optional: a month, then an editorial note.

Claude writes the article as a Markdown draft in `data/drafts/`, where the check reads
it. Once the check passes, the save hook writes the deliverable,
`articles/article_YYYY-MM.html`: one `<section class="lwa">` holding its own `<style>`,
to paste as an HTML widget in the intranet page. It uses the LumApps brand shell of the
artifact pages (`assets/shell.css`, copied from the `lumapps-utils` artifact skill), so
the articles look like the other pages Claude publishes. It lays out the checked draft
and adds no figure of its own, so always fix the draft, never the HTML. By hand:

```bash
python3 render_monthly_html.py data/drafts/article_2026-10.md
```

### Running the script by hand

From this folder:

```bash
python3 prepare_data.py
```

That pulls fresh data into `data/` and prints the analysis:

- the five overview lines to copy as they are (Jobs Done, Users with a Job Done, Jobs
  per User, MAU, Reach), then the totals over the last 6 months;
- the feature breakdown by product domain group, both platforms together;
- three ranked lists telling you what to write about: biggest moves of the month (each
  feature against its own previous month, in Jobs Done), strongest relative moves,
  newly tracked features;
- the *AGENTS DETAIL* (experimental), once AI & Search reaches the explore: the Agents
  total, then the largest agents, the biggest absolute growth and the widest adoption
  across organizations.

The writing rules live in the skill (see *Layout*). Save the draft as
`data/drafts/article_YYYY-MM.md`.

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
`--month` says. A report month must fall inside that window. There is no
year-over-year figure: the dashboard's Overview tab shows none.

Common combinations:

```bash
# the usual monthly run
python3 prepare_data.py

# a given month
python3 prepare_data.py --month 2026-08

# flag something the data alone cannot tell you
python3 prepare_data.py --note "Campaigns had a big launch this month, worth a mention"
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
python3 check_quarterly_article.py data/drafts/quarterly_2026-Q3.md
python3 render_quarterly_html.py data/drafts/quarterly_2026-Q3.md
```

The last command writes the deliverable, `articles/quarterly_2026-Q3.html`, in the same
brand shell, to paste as an HTML widget. It lays out the checked draft and adds no
figure of its own, so always fix the draft, never the HTML. `--out-dir` writes the HTML
elsewhere, for a preview. The save hook runs
it after a passing check.

A quarter is read as the Overview tab reads it with *Time Frame* set to "1 quarter ago
for 1 quarter": Jobs Done and Users with a Job Done over the calendar quarter, MAU over
the 28 days that end it, and Reach as users with a Job Done over those 28 days divided
by MAU. Every change compares with the quarter before. The script fetches the report quarter and the four before it, and
warns when the quarter is not over yet. Wait a day or two after the quarter ends so its
last day has landed in Looker.

The article names customers in each domain group's biggest movers: the three
organizations whose Jobs Done rose the most against the quarter before, and the three
that fell the most, ranked on the change in Jobs Done. Organizations are ranked one
by one, never grouped by Salesforce account (one account named "LumApps" holds dozens of
customer organizations), and labelled with their account name and their slug. It is
meant for internal readers.

## Checking the article

```bash
python3 check_article.py data/drafts/article_2026-10.md
```

It verifies that the five overview lines are the dashboard's, to the digit, that every
other figure in the article traces back to the CSVs, per-agent figures in the Agents
paragraph included, and that the editorial rules hold (structure, banned wording, five
feature paragraphs, emoji, no year-over-year). It also checks that the scope sentence
lists exactly the domains and features tracked that month, each domain's features from
largest to smallest, leaving out features whose go-live month has not come yet
(`GO_LIVE` in `jobs_done_common.py`). The scope grows over time, so
this check catches a sentence copied from last month. Figures written without a unit,
such as "164 Jobs Done" or "8 customers", are not checked.

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
a person has looked at what they find. The first runs on the consolidated explore
(November 2026) found days with almost no Jobs Done in it: 12 September 2026 in every
cell, and 9 and 10 October 2026 in the LumApps go cells.

| Check | What raises an alert |
|---|---|
| Daily volume | A day under half, or over twice, the median of the same weekday over the 4 weeks before. Read per cell (`organizations.cell`), since cells break separately; a cell that carries both platforms adds them up. Units under 50,000 Jobs Done a day are not checked. |

The days checked are the ones the article compares: the report month and the one
before (monthly), the report quarter and the one before (quarterly). Jobs Done is the
sum of these days, so a broken day changes the article's figure directly. Alert days of
one unit close together form one episode, so an incident is reviewed once.

**The scripts do not decide.** Both print *DATA VOLUME ALERTS*, with the verdicts on
record. For each new one, investigate (a public holiday in the cell's region, an
incident upstream), then record the verdict in `VOLUME_REVIEWS` in
`jobs_done_common.py`:

- `"expected"`: a real dip or peak, such as a public holiday. Nothing else to do.
- `"incident"`: the data is wrong. Report it upstream, and open the article on a line
  `*Data warning: <what is affected, and that a corrected version will follow>.*`.
  The check fails without it.

A verdict stays on record, keyed on the cell and the first day, so a holiday reviewed
for one article is not asked again for the next one that covers it. The daily data is in
`data/daily_volume_YYYY-MM.csv` and `data/quarterly/daily_volume_YYYY-QN.csv`.

## Layout

```
jobs_done_post/
├── README.md           this file
├── CLAUDE.md           data sources, metric definitions, data limitations
├── writing-rules.md            writing rules shared by both articles
├── jobs_done_common.py         Looker config, overview KPIs, emoji, go-live, reviews, shared checks
├── prepare_data.py             monthly: Looker fetch + analysis
├── check_article.py            monthly: article verification
├── render_monthly_html.py      monthly: the checked article as an HTML block
├── prepare_quarterly.py        quarterly: Looker fetch + analysis
├── check_quarterly_article.py  quarterly: article verification
├── render_quarterly_html.py    quarterly: the checked article as an HTML block
├── requirements.txt
├── .env.example
├── assets/shell.css    the LumApps brand shell of the HTML blocks
├── articles/           article_YYYY-MM.html, quarterly_YYYY-QN.html: the deliverables
└── data/               gitignored, regenerated on every run
    ├── totals_YYYY-MM.csv         both platforms together, per month
    ├── features_YYYY-MM.csv       domain group x feature
    ├── agents_YYYY-MM.csv         Agents, per agent (empty until AI & Search lands)
    ├── daily_volume_YYYY-MM.csv   daily Jobs Done per cell, for the volume checks
    ├── quarterly/      {totals,features,companies,group_movers,daily_volume,...}_YYYY-QN.csv
    └── drafts/         article_YYYY-MM.md, quarterly_YYYY-QN.md: the checked Markdown drafts

.claude/skills/monthly-jobs-done-article/
├── SKILL.md                    the steps Claude follows
└── references/
    ├── writing-rules.md        the monthly rules
    └── example-article.md      the expected shape, figures removed

.claude/skills/quarterly-jobs-done-article/
├── SKILL.md
└── references/
    └── writing-rules.md        the quarterly structure and domain block
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
| `... not found. Run without --no-fetch` | Run the script without `--no-fetch`. |
| `YYYY-MM missing from the data` | The month is outside the fetched window. |
| `data is Nh old` in a check | The data is more than 24 hours old. Re-run the script, then the check. |
| The hook never runs | Open `/hooks` once or restart the session. It needs `jq` and `python3` on the PATH. |
| `... is not over yet: its figures are partial` | The quarter is still running, or its last day has not landed. Wait, then re-run. |
| Figures do not match an old published article | Expected. Articles before November 2026 read two other explores, one per platform, over other windows: the consolidated explore is a fresh baseline. Looker also revises history, and a newly tracked feature comes with backfilled history. Do not restate an old month from memory. |
| Figures do not match the dashboard | Check the dashboard's filters: Platform on "All", Time Frame on "1 month ago for 1 month" or "1 quarter ago for 1 quarter". A single feature's figures are read with its Feature filter. |
