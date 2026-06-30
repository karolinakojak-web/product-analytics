# Jobs Done — Monthly Article Generator

## How to proceed

1. Run `python3 prepare_data.py` from this folder. It prints full analytics to the terminal.
2. Read the output — platform totals with MAU, feature MoM/YoY/frequency, 13-month trend classification, and notable movers for both companies.
3. Write the article following the style rules below.
4. Save as `article_YYYY-MM.md` in this folder.

**Optional:** `python3 prepare_data.py --month 2026-04` to target a specific month.

---

## Data files — structure and naming

All CSV files live in the `data/` subfolder. Four files per reporting period:

| File pattern | Content |
|---|---|
| `lumapps_all_YYYY-MM.csv` | Lumapps platform totals: Jobs Done, Users Completing Jobs, MAU |
| `beekeeper_all_YYYY-MM.csv` | Beekeeper platform totals: Jobs Done, Users Completing Jobs, MAU |
| `lumapps_features_YYYY-MM.csv` | Lumapps feature-level breakdown (C&C only by design) |
| `beekeeper_features_YYYY-MM.csv` | Beekeeper feature-level breakdown (all domains) |

**Lumapps scope:** Jobs Done covers Communication & Collaboration only — by design, not a data gap.

**Beekeeper scope:** all domain groups included — Communication & Collaboration, Work & Automation, Channels, People & Growth.

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
- `article_2026-05.md` — the current approved style (most recent, use this as the primary template)
- April 2026 article pasted at the bottom of this file — useful for voice reference

### Opening (always the same)
```
Hi Team,

Here is how our key product usage KPI, Jobs Done, performed in [Month] across two platforms.
```

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
- No corporate filler. No "it is worth noting". No "one could argue".

### What to cover — and what to skip
**Only cover features with the strongest MoM change or biggest influence on the overall result.** Skip everything else. 2–3 features per company is usually enough. Stable features with unremarkable numbers get no mention.

For each feature you do cover: one or two sentences max. Include the number, the direction, and one piece of context (YoY comparison, consecutive months, frequency signal, seasonal pattern). Don't list every metric — pick the one that tells the story.

### Trend language rules
- Do not use "recovered" or "bounced back" based on a single positive MoM. Check 3+ months of context. A feature is only recovering if it is returning toward a prior reference level, not just up from a recent dip.
- Do not include notes like "this needs investigation" or "verify before publishing" — that is the analyst's job before the article goes out. If a number is not ready to publish, leave it out entirely.
- Do not overinterpret. Describe what the data shows; don't speculate about causes unless they are clearly visible in the numbers (e.g. a known seasonal pattern, a consecutive streak).

### LumApps scope note (always include)
Add this after the LumApps opening line:

> Note that for LumApps, Jobs Done currently covers only a handful of features and only within the Communication & Collaboration product domain, so a decline does not indicate a platform-wide pullback but just a change in specific product domain engagement.

### Emojis for features
📄 Content · 💬 Chats · 📡 Streams · 🏠 Spaces · 📝 Posts · 🎬 Videos · 👍 Reactions · 📊 Surveys · ☑️ Tasks · 📅 Shifts · 🗂️ Forms · 🔗 Shortcuts · 📢 Campaigns · 📆 Company Events · ⚙️ Workflows

### Close each company section
`Full breakdown available in the [LumApps / Beekeeper Jobs Done dashboard].`

### Data notes (end of article)
One short paragraph. State only permanent limitations (Workflows users metric) and anything anomalous that was excluded from this issue. Do not describe what was investigated or not.

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
