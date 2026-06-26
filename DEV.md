# DEV — Technical Notes

## Directory Layout

```
signal_threads/
├── transcripts/
│   ├── index.html                # self-contained episode browser (episodes data inlined)
│   ├── episodes.json             # metadata cache (title, date, tags, abstract, has_html)
│   ├── translate-ui.js           # bilingual UI — shared, loaded by all episode pages
│   ├── translate-ui.css
│   ├── {slug}.html               # episode transcript pages
│   ├── audio/{slug}.mp3
│   ├── data/{slug}.json          # structured transcript (canonical local source)
│   └── translations/{slug}.json  # Chinese translations
└── scripts/
    ├── update.sh                 # scrape + download + build pipeline
    ├── parse_episodes.py         # homepage HTML → episodes.json
    ├── build_index.py            # episodes.json → index.html (data inlined)
    ├── gen_html.py               # source page or data JSON → {slug}.html
    ├── extract_data.py           # existing HTML → data/{slug}.json (one-time import)
    ├── translate_google.py       # Google Translate: data/{slug}.json → translations/{slug}.json
    └── render_all.py             # batch render all HTML, baking translations inline
```

---

## Data Pipeline

```
signalsandthreads.com
      │  update.sh
      ▼
data/{slug}.json          ← structured transcript; never re-scraped after this
      │  translate_google.py
      ▼
translations/{slug}.json  ← {"paragraphs": [{"idx": N, "en": "...", "zh": "..."}]}
      │  render_all.py
      ▼
{slug}.html               ← window.__ZH inlined; works via file:// with no server
```

`data/{slug}.json` schema:
```json
{
  "slug": "build-systems",
  "title": "Build Systems with...",
  "mp3_rel": "audio/build-systems.mp3",
  "transcript": [
    {"type": "ts",      "text": "00:01:23"},
    {"type": "speaker", "text": "RON"},
    {"type": "p",       "text": "So tell me about..."}
  ]
}
```

---

## Why `file://` works without a server

`fetch()` is blocked on `file://`. To work around this, `render_all.py` bakes the
translation JSON directly into each HTML file as:

```html
<script>window.__ZH = { "slug": "...", "paragraphs": [...] };</script>
```

`translate-ui.js` checks `window.__ZH` first; only falls back to `fetch()` when
running under HTTP (e.g., during development).

`index.html` also has all episode metadata inlined via `build_index.py` for the
same reason.

---

## Bilingual UI (`translate-ui.js` / `translate-ui.css`)

These two files are external and shared — changing them takes effect immediately
without re-running `render_all.py`.

Each paragraph group renders as:
```
[EN] [⎘]  [中] [⎘]     ← .para-controls bar
<p data-p="N">English</p>
<div class="zh-block">Chinese</div>
```

- `EN` toggles `p.en-hidden` (display:none) for that paragraph
- `中` toggles `zh-block.zh-folded` (display:none) for that block
- `⎘` after EN copies English; `⎘` after 中 copies Chinese
- Global toolbar buttons iterate all paragraphs at once

`data-p="N"` index on `<p>` elements maps to `{"idx": N}` in the translations JSON.

---

## `translate_google.py` internals

Uses `deep-translator` (`GoogleTranslator`, free, no API key).

- `CHAR_LIMIT = 4000` — splits long paragraphs at sentence boundaries before translating
- `DELAY = 0.2s` between calls to avoid rate-limiting
- Retry logic: on "No translation was found", waits 0.5s and retries with a `.` appended; then 2s back-off; then stores empty string
- `--fix-gaps`: reads existing JSON, skips paragraphs where `zh` is non-empty, only re-translates the gaps — safe to re-run after failures
- Default mode (no flags): automatically detects gaps in existing files and fills them; skips fully-complete episodes

---

## `gen_html.py` — TrEx parser

`TrEx(HTMLParser)` extracts transcript content from a Simplecast-hosted episode page.

Key detail: the transcript `<div>` also contains bare text nodes (SUMMARY, CONTENTS
headings, list items). An `in_text_tag` counter ensures only text inside `<p>`, `<h1>`,
`<h2>` is captured — bare text outside those tags is ignored.

Speaker names come from `<h1>` → type `"speaker"`.  
Timestamps come from `<h2>` → type `"ts"`.  
Paragraphs come from `<p>` → type `"p"`, assigned sequential `data-p` index.

---

## MP3 sourcing

`update.sh` tries two sources in order:

1. **RSS feed** (`feeds.simplecast.com/L9810DOa`) — has `<enclosure url="...">` for recent episodes
2. **Simplecast API** (`api.simplecast.com/episodes/{uuid}`) — fallback for older episodes
   not in RSS; episode UUID is embedded in the page source as `simplecast.com/e/{uuid}`

---

## Adding an episode manually

```bash
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
SLUG=the-episode-slug

curl -sL -A "$UA" "https://signalsandthreads.com/$SLUG/" > /tmp/$SLUG.html

# get MP3 via Simplecast API
EP=$(grep -o 'simplecast\.com/e/[a-f0-9-]\{36\}' /tmp/$SLUG.html | head -1 | cut -d/ -f3)
MP3=$(curl -s "https://api.simplecast.com/episodes/$EP" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['audio_file_url'])")

curl -L -A "$UA" "$MP3" -o "transcripts/audio/$SLUG.mp3"
python3 scripts/gen_html.py /tmp/$SLUG.html $SLUG "audio/$SLUG.mp3" transcripts/
zsh scripts/update.sh --meta-only
```
