# Jobs Done articles: shared writing rules

These rules apply to every Jobs Done article, monthly and quarterly. Each skill adds its
own rules on structure and selection:

- `.claude/skills/monthly-jobs-done-article/references/writing-rules.md`
- `.claude/skills/quarterly-jobs-done-article/references/writing-rules.md`

The constants they rely on (emoji per feature, go-live months, banned wording) live in
`jobs_done_common.py`, which both article checks import.

## Tone and length
- **Engaged and human** — write like a colleague sharing news, not like a dashboard export.
- **Positive framing** where the data allows it. Lead with what's working before what isn't.
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

## Emojis for features

This list is authoritative — use it even if an older article used a different glyph.
📄 Content · 💬 Chats · 📡 Streams · 🏠 Spaces · 📝 Posts · 🎬 Videos · 👍 Reactions · 📊 Surveys · ☑️ Tasks · 📅 Shifts · 🗂️ Forms · 🔗 Shortcuts · 📢 Campaigns · 📆 Company Events · ⚙️ Workflows · 🗨️ Comments · 📁 Documents · 🤝 Referrals · 🤖 Agents · 🔍 Search

## Scope sentence (opens each platform section)

Each `## LumApps` and `## Beekeeper` section starts with one sentence listing the product
domain groups Jobs Done covers, each with its features, before any commentary:

```
Jobs Done covers Communication & Collaboration (Content, Posts, Comments, Reactions, Spaces, Videos) and AI & Search (Search, Agents).

Jobs Done covers Communication & Collaboration (Streams, Chats, Comments, Reactions, Documents, Company Events), Work & Automation (Tasks, Forms, Shifts, Shortcuts, Workflows), People & Growth (Surveys, Referrals) and Channels (Campaigns).
```

⚠️ **Check the scope every issue, do not copy the last one's sentence.** The scope is
growing: AI & Search joined LumApps in September 2026 and another domain is on the way.
Rebuild both sentences from the domain groups and features in the script output. Within a
domain, list the features from largest to smallest by Jobs Done. A feature listed in
`GO_LIVE` in `jobs_done_post/jobs_done_common.py` (currently Agents and Search, from September 2026) stays out until
its go-live month (for a quarter: until the quarter that contains it), even though its
backfilled data already shows up.

## Go-live dates

**A short history does not mean a recent launch.** The explore backfills data when a
feature is onboarded, so a short history flags backfilled features, not new ones. Check the
real go-live date before calling anything new. Known cases: **Agents** and **Search** (AI & Search,
LumApps) show history from 2025 or early 2026 but were only added to Jobs Done in
**September 2026**. They must not appear in any article before then.
