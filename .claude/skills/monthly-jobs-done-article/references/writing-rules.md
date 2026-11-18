# Monthly article: writing rules

These rules are specific to the monthly article. Read `jobs_done_post/writing-rules.md`
first: tone, staying inside the metric, trend language, emojis, the scope sentence and
go-live dates are shared with the quarterly article. `jobs_done_post/check_article.py`
enforces what can be checked mechanically; the rest is on you.

The article reports LumApps and Beekeeper **combined**, as the consolidated dashboard
does: no platform section, no figure of one platform alone.

## Read the example article first
- [example-article.md](example-article.md) (in this skill): the expected shape with every
  figure replaced by a placeholder. Use it for structure only.

It follows the markdown skeleton: the title below, a `## High level overview` block, then
a `## Features of the month` section that opens on the scope sentence, introduces the
month's story in two or three sentences, holds their paragraphs and closes on the
dashboard line.

## Title (always the same shape)

```
# Jobs Done - <Month> <Year> Product Performance
```

A plain hyphen, and the `Product Performance` suffix is part of the title, not optional.

## Opening (always the same)

```
Hi Team, here is how our key product usage KPI, Jobs Done, performed in [Month] across LumApps and Beekeeper.

*Don't you know what "Jobs Done" metrics are? [Read this introduction](https://we.lumapps.com/we/ls/space/5070108616032256/team-engineering/article/ddf2b3ba-e590-4806-ac0a-00669376237c)*
```

The second line is a standing link to the Jobs Done explainer: carry it over verbatim
every month. **It is italicised**, like the closing line below.

## High level overview block

The five KPIs of the dashboard's Overview tab, in its order and with its names. The
script prints the five lines under *HIGH LEVEL OVERVIEW*: **copy them as they are**. The
check rebuilds them from the data and fails on any difference, because a reader must
find the same figures on the dashboard.

```
✅ Jobs Done: XXX.XM (+X.X% MoM)
👥 Users with a Job Done: X.XXM (+X.X% MoM)
🔁 Jobs per User: XX.X (+X.X% MoM)
📈 MAU: X.XXM (+X.X% MoM)
🎯 Reach: XX.X% (+X.X pts MoM)
```

Two or three plain sentences follow, on the month as a whole: the direction of Jobs
Done, and how it sits against the months before (the 13-month table), then what Users
with a Job Done and Jobs per User say about it (more people, or the same people doing
more). Their figures must come from the overview or the 13-month table of the script.

## Length

- **Readable in 2 minutes**, but each paragraph explains, it does not only list figures.
  Readers go to the dashboard for the full breakdown; the article tells them what
  happened and why. The articles up to September 2026 had one introduction and two or
  three explained features per platform: the combined article keeps that depth.

## Scope sentence (opens the features section)

Format and rules: *Scope sentence* in `jobs_done_post/writing-rules.md`.

`check_article.py` compares the sentence with the data for the report month and fails
on a missing or extra domain or feature, or on features out of size order.

## The five features of the month

**An introduction first.** After the scope sentence, two or three sentences tell the
story of the month, as the platform introductions did before November 2026:

1. What the total did, and which feature drove it, with its change (*BIGGEST MOVES*).
2. What went the other way, or added to it: the features that moved against the total,
   with the size of their move.
3. When it holds, a pattern across features: several features up for a third month in
   a row, a whole tribe moving together.

Any feature figure may appear here; the check traces it like the others. The check
fails without the introduction.

```
October held the level September reached. Content lost X.XXM Jobs Done (-X.X% MoM) and carried the small drop of the total. Ten other features grew, led by Spaces (+XXX.XK Jobs Done) and Posts (+XXX.XK), while Shortcuts and Campaigns grew for a third month in a row.
```

**Exactly five feature paragraphs**, picked among all features of both platforms (the
articles before November 2026 had 2 or 3 per platform). The script ranks the candidates
for you: do not re-rank them by eye, and do not go looking outside its lists.

Pick in this order:

