#!/usr/bin/env python3
"""Render a checked quarterly Jobs Done article as the HTML block for the intranet.

    python3 render_quarterly_html.py data/drafts/quarterly_2026-Q3.md [--out-dir DIR]

Writes articles/quarterly_2026-Q3.html (the deliverable) from the checked Markdown draft:
one <section class="lwa"> holding its
own <style>, to paste as an HTML widget. It uses the LumApps brand shell of the artifact
pages (assets/shell.css: dark header, LumApps yellow, cream cards, Roboto), so the
articles look like every other page Claude publishes on the intranet.

Every figure comes from the Markdown article, which check_quarterly_article.py has
already traced to the data: this script only lays it out (cards for the overview, one
block per domain group with its features and its biggest movers by company). It adds no figure of
its own, except the bar widths, drawn from the shares the article prints. Above the
overview, it adds a folded glossary: the metrics, and what one Job Done is for each
feature of the scope sentence.

It fails on a line it cannot read, so a layout change never drops content silently.
The monthly render (render_monthly_html.py) shares the helpers below.
"""

import argparse
import html
import re
import sys
from pathlib import Path

from jobs_done_common import (EMOJI, FEATURE_DEFINITIONS, GLOSSARY_METRICS_QUARTERLY, SCOPE,
                              SCOPE_GROUP, overview_lines, KPI_EMOJI)

# The LumApps brand shell, copied from the artifact skill of the lumapps-utils plugin
# (skills/artifact/assets/shell.css, plugin 0.5.0). Every selector starts with .lwa, so
# the CMS styles cannot change the block. Update the copy when the shell changes.
SHELL_CSS = (Path(__file__).parent / "assets" / "shell.css").read_text(encoding="utf-8")

# The deliverables. The Markdown they come from is a draft kept in data/drafts/ (gitignored).
ARTICLES_DIR = Path(__file__).parent / "articles"

