---
name: monthly-jobs-done-article
description: Write the monthly Jobs Done article covering LumApps and Beekeeper, from fresh Looker data, and check it against the data before handing it over.
argument-hint: "[YYYY-MM] [editorial note]"
disable-model-invocation: true
allowed-tools: Bash(python3 jobs_done_post/prepare_data.py *), Bash(python3 jobs_done_post/check_article.py *)
---

# Monthly Jobs Done article

Arguments: `$ARGUMENTS`

- A leading `YYYY-MM` is the report month, passed as `--month`. Without one, the script
  targets the last complete calendar month.
- Anything else is the analyst's editorial note, passed as `--note "<text>"`.

Run everything from the repository root. The scripts resolve `data/` from their own
location, so the paths below work as written.

## Steps

1. **Fetch and analyse.**

   ```bash
   python3 jobs_done_post/prepare_data.py --fetch [--month YYYY-MM] [--note "<text>"]
   ```

   It pulls fresh data from Looker into `jobs_done_post/data/` and prints the analysis:
   platform totals with MAU, feature MoM/YoY/frequency, 13-month trend classification
   (15 months fetched, so the report month has its YoY), and the three ranked lists that
   decide what to write about. If it fails on credentials or a 403, stop and point the
   user to the setup section of `jobs_done_post/README.md`. Do not work around it.

2. **Load the context.** Read these before writing a word:
   - `jobs_done_post/CLAUDE.md`: what the metrics mean, how to read them, and the
     permanent data limitations.
   - [references/writing-rules.md](references/writing-rules.md): every rule for the
     article (structure, scope sentence, selection, wording, YoY, emoji, closing links).
   - The reference articles it lists, then
     [references/april-2026.md](references/april-2026.md) for voice.

3. **Write the article** from the script output only. Do not restate an old month from
   memory or from a past article: Looker revises history.

4. **Save it** as `jobs_done_post/articles/article_YYYY-MM.md`. A hook runs
   `check_article.py` on every save and sends failures back. Fix each one and save again
   until it passes. If a figure fails and the prose looks right, the data may be stale:
   re-run step 1 before rewriting.

5. **Hand it over.** Give the path, then list the check's warnings (quantity words such as
   "most" or "a third") with the figures behind each, so the user can confirm them. Those
   are judgements the script cannot make.
