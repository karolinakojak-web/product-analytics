#!/usr/bin/env python3
"""Render a checked quarterly Jobs Done article as the HTML block for the intranet.

    python3 render_quarterly_html.py articles/quarterly_2026-Q3.md

Writes articles/quarterly_2026-Q3.html next to it: one <style> and one <div>, to paste
as embedded content. Every figure comes from the Markdown article, which
check_quarterly_article.py has already traced to the data: this script only lays it
out (tiles for the overview, one card per domain group with its features and its top
3 companies). It adds no figure of its own, except the bar widths, drawn from the
shares the article prints.

It fails on a line it cannot read, so a layout change never drops content silently.
"""

import html
import re
import sys
from pathlib import Path

CSS = """\
.jdq { --jdq-bg: #f6f7f9; --jdq-surface: #ffffff; --jdq-ink: #18202b; --jdq-muted: #5b6676;
  --jdq-line: #dfe3ea; --jdq-lum: #2f5bd3; --jdq-bee: #c27a0e; --jdq-up: #1f8a4c; --jdq-up-bg: #e3f4ea;
  --jdq-down: #c2412d; --jdq-down-bg: #fbe7e3; --jdq-flat: #5b6676; --jdq-flat-bg: #eceff3;
  --jdq-track: #dbe3f7; --jdq-num: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--jdq-bg); color: var(--jdq-ink); border-radius: 12px; padding: 20px;
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  display: grid; gap: 28px; text-align: left;
  max-width: 1080px; margin-inline: auto; padding-inline: 20px; }  /* centred column, as in the published pages */
.jdq, .jdq * { box-sizing: border-box; }
.jdq p, .jdq ol, .jdq ul, .jdq h2 { margin: 0; padding: 0; }
.jdq .jdq-def { font-size: 12.5px; color: var(--jdq-muted); margin: -12px 0 0; }  /* small, just before the overview */
.jdq .jdq-mast { display: grid; gap: 8px; }
.jdq .jdq-eyebrow { font-size: 12px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; color: var(--jdq-muted); }
.jdq .jdq-title { font-size: 30px; line-height: 1.2; font-weight: 700; }
.jdq .jdq-h2 { font-size: 24px; line-height: 1.25; font-weight: 700; }
.jdq .jdq-overview { display: grid; gap: 16px; }
.jdq .jdq-klabel { font-size: 12px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--jdq-muted); margin-bottom: 8px; }
.jdq .jdq-tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.jdq .jdq-tile { background: var(--jdq-surface); border: 1px solid var(--jdq-line); border-top: 3px solid var(--jdq-lum);
  border-radius: 10px; padding: 12px 14px; display: grid; grid-template-columns: 1fr auto; row-gap: 2px; }
.jdq .jdq-tile.jdq-beekeeper { border-top-color: var(--jdq-bee); }
.jdq .jdq-tl { font-weight: 600; }
.jdq .jdq-tv { font-size: 28px; font-weight: 700; line-height: 1.15; font-variant-numeric: tabular-nums; }
.jdq .jdq-tc { grid-column: 2; grid-row: 1 / 3; align-self: center; }
.jdq .jdq-tu { grid-column: 1 / -1; color: var(--jdq-muted); font-size: 12.5px; }
.jdq .jdq-hl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.jdq .jdq-hlbox { background: var(--jdq-surface); border: 1px solid var(--jdq-line); border-radius: 10px; padding: 12px 16px; display: grid; gap: 6px; }
.jdq .jdq-hlbox ul { padding-left: 18px; display: grid; gap: 6px; }
.jdq .jdq-h3 { font-size: 17px; font-weight: 700; }
.jdq .jdq-chg { font: 500 12.5px/1 var(--jdq-num); padding: 2px 6px; border-radius: 5px; white-space: nowrap; }
.jdq .jdq-chg.jdq-up { color: var(--jdq-up); background: var(--jdq-up-bg); }
.jdq .jdq-chg.jdq-down { color: var(--jdq-down); background: var(--jdq-down-bg); }
.jdq .jdq-chg.jdq-flat { color: var(--jdq-flat); background: var(--jdq-flat-bg); }
.jdq .jdq-platform { display: grid; gap: 14px; }
.jdq .jdq-phead { display: grid; gap: 8px; border-left: 4px solid var(--jdq-lum); padding-left: 14px; }
.jdq .jdq-beekeeper .jdq-phead { border-left-color: var(--jdq-bee); }
.jdq .jdq-scope { color: var(--jdq-muted); font-size: 14px; }
.jdq .jdq-dom { background: var(--jdq-surface); border: 1px solid var(--jdq-line); border-radius: 10px; padding: 14px 16px; display: grid; gap: 10px; }
.jdq .jdq-dhead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.jdq .jdq-dname { font-size: 18px; font-weight: 700; }
.jdq .jdq-gshare { margin-left: auto; color: var(--jdq-muted); font-size: 12.5px; }
.jdq .jdq-big { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; font-size: 14px; }
.jdq .jdq-bigv { font-size: 26px; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.jdq .jdq-muted { color: var(--jdq-muted); font-size: 12.5px; }
.jdq .jdq-cols { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 28px; align-items: start; }
.jdq .jdq-col { min-width: 0; }
.jdq .jdq-toph { font-size: 12px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--jdq-muted); margin-bottom: 6px; }
.jdq .jdq-toph span { text-transform: none; letter-spacing: 0; font-weight: 400; }
.jdq .jdq-colh { margin-bottom: 6px; font-size: 12px; font-weight: 600; color: var(--jdq-muted); }  /* one label above each column */
.jdq .jdq-colh .jdq-who { letter-spacing: .06em; text-transform: uppercase; }
.jdq .jdq-colh .jdq-hn { text-align: right; white-space: nowrap; }
.jdq .jdq-list { list-style: none; display: grid; gap: 5px; }
.jdq .jdq-frow, .jdq .jdq-trow { display: grid; align-items: center; gap: 10px; font-size: 13.5px; margin: 0; }
.jdq .jdq-frow { grid-template-columns: minmax(7em, 11em) minmax(60px, 1fr) 3.8em 4.6em 5em; }
.jdq .jdq-trow { grid-template-columns: minmax(0, 1fr) minmax(40px, 80px) 3.8em 4.6em; }
.jdq .jdq-who { overflow-wrap: anywhere; line-height: 1.3; }  /* real names wrap, never cut */
.jdq .jdq-num { font: 500 12.5px var(--jdq-num); text-align: right; }
.jdq .jdq-q { text-align: right; white-space: nowrap; }
.jdq .jdq-bar { display: block; height: 6px; background: var(--jdq-track); border-radius: 3px; overflow: hidden; }
.jdq .jdq-fill { display: block; height: 100%; background: var(--jdq-lum); }
.jdq .jdq-beekeeper .jdq-fill { background: var(--jdq-bee); }
.jdq .jdq-insight { font-size: 14px; background: var(--jdq-bg); border-radius: 8px; padding: 8px 12px; }
.jdq .jdq-footer { font-size: 13px; color: var(--jdq-muted); font-style: italic; }
.jdq a { color: var(--jdq-lum); text-decoration: underline; }
@media (max-width: 760px) {
  .jdq .jdq-cols, .jdq .jdq-hl, .jdq .jdq-tiles { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .jdq { padding: 14px; }
  .jdq .jdq-frow { grid-template-columns: minmax(0, 1fr) 3.4em 4.4em 4.8em; }
  .jdq .jdq-trow { grid-template-columns: minmax(0, 1fr) 3.4em 4.4em; }
  .jdq .jdq-bar, .jdq .jdq-colh .jdq-hb { display: none; }
  .jdq .jdq-gshare { margin-left: 0; width: 100%; }
}
"""

