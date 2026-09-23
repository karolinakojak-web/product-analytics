# Jobs Done — Monthly Article Generator

## How to proceed

1. Run `python3 prepare_data.py --fetch` from this folder. It pulls fresh data from
   Looker, writes the CSVs into `data/`, and prints full analytics to the terminal.
2. Read the output — platform totals with MAU, feature MoM/YoY/frequency, 13-month trend classification (15 months fetched, so the report month has its YoY), and notable movers for both companies.
3. Write the article following the style rules below.
4. Save as `articles/article_YYYY-MM.md`. **A hook checks it automatically on save** and
   reports any failure straight back, so fix what it reports before handing the article over.

---

## Automatic quality check

`check_article.py` verifies a written article. A **Claude Code hook runs it on every save**
of `articles/article_*.md`, configured in `.claude/settings.json` at the repo root. Nothing
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
| Wording | Em dashes, superlative rankings, recovery verbs, analyst vocabulary. |
| Selection | At most 3 feature paragraphs per platform, correct emoji per feature, no year-over-year inside a feature paragraph. |
| Warnings | Quantity words ("most", "half", "a third") are listed, never blocking. The script cannot judge them; a human confirms them against the figures. |

**What it cannot do**

- It only fires on writes made **by Claude**. Editing the article by hand in an editor
  triggers nothing, so run the command above after a manual edit.
- Warnings are not failures. The August 2026 issue shipped a wrong "most of July's drop"
  that only a human could catch, which is exactly why quantity words are surfaced.
- A failure can mean the data is stale rather than the article being wrong. Re-run
  `python3 prepare_data.py --fetch` before assuming the prose is at fault.
- If the hook seems not to run, open `/hooks` once or restart the session. It needs `jq`
  and `python3` on the PATH.

**One-time setup:** `pip install -r requirements.txt`, then set the three Looker
variables documented in `.env.example`.

**Options:**
- `--fetch` pull fresh CSVs from Looker before analysing. Without it, the script reads whatever is already in `data/`.
- `--month 2026-04` target a specific report month. Defaults to the last complete calendar month.
- `--note "<text>"` pass editorial context for the month (a new feature, a known incident, an angle to take).

---

## Where the data comes from

`--fetch` queries the Looker API directly. There is no manual CSV export step any more.

