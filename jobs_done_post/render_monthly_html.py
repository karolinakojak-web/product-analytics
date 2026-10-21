#!/usr/bin/env python3
"""Render a checked monthly Jobs Done article as the HTML block for the intranet.

    python3 render_monthly_html.py articles/article_2026-09.md

Writes articles/article_2026-09.html next to it: one <style> and one <div>, to paste
as embedded content. It uses the look of the quarterly block (render_quarterly_html.py):
tiles for the overview, then one section per platform with one card per feature
paragraph. Every figure comes from the Markdown article, which check_article.py has
already traced to the data: this script only lays it out and adds no figure of its own.
Above the overview, it adds a folded glossary: the metrics, and what one Job Done is
for each feature of the scope sentences (render_glossary in render_quarterly_html.py).

It fails on an overview line it cannot read, so a layout change never drops a figure
silently.
"""

import html
import re
import sys
from pathlib import Path

from jobs_done_common import GLOSSARY_METRICS
from render_quarterly_html import (CSS, PLATFORMS, Unreadable, chip, inline, paragraphs,
                                   render_glossary, scope_features, split_on)

# The quarterly CSS, plus what the monthly layout adds: two chips per tile (MoM and YoY)
# and the feature cards, emoji on the left, the paragraph on the right.
MONTHLY_CSS = CSS + """\
.jdq .jdq-tc { display: grid; gap: 4px; justify-items: end; color: var(--jdq-muted); font-size: 12.5px; }
.jdq .jdq-feat { background: var(--jdq-surface); border: 1px solid var(--jdq-line); border-radius: 10px;
  padding: 14px 16px; display: grid; grid-template-columns: 2em minmax(0, 1fr); gap: 10px; align-items: start; }
.jdq .jdq-femoji { font-size: 22px; line-height: 1.2; text-align: center; }
"""

OVERVIEW_ITEM = re.compile(r"^- (LumApps|Beekeeper) (\S+) \(([^)]+)\)$")
OVERVIEW_CHANGE = re.compile(r"^(\S+) (MoM|YoY)$")
CHANGE = re.compile(r"([+-]\d[\d.]*%|\bflat\b)(?= (?:MoM|YoY))")
# A feature paragraph, as check_article.py counts them: a leading emoji and a bold name.
LEAD_EMOJI = re.compile(r"^([^\w\s*\[]+)\s*")


def with_chips(text: str) -> str:
    """Inline Markdown, with each '<change> MoM' or '<change> YoY' turned into a chip."""
    return CHANGE.sub(lambda m: chip(m.group(1)), inline(text))


def render_overview(lines: list[str], month: str) -> str:
    subtitle = {"Jobs Done": f"last 28 days of {month}",
                "MAU": f"active users, last 28 days of {month}"}
    out, blocks = [], []
    for line in (l.strip() for l in lines):
        if not line or line == "---":
            continue
        if line.startswith("- "):
            m = OVERVIEW_ITEM.match(line)
            if not m or not blocks:
                raise Unreadable(f"overview line: {line!r}")
            changes = []
            for part in m.group(3).split(", "):
                c = OVERVIEW_CHANGE.match(part)
                if not c:
                    raise Unreadable(f"overview change: {part!r} in {line!r}")
                changes.append(c.groups())
            blocks[-1][1].append((m.group(1), m.group(2), changes))
        else:
            blocks.append((line, []))
    for label, items in blocks:
        kind = next((k for k in subtitle if k in label), None)
        if not kind:
            raise Unreadable(f"overview label: {label!r}")
        tiles = "".join(
            f'<div class="jdq-tile jdq-{PLATFORMS[p]}"><span class="jdq-tl">{p}</span>'
            f'<span class="jdq-tv">{html.escape(v)}</span>'
            f'<span class="jdq-tc">{"".join(f"<span>{chip(c)} {u}</span>" for c, u in changes)}</span>'
            f'<span class="jdq-tu">{subtitle[kind]}</span></div>'
            for p, v, changes in items)
        out.append(f'<div><div class="jdq-klabel">{html.escape(label)}</div>'
                   f'<div class="jdq-tiles">{tiles}</div></div>')
    return f'<div class="jdq-overview"><h2 class="jdq-h2">High level overview</h2>{"".join(out)}</div>'


def render_platform(platform: str, lines: list[str]) -> str:
    """Scope sentence and intro in the header, one card per feature paragraph, then the
    italic lines (dashboard link, data note) as the footer."""
    head, cards, foot = [], [], []
    for p in paragraphs(lines):
        if p.startswith("*") and p.endswith("*") and not p.startswith("**"):
            foot.append(f'<p class="jdq-footer">{inline(p[1:-1])}</p>')
        elif (m := LEAD_EMOJI.match(p)) and "**" in p:
            cards.append(f'<div class="jdq-feat"><span class="jdq-femoji" aria-hidden="true">'
                         f'{html.escape(m.group(1))}</span><p>{with_chips(p[m.end():])}</p></div>')
        elif cards:
            raise Unreadable(f"{platform}: paragraph after the feature cards: {p[:60]!r}")
        else:
            cls = ' class="jdq-scope"' if p.startswith("Jobs Done covers") else ""
            head.append(f"<p{cls}>{with_chips(p)}</p>")
    return (f'<div class="jdq-platform jdq-{PLATFORMS[platform]}"><div class="jdq-phead">'
            f'<h2 class="jdq-h2">{platform}</h2>{"".join(head)}</div>'
            f'{"".join(cards)}{"".join(foot)}</div>')


def render(text: str) -> str:
    lines = text.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    month = re.search(r"Jobs Done - (\w+ \d{4})", title or "")
    if not month:
        raise Unreadable("no '# Jobs Done - <Month> <Year> Product Performance' title")
    sections = split_on(lines, "## ")
    top = lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))]
    mast = [f"<p>{inline(p)}</p>" for p in paragraphs(top) if not p.startswith("# ")]

    scopes = {name: fs for name, sec in sections if name in PLATFORMS and (fs := scope_features(sec))}
    body = [render_glossary(scopes, GLOSSARY_METRICS)] if scopes else []
    for name, sec in sections:
        if name == "High level overview":
            body.append(render_overview(sec, month.group(1)))
        elif name in PLATFORMS:
            body.append(render_platform(name, sec))
        else:
            raise Unreadable(f"unknown section '## {name}'")

    return (f"<style>\n{MONTHLY_CSS}\n</style>\n"
            f'<div class="jdq"><div class="jdq-mast"><span class="jdq-eyebrow">'
            f'Product usage KPI · Monthly</span><h2 class="jdq-title">{inline(title)}</h2>'
            f'{"".join(mast)}</div>{"".join(body)}</div>\n')


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: render_monthly_html.py articles/article_YYYY-MM.md")
    src = Path(sys.argv[1])
    if not re.search(r"article_\d{4}-\d{2}\.md$", src.name):
        sys.exit(f"[render_monthly] expected article_YYYY-MM.md, got {src.name}")
    try:
        out = render(src.read_text(encoding="utf-8"))
    except Unreadable as e:
        sys.exit(f"[render_monthly] cannot lay out {src.name}: {e}")
    dest = src.with_suffix(".html")
    dest.write_text(out, encoding="utf-8")
    print(f"[render_monthly] wrote {dest}")


if __name__ == "__main__":
    main()