PLATFORMS = {"LumApps": "lumapps", "Beekeeper": "beekeeper"}
OVERVIEW_ITEM = re.compile(r"^- (LumApps|Beekeeper) (\S+) \((\S+|flat) QoQ\)$")
GROUP_LINE = re.compile(r"^- Jobs Done: (\S+) \((\S+|flat) QoQ\), ([\d.]+)% of (LumApps|Beekeeper) Jobs Done$")
FEATURE_LINE = re.compile(r"^- (\S+)\s+\*\*([^*]+)\*\*: (\S+) \(([^)]*?)(?: QoQ)?\), ([\d.]+)% of the domain$")
COMPANY_LINE = re.compile(r"^\d\.\s+(.+), (\S+) \(([\d.]+)% of .+ Jobs Done\)$")
CHANGE = re.compile(r"([+-]\d[\d.]*%|\bflat\b)(?= QoQ)")


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
    """A QoQ as a coloured chip: under 0.05% either way reads as flat, as in the article."""
    value = 0.0 if change == "flat" else float(change.rstrip("%"))
    kind = "flat" if abs(value) < 0.05 else ("up" if value > 0 else "down")
    return f'<span class="jdq-chg jdq-{kind}">{html.escape(change)}</span>'


def with_chips(text: str) -> str:
    """Inline Markdown, with each '<change> QoQ' turned into a chip."""
    return CHANGE.sub(lambda m: chip(m.group(1)), inline(text))


