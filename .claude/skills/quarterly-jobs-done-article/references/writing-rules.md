# Quarterly article: writing rules

These rules are specific to the quarterly article. Read `jobs_done_post/writing-rules.md`
first: tone, staying inside the metric, trend language, emojis, the scope sentence and
go-live dates are shared with the monthly article. `jobs_done_post/check_quarterly_article.py`
enforces what can be checked mechanically; the rest is on you.

## What a quarter measures

The article reports LumApps and Beekeeper **combined**, and reads a quarter as the
consolidated dashboard's Overview tab does with *Time Frame* set to "1 quarter ago for
1 quarter":

| | |
|---|---|
| Jobs Done | the daily Jobs Done of the calendar quarter, summed |
| Users with a Job Done | unique users who completed that job during the quarter |
| Jobs per User | Jobs Done / Users with a Job Done |
| MAU | users active over the 28 days that end the quarter |
| Reach | users with a Job Done over those 28 days, as a share of MAU |

MAU and Reach are 28-day figures, as on the dashboard, while Users with a Job Done cover
the whole quarter and are larger than MAU. Never divide one by the other, and never quote MAU
outside its overview line. "Active users" appears nowhere in the article: write MAU in
the overview, Users with a Job Done elsewhere.

The domain blocks show no users figure; a 💡 line may quote a feature's users from the
script output, as "Users with a Job Done". Users do not add up across features or domain
groups: only Jobs Done does.

Every change compares the quarter with the one before (QoQ). No year-over-year figure.

## Structure

The article is written in Markdown, then laid out as an HTML block for the intranet by
`jobs_done_post/render_quarterly_html.py` (the save hook runs it once the check passes).
The renderer reads the lines below exactly as they are: keep their shape.

````
# Jobs Done - Q3 2026 Product Performance

Hi Team, here is how our key product usage KPI, Jobs Done, performed in Q3 2026 across LumApps and Beekeeper. Every change compares with Q2 2026.

---

## High level overview

✅ Jobs Done: XXX.XM (+X.X% QoQ)
👥 Users with a Job Done: X.XXM (+X.X% QoQ)
🔁 Jobs per User: XXX.X (+X.X% QoQ)
📈 MAU: X.XXM (+X.X% QoQ)
🎯 Reach: XX.X% (+X.X pts QoQ)

### Which features grew the most?

- 📄 **Content** +X.X% QoQ: up in each of the last four quarters.
- ⚙️ **Workflows** +X.X% QoQ: XX.X% of Work & Automation.

### Which features declined?

- 📅 **Shifts** -XX.X% QoQ: while Users with a Job Done rose +X.X%.
- 📝 **Posts** -XX.X% QoQ: X.X% of Communication & Collaboration.

Jobs Done grew +X.X% QoQ in QN YYYY, a fourth quarter up in a row, though slower than in QN. Users with a Job Done (+X.X%) and Jobs per User (+X.X%) both grew: more people completed a job, and each of them completed a few more. Communication & Collaboration carried the quarter (+X.X% QoQ, XX.X% of all Jobs Done), while the three other tribes went down: Work & Automation (-X.X%), Channels (-X.X%) and People & Growth (-X.X%).

---

## By tribe

Jobs Done covers Communication & Collaboration (Content, Streams, ...), Work & Automation (...), Channels (Campaigns) and People & Growth (Surveys, Referrals).

### Communication & Collaboration

- Jobs Done: XXX.XM (+X.X% QoQ), XX.X% of all Jobs Done

Features by Jobs Done:
- 📄 **Content**: XXX.XM (+X.X% QoQ), XX.X% of the tribe
- 📡 **Streams**: XX.XM (-X.X% QoQ), XX.X% of the tribe
- 📆 **Company Events**: XX.XK (-XX.X% QoQ), 0.01% of the tribe

Top 3 companies by Jobs Done:
1. Company A (company-a), XX.XM (X.X% of Communication & Collaboration Jobs Done)
2. Company B (company-b), XX.XM (X.X% of Communication & Collaboration Jobs Done)
3. Company C (company-c), XX.XM (X.X% of Communication & Collaboration Jobs Done)

💡 <one or two sentences>

<next domain group...>

*Full breakdown available in the [Jobs Done dashboard](https://bi.lumapps.com/dashboards/product_bi::platform_jobs_done?tab_name=Overview&Overview+Time+Frame=1+quarter+ago+for+1+quarter).*
````

- **The five overview lines are the script's.** It prints them under *HIGH LEVEL
  OVERVIEW*: copy them as they are. The check rebuilds them from the data and fails on
  any difference, because a reader must find the same figures on the dashboard.
- **An introduction closes the overview**, after the two highlight lists: two or three
  sentences, as the platform introductions did before Q4 2026. Say what Jobs Done did
  over the quarter and how it sits against the quarters before (the quarter-by-quarter
  table); what Users with a Job Done and Jobs per User say about it (more people, or
  the same people doing more); then which tribes carried the move and which went the
  other way, with their change. Figures come from the totals or the tribes; a single
  feature's figures belong to the highlights. Name no customer here. The check fails
  without it.
- **Two highlight sections follow the overview**: *Which features grew the most?*
  and *Which features declined?* See *The highlights* below.
- **Title, opening and the dashboard line are fixed.** QoQ needs no definition line:
  the glossary the render adds above the overview defines it. Copy them, changing only
  the quarters.
- **A `*Data warning: ...*` line**, when the shared rules require one, goes right under
  the title. The HTML shows it in italics under the title, never as a banner.
- **One `###` block per tribe** (product domain group) in the scope sentence, ordered from
  largest to smallest by Jobs Done, as the script prints them.
- **Every feature of the group gets its line**, from largest to smallest. No selection.
  A feature not live yet in the quarter (the script lists them under *NOT LIVE IN THIS
  QUARTER*) gets no line and stays out of the scope sentence.
- **A feature is one name across both platforms**: Reactions adds up the reactions of
  LumApps and Beekeeper. No line names a platform.
- **AI & Search is read at product domain level**: Agents, Search and Ask AI are its
  features, never individual agents. It has no data on the consolidated explore yet.

## The highlights

The two sections pick from the script's *HIGHLIGHTS* lists, which rank every feature on
QoQ.

- **2 or 3 points per section.**
- One line per point: emoji, bold feature name, the QoQ, then after a colon one short
  clause taken from the feature's figures (a streak, users against volume, its weight in
  its group).
