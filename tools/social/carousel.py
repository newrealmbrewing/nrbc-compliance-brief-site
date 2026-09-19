#!/usr/bin/env python3
"""Build the daily LinkedIn carousel PDF from items.json (brand style).

Usage: python3 tools/social/carousel.py --date YYYY-MM-DD --out /path/brief-carousel.pdf
Pages are portrait 4:5 (1080x1350pt), capped at 6 pages: cover, the top story,
up to 3 further item cards (federal, then states), then a subscribe CTA page.
(4:5 portrait adopted 2026-09-19 at Jeremy's direction so the feed viewer
shows exactly one page at a time; square 1:1 + 6-page cap were 2026-09-17.)
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
    c.setFillColor(BLACK); c.rect(0, H - 184, W, 184, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 48); c.drawString(72, H - 96, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 20)
    c.drawString(72, H - 136, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(MUTED); c.setFont("OpenSans", 18); c.drawRightString(W - 72, H - 136, sub)

def cover(c, entry, tops):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 68); c.drawString(88, H - 230, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 26)
    c.drawString(88, H - 284, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 24)
    c.drawString(88, H - 344, f"Vol. {entry['vol']}  •  Edition {entry['ed']}  •  {entry['pretty']}")
    c.setStrokeColor(GREEN); c.setLineWidth(6); c.line(88, H - 388, 340, H - 388)
    if tops:
        c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 22); c.drawString(88, 560, "TOP STORY")
        y = 500
        for ln in wrap(c, tops[0]["headline"], "Oswald-Bold", 48, W - 176)[:4]:
            c.setFillColor(WHITE); c.setFont("Oswald-Bold", 48); c.drawString(88, y, ln); y -= 60
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 22)
    c.drawString(88, 104, "Swipe for today's items  →")
    c.showPage()

def item_page(c, entry, it, idx, total):
    c.setFillColor(BG); c.rect(0, 0, W, H, stroke=0, fill=1)
    header(c, f"Vol. {entry['vol']} • Ed. {entry['ed']} • {entry['pretty']}")
    c.setFillColor(WHITE); c.rect(56, 128, W - 112, H - 184 - 184, stroke=0, fill=1)
    label = {"top": "TOP STORY", "federal": "FEDERAL", "states": "AROUND THE STATES"}.get(it["section"], "BRIEF")
    x, top = 104, H - 264
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 22); c.drawString(x, top, label)
    c.setFillColor(MUTED); c.setFont("OpenSans", 19); c.drawRightString(W - 104, top, f"{idx}/{total}")
    y = top - 68
    y = draw_lines(c, wrap(c, it["headline"], "Oswald-Bold", 40, W - 208), x, y, "Oswald-Bold", 40, 52, BLACK, 4) - 16
    meta = " • ".join(v for v in [" / ".join(it.get("jurisdictions", [])), it.get("source", ""), it.get("item_date", "")] if v)
    y = draw_lines(c, wrap(c, meta, "OpenSans-Bold", 19, W - 208), x, y, "OpenSans-Bold", 19, 28, MUTED, 2) - 20
    if it.get("summary"):
        y = draw_lines(c, wrap(c, it["summary"], "OpenSans", 24, W - 208), x, y, "OpenSans", 24, 36, INK, 9) - 24
    if it.get("why"):
        c.setStrokeColor(GREEN); c.setLineWidth(6); ly = y + 24
        lines = wrap(c, "Why it matters: " + it["why"], "OpenSans-Italic", 23, W - 240)[:5]
        c.line(x, ly, x, ly - len(lines) * 34 + 8)
        draw_lines(c, lines, x + 28, y, "OpenSans-Italic", 23, 34, DGREEN, 5)
    c.showPage()

def cta(c, entry):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 60); c.drawString(88, H - 320, "Every morning at 7:00 AM ET.")
    c.setFillColor(HexColor("#cfcfcf")); c.setFont("OpenSans", 26); y = H - 400
    for ln in wrap(c, "Alcohol and hemp/THC regulation — federal and all 50 states. Read it in three minutes or listen in two. Every headline links to the original source.", "OpenSans", 26, W - 200):
        c.drawString(88, y, ln); y -= 40
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 30)
    c.drawString(88, y - 60, "compliance.newrealmbrewing.com")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 23)
    c.drawString(88, y - 116, "Subscribe by email, browse the archive, and follow the podcast —")
    c.drawString(88, y - 152, "link in the first comment.")
    c.setFillColor(MUTED); c.setFont("OpenSans", 18)
    c.drawString(88, 96, "For general information only — not legal advice.")
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
    print(f"carousel: {a.out} ({len(items)} item pages + cover + CTA, portrait 4:5)")

if __name__ == "__main__":
    main()
