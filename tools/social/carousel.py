#!/usr/bin/env python3
"""Build the daily LinkedIn carousel PDF from items.json (brand style).

Usage: python3 tools/social/carousel.py --date YYYY-MM-DD --out /path/brief-carousel.pdf
Poster-style deck, 4:5 portrait pages (1080x1350pt), capped at 6 pages (cover,
top story, up to 3 further items, CTA). Per Jeremy's direction 2026-09-19 each
item page carries: the title (large), the item's summary paragraph at a size
readable in the feed, and a closing "Why it matters" line when the edition has
one. No sentence-splitting of source text (abbreviations like "Gov." broke it).
Fonts: converts the repo's woff2 to TTF at runtime.
"""
import argparse, json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fontTools.ttLib import woff2
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

W, H = 1080, 1350
MAX_ITEM_PAGES = 4  # top story + up to 3 more; cover + items + CTA <= 6 pages
BLACK, WHITE, GREEN = HexColor("#000000"), HexColor("#ffffff"), HexColor("#00B050")
INK, MUTED, DGREEN, BG = HexColor("#2b2b2b"), HexColor("#8a8a8a"), HexColor("#1e7a3c"), HexColor("#ebebeb")
MARGIN = 84

def register_fonts():
    td = tempfile.mkdtemp()
    for src, name in [("oswald-latin-700-normal", "Oswald-Bold"),
                      ("oswald-latin-500-normal", "Oswald-Med"),
                      ("open-sans-latin-400-normal", "OpenSans"),
                      ("open-sans-latin-700-normal", "OpenSans-Bold"),
                      ("open-sans-latin-400-italic", "OpenSans-Italic")]:
        ttf = os.path.join(td, name + ".ttf")
        woff2.decompress(os.path.join(ROOT, "assets", "fonts", src + ".woff2"), ttf)
        pdfmetrics.registerFont(TTFont(name, ttf))

def wrap(c, text, font, size, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def clip_lines(lines, maxlines):
    """Cap at maxlines, ellipsizing the last kept line if content was cut."""
    if len(lines) <= maxlines:
        return lines
    kept = lines[:maxlines]
    kept[-1] = kept[-1].rstrip(".,;:") + " …"
    return kept

def draw_lines(c, lines, x, y, font, size, leading, color):
    c.setFont(font, size); c.setFillColor(color)
    for i, ln in enumerate(lines):
        c.drawString(x, y - i * leading, ln)
    return y - len(lines) * leading

def footer_bar(c, entry, light_page=True):
    c.setFillColor(BLACK); c.rect(0, 0, W, 96, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 26); c.drawString(MARGIN, 36, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 15)
    c.drawRightString(W - MARGIN, 40, f"DAILY COMPLIANCE BRIEF  •  VOL. {entry['vol']}, ED. {entry['ed']}")

def cover(c, entry, tops):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 64); c.drawString(MARGIN, H - 170, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 24)
    c.drawString(MARGIN, H - 222, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 24)
    c.drawString(MARGIN, H - 274, f"Vol. {entry['vol']}  •  Edition {entry['ed']}  •  {entry['pretty']}")
    c.setStrokeColor(GREEN); c.setLineWidth(6); c.line(MARGIN, H - 318, MARGIN + 250, H - 318)
    if tops:
        c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 28); c.drawString(MARGIN, 796, "TOP STORY")
        lines = clip_lines(wrap(c, tops[0]["headline"], "Oswald-Bold", 76, W - 2 * MARGIN), 5)
        draw_lines(c, lines, MARGIN, 716, "Oswald-Bold", 76, 92, WHITE)
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 26)
    c.drawString(MARGIN, 136, "Swipe for today's items  →")
    c.showPage()

