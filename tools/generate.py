#!/usr/bin/env python3
"""NRBC Compliance Brief site generator.

Repo layout (paths relative to repo root):
  manifest.json                   - list of editions, oldest first
  items.json                      - item-level index parsed from editions (for Browse filters)
  templates/index.template.html   - landing page template
  templates/edition.template.html - wrapper for a single edition page
  editions/YYYY-MM-DD.html        - generated edition pages
  index.html                      - generated landing page

Commands:
  add     --raw <email.html> --date YYYY-MM-DD --vol V --ed E --subject "..." [--episode URL]
          Wraps the raw email into editions/<date>.html, updates manifest.json,
          re-parses that edition's items into items.json, regenerates index.html.
  build   Regenerates index.html from manifest.json + items.json.
  reindex Re-parses ALL editions into items.json, then rebuilds index.html.

Stdlib only. `add` is idempotent per date.
"""
import argparse
import html as html_mod
import json
import os
import re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://compliance.newrealmbrewing.com"

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

US_STATES = {s.upper() for s in [
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware",
    "Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky",
    "Louisiana","Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi",
    "Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico",
    "New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania",
    "Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
    "Virginia","Washington","West Virginia","Wisconsin","Wyoming"]}

TOPIC_RULES = [
    ("Hemp & THC", r"hemp|thc|thca|cannabis|marijuana|cannabinoid|delta-\d"),
    ("Alcohol", r"alcohol|beer|brewer|wine|winery|spirits|distill|liquor|\bttb\b|\babc\b|cider|seltzer"),
    ("Tariffs & Trade", r"tariff|trade (?:deal|talks|war)|retaliat|import|export"),
    ("Taxes & Revenue", r"\btax|excise|revenue|fiscal"),
    ("Courts & Lawsuits", r"court|lawsuit|sued?\b|suit\b|ruling|judge|injunction|appeal|litigat"),
    ("Licensing", r"licens|permit|microbusiness"),
    ("DTC & Distribution", r"\bdtc\b|direct-to-consumer|shipping|distribut|wholesale|self-distribution"),
    ("Enforcement & Recalls", r"enforce|recall|crackdown|seiz|violation|complaint|raid"),
    ("Rulemaking & Guidance", r"rulemaking|proposed rule|draft rule|guidance|comment period|files? rules|regulator"),
]

# Section labels may be authored as literal uppercase or title case with a
# CSS text-transform, so match case-insensitively on the element text.
SECTION_MARKERS = [
    ("top", r"(?i)>\s*top\s+story\s*<"),
    ("federal", r"(?i)>\s*federal\s*<"),
    ("states", r"(?i)>\s*around\s+the\s+states\s*<"),
    ("radar", r"(?i)>\s*on\s+the\s+radar\s*<"),
]


def p(*parts):
    return os.path.join(ROOT, *parts)


