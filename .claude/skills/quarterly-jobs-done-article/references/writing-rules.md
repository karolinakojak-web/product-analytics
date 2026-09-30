# Quarterly article: writing rules

These rules are specific to the quarterly article. Read `jobs_done_post/writing-rules.md`
first: tone, staying inside the metric, trend language, emojis, the scope sentence and
go-live dates are shared with the monthly article. `jobs_done_post/check_quarterly_article.py`
enforces what can be checked mechanically; the rest is on you.

## What a quarter measures

The quarterly article does not read the monthly 28-day window. `prepare_quarterly.py`
measures the whole quarter:

| | |
|---|---|
| Jobs Done | daily Jobs Done summed over every day of the quarter |
| Users Completing Jobs | unique users who completed that job at least once in the quarter |

There is no MAU in the quarterly article: the users figure is Users Completing Jobs over
the quarter, at platform level in the overview and per feature in the blocks. Call it
"Users Completing Jobs", never "active users", which reads as the whole active base.
Users do not add up across features or domain groups: only Jobs Done does.

Every change compares the quarter with the one before (QoQ). No year-over-year figure.

## Structure

````
# Jobs Done - Q2 2026 Product Performance

Hi Team, here is how our key product usage KPI, Jobs Done, performed in Q2 2026 across two platforms. Every change compares with Q1 2026.

*Don't you know what "Jobs Done" metrics are? [Read this introduction](https://we.lumapps.com/we/ls/space/5070108616032256/team-engineering/article/ddf2b3ba-e590-4806-ac0a-00669376237c)*

---

## High level overview

✅️ Jobs Done
- LumApps 385.8M (+7.2% QoQ)
- Beekeeper 114.8M (-0.9% QoQ)

👥 Users Completing Jobs
- LumApps 3.49M (+5.6% QoQ)
- Beekeeper 788.1K (+1.8% QoQ)

### Which product domains grew the most?

- 👍 **Reactions** (Beekeeper) +13.4% QoQ: a third quarter up in a row, with more people reacting.
- 🗂️ **Forms** (Beekeeper) +10.5% QoQ: up in each of the last four quarters.
- 📄 **Content** (LumApps) +8.2% QoQ: 95.0% of Communication & Collaboration Jobs Done.

### Which product domains declined?

- ⚙️ **Workflows** (Beekeeper) -13.5% QoQ: the largest drop of Work & Automation.
- 📝 **Posts** (LumApps) -13.4% QoQ: fewer people posted, and less often.

Continue reading for a detailed breakdown of each product domain.

---

## LumApps

Jobs Done covers Communication & Collaboration (Content, Spaces, Posts, Reactions, Videos, Comments).

<one to three sentences on the platform's quarter>

### Communication & Collaboration

<one sentence: the group's Jobs Done and QoQ>

⬆️ 📄 **Content** (95.0% of Communication & Collaboration Jobs Done)
- Jobs Done: 359.6M (+8.2% QoQ)
- Users Completing Jobs: 3.46M (+5.5% QoQ)
- Top 3 companies by Jobs Done:
  1. Company A (company-a), 21.6M (6.0% of Content Jobs Done)
  2. Company B (company-b), 17.0M (4.7% of Content Jobs Done)
  3. Company C (company-c), 15.5M (4.3% of Content Jobs Done)

💡 <one or two sentences>

<next feature, next group...>

*Full breakdown available in the [LumApps Jobs Done dashboard](...).*

---

## Beekeeper

<same shape>
````

- **Two highlight sections follow the overview**: *Which product domains grew the most?*
  and *Which product domains declined?* See *The highlights* below.
- **Title, opening, intro link and the two dashboard lines are fixed.**
  Copy them, changing only the quarters. The dashboard lines are the monthly ones,
  character for character (see the monthly rules, *Close each company section*).
- **One `###` section per product domain group** in the scope sentence, ordered from
  largest to smallest by Jobs Done, as the script prints them.