# What the Jobs Done pages add to the shell: the KPI values, the change tags, the bars,
# the glossary. Same rule: every selector under .lwa, the shell's colours only.
JD_CSS = """\
/* Jobs Done additions to the brand shell */
/* Yellow is kept as an accent (header, card tops, bars). Tables, cards and steps use
   white and the shell's lines instead of its cream and yellow fills. */
/* Body text one pixel under the shell's 16px; the titles keep the shell's sizes. */
.lwa{font-size:15px}
.lwa table{font-size:inherit}   /* tables do not inherit it in quirks mode */
.lwa th{background:#EEEEEE !important; border-bottom:2px solid #D4D4D4 !important; color:var(--ink) !important; font-size:13px; text-transform:uppercase; letter-spacing:.04em}
.lwa .lwa-cards > div, .lwa .lwa-steps > div{background:var(--white)}
/* KPI tiles: a pale tint of their top colour, to set them apart (white where color-mix is unsupported) */
.lwa .jd-kpis > div{background:color-mix(in srgb, var(--c) 16%, white)}
.lwa .lwa-steps .lwa-n{background:var(--cream)}
.lwa .lwa-callout{background:var(--white); border:1px solid var(--line); border-left:6px solid var(--blue)}
.lwa .jd-kpis > div{display:grid; gap:2px}
/* five cards of one size on one row. The widget is narrower than the page on some
   layouts, so the rows follow the width of the block itself (a container query):
   three then two centred when it is narrow, one per row on a phone. */
.lwa .jd-kpis-box{container-type:inline-size; margin:0 0 16px}
.lwa .jd-kpis{grid-template-columns:repeat(5,minmax(0,1fr)); margin:0; row-gap:14px}
/* each card spans four rows of the grid (label, value, change, subtitle), shared by the
   cards of a row, so a label on two lines keeps every value on one line */
.lwa .jd-kpis > div{padding:14px; grid-row:span 4; grid-template-rows:subgrid; row-gap:2px; align-content:start}
.lwa .lwa-cards > div > span.jd-v{font-size:26px}
@container (max-width:900px){
  .lwa .jd-kpis{grid-template-columns:repeat(6,minmax(0,1fr))}
  .lwa .jd-kpis > div{grid-column:span 2}
  .lwa .jd-kpis > div:nth-child(4){grid-column:2 / span 2}
}
@container (max-width:520px){
  .lwa .jd-kpis{grid-template-columns:1fr}
  .lwa .jd-kpis > div, .lwa .jd-kpis > div:nth-child(4){grid-column:auto}
}
.lwa .lwa-cards > div > span.jd-v{font-size:30px; font-weight:900; line-height:1.15; color:var(--ink); font-variant-numeric:tabular-nums}
.lwa .lwa-tag{font-variant-numeric:tabular-nums; white-space:nowrap}
.lwa{--jd-down:#F4A396}
.lwa .lwa-tag--down{background:var(--jd-down)}
.lwa .jd-hl > div > ul{margin:6px 0 0; padding-left:20px; font-size:15px}
/* biggest movers: a light green or coral edge per side, the leading feature under the name */
.lwa tr.jd-sub td{background:#F7F7F7 !important; font-size:13px; font-weight:700; color:var(--ink-soft) !important; padding-top:7px !important; padding-bottom:7px !important}
.lwa tr.jd-gain td:first-child{box-shadow:inset 4px 0 0 #DCEFA8}
.lwa tr.jd-loss td:first-child{box-shadow:inset 4px 0 0 #F8C9C2}
.lwa .jd-led{display:block; font-size:13px; color:var(--ink-soft)}
/* the same air before each section and each tribe, the first tribe excepted */
.lwa .lwa-body > h2{margin-top:56px}   /* the shell zeroes the top margin of every body child */
.lwa h3.jd-tribe{font-size:21px; margin:56px 0 8px}
.lwa h2 + h3.jd-tribe{margin-top:12px}
/* an overview value with its unrounded figure as a tooltip */
.lwa .jd-exact{text-decoration:underline dotted #BDBDBD; text-decoration-thickness:2px; text-underline-offset:6px}
.lwa .jd-group{display:flex; flex-wrap:wrap; align-items:baseline; gap:6px 12px; margin:0 0 12px}
.lwa .jd-group .jd-v{font-size:17px; font-weight:900; font-variant-numeric:tabular-nums}
.lwa .jd-muted{color:var(--ink-soft); font-size:14px}
.lwa td.jd-num, .lwa th.jd-num{text-align:right !important; white-space:nowrap; font-variant-numeric:tabular-nums}
.lwa td.jd-share{width:34%}
.lwa .jd-share-row{display:grid; grid-template-columns:minmax(40px,1fr) 4.2em; gap:10px; align-items:center}
.lwa .jd-bar{display:block; height:8px; background:#DCDCDC; border-radius:4px; overflow:hidden}
.lwa .jd-fill{display:block; height:100%; background:#707070; border-radius:4px}
.lwa .lwa-steps .lwa-n{font-size:22px; font-weight:400}
.lwa .lwa-steps > div{align-items:center}
.lwa .lwa-steps > div > div > p{margin:0}
/* the scope, the same in every report: small and muted, at the very end */
.lwa .jd-scope{color:var(--ink-soft); font-size:13px; line-height:1.5; margin:24px 0 8px; padding-top:12px; border-top:1px solid var(--line)}
.lwa .jd-scope p{margin:0 0 2px}
.lwa .jd-scope ul{margin:0; padding-left:18px}
.lwa .jd-scope li{margin:1px 0}
.lwa .jd-scope strong{font-weight:700}
/* the dashboard line, in plain text above the scope so it stands out */
.lwa .jd-footer{margin:24px 0 0; padding:12px 16px; background:#F3F3F3; border-radius:10px; font-size:15px; font-weight:700; color:var(--ink)}
.lwa .jd-gloss{margin:0 0 20px; background:var(--white); border:1px solid var(--line); border-left:6px solid var(--yellow); border-radius:10px}
.lwa .jd-gloss > summary{cursor:pointer; padding:12px 16px; list-style:none; display:flex; align-items:center; gap:12px; font-weight:700}
.lwa .jd-gloss > summary > div{display:flex; flex-wrap:wrap; align-items:baseline; column-gap:12px; row-gap:2px}
.lwa .jd-gloss > summary b{font-size:16px}
.lwa .jd-gloss > summary::-webkit-details-marker{display:none}
.lwa .jd-gloss > summary span{font-weight:400; font-size:14px; color:var(--ink-soft)}
.lwa .jd-gloss > summary::after{content:"Show definitions ▾"; margin-left:auto; flex:none; white-space:nowrap; background:var(--yellow); border-radius:999px; padding:6px 14px; font-size:13px; font-weight:700}
.lwa .jd-gloss[open] > summary::after{content:"Hide ▴"; background:#EEEEEE; color:var(--ink)}
.lwa .jd-gbody{padding:0 16px 14px}
.lwa .jd-gterms{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin:4px 0 18px}
.lwa .jd-gterms > div{background:#F3F3F3; border-radius:8px; padding:10px 12px; font-size:14px; line-height:1.4}
.lwa .jd-gterms b{display:block; margin-bottom:2px}
.lwa .jd-gterms span{color:var(--ink-soft)}
.lwa .jd-gfeatures{columns:2; column-gap:32px}
.lwa .jd-gtribe{break-inside:avoid; margin:0 0 16px}
.lwa .jd-gtribe > p{margin:0 0 4px; font-size:12.5px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-soft)}
.lwa .jd-gtribe > div{display:grid; grid-template-columns:150px 1fr; gap:12px; padding:7px 0; border-bottom:1px solid var(--line); font-size:14px; line-height:1.4}
.lwa .jd-gtribe > div:last-child{border-bottom:0}
.lwa .jd-gtribe span{color:var(--ink)}
@media (max-width:720px){
  .lwa .jd-gterms{grid-template-columns:1fr 1fr}
  .lwa .jd-gfeatures{columns:1}
  .lwa td.jd-share{width:auto}
  .lwa .jd-bar{display:none}
}
"""

