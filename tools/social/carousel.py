#!/usr/bin/env python3
"""Build the daily LinkedIn carousel PDF from items.json (brand style).

Usage: python3 tools/social/carousel.py --date YYYY-MM-DD --out /path/brief-carousel.pdf
Pages are landscape 16:9 (1920x1080pt), capped at 6 pages: cover, the top story,
up to 3 further item cards (federal, then states), then a subscribe CTA page.
(16:9 landscape adopted 2026-09-19 at Jeremy's direction: LinkedIn's document
viewer fills the post width, so only a page as wide as the viewer shows one
page at a time — square and 4:5 both left the next page peeking.)
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

W, H = 1920, 1080
MAX_ITEM_PAGES = 4  # top story + up to 3 more; cover + items + CTA <= 6 pages
BLACK, WHITE, GREEN = HexColor("#000000"), HexColor("#ffffff"), HexColor("#00B050")
INK, MUTED, DGREEN, BG = HexColor("#2b2b2b"), HexColor("#8a8a8a"), HexColor("#1e7a3c"), HexColor("#ebebeb")

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

def draw_lines(c, lines, x, y, font, size, leading, color, maxlines=None):
    c.setFont(font, size); c.setFillColor(color)
    for i, ln in enumerate(lines if maxlines is None else lines[:maxlines]):
        c.drawString(x, y - i * leading, ln)
    n = len(lines if maxlines is None else lines[:maxlines])
    return y - n * leading

def header(c, sub):
    c.setFillColor(BLACK); c.rect(0, H - 150, W, 150, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 44); c.drawString(80, H - 84, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 18)
    c.drawString(80, H - 120, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(MUTED); c.setFont("OpenSans", 17); c.drawRightString(W - 80, H - 120, sub)

def cover(c, entry, tops):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 72); c.drawString(100, H - 190, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 26)
    c.drawString(100, H - 244, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 22)
    c.drawString(100, H - 298, f"Vol. {entry['vol']}  •  Edition {entry['ed']}  •  {entry['pretty']}")
    c.setStrokeColor(GREEN); c.setLineWidth(6); c.line(100, H - 340, 360, H - 340)
    if tops:
        c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 22); c.drawString(100, 440, "TOP STORY")
        y = 372
        for ln in wrap(c, tops[0]["headline"], "Oswald-Bold", 54, W - 220)[:3]:
            c.setFillColor(WHITE); c.setFont("Oswald-Bold", 54); c.drawString(100, y, ln); y -= 68
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 22)
    c.drawString(100, 84, "Swipe for today's items  →")
    c.showPage()

def item_page(c, entry, it, idx, total):
    c.setFillColor(BG); c.rect(0, 0, W, H, stroke=0, fill=1)
    header(c, f"Vol. {entry['vol']} • Ed. {entry['ed']} • {entry['pretty']}")
    c.setFillColor(WHITE); c.rect(72, 84, W - 144, H - 150 - 84 - 28, stroke=0, fill=1)
    label = {"top": "TOP STORY", "federal": "FEDERAL", "states": "AROUND THE STATES"}.get(it["section"], "BRIEF")
    x, top = 140, H - 232
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 22); c.drawString(x, top, label)
    c.setFillColor(MUTED); c.setFont("OpenSans", 18); c.drawRightString(W - 140, top, f"{idx}/{total}")
    y = top - 64
    y = draw_lines(c, wrap(c, it["headline"], "Oswald-Bold", 42, W - 280), x, y, "Oswald-Bold", 42, 54, BLACK, 3) - 14
    meta = " • ".join(v for v in [" / ".join(it.get("jurisdictions", [])), it.get("source", ""), it.get("item_date", "")] if v)
    y = draw_lines(c, wrap(c, meta, "OpenSans-Bold", 18, W - 280), x, y, "OpenSans-Bold", 18, 28, MUTED, 2) - 18
    if it.get("summary"):
        y = draw_lines(c, wrap(c, it["summary"], "OpenSans", 26, 1440), x, y, "OpenSans", 26, 40, INK, 7) - 22
    if it.get("why"):
        c.setStrokeColor(GREEN); c.setLineWidth(6); ly = y + 24
        lines = wrap(c, "Why it matters: " + it["why"], "OpenSans-Italic", 24, 1400)[:4]
        c.line(x, ly, x, ly - len(lines) * 36 + 8)
        draw_lines(c, lines, x + 28, y, "OpenSans-Italic", 24, 36, DGREEN, 4)
    c.showPage()

def cta(c, entry):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 58); c.drawString(100, H - 220, "Every morning at 7:00 AM ET.")
    c.setFillColor(HexColor("#cfcfcf")); c.setFont("OpenSans", 26); y = H - 300
    for ln in wrap(c, "Alcohol and hemp/THC regulation — federal and all 50 states. Read it in three minutes or listen in two. Every headline links to the original source.", "OpenSans", 26, 1500):
        c.drawString(100, y, ln); y -= 42
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 32)
    c.drawString(100, y - 64, "compliance.newrealmbrewing.com")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 24)
    c.drawString(100, y - 124, "Subscribe by email, browse the archive, and follow the podcast — link in the first comment.")
    c.setFillColor(MUTED); c.setFont("OpenSans", 18)
    c.drawString(100, 84, "For general information only — not legal advice.")
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
    print(f"carousel: {a.out} ({len(items)} item pages + cover + CTA, landscape 16:9)")

if __name__ == "__main__":
    main()