| Platform | LookML dashboard | Explore |
|---|---|---|
| LumApps | [`base::jobs_done`](https://bi.lumapps.com/dashboards/base%3A%3Ajobs_done) — defined in the `internal/bi` repo | `base` / `fct_jobs_done__bi` |
| Beekeeper | [`product_bi::jobs_done`](https://bi.lumapps.com/dashboards/product_bi%3A%3Ajobs_done) — defined in the `looker` repo | `product_bi` / `jobs_done` |

Both dashboards have four tabs. Three are pulled — **Jobs Done**, **Users Completing
Jobs** and **Frequency**. The fourth, *Month overview*, is skipped: it is a one-month
snapshot already contained in the 13-month series. Each tab is fetched at two scopes
(platform total, and broken down by domain group + feature), so 6 queries per platform.

The dashboard tiles pivot on feature. The API requests the same data **unpivoted**, so
it arrives in long format with one row per month × domain × feature.

The *Users Completing Jobs* tab shows four looks where the others show two, but they hold
only two distinct measures (`active_users_28d`, MAU) across the two scopes — the extra two
are subsets. Everything else on the tabs (`MoM %`, `Users Completing Jobs / MAU`) is a
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

`data/raw/` holds the twelve untouched per-tab responses (`<platform>_<tab>_<scope>_YYYY-MM.csv`)
as an audit trail. The four files above are merged from them and are what the analytics read.

**Lumapps scope:** the list of product domain groups is growing. Communication &
Collaboration was the only one for a long time; **AI & Search** was added to Jobs Done in
**September 2026** (single `Agents` feature, small volume, earlier data is backfill), and
a third domain is on the way.

Articles up to August 2026 carried a standing note saying LumApps Jobs Done covered only
Communication & Collaboration. **That note is retired** — it stopped being true. Do not
reinstate it. Read the domain groups from the script output instead of assuming a scope.

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

## Article style rules

### Read the reference articles first
- `articles/article_2026-07.md` and `articles/article_2026-06.md` — the two most recent, use these as the primary template
- `articles/article_2026-05.md` — same structure, slightly longer feature commentary
- April 2026 article pasted at the bottom of this file — useful for voice reference

All three follow the same markdown skeleton: the title below, a `## High level overview`
block, then one `##` section per platform, each closing on its dashboard line.

### Title (always the same shape)

```
# Jobs Done - <Month> <Year> Product Performance
```

A plain hyphen, and the `Product Performance` suffix is part of the title, not optional.

### Opening (always the same)

```
Hi Team, here is how our key product usage KPI, Jobs Done, performed in [Month] across two platforms.

*Don't you know what "Jobs Done" metrics are? [Read this introduction](https://we.lumapps.com/we/ls/space/5070108616032256/team-engineering/article/ddf2b3ba-e590-4806-ac0a-00669376237c)*
```

The second line is a standing link to the Jobs Done explainer — carry it over verbatim
every month. **It is italicised**, like the two closing lines below.

### High level overview block
```
✅ Jobs Done
- LumApps XXX.XM (+X.X% MoM, +X.X% YoY)
- Beekeeper XX.XM (+X.X% MoM, +X.X% YoY)

👨‍🦲 MAU
- LumApps X.XXM (+X.X% MoM)
- Beekeeper XXXK (+X.X% MoM)
```

### Tone and length
- **Engaged and human** — write like a colleague sharing news, not like a dashboard export.
- **Positive framing** where the data allows it. Lead with what's working before what isn't.
- **Short.** The article is a quick summary — readers go to the dashboard for details. Aim for something readable in 2 minutes.
- Use M for millions, K for thousands. Every claim has a number behind it.
- **Simple and direct.** Short sentences, ordinary words, one idea at a time. Say what
  happened, not what it signifies.
- **Never let analytical vocabulary reach the prose.** The script's wording is for
  reading the data, not for the article. "Content accounts for almost the entire monthly
  move" is the contribution metric leaking in; write "Content explains almost all of the
  drop". Same for "swing", "driver", "penetration", "reach".
- No figurative phrasing ("gave back the summer spike"), no sentence fragments
  ("Still the platform's backbone").
- **Name the metric a percentage belongs to.** MAU and Users Completing Jobs are different
  numbers and move differently: in August 2026, MAU was +1.4% and UCJ +1.9%. Writing
  "more people active (+1.9%)" puts a MAU label on a UCJ figure and reads as a
  contradiction of the overview. Say "Users Completing Jobs", "active user base" or
  "frequency" explicitly, every time.
- No corporate filler. No "it is worth noting". No "one could argue".
- **No em dashes (—).** Rewrite the sentence rather than swapping the character for an
  en dash or a double hyphen: a comma, a colon, parentheses, or two shorter sentences
  almost always read better. Articles published before this rule keep their original
  punctuation.

### What to cover — and what to skip

**2–3 features per company. No more.** The script ranks the candidates for you — do not
re-rank them by eye, and do not go looking outside its lists.

Pick in this order:

1. **BIGGEST DRIVERS OF THE MONTH** — take the top 1–2. This list is sorted by each
   feature's contribution to the platform's monthly change, which is what "explains the month"
   means. A feature contributing 85% of the change *is* the story, even at a modest -7% MoM.
2. **STRONGEST RELATIVE MOVES** — at most one, and only if it tells a story. These move
   sharply in % but barely shift the total, so never lead with one.
3. **NEWLY TRACKED FEATURES** — worth one line the first time it appears in an article,
   then leave it alone until it has real volume. Say it is new and give the raw numbers;
   do not read a trend into a few months of history.

**A short history does not mean a recent launch.** The explore backfills data when a
feature is onboarded, so this list flags backfilled features, not new ones. Check the
real go-live date before calling anything new. Known case: **Agents** (AI & Search,
LumApps) shows history from early 2026 but was only added to Jobs Done in **September
2026** — it must not appear in any article before then.

Everything else gets no mention. Stable features with unremarkable numbers get no mention.

Never justify a pick with "biggest MoM %" alone — that metric systematically promotes
small features. In August 2026 it ranked Videos (-26.7%, 1.1% of the change) above
Content (-7.1%, 85.5% of it).

For each feature you do cover: one or two sentences max. Include the number, the direction, and one piece of context: consecutive months up or down, frequency versus users, a known seasonal pattern, or how the month sits against recent months. Don't list every metric, pick the one that tells the story.

### Year-over-year: overview only

**YoY is a platform-level figure only.** It is allowed in two places:

1. the High level overview block, and
2. the opening paragraph of a platform section, when it carries the angle of the month
   (e.g. framing a down month against strong annual growth).

**Never in a feature paragraph.** Do not put a YoY figure there, and do not paraphrase
one either ("over twelve months it is down 7%", "nearly double last August").

These are monthly articles: the feature commentary explains the month, and a YoY figure
pulls the reader onto a different time scale. This came out of the review of the June
and July 2026 issues, so it is a team convention.

⚠️ `articles/article_2026-06.md` and `articles/article_2026-07.md` still carry
feature-level YoY, since they predate the correction. Follow them for style, not on this
point.

### Editorial note from the analyst

`--note "<text>"` prints a block at the top of the report. When it is there, treat it as
a steer that outranks the ranking above: if it asks for a feature to be covered, cover it
even when the lists would have dropped it. Keep it to the length the data supports.

```
python3 prepare_data.py --note "Agents was added to LumApps Jobs Done, worth a mention"
```

### Trend language rules
- Do not use "recovered" or "bounced back" based on a single positive MoM. Check 3+ months of context. A feature is only recovering if it is returning toward a prior reference level, not just up from a recent dip.
- Do not include notes like "this needs investigation" or "verify before publishing" — that is the analyst's job before the article goes out. If a number is not ready to publish, leave it out entirely.
- Do not overinterpret. Describe what the data shows; don't speculate about causes unless they are clearly visible in the numbers (e.g. a known seasonal pattern, a consecutive streak).
- **Check quantity words against the data.** "most", "nearly all", "half", "the bulk of"
  are claims, not flourishes. Compute them before writing: a month that recovers 1.5M of
  a 4.0M drop makes up a third of it, not most of it.
- **No superlative rankings over time.** Avoid "best month of the year", "second-best
  month so far", "strongest growth of 2026", "highest ever". These were dropped in
  review: they are fragile (one revision of the data invalidates them), they invite
  the reader to compare across a window the article is not about, and they add nothing the
  figure itself does not already say. Give the number and the direction, and stop there.
  Describing a feature's current size ("Beekeeper's biggest feature") is fine, that is a
  statement about now, not a ranking of months.

  ⚠️ The June and July 2026 articles contain "best KPI of the current year" and
  "second-best month of the year". They predate this rule. Do not copy them on this point.

### Emojis for features

This list is authoritative — use it even if an older article used a different glyph.
📄 Content · 💬 Chats · 📡 Streams · 🏠 Spaces · 📝 Posts · 🎬 Videos · 👍 Reactions · 📊 Surveys · ☑️ Tasks · 📅 Shifts · 🗂️ Forms · 🔗 Shortcuts · 📢 Campaigns · 📆 Company Events · ⚙️ Workflows · 🗨️ Comments · 📁 Documents · 🤝 Referrals · 🤖 Agents

### Close each company section

Both links are fixed — copy them as they are:

```
*Full breakdown available in the [LumApps Jobs Done dashboard](https://bi.lumapps.com/dashboards/base::jobs_done?tab_name=Jobs+Done&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
*Full breakdown available in the [Beekeeper Jobs Done dashboard](https://bi.lumapps.com/dashboards/product_bi::jobs_done?tab_name=Jobs+Done&Tenant+Selection=commercial%5E_all&Tenant+Subdomain=&Company+Size=&Industry=&+Commercial+Phase=&Commercial+Swarm=&Is+CS+Ops+Managed+%28Yes+%2F+No%29=&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
```

Both URLs open on the *Jobs Done* tab filtered to Communication & Collaboration, which
is where the article's commentary sits. LumApps now also has AI & Search; the link is
deliberately left on C&C.

---

## Interpretation guidance
- **Volume up + Users up** → growing reach
- **Volume up + Users flat** → existing users engage more (frequency rising)
- **Volume up + Users down** → fewer people doing more — intensity signal
- **Volume down + Frequency flat** → reach problem (fewer users, same depth per user)
- **Volume down + Frequency down** → most concerning — users leaving and disengaging
- **UCJ/MAU > 85%** → broadly adopted across the active user base
- **UCJ/MAU < 30%** → niche or early-stage feature

---

## Known permanent data limitations

- **Customer-level breakdowns** not in the CSV export — available in Looker with filters.
- **Users and MAU cannot be summed across domain groups.** They count *unique* users, so a
  user active in two domains is counted once at platform level but twice if the rows are
  added up. This is why the `all` files have no domain column: platform totals are queried
  at platform grain. Only Jobs Done volume is safely additive.
- **Historical figures can be revised.** The Beekeeper total published for April 2026
  (32.9M) no longer reproduces — the explore now returns 34.3M for that month. Do not
  restate an old month from memory; re-read it from the current output.
- **Workflows (Beekeeper) users metric** always 0 — do not report it. Volume is valid.
- **MAU** comes from the `_all_` files. If those files are missing, note MAU is unavailable.

---

## Reference: April 2026 article (voice benchmark)

Hi Team,

Here is how our key product usage KPI, Jobs Done, performed in April across two platforms.

High level overview

✅️ Jobs Done

LumApps 119.0M (-2.7% MoM)
Beekeeper 32.9M (-6.5% MoM)

👨‍🦲 MAU

LumApps 2,85M (+0.8% MoM)
Beekeeper 691.9K (-0.2% MoM)

Insights

LumApps is growing its active user base - MAU reached 2.85M (+0.8%) in April, and Users Completing Jobs have grown consistently for four months in a row (on avg +3.8% per month). Jobs Done across Communication & Collaboration features declined slightly (-2.7%) in April, but users keep growing - meaning more people are engaging with these features even if each does slightly less.
Note that for LumApps, Jobs Done currently covers only a handful of features and only within the Communication & Collaboration product domain, so a decline in April does not indicate a platform-wide pullback but just a change in specific product domain engagement.

Top engaged features in April:

📄 Content - 108.8M JD (-2.0%), 2.75M active users (+1.1%) - a modest decline after a year of overall growth, with more users visiting content but interacting slightly less often than in March. Standout accounts include DoorDash with the highest frequency of 163 content interactions per user in April, and LVMH which grew across all dimensions - users engaging with content (+11%), Jobs Done (+15%), and frequency of engagement (+4.2%).

Feature usage declines in April:

🏠 Spaces - 3.3M JD (-9.8%), 524K active users (-5.8%) - a pullback after two months of growth, but Spaces has shown this pattern repeatedly throughout the year, consistently recovering the following month. One to watch but not a new trend

📝 Posts - 1.6M JD (-14.9%), 334K active users (-8.8%) - activity has slowed in the last two consecutive months, though a similar slowdown appeared around the same time last year. One to watch but likely seasonal

Full breakdown available in the Lumapps Jobs Done dashboard.

Beekeeper tracks Jobs Done across a wider feature portfolio spanning Communication & Collaboration, Work & Automation, Channels, and People & Growth. In April, activity declined across most domains and industries - here's what stood out.

Top engaged features in April:

☑️ Tasks (Work & Automation) +4.0% - the only feature to grow this month, and part of a bigger story: Tasks has nearly doubled over the past year with consistent growth month after month. In April we see fewer users (-6.5%) but significantly higher frequency (+11.3%) - meaning the same people were using this feature more, and growth was driven by existing customers - for example BUTLERS nearly tripled its Tasks usage this month.

👍 Reactions (Communication & Collaboration) - almost 4 in 10 Beekeeper users reacted to something in April, and activity has been on a consistent upward trend over the past year - growing from 1.4M to over 2M Jobs Done. April's -2.1% is a minor pullback in the context of a feature that keeps growing.

Feature usage declines in April:

💬 Streams (Communication & Collaboration) - used by 83% of Beekeeper users, but activity has been softening for two consecutive months (-7.9%). Users aren't leaving - they're just communicating less frequently per session.

📊 Surveys (People & Growth) -29.5% - a sharp reversal after March's strong comeback, with both users (-16.7%) and frequency (-15.4%) declining together. The pattern over recent months suggests surveys are used in bursts around specific campaigns rather than as a regular habit.

📅 Shifts (Work & Automation) -8.4% - a single month decline after a strong March (+9.2%). Healthcare, which makes up more than half of all Shifts activity, declined -6.8% and drove most of the overall drop - largely concentrated in one account, Hofmatt, which didn't use Shifts in April (46K → 22 JD). Hospitality (+7.1%) and Construction (+52.9%) bucked the trend but are too small in volume to offset.

Full breakdown available in the Beekeeper Jobs Done dashboard.