- **Every feature of the scope gets its own block**, under its group, from largest to
  smallest. No selection: this is where the quarterly differs most from the monthly.
  A feature not live yet in the quarter (the script lists them under *NOT LIVE IN THIS
  QUARTER*) gets no block and stays out of the scope sentence.
- **AI & Search is read at product domain level**: Agents and Search are its features,
  never individual agents.

## The highlights

The two sections pick from the script's *HIGHLIGHTS* lists, which rank the features of
both platforms together on QoQ.

- **2 or 3 points per section**, and **both platforms in each** whenever both have a
  candidate. Two points are enough.
- One line per point: emoji, bold feature name, platform in brackets, the QoQ, then after
  a colon one short clause taken from the feature's figures (a streak, users against
  volume, its weight in its group).
- **A small feature** (flagged `small`, under 1% of its group) may be picked, but its line
  must say its share, as in "0.4% of Communication & Collaboration".
- **Never list a feature from the *SET ASIDE* list.** Its QoQ is not like for like: it
  joined Jobs Done during the quarter, so the quarter before is backfill, or what it
  counts changed during the comparison (Search from 6 August 2026).
- Growth goes in the first section, declines in the second; the sign must match.

## Steps and spikes

A QoQ can be exact and still mislead. The script reads every feature's weekly Jobs Done
over the quarter and the one before, and prints *STEPS AND SPIKES* when it finds:

- **a step**: a new level that stays (Search in August 2026, when suggestion clicks
  started being counted);
- **a spike**: one or two weeks far off the usual level (Workflows at the end of February
  2026, a single customer's two weeks).

For each, it names the companies behind the change and says whether **one company
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
  highlights, and its 💡 line must say what happened and name the month the script
  prints, e.g. "Q1 included a spike at the end of February 2026 ..., almost entirely from
  <the one company>". One company: name it. A change in what is counted: say it only once
  confirmed, and record it in `TRACKING_CHANGES` as well.
- **`real`**: a genuine change in usage, such as a large customer's launch. The feature
  stays a normal candidate.

A verdict is keyed on (platform, feature, week), so it carries over to the next reports
that still see the same anomaly.

## The feature block

1. **Heading**: direction arrow, feature emoji, bold name, share of its group's Jobs Done.
   ⬆️ when Jobs Done grew QoQ, ⬇️ when it fell, ➡️ when it moved by less than 0.05%.
   Write such a change with two decimals (+0.04%), or "flat" when it rounds to 0.00%:
   never "+0.0%" or "-0.0%".
2. **Jobs Done** with its QoQ.
3. **Users Completing Jobs** with its QoQ. For Beekeeper Workflows, write
   `- Users Completing Jobs: not tracked`: the users metric is always 0 there.
4. **Top 3 companies by Jobs Done**, in the script's order, each with its Jobs Done and
   its share of the feature's Jobs Done. Write each name and slug exactly as the script
   prints them. The list is internal: the analyst removes names before sharing further if
   needed. Skip the list only when the script prints no company for the feature.
5. **💡 One or two sentences** that say what the figures above cannot say on their own:
   users and volume moving apart (frequency), a streak of quarters up or down, one
   company carrying most of the feature. The script gives the streaks and frequencies.
   A streak marked "in every quarter of the window (4+ in a row)" fills the whole fetched
   window and may be longer: write "up in each of the last four quarters", never "a
   fifth quarter" or any count the script did not print.

## What the 💡 line must not do

- **No cause the data does not show.** No "likely year-end feedback" or "holiday season
  campaigns": the data carries no industry, segment or calendar reason. A streak or a
  concentration on one company is visible in the figures; a motive is not.
- **No "grew 5.7x faster than users".** A ratio of two percentages misleads as soon as
  one of them is small. Say that volume grew more than users, and give both.
- **Small features move a lot.** A +20% on a feature that is 2.5% of its group is worth
  saying with that share next to it, as the heading already does. Never present it as
  the story of the quarter.