def item_page(c, entry, it, idx, total):
    c.setFillColor(WHITE); c.rect(0, 0, W, H, stroke=0, fill=1)
    label = {"top": "TOP STORY", "federal": "FEDERAL", "states": "AROUND THE STATES"}.get(it["section"], "BRIEF")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 28); c.drawString(MARGIN, H - 130, label)
    c.setFillColor(MUTED); c.setFont("OpenSans", 24); c.drawRightString(W - MARGIN, H - 130, f"{idx}/{total}")
    juris = " / ".join(it.get("jurisdictions", []))
    if juris and juris.upper() != label:
        c.setFillColor(INK); c.setFont("OpenSans-Bold", 26); c.drawString(MARGIN, H - 180, juris.upper())
    # Title
    hl = clip_lines(wrap(c, it["headline"], "Oswald-Bold", 56, W - 2 * MARGIN), 4)
    y = draw_lines(c, hl, MARGIN, H - 272, "Oswald-Bold", 56, 70, BLACK) - 24
    # Details paragraph — the item's full summary, sized to read in the feed.
    if it.get("summary"):
        lines = clip_lines(wrap(c, it["summary"], "OpenSans", 30, W - 2 * MARGIN), 10)
        y = draw_lines(c, lines, MARGIN, y - 16, "OpenSans", 30, 44, INK) - 26
    # Closing takeaway, when the edition carries one.
    if it.get("why"):
        lines = clip_lines(wrap(c, "Why it matters: " + it["why"], "OpenSans-Italic", 28, W - 2 * MARGIN - 36), 5)
        c.setStrokeColor(GREEN); c.setLineWidth(8)
        c.line(MARGIN, y - 8, MARGIN, y - 8 - (len(lines) - 1) * 42 - 30)
        draw_lines(c, lines, MARGIN + 36, y - 38, "OpenSans-Italic", 28, 42, DGREEN)
    src_line = " • ".join(v for v in [it.get("source", ""), it.get("item_date", "")] if v)
    if src_line:
        c.setFillColor(MUTED); c.setFont("OpenSans", 22); c.drawString(MARGIN, 140, f"Source: {src_line} — link in the email & site edition")
    footer_bar(c, entry)
    c.showPage()

def cta(c, entry):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    lines = ["Every morning", "at 7:00 AM ET."]
    y = H - 300
    for ln in lines:
        c.setFillColor(WHITE); c.setFont("Oswald-Bold", 84); c.drawString(MARGIN, y, ln); y -= 100
    c.setFillColor(HexColor("#cfcfcf")); c.setFont("OpenSans", 30); y -= 30
    for ln in wrap(c, "Alcohol and hemp/THC regulation — federal and all 50 states. Read it in three minutes or listen in two.", "OpenSans", 30, W - 2 * MARGIN):
        c.drawString(MARGIN, y, ln); y -= 46
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 36)
    c.drawString(MARGIN, y - 60, "compliance.newrealmbrewing.com")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 26)
    c.drawString(MARGIN, y - 120, "Subscribe, browse the archive, and follow the")
    c.drawString(MARGIN, y - 160, "podcast — link in the first comment.")
    c.setFillColor(MUTED); c.setFont("OpenSans", 20)
    c.drawString(MARGIN, 136, "For general information only — not legal advice.")
    c.showPage()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    register_fonts()
    manifest = json.load(open(os.path.join(ROOT, "manifest.json")))
    items = [i for i in json.load(open(os.path.join(ROOT, "items.json"))) if i["date"] == a.date]
    e = next(x for x in manifest if x["date"] == a.date)
    from datetime import datetime
    d = datetime.strptime(a.date, "%Y-%m-%d")
    e = dict(e, pretty=d.strftime("%A, %B %-d, %Y").replace(" 0", " "))
    order = {"top": 0, "federal": 1, "states": 2}
    items.sort(key=lambda i: order.get(i["section"], 3))
    items = items[:MAX_ITEM_PAGES]
    c = canvas.Canvas(a.out, pagesize=(W, H))
    c.setTitle(f"NRBC Compliance Brief — Vol. {e['vol']}, Ed. {e['ed']}")
    cover(c, e, [i for i in items if i["section"] == "top"])
    for n, it in enumerate(items, 1):
        item_page(c, e, it, n, len(items))
    cta(c, e)
    c.save()
    print(f"carousel: {a.out} ({len(items)} item pages + cover + CTA, poster 4:5)")

if __name__ == "__main__":
    main()