1. **BIGGEST MOVES OF THE MONTH**: take the top 3, and lead with them. This list compares each feature
   with its own previous month and ranks it on its change in Jobs Done. A feature that
   lost 1.68M Jobs Done *is* the story, even at a modest -1.3% MoM. A feature marked
   "moved AGAINST the total" went the other way from the total: worth saying.
2. **STRONGEST RELATIVE MOVES**: at most two, and only if they tell a story. These move
   sharply in % but barely shift the total, so never lead with one.
3. **NEWLY TRACKED FEATURES**: worth one paragraph the first time it appears in an
   article, then leave it alone until it has real volume. Say it is new and give the raw
   numbers; do not read a trend into a few months of history.

**A short history does not mean a recent launch**: see *Go-live dates* in
`jobs_done_post/writing-rules.md`.

When these lists hold fewer than five good candidates, take the next ones down
*BIGGEST MOVES*: it always lists at least five features. Everything else gets no mention. Stable features with unremarkable numbers get no mention.

Never justify a pick with "biggest MoM %" alone: that metric systematically promotes
small features. In August 2026 it ranked Videos (-26.7%, about -110K Jobs Done) above
Content (-7.1%, -8.51M). Never write a feature's change as a share of the total's change
either: when ups and downs offset, it runs far above 100% (Content was "306% of the
change" in October 2026). Give the feature's own change, in % or in Jobs Done.

For each feature: two sentences, three at most, opening on its emoji and its bold name.

1. **What happened**: Jobs Done, its change (in % and, for a large feature, in Jobs
   Done), and how the month sits against recent ones (consecutive months up or down,
   after last month's move).
2. **What explains it**: split the move between people and depth. Users with a Job Done
   say whether more or fewer people did the job; Jobs per User say whether each of them
   did it more or less often. Say which one carried the move, in plain words ("more
   people opened a campaign, each one opening fewer"). When it adds something, give the
   feature's Reach or its share of its tribe.

Pick the context that tells the story; do not list every metric. A feature's Reach is
the dashboard's, with its *Feature* filter: name it "Reach".

```
📢 **Campaigns** grew +XX.X% MoM to XXX.XK Jobs Done, a third month up in a row. Users with a Job Done jumped +XX.X% to XXX.XK while Jobs per User fell -XX.X%: many more people opened a campaign, each one opening fewer.
```

### The Agents paragraph (experimental, once AI & Search reaches the explore)

When Agents is covered, it gets one 🤖 paragraph, which counts as one of the five:

1. One sentence on all agents together: the **Agents** total Jobs Done and its MoM, from
   the feature breakdown.
2. Then one or two agents, taken from the *AGENTS DETAIL* lists of the script (largest,
   biggest growth, widest adoption). Give each one figure that says why it stands out:
   its share of all agent Jobs Done, its growth in Jobs Done, or how many organizations
   use it.

Name an agent exactly as the script prints it, customer name included: the analyst
removes it before publishing if needed. Prefer absolute figures for a single agent. At a
few hundred Jobs Done, "+542.9%" says less than "up 76 Jobs Done". Do not pick the agent
literally named "Agents": its name says nothing to a reader.

## No year-over-year

The dashboard's Overview tab shows no year-over-year figure, so the article has none:
not in the overview, not in a paragraph, not paraphrased ("nearly double last
October"). The check fails on it.

## Editorial note from the analyst

`--note "<text>"` prints a block at the top of the report. When it is there, treat it as
a steer that outranks the ranking above: if it asks for a feature to be covered, cover it
even when the lists would have dropped it. Keep it to the length the data supports.

```
python3 jobs_done_post/prepare_data.py --note "Campaigns had a big launch this month, worth a mention"
```

## Close the features section

The dashboard line is fixed: copy it as it is.

```
*Full breakdown available in the [Jobs Done dashboard](https://bi.lumapps.com/dashboards/product_bi::platform_jobs_done?tab_name=Overview&Overview+Time+Frame=1+month+ago+for+1+month).*
```

It opens the consolidated dashboard on its Overview tab, for the last month, both
platforms together: the figures of the article.
