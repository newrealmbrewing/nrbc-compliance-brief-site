#!/usr/bin/env python3
"""NRBC Compliance Brief site generator.

Repo layout (all paths relative to repo root):
  manifest.json                 - list of editions, oldest first
  templates/index.template.html - landing page template
  templates/edition.template.html - wrapper for a single edition page
  editions/YYYY-MM-DD.html      - generated edition pages
  index.html                    - generated landing page

Commands:
  python3 tools/generate.py add --raw <email.html> --date 2026-08-25 --vol 1 --ed 11 \
      --subject "New Realm Compliance Brief — Vol. 1, Ed. 11 — Tue Aug 25: ..." \
      [--episode https://share.transistor.fm/s/xxxx]
      Wraps the raw email HTML into editions/<date>.html, appends/updates the
      manifest entry, and regenerates index.html.
  python3 tools/generate.py build
      Regenerates index.html (and re-wraps any editions_raw inputs if given
      via --raw-dir) from manifest.json.

Stdlib only. Idempotent: re-adding an existing date replaces that entry.
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def p(*parts):
    return os.path.join(ROOT, *parts)


def load_manifest():
    with open(p("manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def save_manifest(m):
    m.sort(key=lambda e: e["date"])
    with open(p("manifest.json"), "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)
        f.write("\n")


def pretty_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{WEEKDAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"


def short_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{MONTHS[d.month - 1][:3]} {d.day}"


def topic_from_subject(subject):
    """Take the text after the 'Wkdy Mon D:' token in the email subject."""
    m = re.search(r"—\s*\w{3}\s+\w{3}\s+\d{1,2}:\s*(.+)$", subject)
    return m.group(1).strip() if m else subject


def extract_body(raw_html):
    """Return the inner content of a full HTML document, or the input as-is
    if it is already a fragment (Outlook-stored bodies are fragments)."""
    m = re.search(r"<body[^>]*>(.*)</body>", raw_html, re.S | re.I)
    return m.group(1) if m else raw_html


def render(template, mapping):
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def wrap_edition(entry, raw_html):
    with open(p("templates", "edition.template.html"), encoding="utf-8") as f:
        tpl = f.read()
    body = extract_body(raw_html)
    topic = topic_from_subject(entry["subject"])
    page = render(tpl, {
        "TITLE": html_mod.escape(f"Vol. {entry['vol']}, Ed. {entry['ed']} — {pretty_date(entry['date'])} — NRBC Compliance Brief"),
        "DESCRIPTION": html_mod.escape(topic),
        "CANONICAL": f"https://compliance.newrealmbrewing.com/editions/{entry['date']}.html",
        "EDITION_BODY": body,
    })
    os.makedirs(p("editions"), exist_ok=True)
    with open(p("editions", f"{entry['date']}.html"), "w", encoding="utf-8") as f:
        f.write(page)


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
    latest = max(manifest, key=lambda e: e["date"])
    topic = html_mod.escape(topic_from_subject(latest["subject"]))
    listen_btn = ""
    if latest.get("episode_url"):
        listen_btn = (f'<a class="btn btn-outline" href="{latest["episode_url"]}">'
                      f"&#9654;&nbsp; Listen to the latest (~2 min)</a>")
    page = render(tpl, {
        "LATEST_META": f"Vol. {latest['vol']} &bull; Edition {latest['ed']} &bull; {pretty_date(latest['date'])}",
        "LATEST_TOPIC": topic,
        "LATEST_URL": f"editions/{latest['date']}.html",
        "LATEST_LISTEN_BTN": listen_btn,
        "ARCHIVE_ROWS": archive_rows(manifest),
        "EDITION_COUNT": str(len(manifest)),
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
    sub.add_parser("build")
    args = ap.parse_args()

    manifest = load_manifest()
    if args.cmd == "add":
        entry = {
            "date": args.date,
            "vol": args.vol,
            "ed": args.ed,
            "subject": args.subject,
            "episode_url": args.episode,
        }
        manifest = [e for e in manifest if e["date"] != args.date] + [entry]
        with open(args.raw, encoding="utf-8") as f:
            raw = f.read()
        wrap_edition(entry, raw)
        save_manifest(manifest)
    build_index(manifest)
    print(f"ok: {len(manifest)} editions; index.html regenerated")


if __name__ == "__main__":
    main()