def bar(share: float) -> str:
    width = min(max(share, 0.0), 100.0)
    return (f'<span class="jdq-bar" aria-hidden="true">'
            f'<span class="jdq-fill" style="width:{width:.2f}%"></span></span>')


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


def render_overview(lines: list[str], quarter: str) -> str:
    out, blocks = [], []
    subtitle = {"Jobs Done": f"Jobs Done in {quarter}",
                "Monthly active users": "active in the last 28 days of the quarter",
                "Users Completing Jobs": "unique users over the quarter"}
    for line in lines:
        if line.startswith(("✅", "📈", "👥")):
            blocks.append((line.strip(), []))
        elif line.startswith("- ") and blocks:
            m = OVERVIEW_ITEM.match(line.strip())
            if not m:
                raise Unreadable(f"overview line: {line!r}")
            blocks[-1][1].append(m.groups())
    for label, items in blocks:
        kind = next((k for k in subtitle if k in label), None)
        if not kind:
            raise Unreadable(f"overview label: {label!r}")
        tiles = "".join(
            f'<div class="jdq-tile jdq-{PLATFORMS[p]}"><span class="jdq-tl">{p}</span>'
            f'<span class="jdq-tv">{html.escape(v)}</span>'
            f'<span class="jdq-tc">{chip(c)} QoQ</span>'
            f'<span class="jdq-tu">{subtitle[kind]}</span></div>'
            for p, v, c in items)
        out.append(f'<div><div class="jdq-klabel">{html.escape(label)}</div>'
                   f'<div class="jdq-tiles">{tiles}</div></div>')
    return "".join(out)


def render_highlights(sections: list[tuple[str, list[str]]]) -> str:
    boxes = []
    for title, lines in sections:
        items = "".join(f"<li>{with_chips(l[2:].strip())}</li>" for l in lines if l.startswith("- "))
        boxes.append(f'<div class="jdq-hlbox"><h3 class="jdq-h3">{inline(title)}</h3><ul>{items}</ul></div>')
    return f'<div class="jdq-hl">{"".join(boxes)}</div>'


def header(row: str, first: str, *labels: str) -> str:
    """Column labels on the same grid as the rows below, the bar column left blank.

    "Share" is each row's share of the domain's Jobs Done.
    """
    cells = "".join(f'<span class="jdq-hn">{l}</span>' for l in labels)
    return (f'<div class="jdq-{row} jdq-colh"><span class="jdq-who">{first}</span>'
            f'<span class="jdq-hb" aria-hidden="true"></span>{cells}</div>')


def render_group(platform: str, name: str, lines: list[str]) -> str:
    jd = change = share = None
    features, companies, insight = [], [], ""
    for line in (l.strip() for l in lines):
        if not line or line == "---" or line in ("Features by Jobs Done:", "Top 3 companies by Jobs Done:"):
            continue
        if m := GROUP_LINE.match(line):
            jd, change, share = m.group(1), m.group(2), m.group(3)
        elif m := FEATURE_LINE.match(line):
            features.append(m.groups())
        elif m := COMPANY_LINE.match(line):
            companies.append(m.groups())
        elif line.startswith("💡"):
            insight = line
        else:
            raise Unreadable(f"{platform}/{name}: {line!r}")
    if jd is None:
        raise Unreadable(f"{platform}/{name}: no '- Jobs Done: ...' line")

    rows = "".join(
        f'<li class="jdq-frow"><span class="jdq-who">{html.escape(emoji)} {html.escape(feat)}</span>'
        f'{bar(float(sh))}<span class="jdq-num">{sh}%</span>'
        f'<span class="jdq-num">{html.escape(v)}</span><span class="jdq-q">{chip(c)}</span></li>'
        for emoji, feat, v, c, sh in features)
    top = "".join(
        f'<li class="jdq-trow"><span class="jdq-who">{html.escape(who)}</span>{bar(float(sh))}'
        f'<span class="jdq-num">{sh}%</span><span class="jdq-num">{html.escape(v)}</span></li>'
        for who, v, sh in companies)
    top_col = (f'<div class="jdq-col">{header("trow", "Top 3 companies", "Share", "Jobs Done")}'
               f'<ol class="jdq-list">{top}</ol></div>' if companies else "")
    return (f'<div class="jdq-dom"><div class="jdq-dhead"><span class="jdq-dname">{inline(name)}</span>'
            f'<span class="jdq-gshare">{share}% of {platform} Jobs Done</span></div>'
            f'<div class="jdq-big"><span class="jdq-bigv">{html.escape(jd)}</span> Jobs Done '
            f'{chip(change)} <span class="jdq-muted">QoQ</span></div>'
            f'<div class="jdq-cols"><div class="jdq-col">{header("frow", "Features", "Share", "Jobs Done", "QoQ")}'
            f'<ol class="jdq-list">{rows}</ol></div>'
            f'{top_col}</div>'
            + (f'<p class="jdq-insight">{inline(insight)}</p>' if insight else "")
            + "</div>")


