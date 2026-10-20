# Monthly article: writing rules

These rules are specific to the monthly article. Read `jobs_done_post/writing-rules.md`
first: tone, staying inside the metric, trend language, emojis, the scope sentence and
go-live dates are shared with the quarterly article. `jobs_done_post/check_article.py`
enforces what can be checked mechanically; the rest is on you.

## Read the example article first
- [example-article.md](example-article.md) (in this skill): the August 2026 article with
  every figure replaced by a placeholder. Use it for structure and voice only.

It follows the markdown skeleton: the title below, a `## High level overview` block, then
one `##` section per platform, each opening on its scope sentence (added in September
2026, so the example lacks it) and closing on its dashboard line.

## Title (always the same shape)

```
# Jobs Done - <Month> <Year> Product Performance
```

A plain hyphen, and the `Product Performance` suffix is part of the title, not optional.

## Opening (always the same)

```
Hi Team, here is how our key product usage KPI, Jobs Done, performed in [Month] across two platforms.

*Don't you know what "Jobs Done" metrics are? [Read this introduction](https://we.lumapps.com/we/ls/space/5070108616032256/team-engineering/article/ddf2b3ba-e590-4806-ac0a-00669376237c)*
```

The second line is a standing link to the Jobs Done explainer — carry it over verbatim
every month. **It is italicised**, like the two closing lines below.

## High level overview block
```
✅ Jobs Done
- LumApps XXX.XM (+X.X% MoM, +X.X% YoY)
- Beekeeper XX.XM (+X.X% MoM, +X.X% YoY)

👨‍🦲 MAU
- LumApps X.XXM (+X.X% MoM)
- Beekeeper XXXK (+X.X% MoM)
```

## Length

- **Short.** The article is a quick summary — readers go to the dashboard for details. Aim for something readable in 2 minutes.

## Scope sentence (opens each platform section)

Format and rules: *Scope sentence* in `jobs_done_post/writing-rules.md`.

`check_article.py` compares each sentence with the data for the report month and fails
on a missing or extra domain or feature. From September 2026 on, it also fails if the
sentence is missing.

## What to cover — and what to skip

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

**A short history does not mean a recent launch**: see *Go-live dates* in
`jobs_done_post/writing-rules.md`.

Everything else gets no mention. Stable features with unremarkable numbers get no mention.

Never justify a pick with "biggest MoM %" alone — that metric systematically promotes
small features. In August 2026 it ranked Videos (-26.7%, 1.1% of the change) above
Content (-7.1%, 85.5% of it).

For each feature you do cover: one or two sentences max. Include the number, the direction, and one piece of context: consecutive months up or down, frequency versus users, a known seasonal pattern, or how the month sits against recent months. Don't list every metric, pick the one that tells the story.

### The Agents paragraph (LumApps, experimental, from September 2026)

When Agents is covered, it gets one 🤖 paragraph, which counts as one of the 2–3 features:

1. One sentence on all agents together: the **Agents** total Jobs Done and its MoM, from
   the feature breakdown.
2. Then one or two agents, taken from the *AGENTS DETAIL* lists of the script (largest,
   biggest growth, widest adoption). Give each one figure that says why it stands out:
   its share of all agent Jobs Done, its growth in Jobs Done, or how many tenants use it.

Name an agent exactly as the script prints it, customer name included: the analyst
removes it before publishing if needed. Prefer absolute figures for a single agent. At a
few hundred Jobs Done, "+542.9%" says less than "up 76 Jobs Done". Do not pick the agent
literally named "Agents": its name says nothing to a reader.

```
🤖 **Agents** reached 3.9K Jobs Done (-33.5% MoM). Routing agent carries 41.8% of them, across 8 customers, while CSE Request Assistant appeared this month with 164 Jobs Done.
```

## Year-over-year: overview only

**YoY is a platform-level figure only.** It is allowed in two places:

1. the High level overview block, and
2. the opening paragraph of a platform section, when it carries the angle of the month
   (e.g. framing a down month against strong annual growth).

**Never in a feature paragraph.** Do not put a YoY figure there, and do not paraphrase
one either ("over twelve months it is down 7%", "nearly double last August").

These are monthly articles: the feature commentary explains the month, and a YoY figure
pulls the reader onto a different time scale. This came out of the review of the June
and July 2026 issues, so it is a team convention.

## Editorial note from the analyst

`--note "<text>"` prints a block at the top of the report. When it is there, treat it as
a steer that outranks the ranking above: if it asks for a feature to be covered, cover it
even when the lists would have dropped it. Keep it to the length the data supports.

```
python3 jobs_done_post/prepare_data.py --note "Agents was added to LumApps Jobs Done, worth a mention"
```

## Close each company section

Both links are fixed — copy them as they are:

```
*Full breakdown available in the [LumApps Jobs Done dashboard](https://bi.lumapps.com/dashboards/base::jobs_done?tab_name=Jobs+Done&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
*Full breakdown available in the [Beekeeper Jobs Done dashboard](https://bi.lumapps.com/dashboards/product_bi::jobs_done?tab_name=Jobs+Done&Tenant+Selection=commercial%5E_all&Tenant+Subdomain=&Company+Size=&Industry=&+Commercial+Phase=&Commercial+Swarm=&Is+CS+Ops+Managed+%28Yes+%2F+No%29=&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
```

Both URLs open on the *Jobs Done* tab filtered to Communication & Collaboration, which
is where the article's commentary sits. LumApps now also has AI & Search; the link is
deliberately left on C&C.