CARD_COLOURS = ("yellow", "blue", "green", "purple", "pink")
# An overview KPI line, as overview_lines() in jobs_done_common.py writes it.
KPI_LINE = re.compile(r"^(\S+) (.+?): (\S+) \((.+) (MoM|QoQ)\)$")
GROUP_LINE = re.compile(r"^- Jobs Done: (\S+) \((\S+|flat) QoQ\), ([\d.]+)% of all Jobs Done$")
FEATURE_LINE = re.compile(r"^- (\S+)\s+\*\*([^*]+)\*\*: (\S+) \(([^)]*?)(?: QoQ)?\), ([\d.]+)% of the tribe$")
# A company of a tribe's biggest movers, as mover_line() in prepare_quarterly.py writes it.
MOVER_LINE = re.compile(r"^(\d)\.\s+(.+?), ([+-]\S+) Jobs Done \((.+?)(?: QoQ)?\)"
                        r"(?:, led by (.+) \(([+-]\S+)\))?$")
MOVER_LABELS = {"Companies gaining the most Jobs Done:": ("▲ Gaining the most", "gain"),
                "Companies losing the most Jobs Done:": ("▼ Losing the most", "loss")}
CHANGE = re.compile(r"([+-]\d[\d.]*%|\bflat\b)(?= QoQ)")
# Introductions stay plain text: the change tags are for cards, lists and tables.
NO_CHIPS = re.compile(r"(?!)")
DOMAINS_SECTION = "By tribe"


class Unreadable(Exception):
    pass


def inline(text: str) -> str:
    """Escape, then the little Markdown the article uses: links, bold, italics."""
    out = html.escape(text, quote=False)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                 lambda m: f'<a href="{m.group(2)}" target="_blank">{m.group(1)}</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", out)


