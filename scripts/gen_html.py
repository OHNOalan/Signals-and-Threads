#!/usr/bin/env python3
"""
Generate or regenerate a transcript HTML from structured data.

Two modes:
  Scrape mode  (called by update.sh for new episodes):
    python3 gen_html.py <source_page.html> <slug> <mp3_rel_or_empty> <out_dir>
    → parses source page → saves data/{slug}.json → renders {slug}.html

  Render mode  (local regeneration, no network):
    python3 gen_html.py --from-data <slug> <out_dir>
    → reads data/{slug}.json → renders {slug}.html
"""
import sys, re, os, json
import html as hm
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')


# ── HTML renderer (data dict → episode HTML) ──────────────────────────────────

def render_html(data, translations=None):
    """Render episode HTML. If translations dict is provided, bakes it in as
    window.__ZH so the page works fully offline via file://."""
    slug    = data['slug']
    title   = data['title']
    mp3_rel = data.get('mp3_rel', '')
    mp3_url = data.get('mp3_url', '')
    blocks  = data['transcript']

    # Store URLs as data attributes — player.js drives loading entirely.
    # Using <source> elements caused the browser to auto-fetch with preload="metadata"
    # before player.js ran, resulting in duplicate requests and canceled CDN loads.
    audio_attrs = ''
    if mp3_rel:
        audio_attrs += f' data-local="{mp3_rel}"'
    if mp3_url:
        audio_attrs += f' data-cdn="{mp3_url}"'
    audio = (
        f'<audio preload="none"{audio_attrs}></audio>'
        if audio_attrs else
        '<p style="color:#aaa;font-size:.85em">Audio not downloaded.</p>'
    )

    parts = []
    p_idx = 0
    for b in blocks:
        t = b['type']
        text = hm.escape(b['text'])
        if t == 'speaker':
            parts.append(f'<h3 class="speaker">{text}</h3>')
        elif t == 'ts':
            parts.append(f'<span class="ts">{text}</span>')
        elif t == 'p':
            parts.append(f'<p data-p="{p_idx}">{text}</p>')
            p_idx += 1

    transcript_html = '\n'.join(parts)

    # Inline translation data when available (works offline via file://)
    zh_script = ''
    if translations:
        zh_json = json.dumps(translations, ensure_ascii=False)
        zh_script = f'<script>window.__ZH = {zh_json};</script>\n'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='5' fill='%23c05800'/><text x='16' y='23' text-anchor='middle' fill='white' font-family='Georgia,serif' font-size='19' font-weight='bold'>S</text></svg>">
