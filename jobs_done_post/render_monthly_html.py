#!/usr/bin/env python3
"""Render a checked monthly Jobs Done article as the HTML block for the intranet.

    python3 render_monthly_html.py data/drafts/article_2026-10.md [--out-dir DIR]

Writes articles/article_2026-10.html (the deliverable) from the checked Markdown draft:
one <section class="lwa"> holding its
own <style>, to paste as an HTML widget, in the LumApps brand shell of the artifact pages
(see render_quarterly_html.py). Five cards for the overview, then the features of the
month, one numbered block per feature paragraph with its emoji. Every figure comes from
the Markdown article, which check_article.py has already traced to the data: this script
only lays it out and adds no figure of its own. Above the overview, it adds a folded
glossary: the metrics, and what one Job Done is for each feature of the scope sentence.

It fails on an overview line it cannot read, so a layout change never drops a figure
silently.
"""

import argparse
import html
import re
import sys
from pathlib import Path

from jobs_done_common import GLOSSARY_METRICS
from render_quarterly_html import (ARTICLES_DIR, NO_CHIPS, Unreadable, exact_values, paragraphs, prose, render_glossary,
                                   render_kpis, scope_tribes, split_on, with_chips, wrap)

FEATURES_SECTION = "Features of the month"
CHANGE = re.compile(r"([+-]\d[\d.]*%|\bflat\b)(?= MoM)")
# A feature paragraph, as check_article.py counts them: a leading emoji and a bold name.
LEAD_EMOJI = re.compile(r"^([^\w\s*\[]+)\s*")


def render_features(lines: list[str]) -> str:
    """Intro, one numbered block per feature paragraph, the italic lines (dashboard link,
    data note), then the scope, the same in every report, so at the very end."""
    head, cards, scope, foot = [], [], [], []
    for p in paragraphs(lines):
        if p.startswith("Jobs Done covers"):
            scope.append(prose(p))
        elif p.startswith("*") and p.endswith("*") and not p.startswith("**"):
            foot.append(prose(p, CHANGE))
        elif (m := LEAD_EMOJI.match(p)) and "**" in p:
            cards.append(f'<div><span class="lwa-n" aria-hidden="true">{html.escape(m.group(1))}</span>'
                         f"<div><p>{with_chips(p[m.end():], CHANGE)}</p></div></div>")
        elif cards:
            raise Unreadable(f"paragraph after the feature cards: {p[:60]!r}")
        else:   # the introduction stays plain text: tags are for the feature blocks
            head.append(prose(p, NO_CHIPS))
    return (f"<h2>{FEATURES_SECTION}</h2>{''.join(head)}"
            f'<div class="lwa-steps">{"".join(cards)}</div>{"".join(foot)}{"".join(scope)}')


def month_exact(m: str, lines: list[str]) -> dict:
    """The unrounded overview values of month `m` ("October 2026"), when its data is on file."""
    import prepare_data as pd
    from datetime import datetime
    key = datetime.strptime(m, "%B %Y").strftime("%Y-%m")
    if not pd.data_file("totals", key).exists():
        return {}
    totals = pd.read_totals(key)
    return exact_values(lines, pd.month_kpis(totals, key),
                        pd.month_kpis(totals, pd.adj_month(key, -1)), "MoM")


def render(text: str, slug: str = "jobs-done") -> str:
    lines = text.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    month = re.search(r"Jobs Done - (\w+ \d{4})", title or "")
    if not month:
        raise Unreadable("no '# Jobs Done - <Month> <Year> Product Performance' title")
    m = month.group(1)
    sections = split_on(lines, "## ")
    top = lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))]
    intro = [p for p in paragraphs(top) if not p.startswith("# ")]

    tribes = next((ts for name, sec in sections if name == FEATURES_SECTION
                   and (ts := scope_tribes(sec))), [])
    body = [render_glossary(tribes, GLOSSARY_METRICS)] if tribes else []
    subtitles = {"Jobs Done": f"over {m}",
                 "Users with a Job Done": f"unique users over {m}",
                 "Jobs per User": "Jobs Done per user with a Job Done",
                 "MAU": f"active users, last 28 days of {m}",
                 "Reach": "users with a Job Done over 28 days / MAU"}
    for name, sec in sections:
        if name == "High level overview":
            body.append(f"<h2>High level overview</h2>"
                        f"{render_kpis(sec, subtitles, month_exact(m, sec))}")
        elif name == FEATURES_SECTION:
            body.append(render_features(sec))
        else:
            raise Unreadable(f"unknown section '## {name}'")
    return wrap(slug, "Product usage KPI · Monthly", title, intro, "".join(body))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", help="data/drafts/article_YYYY-MM.md, the checked draft")
    parser.add_argument("--out-dir", default=str(ARTICLES_DIR),
                        help="where to write the HTML (default: articles/)")
    args = parser.parse_args()
    src = Path(args.draft)
    m = re.search(r"article_(\d{4}-\d{2})\.md$", src.name)
    if not m:
        sys.exit(f"[render_monthly] expected article_YYYY-MM.md, got {src.name}")
    try:
        out = render(src.read_text(encoding="utf-8"), f"jobs-done-{m.group(1)}")
    except Unreadable as e:
        sys.exit(f"[render_monthly] cannot lay out {src.name}: {e}")
    dest = Path(args.out_dir) / src.with_suffix(".html").name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    print(f"[render_monthly] wrote {dest}")


if __name__ == "__main__":
    main()
