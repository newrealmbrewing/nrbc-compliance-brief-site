#!/usr/bin/env python3
"""Build the daily LinkedIn carousel PDF from items.json (brand style).

Usage: python3 tools/social/carousel.py --date YYYY-MM-DD --out /path/brief-carousel.pdf
Pages are 4:5 portrait (540x675pt): cover, one card per item (top story,
federal, states — radar items are grouped on one closing-radar card when
present in the edition page but items.json carries top/federal/states only),
then a subscribe CTA page. Fonts: converts the repo's woff2 to TTF at runtime.
"""
import argparse, json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from fontTools.ttLib import woff2
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

W, H = 540, 675
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
    c.setFillColor(BLACK); c.rect(0, H - 92, W, 92, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 24); c.drawString(36, H - 48, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 10)
    c.drawString(36, H - 68, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(MUTED); c.setFont("OpenSans", 9); c.drawRightString(W - 36, H - 68, sub)

def cover(c, entry, tops):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 34); c.drawString(44, H - 130, "NEW REALM BREWING")
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 13)
    c.drawString(44, H - 158, "D A I L Y   C O M P L I A N C E   B R I E F")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 12)
    c.drawString(44, H - 190, f"Vol. {entry['vol']}  •  Edition {entry['ed']}  •  {entry['pretty']}")
    c.setStrokeColor(GREEN); c.setLineWidth(3); c.line(44, H - 214, 170, H - 214)
    if tops:
        c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 11); c.drawString(44, 330, "TOP STORY")
        y = 300
        for ln in wrap(c, tops[0]["headline"], "Oswald-Bold", 26, W - 88)[:5]:
            c.setFillColor(WHITE); c.setFont("Oswald-Bold", 26); c.drawString(44, y, ln); y -= 33
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 11)
    c.drawString(44, 64, "Swipe for today's items  →")
    c.showPage()

def item_page(c, entry, it, idx, total):
    c.setFillColor(BG); c.rect(0, 0, W, H, stroke=0, fill=1)
    header(c, f"Vol. {entry['vol']} • Ed. {entry['ed']} • {entry['pretty']}")
    c.setFillColor(WHITE); c.rect(28, 64, W - 56, H - 92 - 92, stroke=0, fill=1)
    label = {"top": "TOP STORY", "federal": "FEDERAL", "states": "AROUND THE STATES"}.get(it["section"], "BRIEF")
    x, top = 52, H - 132
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 11); c.drawString(x, top, label)
    c.setFillColor(MUTED); c.setFont("OpenSans", 9.5); c.drawRightString(W - 52, top, f"{idx}/{total}")
    y = top - 34
    y = draw_lines(c, wrap(c, it["headline"], "Oswald-Bold", 21, W - 104), x, y, "Oswald-Bold", 21, 27, BLACK, 5) - 8
    meta = " • ".join(v for v in [" / ".join(it.get("jurisdictions", [])), it.get("source", ""), it.get("item_date", "")] if v)
    y = draw_lines(c, wrap(c, meta, "OpenSans-Bold", 9.5, W - 104), x, y, "OpenSans-Bold", 9.5, 14, MUTED, 2) - 10
    if it.get("summary"):
        y = draw_lines(c, wrap(c, it["summary"], "OpenSans", 12.5, W - 104), x, y, "OpenSans", 12.5, 19, INK, 11) - 12
    if it.get("why"):
        c.setStrokeColor(GREEN); c.setLineWidth(3); ly = y + 12
        lines = wrap(c, "Why it matters: " + it["why"], "OpenSans-Italic", 11.5, W - 120)[:5]
        c.line(x, ly, x, ly - len(lines) * 17 + 4)
        draw_lines(c, lines, x + 14, y, "OpenSans-Italic", 11.5, 17, DGREEN, 5)
    c.showPage()

def cta(c, entry):
    c.setFillColor(BLACK); c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(WHITE); c.setFont("Oswald-Bold", 30); c.drawString(44, H - 200, "Every morning at 7:00 AM ET.")
    c.setFillColor(HexColor("#cfcfcf")); c.setFont("OpenSans", 13); y = H - 240
    for ln in wrap(c, "Alcohol and hemp/THC regulation — federal and all 50 states. Read it in three minutes or listen in two. Every headline links to the original source.", "OpenSans", 13, W - 100):
        c.drawString(44, y, ln); y -= 20
    c.setFillColor(GREEN); c.setFont("OpenSans-Bold", 15)
    c.drawString(44, y - 30, "compliance.newrealmbrewing.com")
    c.setFillColor(HexColor("#9e9e9e")); c.setFont("OpenSans", 11.5)
    c.drawString(44, y - 58, "Subscribe by email, browse the archive, and follow the podcast —")
    c.drawString(44, y - 76, "link in the first comment.")
    c.setFillColor(MUTED); c.setFont("OpenSans", 9)
    c.drawString(44, 56, "For general information only — not legal advice.")
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
    c = canvas.Canvas(a.out, pagesize=(W, H))
    c.setTitle(f"NRBC Compliance Brief — Vol. {e['vol']}, Ed. {e['ed']}")
    cover(c, e, [i for i in items if i["section"] == "top"])
    for n, it in enumerate(items, 1):
        item_page(c, e, it, n, len(items))
    cta(c, e)
    c.save()
    print(f"carousel: {a.out} ({len(items)} item pages + cover + CTA)")

if __name__ == "__main__":
    main()