def render_platform(platform: str, lines: list[str]) -> str:
    groups = split_on(lines, "### ")
    intro = lines[:next((i for i, l in enumerate(lines) if l.startswith("### ")), len(lines))]
    footer = next((l.strip() for l in lines if l.startswith("*Full breakdown")), "")
    if groups:   # the footer sits under the last group: keep it out of the card
        last = groups[-1][1]
        groups[-1] = (groups[-1][0], [l for l in last if not l.startswith("*Full breakdown")])
    head = []
    for p in paragraphs(intro):
        cls = ' class="jdq-scope"' if p.startswith("Jobs Done covers") else ""
        head.append(f"<p{cls}>{inline(p)}</p>")
    cards = "".join(render_group(platform, g, ls) for g, ls in groups)
    foot = f'<p class="jdq-footer">{inline(footer.strip("*"))}</p>' if footer else ""
    return (f'<div class="jdq-platform jdq-{PLATFORMS[platform]}"><div class="jdq-phead">'
            f'<h2 class="jdq-h2">{platform}</h2>{"".join(head)}</div>{cards}{foot}</div>')


def render(text: str) -> str:
    lines = text.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), None)
    quarter = re.search(r"Q[1-4] \d{4}", title or "")
    if not quarter:
        raise Unreadable("no '# Jobs Done - QN YYYY Product Performance' title")
    sections = split_on(lines, "## ")
    top = lines[:next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))]

    mast, definition = [], ""
    for p in paragraphs(top):
        if p.startswith("# "):
            continue
        if p.startswith("*Data warning:"):
            mast.append(f"<p>{inline(p)}</p>")   # in the text, never as a banner
        elif p.startswith("*QoQ"):
            definition = re.sub(r"^QoQ", "<strong>QoQ</strong>", inline(p.strip("*")))
            definition = f'<p class="jdq-def">{definition}</p>'
        else:
            mast.append(f"<p>{inline(p)}</p>")

    body = []
    for name, sec in sections:
        if name == "High level overview":
            hl = split_on(sec, "### ")
            before = sec[:next((i for i, l in enumerate(sec) if l.startswith("### ")), len(sec))]
            body.append(f'<div class="jdq-overview"><h2 class="jdq-h2">High level overview</h2>'
                        f"{render_overview(before, quarter.group(0))}{render_highlights(hl)}</div>")
        elif name in PLATFORMS:
            body.append(render_platform(name, sec))
        else:
            raise Unreadable(f"unknown section '## {name}'")

    return (f"<style>\n{CSS}\n</style>\n"
            f'<div class="jdq"><div class="jdq-mast"><span class="jdq-eyebrow">'
            f'Product usage KPI · Quarterly</span><h2 class="jdq-title">{inline(title)}</h2>'
            f'{"".join(mast)}</div>{definition}{"".join(body)}</div>\n')


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: render_quarterly_html.py articles/quarterly_YYYY-QN.md")
    src = Path(sys.argv[1])
    if not re.search(r"quarterly_\d{4}-Q[1-4]\.md$", src.name):
        sys.exit(f"[render_quarterly] expected quarterly_YYYY-QN.md, got {src.name}")
    try:
        out = render(src.read_text(encoding="utf-8"))
    except Unreadable as e:
        sys.exit(f"[render_quarterly] cannot lay out {src.name}: {e}")
    dest = src.with_suffix(".html")
    dest.write_text(out, encoding="utf-8")
    print(f"[render_quarterly] wrote {dest}")


if __name__ == "__main__":
    main()
