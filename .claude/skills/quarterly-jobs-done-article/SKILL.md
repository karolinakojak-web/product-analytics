---
name: quarterly-jobs-done-article
description: Write the quarterly Jobs Done article covering LumApps and Beekeeper combined, with one block per domain group (its features and its top 3 companies), from fresh Looker data on the consolidated dashboard's explore, check it against the data, and render it as the HTML block for the intranet.
argument-hint: "[YYYY-QN] [editorial note]"
disable-model-invocation: true
allowed-tools: Bash(python3 jobs_done_post/prepare_quarterly.py), Bash(python3 jobs_done_post/prepare_quarterly.py *), Bash(python3 jobs_done_post/check_quarterly_article.py *), Bash(python3 jobs_done_post/render_quarterly_html.py *)
---

# Quarterly Jobs Done article

Arguments: `$ARGUMENTS`

- A leading `YYYY-QN` (for example `2026-Q3`) is the report quarter, passed as
  `--quarter`. Without one, the script targets the last complete calendar quarter.
- Anything else is the analyst's editorial note, passed as `--note "<text>"`.

Run everything from the repository root.

The article reports LumApps and Beekeeper combined, and every figure of its overview must
match the consolidated dashboard (`product_bi::platform_jobs_done`, Overview tab,
Time Frame "1 quarter ago for 1 quarter"). The source of truth is that dashboard and its explore:
see *Where the data comes from* in `jobs_done_post/CLAUDE.md`.

## Steps

1. **Fetch and analyse, always on fresh data.** Never reuse data already on disk,
   never pass `--no-fetch`: Looker revises history and upstream fixes land between runs.
   The check refuses data more than 24 hours old; if it does, re-run this step.

   ```bash
   python3 jobs_done_post/prepare_quarterly.py [--quarter YYYY-QN] [--note "<text>"]
   ```

   It pulls the quarter and the four before it into `jobs_done_post/data/quarterly/`, then
   prints the five overview lines to copy as they are, the totals quarter by quarter,
   each domain group with its top 3 companies, every feature by domain group with its
   QoQ, users, Jobs per User, streak and top 3 companies, the features not live yet in
   the quarter, and the *HIGHLIGHTS* candidates for the two highlight sections, with the
   features set aside because their QoQ is not like for like, and the *STEPS AND SPIKES*
   in weekly Jobs Done with the companies behind each.

   **If it prints *ANOMALIES TO REVIEW BEFORE WRITING*, stop there.** For each anomaly,
   investigate (see *Steps and spikes* in the quarterly rules), show the user what you
   found, and ask whether its QoQ is misleading or a real change in usage. Record their
   verdict in `ANOMALY_REVIEWS` in `jobs_done_post/jobs_done_common.py`, then re-run the
   script. Never decide the verdict yourself.

   **If it prints *DATA VOLUME ALERTS* with alerts not reviewed, stop there.** The data
   itself may be broken: a day far off its usual volume in a cell. For each one,
   look for a reason (a public holiday in the cell's region, a known incident upstream),
   show the user what you found, and ask for the verdict: `expected` or `incident`.
   Record it in `VOLUME_REVIEWS` in `jobs_done_post/jobs_done_common.py`, then re-run
   the script. Never decide the verdict yourself. An `incident` verdict means the
   article opens on a `*Data warning: ...*` line (see the shared writing rules).

   **If it prints *COMPANY DIRECTORY ISSUES*, tell the user** in your hand-over: the
   company join inflating totals (duplicate rows upstream), an organization with no
   account name left out of a top 3, or an organization of a top 3 under the catch-all
   Salesforce account "LumApps", whose name is then not its own. The article's figures
   are unaffected, but the issue must be reported, and a wrong or missing name may
   mislead or hide a customer. If it warns that the quarter is not over, stop and tell the
   user: the figures would be partial. If it fails on credentials or a 403, point the
   user to the setup section of `jobs_done_post/README.md`.

2. **Load the context.** Read these before writing a word:
   - `jobs_done_post/CLAUDE.md`: where the data comes from, what the metrics mean and
     the permanent data limitations.
   - `jobs_done_post/writing-rules.md`: the rules shared with the monthly article
     (tone, staying inside the metric, trend language, emoji, scope sentence, go-live).
   - [references/writing-rules.md](references/writing-rules.md): what a quarter
     measures, the quarterly structure, the highlights, the domain block, and what the
     💡 line must not do.

3. **Write the article** from the script output only, in English, in the Markdown shape
   of the rules. Every domain group of the scope gets its block, and every feature its
   line in it; there is no selection.

4. **Save it** as the Markdown draft `jobs_done_post/data/drafts/quarterly_YYYY-QN.md`
   (gitignored, never handed over: the HTML is the deliverable). A hook runs
   `check_quarterly_article.py` on every save and sends failures back. Fix each one and
   save again until it passes. Once the check passes, the same hook runs
   `render_quarterly_html.py`, which writes `jobs_done_post/articles/quarterly_YYYY-QN.html`.
   If the hook did not run (manual edit), run both by hand:

   ```bash
   python3 jobs_done_post/check_quarterly_article.py jobs_done_post/data/drafts/quarterly_YYYY-QN.md
   python3 jobs_done_post/render_quarterly_html.py jobs_done_post/data/drafts/quarterly_YYYY-QN.md
   ```

   Never edit the HTML by hand: fix the draft and save it again. Never publish the HTML
   as an Artifact: it names customers, so it stays a local file.

5. **Hand it over.** Give the path of the HTML (the deliverable, to paste as an HTML
   widget), never the draft, then list the check's warnings (quantity words) with
   the figures behind each, and remind the user that the article names customers in the
   top 3 lists.
