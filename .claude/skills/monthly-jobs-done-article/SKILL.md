---
name: monthly-jobs-done-article
description: Write the monthly Jobs Done article covering LumApps and Beekeeper combined, from fresh Looker data on the consolidated dashboard's explore, check it against the data, and render it as the HTML block for the intranet.
argument-hint: "[YYYY-MM] [editorial note]"
disable-model-invocation: true
allowed-tools: Bash(python3 jobs_done_post/prepare_data.py), Bash(python3 jobs_done_post/prepare_data.py *), Bash(python3 jobs_done_post/check_article.py *), Bash(python3 jobs_done_post/render_monthly_html.py *)
---

# Monthly Jobs Done article

Arguments: `$ARGUMENTS`

- A leading `YYYY-MM` is the report month, passed as `--month`. Without one, the script
  targets the last complete calendar month.
- Anything else is the analyst's editorial note, passed as `--note "<text>"`.

Run everything from the repository root. The scripts resolve `data/` from their own
location, so the paths below work as written.

The article reports LumApps and Beekeeper combined, and every figure in it must match the
consolidated dashboard (`product_bi::platform_jobs_done`, Overview tab, Time Frame
"1 month ago for 1 month"): Jobs Done and users over the calendar month, MAU and Reach
over its last 28 days. The source of truth is that dashboard and its explore: see *Where the
data comes from* in `jobs_done_post/CLAUDE.md`.

## Steps

1. **Fetch and analyse, always on fresh data.** Never reuse data already on disk,
   never pass `--no-fetch`: Looker revises history and upstream fixes land between runs.
   The check refuses data more than 24 hours old; if it does, re-run this step.

   ```bash
   python3 jobs_done_post/prepare_data.py [--month YYYY-MM] [--note "<text>"]
   ```

   It pulls fresh data from Looker into `jobs_done_post/data/` and prints the analysis:
   the five overview lines to copy as they are, the 6-month totals, the feature
   breakdown by domain group with MoM, users, Jobs per User, Reach and trend, and the
   three ranked lists that decide what to write about. If it fails on credentials or a
   403, stop and point the user to the setup section of `jobs_done_post/README.md`. Do
   not work around it.

   **If it prints *DATA VOLUME ALERTS* with alerts not reviewed, stop there.** The data
   itself may be broken: a day far off its usual volume in a cell. For each one, look
   for a reason (a public holiday in the cell's region, a known incident upstream),
   show the user what you found, and ask for the verdict: `expected` or `incident`.
   Record it in `VOLUME_REVIEWS` in `jobs_done_post/jobs_done_common.py`, then re-run
   the script. Never decide the verdict yourself. An `incident` verdict means the
   article opens on a `*Data warning: ...*` line (see the shared writing rules).

2. **Load the context.** Read these before writing a word:
   - `jobs_done_post/CLAUDE.md`: where the data comes from, what the metrics mean, how
     to read them, and the permanent data limitations.
   - `jobs_done_post/writing-rules.md`: the rules shared with the quarterly article
     (tone, staying inside the metric, trend language, emoji, scope sentence, go-live).
   - [references/writing-rules.md](references/writing-rules.md): the monthly rules
     (structure, the overview, the five features, the Agents paragraph, closing line).
   - [references/example-article.md](references/example-article.md): the expected
     shape, figures removed.

3. **Write the article** from the script output only. Do not restate an old month from
   memory or from a past article: Looker revises history, and articles before November
   2026 read other sources.

4. **Save it** as the Markdown draft `jobs_done_post/data/drafts/article_YYYY-MM.md`
   (gitignored, never handed over: the HTML is the deliverable). A hook runs
   `check_article.py` on every save and sends failures back. Fix each one and save again
   until it passes. If a figure fails and the prose looks right, the data may be stale:
   re-run step 1 before rewriting. Once the check passes, the same hook runs
   `render_monthly_html.py`, which writes `jobs_done_post/articles/article_YYYY-MM.html`.
   If the hook did not run (manual edit), run both by hand:

   ```bash
   python3 jobs_done_post/check_article.py jobs_done_post/data/drafts/article_YYYY-MM.md
   python3 jobs_done_post/render_monthly_html.py jobs_done_post/data/drafts/article_YYYY-MM.md
   ```

   Never edit the HTML by hand: fix the draft and save it again. Never publish the HTML
   as an Artifact: an agent name can be a customer name, so it stays a local file.

5. **Hand it over.** Give the path of the HTML (the deliverable, to paste as an HTML
   widget), never the draft, then list the check's warnings (quantity words such as
   "most" or "a third") with the figures behind each, so the user can confirm them. Those
   are judgements the script cannot make.
