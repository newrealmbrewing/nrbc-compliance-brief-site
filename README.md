# NRBC Compliance Brief — site

Public archive and landing page for the New Realm Brewing Daily Compliance Brief,
served by GitHub Pages at **https://compliance.newrealmbrewing.com**.

## How it stays current

Every morning, after the 7:00 AM ET email is sent, the daily automation:

1. Saves the day's sent email HTML.
2. Runs `python3 tools/generate.py add --raw <email.html> --date YYYY-MM-DD --vol V --ed E --subject "<email subject>" [--episode <share.transistor.fm URL>]`
   which writes `editions/YYYY-MM-DD.html`, updates `manifest.json`, and regenerates `index.html`.
3. Pushes the three changed files via the GitHub contents API.

`manifest.json` is the source of truth for the archive listing (the mailbox remains
the ultimate durable record — this repo can be rebuilt from Sent Items at any time).

## Layout

- `index.html` — generated landing page. **Do not hand-edit**; change `templates/index.template.html` and rebuild.
- `editions/` — one page per edition, the sent email wrapped in site chrome (`templates/edition.template.html`).
- `tools/generate.py` — stdlib-only generator. `add` is idempotent per date; `build` regenerates the index only.
- `CNAME` — custom-domain binding for GitHub Pages.

## Rebuild everything

```
python3 tools/generate.py build
```