def chip(change: str) -> str:
    """A change as a coloured tag ("+1.2%", "-0.4 pts", "flat"): green up, pink down,
    plain when it rounds to nothing, as in the article."""
    value = 0.0 if change == "flat" else float(change.split()[0].rstrip("%"))
    kind = "" if abs(value) < 0.05 else (" lwa-tag--done" if value > 0 else " lwa-tag--down")
    return f'<span class="lwa-tag{kind}">{html.escape(change)}</span>'


def with_chips(text: str, pattern: re.Pattern = CHANGE) -> str:
    """Inline Markdown, with each change before its unit turned into a tag."""
    return pattern.sub(lambda m: chip(m.group(1)), inline(text))


def share_cell(share: str) -> str:
    width = min(max(float(share), 0.0), 100.0)
    return (f'<td class="jd-share"><div class="jd-share-row"><span class="jd-bar" aria-hidden="true">'
            f'<span class="jd-fill" style="width:{width:.2f}%"></span></span>'
            f'<span class="jd-num">{share}%</span></div></td>')


def paragraphs(lines: list[str]) -> list[str]:
    """Non-empty lines grouped into paragraphs, separators dropped."""
    out, cur = [], []
    for line in lines + [""]:
        if line.strip() in ("", "---"):
            if cur:
                out.append(" ".join(cur))
                cur = []
        else:
            cur.append(line.strip())
    return out