<title>{hm.escape(title)}</title>
<script>(function(){{var s=localStorage.getItem('dark'),d=window.matchMedia('(prefers-color-scheme:dark)').matches;if(s==='1'||(s===null&&d)){{document.documentElement.className='dark';document.documentElement.style.background='#13161f';}}}})();</script>
<link rel="stylesheet" href="player.css">
<link rel="stylesheet" href="translate-ui.css">
<script defer src="translate-ui.js"></script>
<script defer src="player.js"></script>
<style>
  body  {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto;
          padding: 0 24px; background: #fafaf8; color: #1a1a1a; line-height: 1.75; }}
  h1   {{ font-size: 1.55em; margin-bottom: 4px; line-height: 1.3; }}
  .meta {{ color: #777; font-size: .88em; margin-bottom: 18px; }}
  .meta a {{ color: #777; }}
  audio {{ width: 100%; margin-bottom: 28px; }}
  hr   {{ border: none; border-top: 1px solid #ddd; margin: 28px 0; }}
  .ts  {{ display: block; color: #aaa; font-size: .78em; font-family: monospace;
          margin-top: 1.6em; margin-bottom: 3px; }}
  h3.speaker {{ margin: 0 0 5px 0; font-size: .95em; color: #c05800;
                text-transform: uppercase; letter-spacing: .06em; }}
  p    {{ margin: 0 0 .9em 0; }}
  /* Critical dark-mode rules inlined to prevent FOUC before translate-ui.css loads */
  html.dark body {{ background: #13161f; color: #c8ccd8; }}
  html.dark h1   {{ color: #dde0ea; }}
  html.dark hr   {{ border-top-color: #1e2235; }}
  html.dark h3.speaker {{ color: #cc7a3a; }}
</style>
</head>
<body>
<h1>{hm.escape(title)}</h1>
<p class="meta">Signals &amp; Threads &nbsp;&middot;&nbsp; Jane Street &nbsp;&middot;&nbsp;
<a href="https://signalsandthreads.com/{slug}/" target="_blank">signalsandthreads.com</a></p>
{audio}
<hr>
{transcript_html}
{zh_script}</body>
</html>"""


# ── Source-page scraper (TrEx) — only text inside <p>, <h1>, <h2> ─────────────

class TrEx(HTMLParser):
    def __init__(self):
        super().__init__()
        self.on = self.skip_p = False
        self.depth = self.base = 0
        self.in_text_tag = 0   # >0 only when inside <p>, <h1>, or <h2>
        self.blocks = []       # list of {type, text}
        self._buf = []

    def _flush(self, btype):
        text = hm.unescape(''.join(self._buf)).strip()
        if text:
            self.blocks.append({'type': btype, 'text': text})
        self._buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls, id_ = d.get('class', ''), d.get('id', '')
        if 'tab-view' in cls and 'transcript' in cls:
            self.on = True
            self.base = self.depth
        if self.on:
            if tag == 'h3' and id_ == 'blurb':
                self.skip_p = True
            elif tag == 'h1':
                self._buf = []
                self.in_text_tag += 1
            elif tag == 'h2':
                self._buf = []
                self.in_text_tag += 1
            elif tag == 'p' and not self.skip_p:
                self._buf = []
                self.in_text_tag += 1
        self.depth += 1

    def handle_endtag(self, tag):
        self.depth -= 1
        if self.on:
            if tag == 'h1':
                self._flush('speaker')
                self.in_text_tag = max(0, self.in_text_tag - 1)
            elif tag == 'h2':
                self._flush('ts')
                self.in_text_tag = max(0, self.in_text_tag - 1)
            elif tag == 'p':
                if not self.skip_p:
                    self._flush('p')
                self.skip_p = False
                self.in_text_tag = max(0, self.in_text_tag - 1)
                self._buf = []
            if self.depth <= self.base:
                self.on = False

    def handle_data(self, d):
        if self.on and not self.skip_p and self.in_text_tag > 0:
            self._buf.append(d)

    def handle_entityref(self, name):
        if self.on and self.in_text_tag > 0:
            self._buf.append(f'&{name};')

    def handle_charref(self, name):
        if self.on and self.in_text_tag > 0:
            self._buf.append(f'&#{name};')


# ── Entry point ───────────────────────────────────────────────────────────────

def scrape_mode(page_file, slug, mp3_rel, out_dir):
    raw = open(page_file, encoding='utf-8', errors='replace').read()
    if len(raw) < 500:
        print(f'  SKIP: empty page for {slug}')
        sys.exit(0)

    m = re.search(r'<title>Signals and Threads \| (.*?)</title>', raw)
    title = hm.unescape(m.group(1)) if m else slug.replace('-', ' ').title()

    ex = TrEx()
    ex.feed(raw)

    data = {
        'slug':       slug,
        'title':      title,
        'mp3_rel':    mp3_rel,
        'transcript': ex.blocks,
    }

    # Save structured data (canonical local source)
    data_dir = os.path.join(out_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    data_path = os.path.join(data_dir, f'{slug}.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Render HTML
    out_path = os.path.join(out_dir, f'{slug}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(render_html(data))
    print(f'  Saved: data/{slug}.json + {slug}.html')


def render_mode(slug, out_dir):
    data_path = os.path.join(out_dir, 'data', f'{slug}.json')
    if not os.path.exists(data_path):
        print(f'  SKIP: no data file for {slug}')
        return
    data = json.load(open(data_path, encoding='utf-8'))
    out_path = os.path.join(out_dir, f'{slug}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(render_html(data))
    p_count = sum(1 for b in data['transcript'] if b['type'] == 'p')
    print(f'  Rendered: {slug}.html ({p_count} paragraphs)')


if __name__ == '__main__':
    if sys.argv[1] == '--from-data':
        _, _, slug, out_dir = sys.argv
        render_mode(slug, out_dir)
    else:
        page_file, slug, mp3_rel, out_dir = sys.argv[1:]
        scrape_mode(page_file, slug, mp3_rel, out_dir)