def load_json(name, default):
    try:
        with open(p(name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(name, data):
    with open(p(name), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def pretty_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"


def short_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{MONTHS[d.month - 1][:3]} {d.day}"


def topic_from_subject(subject):
    m = re.search(r"—\s*\w{3}\s+\w{3}\s+\d{1,2}:\s*(.+)$", subject)
    return m.group(1).strip() if m else subject


def clean_text(fragment):
    txt = re.sub(r"<[^>]+>", " ", fragment)
    txt = html_mod.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def norm_jurisdiction(tok):
    t = tok.strip()
    up = t.upper().replace("U.S.A.", "U.S.")
    if up in ("FEDERAL", "U.S.", "US", "UNITED STATES", "NATIONAL", "TTB", "FDA", "DEA", "USDA", "CONGRESS"):
        return "Federal"
    if "CANADA" in up or up in ("TRADE", "TARIFFS"):
        return "Trade & Canada"
    if up in ("COURTS", "LITIGATION"):
        return None  # category token, not a jurisdiction — the topic filter covers it
    if up in US_STATES:
        return up.title().replace("Of", "of")
    return t.title() if t.isupper() else t


def classify_topics(text):
    low = text.lower()
    topics = [name for name, rx in TOPIC_RULES if re.search(rx, low)]
    return topics or ["Other"]


def extract_body(raw_html):
    m = re.search(r"<body[^>]*>(.*)</body>", raw_html, re.S | re.I)
    return m.group(1) if m else raw_html


def parse_items(edition_html, entry):
    """Parse TOP STORY / FEDERAL / AROUND THE STATES items from an edition page
    (works on both raw email bodies and wrapped edition pages)."""
    h = edition_html
    # section boundaries in document order
    marks = []
    for name, rx in SECTION_MARKERS:
        m = re.search(rx, h)
        if m:
            marks.append((m.start(), name))
    marks.sort()
    if not marks:
        return []
    spans = {}
    for i, (pos, name) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(h)
        spans[name] = (pos, end)

    items = []
    # Headline = an anchor styled with the Oswald display face; some editions put
    # the font on the <p>, others on the <a> itself, so require Oswald in either tag.
    head_rx = re.compile(r'<p([^>]*)>\s*<a href="([^"]+)"([^>]*)>(.*?)</a>', re.S)
    meta_rx = re.compile(r'<p[^>]*#8a8a8a[^>]*>(.*?)</p>', re.S)
    body_rx = re.compile(r'<p[^>]*#2b2b2b[^>]*>(.*?)</p>', re.S)
    why_rx = re.compile(r'<p[^>]*#1e7a3c[^>]*>(.*?)</p>', re.S)

    for section in ("top", "federal", "states"):
        if section not in spans:
            continue
        s, e = spans[section]
        chunk = h[s:e]
        for hm in head_rx.finditer(chunk):
            if "Oswald" not in hm.group(1) and "Oswald" not in hm.group(3):
                continue
            url, head_html = hm.group(2), hm.group(4)
            headline = clean_text(head_html)
            rest = chunk[hm.end():hm.end() + 3500]
            mm = meta_rx.search(rest)
            if not mm:
                continue
            meta = clean_text(mm.group(1))
            parts = [x.strip() for x in re.split(r"•|•", meta)]
            if len(parts) < 2:
                continue
            jur_raw, source = parts[0], parts[1]
            item_date = parts[2] if len(parts) > 2 else ""
            jurisdictions = [j for j in (norm_jurisdiction(t) for t in jur_raw.split("/") if t.strip()) if j]
            if not jurisdictions:
                jurisdictions = ["Federal"]
            bm = body_rx.search(rest, mm.end() - mm.start() if False else 0)
            # search for the first body paragraph AFTER the meta line
            bm = body_rx.search(rest[mm.end():])
            summary = clean_text(bm.group(1)) if bm else ""
            wm = why_rx.search(rest[mm.end():])
            why = clean_text(wm.group(1)) if wm else ""
            if why.lower().startswith("why it matters:"):
                why = why[len("why it matters:"):].strip()
            items.append({
                "date": entry["date"], "vol": entry["vol"], "ed": entry["ed"],
                "section": section, "jurisdictions": jurisdictions, "source": source,
                "item_date": item_date, "headline": headline, "url": url,
                "summary": summary, "why": why,
                "topics": classify_topics(headline + " " + summary),
                "edition_page": f"editions/{entry['date']}.html",
            })
    return items


def update_items_for(entry, edition_html):
    items = load_json("items.json", [])
    items = [i for i in items if i["date"] != entry["date"]]
    items.extend(parse_items(edition_html, entry))
    items.sort(key=lambda i: (i["date"], {"top": 0, "federal": 1, "states": 2}[i["section"]]))
    save_json("items.json", items)
    return items



def make_og_card(entry, headline, out_path):
    """Render a per-edition 1200x630 OpenGraph card as a brand tile: masthead,
    tagline, large Vol/Ed, date. No headline text — LinkedIn's desktop feed
    shows this image at ~140px where body text is unreadable (redesign
    2026-08-26, approved by Jeremy); the headline renders as the link card's
    title text on every platform anyway. Requires Pillow; caller handles
    failure. The headline parameter is kept for interface stability."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1200, 630
    GREEN, WHITE, MUT, LGT, INK2 = "#00B050", "#ffffff", "#8a8a8a", "#9e9e9e", "#0a0a0a"
    BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    SQ = 0.88  # horizontal squeeze for a condensed display look
    img = Image.new("RGB", (W, H), "#000000")
    d = ImageDraw.Draw(img)

    def condensed_img(text, size, fill, tracking=0):
        f = ImageFont.truetype(BOLD, size)
        tmp_w = int(sum(d.textlength(ch, font=f) + tracking for ch in text)) + 20
        tmp = Image.new("RGBA", (tmp_w, size + 30), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        x = 0
        for ch in text:
            td.text((x, 0), ch, font=f, fill=fill)
            x += td.textlength(ch, font=f) + tracking
        return tmp.resize((int(tmp_w * SQ), size + 30), Image.LANCZOS)

    def condensed_width(text, size, tracking=0):
        f = ImageFont.truetype(BOLD, size)
        return (sum(d.textlength(ch, font=f) + tracking for ch in text)) * SQ

    d.rectangle([0, 0, W, 18], fill=GREEN)
    m = condensed_img("NEW REALM BREWING", 92, WHITE, tracking=2)
    img.paste(m, (86, 84), m)
    f_lbl = ImageFont.truetype(BOLD, 34)
    x = 90
    for ch in "DAILY COMPLIANCE BRIEF":
        d.text((x, 204), ch, font=f_lbl, fill=GREEN)
        x += d.textlength(ch, font=f_lbl) + 12

    v = condensed_img(f"Vol. {entry['vol']}  \u2022  Ed. {entry['ed']}", 82, WHITE, tracking=1)
    img.paste(v, (86, 300), v)
    dt = condensed_img(pretty_date(entry["date"]), 54, LGT, tracking=1)
    img.paste(dt, (86, 412), dt)

    d.rectangle([0, 532, W, H], fill=INK2)
    f_url = ImageFont.truetype(BOLD, 28)
    d.text((86, 570), "compliance.newrealmbrewing.com", font=f_url, fill=GREEN)
    f_tag = ImageFont.truetype(REG, 24)
    t = "\u25b6  Read in 3 min or listen in 2"
    d.text((W - 86 - d.textlength(t, font=f_tag), 572), t, font=f_tag, fill=MUT)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    img.save(out_path, optimize=True)


def og_image_for(entry, items=None):
    """Generate assets/og/<date>.png for an edition; return its site-absolute URL.
    Falls back to the generic banner if Pillow or fonts are unavailable."""
    headline = None
    if items:
        tops = [i for i in items if i["date"] == entry["date"] and i["section"] == "top"]
        if tops:
            headline = tops[0]["headline"]
    if not headline:
        headline = topic_from_subject(entry["subject"])
    out = p("assets", "og", f"{entry['date']}.png")
    try:
        make_og_card(entry, headline, out)
        return f"https://compliance.newrealmbrewing.com/assets/og/{entry['date']}.png"
    except Exception as e:
        print(f"og card fallback ({e.__class__.__name__}: {e}) - using generic banner")
        return "https://compliance.newrealmbrewing.com/assets/og-banner.png"


def render(template, mapping):
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def transcript_section(transcript_text):
    """Collapsible audio-transcript card appended below the brief (2026-08-26).
    The narration script is the verbatim transcript — the audio is synthesized
    from it — so no speech-to-text is involved."""
    if not transcript_text or not transcript_text.strip():
        return ""
    paras = [f"<p>{html_mod.escape(par.strip())}</p>"
             for par in re.split(r"\n\s*\n", transcript_text.strip()) if par.strip()]
    return ('<details class="transcript"><summary>Audio transcript (~2 min read)</summary>'
            + "\n".join(paras) + "</details>")


def edition_title(entry):
    """Headline-first page title (SEO pass 2026-09-02): lead with the top story
    people would actually search for, keep the brand and edition identity after."""
    topic = topic_from_subject(entry["subject"])
    d = datetime.strptime(entry["date"], "%Y-%m-%d")
    return (f"{topic} — NRBC Compliance Brief Vol. {entry['vol']}, "
            f"Ed. {entry['ed']} ({MONTHS[d.month - 1][:3]} {d.day}, {d.year})")


def edition_description(entry, day_items):
    """Meta description built from the day's parsed items: top story plus the
    next headlines, capped near what search results display."""
    tops = [i for i in day_items if i["section"] == "top"]
    rest = [i for i in day_items if i["section"] != "top"]
    parts = []
    if tops:
        parts.append(tops[0]["headline"].rstrip("."))
    more = "; ".join(i["headline"].rstrip(".") for i in rest[:2])
    if more:
        parts.append("Also: " + more)
    desc = ". ".join(parts)
    if not desc:
        desc = topic_from_subject(entry["subject"])
    tail = " Daily alcohol and hemp/THC regulatory brief — federal and all 50 states."
    if len(desc) + len(tail) <= 300:
        desc += "." if not desc.endswith(".") else ""
        desc += tail
    return desc[:300]


def edition_published_iso(date_iso):
    """7:00 AM America/New_York on the edition date, with correct UTC offset."""
    try:
        from zoneinfo import ZoneInfo
        d = datetime.strptime(date_iso, "%Y-%m-%d").replace(
            hour=7, tzinfo=ZoneInfo("America/New_York"))
        return d.isoformat()
    except Exception:
        return f"{date_iso}T07:00:00-05:00"


def edition_jsonld(entry, og_url, description):
    published = edition_published_iso(entry["date"])
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": topic_from_subject(entry["subject"]),
        "alternativeHeadline": f"NRBC Compliance Brief Vol. {entry['vol']}, Ed. {entry['ed']}",
        "description": description,
        "datePublished": published,
        "dateModified": published,
        "image": [og_url or f"{SITE}/assets/og-banner.png"],
        "mainEntityOfPage": f"{SITE}/editions/{entry['date']}.html",
        "isAccessibleForFree": True,
        "author": {"@type": "Organization", "name": "New Realm Brewing",
                   "url": "https://newrealmbrewing.com"},
        "publisher": {"@type": "Organization", "name": "New Realm Brewing",
                      "logo": {"@type": "ImageObject", "url": f"{SITE}/assets/og-banner.png"}},
        "isPartOf": {"@type": "WebSite", "name": "NRBC Compliance Brief", "url": SITE + "/"},
    }
    if entry.get("episode_url"):
        data["associatedMedia"] = {"@type": "AudioObject", "name": "Audio edition (~2 min)",
                                   "url": entry["episode_url"]}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


def write_sitemap(manifest):
    """sitemap.xml: landing page plus every edition page (SEO pass 2026-09-02)."""
    latest = max((e["date"] for e in manifest), default=None)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    if latest:
        lines.append(f"<url><loc>{SITE}/</loc><lastmod>{latest}</lastmod><changefreq>daily</changefreq></url>")
    for e in sorted(manifest, key=lambda x: x["date"]):
        lines.append(f"<url><loc>{SITE}/editions/{e['date']}.html</loc><lastmod>{e['date']}</lastmod></url>")
    lines.append("</urlset>")
    with open(p("sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(manifest) + (1 if latest else 0)


def wrap_edition(entry, raw_html, og_url=None, transcript_text=None, day_items=None):
    with open(p("templates", "edition.template.html"), encoding="utf-8") as f:
        tpl = f.read()
    body = extract_body(raw_html)
    description = edition_description(entry, day_items or [])
    page = render(tpl, {
        "OG_IMAGE": og_url or "https://compliance.newrealmbrewing.com/assets/og-banner.png",
        "TITLE": html_mod.escape(edition_title(entry)),
        "DESCRIPTION": html_mod.escape(description),
        "CANONICAL": f"https://compliance.newrealmbrewing.com/editions/{entry['date']}.html",
        "PUBLISHED": edition_published_iso(entry["date"]),
        "JSONLD": edition_jsonld(entry, og_url, description),
        "EDITION_BODY": body,
        "TRANSCRIPT_SECTION": transcript_section(transcript_text),
    })
    os.makedirs(p("editions"), exist_ok=True)
    with open(p("editions", f"{entry['date']}.html"), "w", encoding="utf-8") as f:
        f.write(page)
    return page


def archive_rows(manifest):
    rows = []
    for e in sorted(manifest, key=lambda x: x["date"], reverse=True):
        topic = html_mod.escape(topic_from_subject(e["subject"]))
        listen = (f'<a class="row-listen" href="{e["episode_url"]}" title="Listen (~2 min)">&#9654;</a>'
                  if e.get("episode_url") else "")
        rows.append(
            f'<li><span class="row-date">{short_date(e["date"])}</span>'
            f'<span class="row-ed">Vol.&nbsp;{e["vol"]}, Ed.&nbsp;{e["ed"]}</span>'
            f'<a class="row-topic" href="editions/{e["date"]}.html">{topic}</a>{listen}</li>'
        )
    return "\n".join(rows)


def build_index(manifest):
    with open(p("templates", "index.template.html"), encoding="utf-8") as f:
        tpl = f.read()
    items = load_json("items.json", [])
    latest = max(manifest, key=lambda e: e["date"])
    topic = html_mod.escape(topic_from_subject(latest["subject"]))
    listen_btn = ""
    if latest.get("episode_url"):
        listen_btn = (f'<a class="btn btn-outline" href="{latest["episode_url"]}">'
                      f"&#9654;&nbsp; Listen to the latest (~2 min)</a>")
    items_json = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = render(tpl, {
        "LATEST_META": f"Vol. {latest['vol']} &bull; Edition {latest['ed']} &bull; {pretty_date(latest['date'])}",
        "LATEST_TOPIC": topic,
        "LATEST_URL": f"editions/{latest['date']}.html",
        "LATEST_LISTEN_BTN": listen_btn,
        "ARCHIVE_ROWS": archive_rows(manifest),
        "EDITION_COUNT": str(len(manifest)),
        "ITEMS_JSON": items_json,
        "UPDATED": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    })
    with open(p("index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("--raw", required=True)
    add.add_argument("--date", required=True)
    add.add_argument("--vol", type=int, required=True)
    add.add_argument("--ed", type=int, required=True)
    add.add_argument("--subject", required=True)
    add.add_argument("--episode", default=None)
    add.add_argument("--transcript", default=None,
                     help="path to the narration script (verbatim audio transcript); "
                          "adds a collapsible Transcript section to the edition page")
    sub.add_parser("build")
    sub.add_parser("reindex")
    sub.add_parser("rebuild")
    args = ap.parse_args()

    manifest = load_json("manifest.json", [])
    if args.cmd == "add":
        entry = {"date": args.date, "vol": args.vol, "ed": args.ed,
                 "subject": args.subject, "episode_url": args.episode}
        manifest = [e for e in manifest if e["date"] != args.date] + [entry]
        manifest.sort(key=lambda e: e["date"])
        with open(args.raw, encoding="utf-8") as f:
            raw = f.read()
        day_items = parse_items(raw, entry)
        og_url = og_image_for(entry, day_items)
        transcript = None
        if args.transcript:
            try:
                with open(args.transcript, encoding="utf-8") as f:
                    transcript = f.read()
            except OSError as e:
                print(f"transcript skipped ({e.__class__.__name__}: {e})")
        page = wrap_edition(entry, raw, og_url, transcript, day_items)
        n = len([i for i in update_items_for(entry, page) if i["date"] == entry["date"]])
        save_json("manifest.json", manifest)
        print(f"parsed {n} items from {entry['date']}; og card: {og_url.rsplit('/', 1)[-1]}")
    elif args.cmd == "rebuild":
        # Re-wrap every existing edition page with the current template
        # (SEO pass 2026-09-02) — the wrapped page is the source since raw
        # emails are not stored in the repo.
        items = load_json("items.json", [])
        for e in manifest:
            with open(p("editions", f"{e['date']}.html"), encoding="utf-8") as f:
                old = f.read()
            m = re.search(r'<div class="brief-wrap">\s*(.*?)\s*</div>\s*</body>', old, re.S)
            if not m:
                print(f"{e['date']}: brief-wrap not found, skipped")
                continue
            inner = m.group(1)
            tm = re.search(r"<details class=\"transcript\">.*?</details>", inner, re.S)
            transcript = None
            if tm:
                paras = re.findall(r"<p>(.*?)</p>", tm.group(0), re.S)
                transcript = "\n\n".join(html_mod.unescape(x) for x in paras)
                inner = inner.replace(tm.group(0), "").strip()
            og_file = p("assets", "og", f"{e['date']}.png")
            og_url = (f"{SITE}/assets/og/{e['date']}.png" if os.path.exists(og_file)
                      else f"{SITE}/assets/og-banner.png")
            day_items = [i for i in items if i["date"] == e["date"]]
            wrap_edition(e, inner, og_url, transcript, day_items)
            print(f"{e['date']} (Ed. {e['ed']}): rebuilt ({len(day_items)} items in description)")
    elif args.cmd == "reindex":
        all_items = []
        for e in manifest:
            with open(p("editions", f"{e['date']}.html"), encoding="utf-8") as f:
                page = f.read()
            got = parse_items(page, e)
            all_items.extend(got)
            print(f"{e['date']} (Ed. {e['ed']}): {len(got)} items")
        all_items.sort(key=lambda i: (i["date"], {"top": 0, "federal": 1, "states": 2}[i["section"]]))
        save_json("items.json", all_items)
    build_index(manifest)
    n_urls = write_sitemap(manifest)
    print(f"ok: {len(manifest)} editions; index.html regenerated; sitemap: {n_urls} urls")


if __name__ == "__main__":
    main()