def split_on(lines: list[str], prefix: str) -> list[tuple[str, list[str]]]:
    """[(heading text, lines under it)] for each line starting with `prefix`."""
    out = []
    for line in lines:
        if line.startswith(prefix):
            out.append((line[len(prefix):].strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def scope_tribes(lines: list[str]) -> list[tuple[str, list[str]]]:
    """The tribes of the scope sentence with their features, in its order."""
    m = SCOPE.search("\n".join(lines))
    if not m:
        return []
    return [(t, [f.strip() for f in fs.split(",")]) for t, fs in SCOPE_GROUP.findall(m.group(1))]


def prose(p: str, pattern: re.Pattern = CHANGE) -> str:
    """A paragraph of the article: the scope sentence muted, a data warning as a callout,
    the dashboard line as the footer."""
    if p.startswith("*Data warning"):
        return f'<div class="lwa-callout lwa-callout--warning"><p>⚠️ {inline(p.strip("*"))}</p></div>'
    if p.startswith("*Full breakdown"):
        return f'<p class="jd-footer">📊 {inline(p.strip("*"))}</p>'
    if p.startswith("Jobs Done covers"):
        return render_scope(p)
    return f"<p>{with_chips(p, pattern)}</p>"


def render_scope(sentence: str) -> str:
    """The scope sentence as a list, one tribe per bullet with its features. The draft
    keeps the sentence, which the checks read; the render moves it to the end of the
    article, under the dashboard line, since it is the same in every report."""
    tribes = SCOPE_GROUP.findall(SCOPE.search(sentence).group(1))
    if not tribes:
        raise Unreadable(f"scope sentence: {sentence[:60]!r}")
    items = "".join(f"<li><strong>{html.escape(t)}</strong>: {html.escape(fs)}</li>" for t, fs in tribes)
    return f'<div class="jd-scope"><p>Jobs Done covers:</p><ul>{items}</ul></div>'


def render_glossary(tribes: list[tuple[str, list[str]]], metrics: list[tuple[str, str]]) -> str:
    """What each metric and each feature of the scope sentence counts, folded by
    default: the metrics as small cards, then the features tribe by tribe, on two
    columns. Shared with the monthly render; each passes its own metric terms. The
    definitions live in jobs_done_common.py."""
    missing = [f for _, fs in tribes for f in fs if f not in FEATURE_DEFINITIONS]
    if missing:
        raise Unreadable(f"no FEATURE_DEFINITIONS entry for {', '.join(missing)}")
    terms = "".join(f"<div><b>{html.escape(t)}</b><span>{html.escape(d)}</span></div>"
                    for t, d in metrics)
    blocks = "".join(
        f'<div class="jd-gtribe"><p>{html.escape(t)}: one Job Done is</p>'
        + "".join(f"<div><b>{EMOJI.get(f, '')} {html.escape(f)}</b>"
                  f"<span>{html.escape(FEATURE_DEFINITIONS[f])}</span></div>" for f in fs)
        + "</div>" for t, fs in tribes)
    return (f'<details class="jd-gloss"><summary><div><b>📖 What the numbers count</b>'
            f'<span>Content counts page views, not pages created. Open for every feature.</span>'
            f'</div></summary><div class="jd-gbody">'
            f'<div class="jd-gterms">{terms}</div><div class="jd-gfeatures">{blocks}</div>'
            f'</div></details>')


def exact_values(lines: list[str], cur: dict | None, prev: dict | None, unit: str) -> dict:
    """{KPI line: its unrounded value}, for the tooltips on the overview cards.

    Read from the CSVs the check traced the article to. A line the data no longer
    rebuilds to the letter (the data was fetched again since) gets no tooltip.
    """
    if not cur:
        return {}
    exact = {"Jobs Done": f"{cur['jd']:,.0f}", "Users with a Job Done": f"{cur['users']:,.0f}",
             "Jobs per User": f"{cur['jpu']:.2f}", "MAU": f"{cur['mau']:,.0f}",
             "Reach": f"{cur['reach']:.2f}%"}
    written = {l.strip() for l in lines}
    return {line: exact[line.split(":")[0].split(" ", 1)[1]]
            for line in overview_lines(cur, prev, unit) if line in written}


def render_kpis(lines: list[str], subtitles: dict[str, str], exact: dict | None = None) -> str:
    """The five KPI lines of an overview as cards, the other lines as paragraphs.

    Five cards of one size on one row, in the dashboard's order. On a narrow block, the
    three Jobs Done KPIs, then MAU and Reach centred; on a phone, one per row. `subtitles` maps each KPI name to the small line under its value.
    `exact` maps a KPI line to its unrounded value, shown as a tooltip on the value.
    """
    exact = exact or {}
    cards, rest = [], []
    for line in (l.strip() for l in lines):
        if not line or line == "---":
            continue
        m = KPI_LINE.match(line)
        if m and m.group(2) in subtitles:
            emoji, name, value, chg, unit = m.groups()
            colour = CARD_COLOURS[len(cards) % len(CARD_COLOURS)]
            tip = (f' class="jd-v jd-exact" title="{html.escape(exact[line])}"' if line in exact
                   else ' class="jd-v"')
            cards.append(f'<div style="--c:var(--{colour})"><b>{html.escape(emoji)} {html.escape(name)}</b>'
                         f'<span{tip}>{html.escape(value)}</span>'
                         f'<span>{chip(chg)} {unit}</span><span>{subtitles[name]}</span></div>')
        elif line.startswith(KPI_EMOJI):
            raise Unreadable(f"overview line: {line!r}")
        else:
            rest.append(line)
    if len(cards) != len(subtitles):
        raise Unreadable(f"overview: {len(cards)} KPI lines, expected {len(subtitles)}")
    return (f'<div class="jd-kpis-box"><div class="lwa-cards jd-kpis">{"".join(cards)}</div></div>'
            + "".join(prose(p, NO_CHIPS) for p in paragraphs(rest)))


def wrap(slug: str, eyebrow: str, title: str, intro: list[str], body: str) -> str:
    """The block: the brand shell around the article, as the artifact skill builds it."""
    return "\n".join([
        f'<section class="lwa" id="lwa-{slug}" aria-label="{html.escape(title)}">',
        f"<style>\n{SHELL_CSS.strip()}\n{JD_CSS.strip()}\n</style>",
        f'<header class="lwa-hero"><div class="lwa-wrap">',
        f'<div class="lwa-eyebrow">{html.escape(eyebrow)}</div>',
        f"<h1>{html.escape(title)}</h1>",
        "</div></header>",
        '<div class="lwa-wrap"><div class="lwa-body">',
        "".join(prose(p) for p in intro),
        body,
        "</div></div>",
        "</section>",
        "",
    ])


def render_highlights(sections: list[tuple[str, list[str]]]) -> str:
    """The two highlight lists as cards, then the introduction that closes the overview
    (the prose after the lists), as plain paragraphs."""
    cards, closing = [], []
    for title, lines in sections:
        colour = "green" if "grew" in title else "jd-down"
        items = "".join(f"<li>{with_chips(l[2:].strip())}</li>" for l in lines if l.startswith("- "))
        cards.append(f'<div style="--c:var(--{colour})"><b>{inline(title)}</b><ul>{items}</ul></div>')
        closing += [l for l in lines if not l.strip().startswith("- ")]
    return (f'<div class="lwa-cards jd-hl">{"".join(cards)}</div>'
            + "".join(prose(p, NO_CHIPS) for p in paragraphs(closing)))


def render_group(name: str, lines: list[str]) -> str:
    jd = change = share = None
    features, movers, insight = [], {}, ""
    side = None
    for line in (l.strip() for l in lines):
        if not line or line == "---" or line == "Features by Jobs Done:":
            continue
        if line in MOVER_LABELS:
            side = MOVER_LABELS[line]
            movers[side] = []
        elif m := GROUP_LINE.match(line):
            jd, change, share = m.group(1), m.group(2), m.group(3)
        elif m := FEATURE_LINE.match(line):
            features.append(m.groups())
        elif side and (m := MOVER_LINE.match(line)):
            movers[side].append(m.groups())
        elif line.startswith("💡"):
            insight = line
        else:
            raise Unreadable(f"{name}: {line!r}")
    if jd is None:
        raise Unreadable(f"{name}: no '- Jobs Done: ...' line")

    rows = "".join(
        f'<tr><td>{html.escape(emoji)} {html.escape(feat)}</td><td class="jd-num">{html.escape(v)}</td>'
        f'<td class="jd-num">{chip(c)}</td>{share_cell(sh)}</tr>'
        for emoji, feat, v, c, sh in features)
    def mover(kind, rank, who, v, q, feature, feature_change):
        led = (f'<span class="jd-led">led by {html.escape(EMOJI.get(feature, ""))} '
               f"{html.escape(feature)} {html.escape(feature_change)}</span>" if feature else "")
        return (f'<tr class="jd-{kind}"><td>{rank}. {html.escape(who)}{led}</td>'
                f'<td class="jd-num">{html.escape(v)}</td>'
                f'<td class="jd-num">{chip(q) if q[0] in "+-" else html.escape(q)}</td></tr>')
    moves = "".join(
        f'<tr class="jd-sub"><td colspan="3">{title}</td></tr>'
        + "".join(mover(kind, *row) for row in rows)
        for (title, kind), rows in movers.items())
    return (f'<h3 class="jd-tribe">{inline(name)}</h3>'
            f'<div class="jd-group"><span class="jd-v">{html.escape(jd)}</span> Jobs Done '
            f'{chip(change)} <span class="jd-muted">QoQ · {share}% of all Jobs Done</span></div>'
            f'<table><tr><th>Feature</th><th class="jd-num">Jobs Done</th><th class="jd-num">QoQ</th>'
            f"<th>Share of the tribe</th></tr>{rows}</table>"
            + (f'<table class="jd-movers"><tr><th>Biggest movers by company</th>'
               f'<th class="jd-num">Change</th><th class="jd-num">QoQ</th></tr>{moves}</table>'
               if movers else "")
            + (f'<div class="lwa-callout"><p>{inline(insight)}</p></div>' if insight else ""))


def render_domains(lines: list[str]) -> str:
    """Scope sentence and intro, one block per domain group, the dashboard line last."""
    groups = split_on(lines, "### ")
    intro = lines[:next((i for i, l in enumerate(lines) if l.startswith("### ")), len(lines))]
    footer = next((l.strip() for l in lines if l.startswith("*Full breakdown")), "")
    if groups:   # the footer sits under the last group: keep it out of its block
        last = groups[-1][1]
        groups[-1] = (groups[-1][0], [l for l in last if not l.startswith("*Full breakdown")])
    scope = [p for p in paragraphs(intro) if p.startswith("Jobs Done covers")]
    return (f"<h2>{DOMAINS_SECTION}</h2>"
            + "".join(prose(p) for p in paragraphs(intro) if p not in scope)
            + "".join(render_group(g, ls) for g, ls in groups)
            + (prose(footer) if footer else "") + "".join(prose(p) for p in scope))


def quarter_exact(q: str, lines: list[str]) -> dict:
    """The unrounded overview values of quarter `q` ("Q3 2026"), when its data is on file."""
    import prepare_quarterly as pq
    key = f"{q[3:]}-{q[:2]}"
    if not pq.data_file("totals", key).exists():
        return {}
    totals = pq.read_totals(key)
    return exact_values(lines, pq.quarter_kpis(totals, key),
                        pq.quarter_kpis(totals, pq.shift_quarter(key, -1)), "QoQ")


def render(text: str, slug: str = "jobs-done") -> str:
    lines = text.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    quarter = re.search(r"Q[1-4] \d{4}", title or "")
    if not quarter:
        raise Unreadable("no '# Jobs Done - QN YYYY Product Performance' title")
    q = quarter.group(0)
    sections = split_on(lines, "## ")
    top = lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))]
    # A *Data warning: ...* line stays in the text, as a callout under the title.
    intro = [p for p in paragraphs(top) if not p.startswith("# ")]

    tribes = next((ts for name, sec in sections if name == DOMAINS_SECTION
                   and (ts := scope_tribes(sec))), [])
    body = [render_glossary(tribes, GLOSSARY_METRICS_QUARTERLY)] if tribes else []
    subtitles = {"Jobs Done": f"over {q}",
                 "Users with a Job Done": f"unique users over {q}",
                 "Jobs per User": "Jobs Done per user with a Job Done",
                 "MAU": f"active users, last 28 days of {q}",
                 "Reach": "users with a Job Done over 28 days / MAU"}
    for name, sec in sections:
        if name == "High level overview":
            hl = split_on(sec, "### ")
            before = sec[:next((i for i, l in enumerate(sec) if l.startswith("### ")), len(sec))]
            body.append(f"<h2>High level overview</h2>"
                        f"{render_kpis(before, subtitles, quarter_exact(q, before))}"
                        f"{render_highlights(hl)}")
        elif name == DOMAINS_SECTION:
            body.append(render_domains(sec))
        else:
            raise Unreadable(f"unknown section '## {name}'")
    return wrap(slug, "Product usage KPI · Quarterly", title, intro, "".join(body))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", help="data/drafts/quarterly_YYYY-QN.md, the checked draft")
    parser.add_argument("--out-dir", default=str(ARTICLES_DIR),
                        help="where to write the HTML (default: articles/)")
    args = parser.parse_args()
    src = Path(args.draft)
    m = re.search(r"quarterly_(\d{4}-Q[1-4])\.md$", src.name)
    if not m:
        sys.exit(f"[render_quarterly] expected quarterly_YYYY-QN.md, got {src.name}")
    try:
        out = render(src.read_text(encoding="utf-8"), f"jobs-done-{m.group(1).lower()}")
    except Unreadable as e:
        sys.exit(f"[render_quarterly] cannot lay out {src.name}: {e}")
    dest = Path(args.out_dir) / src.with_suffix(".html").name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    print(f"[render_quarterly] wrote {dest}")


if __name__ == "__main__":
    main()
