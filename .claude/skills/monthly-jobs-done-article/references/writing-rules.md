# Monthly article: writing rules

Every rule below applies to the monthly article. `jobs_done_post/check_article.py` enforces
the ones that can be checked mechanically; the rest are on you.

## Read the reference articles first
- `jobs_done_post/articles/article_2026-07.md` and `jobs_done_post/articles/article_2026-06.md` — the two most recent, use these as the primary template
- `jobs_done_post/articles/article_2026-05.md` — same structure, slightly longer feature commentary
- `references/april-2026.md` (in this skill) — useful for voice reference

All three follow the same markdown skeleton: the title below, a `## High level overview`
block, then one `##` section per platform, each opening on its scope sentence (added in
September 2026, so the reference articles lack it) and closing on its dashboard line.

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

## Scope sentence (opens each platform section)

Each `## LumApps` and `## Beekeeper` section starts with one sentence listing the product
domain groups Jobs Done covers, each with its features, before any commentary:

```
Jobs Done covers Communication & Collaboration (Content, Posts, Comments, Reactions, Spaces, Videos) and AI & Search (Agents).

Jobs Done covers Communication & Collaboration (Streams, Chats, Comments, Reactions, Documents, Company Events), Work & Automation (Tasks, Forms, Shifts, Shortcuts, Workflows), People & Growth (Surveys, Referrals) and Channels (Campaigns).
```

⚠️ **Check the scope every month, do not copy last month's sentence.** The scope is
growing: AI & Search joined LumApps in September 2026 and another domain is on the way.
Rebuild both sentences from the domain groups and features in the script output. Within a
domain, list the features from largest to smallest by Jobs Done. A feature listed in
`GO_LIVE` in `jobs_done_post/check_article.py` (currently Agents, from September 2026) stays out until
its go-live month, even though its backfilled data already shows up.

`check_article.py` compares each sentence with the data for the report month and fails
on a missing or extra domain or feature. From September 2026 on, it also fails if the
sentence is missing.

## Tone and length
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

## Claims must stay inside the metric

Jobs Done measures **one key action per feature**, on a **subset** of the features that
exist. Every figure is a statement about Jobs Done, never about the platform. Say which.

| Do not write | Write |
|---|---|
| "Beekeeper's biggest feature" | "the largest of the Beekeeper features we track" |
| "used by 82.5% of active users" | "82.5% of active users completed a Streams job this month" |
| "the only feature to grow" | "the only one of the tracked features to grow" |

The arithmetic behind those phrasings is right; the scope the words imply is not.
"used by" suggests general usage of the feature, which the metric does not measure. The
same caution applies to any comparative or coverage claim, and to the UCJ/MAU thresholds
below: they describe adoption of a tracked action, not of a feature.

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

⚠️ `jobs_done_post/articles/article_2026-06.md` and `jobs_done_post/articles/article_2026-07.md` still carry
feature-level YoY, since they predate the correction. Follow them for style, not on this
point.

## Editorial note from the analyst

`--note "<text>"` prints a block at the top of the report. When it is there, treat it as
a steer that outranks the ranking above: if it asks for a feature to be covered, cover it
even when the lists would have dropped it. Keep it to the length the data supports.

```
python3 jobs_done_post/prepare_data.py --note "Agents was added to LumApps Jobs Done, worth a mention"
```

## Trend language rules
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
  Describing a feature's current size is fine as a statement about now rather than a
  ranking of months, but keep it inside the metric: "the largest of the features we
  track", not "Beekeeper's biggest feature".

  ⚠️ The June and July 2026 articles contain "best KPI of the current year" and
  "second-best month of the year". They predate this rule. Do not copy them on this point.

## Emojis for features

This list is authoritative — use it even if an older article used a different glyph.
📄 Content · 💬 Chats · 📡 Streams · 🏠 Spaces · 📝 Posts · 🎬 Videos · 👍 Reactions · 📊 Surveys · ☑️ Tasks · 📅 Shifts · 🗂️ Forms · 🔗 Shortcuts · 📢 Campaigns · 📆 Company Events · ⚙️ Workflows · 🗨️ Comments · 📁 Documents · 🤝 Referrals · 🤖 Agents

## Close each company section

Both links are fixed — copy them as they are:

```
*Full breakdown available in the [LumApps Jobs Done dashboard](https://bi.lumapps.com/dashboards/base::jobs_done?tab_name=Jobs+Done&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
*Full breakdown available in the [Beekeeper Jobs Done dashboard](https://bi.lumapps.com/dashboards/product_bi::jobs_done?tab_name=Jobs+Done&Tenant+Selection=commercial%5E_all&Tenant+Subdomain=&Company+Size=&Industry=&+Commercial+Phase=&Commercial+Swarm=&Is+CS+Ops+Managed+%28Yes+%2F+No%29=&Time+Frame=13+month+ago+for+13+month&Product+Domain+Group=Communication+%26+Collaboration).*
```

Both URLs open on the *Jobs Done* tab filtered to Communication & Collaboration, which
is where the article's commentary sits. LumApps now also has AI & Search; the link is
deliberately left on C&C.