- **A small feature** (flagged `small`, under 1% of its group) may be picked, but its line
  must say its share, as in "0.4% of Communication & Collaboration".
- **Never list a feature from the *SET ASIDE* list.** Its QoQ is not like for like: it
  joined Jobs Done during the quarter, so the quarter before is backfill, or what it
  counts changed during the comparison (Search from 6 August 2026), or a reviewed step
  or spike makes it misleading.
- Growth goes in the first section, declines in the second; the sign must match.

## Steps and spikes

A QoQ can be exact and still mislead. The script reads every feature's weekly Jobs Done
over the quarter and the one before, and prints *STEPS AND SPIKES* when it finds:

- **a step**: a new level that stays (Search in August 2026, when suggestion clicks
  started being counted);
- **a spike**: one or two weeks far off the usual level (Workflows at the end of February
  2026, a single customer's two weeks).

For each, it names the organizations behind the change and says whether **one company
explains it** or it is **spread over many**.

**The detection never decides.** An anomaly nobody has reviewed yet is printed in
*ANOMALIES TO REVIEW BEFORE WRITING*, with its weekly series and the companies behind
it, and marked ⚠️ wherever the feature appears. It stays a normal candidate, and
`check_quarterly_article.py` fails until a verdict is recorded in `ANOMALY_REVIEWS`
(`jobs_done_common.py`):

- **Investigate first**: which companies (the script's list), which events (for a spread
  step, `fct_user_actions` by action type, as for Search). Show the findings to the
  analyst and let them decide. Never record a verdict on your own.
- **`misleading`**: the QoQ does not measure usage. The feature is set aside from the
  highlights, and its domain's 💡 line must say what happened and name the month the
  script prints, e.g. "Q1 included a spike at the end of February 2026 ..., almost entirely from
  <the one company>". One company: name it. A change in what is counted: say it only once
  confirmed, and record it in `TRACKING_CHANGES` as well.
- **`real`**: a genuine change in usage, such as a large customer's launch. The feature
  stays a normal candidate.

A verdict is keyed on (feature, week), the feature being both platforms together, so it
carries over to the next reports that still see the same anomaly.

## The domain block

1. **Heading**: `### <Domain group>`, the name only.
2. **The Jobs Done line**: `- Jobs Done: <JD> (<QoQ> QoQ), <share>% of all Jobs Done`,
   the group's figures as the script prints them.
3. **`Features by Jobs Done:`**, then one line per feature:
   `- <emoji> **<Feature>**: <JD> (<QoQ> QoQ), <share>% of the tribe`. Write a share
   under 0.1% with two decimals (0.04%), as the script prints it. Write a change under
   0.05% either way with two decimals (+0.04%), or "flat" when it rounds to 0.00%:
   never "+0.0%" or "-0.0%".
4. **`Top 3 companies by Jobs Done:`**, the group's top 3 from the script (*Top 3
   companies of the group*), each with its Jobs Done and its share of the group's Jobs
   Done: `1. <Company> (<slug>), <JD> (<share>% of <Domain group> Jobs Done)`. A company
   is one organization, labelled with its Salesforce account name and its slug: write
   each exactly as the script prints them. The list is internal: the analyst removes
   names before sharing further if needed. Skip the list only when the script prints no
   company for the group. The per-feature top 3 the script also prints is material for
   the 💡 line only.
5. **💡 One or two sentences** for the whole domain, saying what the lines above cannot
   say on their own: which feature drives the group's change, a streak of quarters up or
   down, users and volume moving apart (Jobs per User), one company carrying most of a
   feature. The script gives the streaks, users and frequencies. A streak marked "in
   every quarter of the window (4+ in a row)" fills the whole fetched window and may be
   longer: write "up in each of the last four quarters", never "a fifth quarter" or any
   count the script did not print. Every figure in it must come from the script output:
   "by more than 10%" fails the check, quote the changes themselves.
   Workflows has no users figure (always 0): never quote one for it.

## What the 💡 line must not do

- **No cause the data does not show.** No "likely year-end feedback" or "holiday season
  campaigns": the data carries no industry, segment or calendar reason. A streak or a
  concentration on one company is visible in the figures; a motive is not.
- **No "grew 5.7x faster than users".** A ratio of two percentages misleads as soon as
  one of them is small. Say that volume grew more than users, and give both.
- **Small features move a lot.** A +20% on a feature that is 2.5% of its group is worth
  saying with that share next to it. Never present it as
  the story of the quarter.
