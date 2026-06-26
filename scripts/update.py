#!/usr/bin/env python3
"""
Signals & Threads local archive updater.

Usage:
  python3 scripts/update.py              # detect new episodes, download, rebuild index
  python3 scripts/update.py --index-only # rebuild index.html only (no downloading)
"""
import subprocess, re, os, time, json, sys
import html as html_mod
from html.parser import HTMLParser

BASE     = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
OUT_DIR  = os.path.join(BASE, 'transcripts')
META_FILE = os.path.join(OUT_DIR, 'meta.json')
AUDIO_DIR = os.path.join(OUT_DIR, 'audio')


# ── Network ───────────────────────────────────────────────────────────────────

def curl(url, binary=False, timeout=30):
    import tempfile
    tmp = tempfile.mktemp(suffix='.bin')
    os.system(
        f"curl -sL --max-time {timeout} "
        f"-A 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' "
        f"'{url}' -o '{tmp}' 2>/dev/null"
    )
    if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        return b'' if binary else ''
    with open(tmp, 'rb') as f:
        data = f.read()
    os.unlink(tmp)
    return data if binary else data.decode('utf-8', errors='replace')


# ── Homepage: get all episode slugs ──────────────────────────────────────────

def get_all_episodes():
    """Return list of (slug, title) from the signalsandthreads.com homepage."""
    data = curl('https://signalsandthreads.com/')
    links = re.findall(r'href="/([a-z0-9][a-z0-9-]+)/"[^>]*>([^<]+)</a>', data)
    seen, episodes = set(), []
    for slug, title in links:
        if slug in seen:
            continue
        seen.add(slug)
        episodes.append((slug, title.strip()))
    return episodes


# ── Episode page metadata ─────────────────────────────────────────────────────

def get_episode_meta(slug):
    """Fetch episode page and return metadata dict."""
    data = curl(f'https://signalsandthreads.com/{slug}/')
    if len(data) < 500:
        return {}

    # episode number + date from <h5 class="season-episode-section">
    ep_num = date_str = ''
    h5 = re.search(r'class="season-episode-section"[^>]*>(.*?)</h5>', data, re.DOTALL)
    if h5:
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html_mod.unescape(h5.group(1)))).strip()
        ep_m   = re.search(r'Episode\s*(\d+)', text)
        date_m = re.search(r'\|\s*(.+)', text)
        ep_num   = ep_m.group(1) if ep_m else ''
        date_str = date_m.group(1).strip() if date_m else ''

    # tags
    tags_m = re.search(r'data-tags="([^"]+)"', data)
    tags = [t.strip() for t in tags_m.group(1).split(',')] if tags_m else []

    # abstract: newer episodes have a BLURB section; older have <p> after </h5>
    abstract = ''
    blurb_m = re.search(r'id="blurb"[^>]*>BLURB</h3>\s*<p>(.*?)</p>', data, re.DOTALL)
    if blurb_m:
        abstract = re.sub(r'<[^>]+>', '', html_mod.unescape(blurb_m.group(1))).strip()
    else:
        after_h5 = re.search(r'</h5>\s*(?:<div[^>]*>.*?</div>\s*)?<p>(.*?)</p>', data, re.DOTALL)
        if after_h5:
            abstract = re.sub(r'<[^>]+>', '', html_mod.unescape(after_h5.group(1))).strip()

    return {'ep_num': ep_num, 'date': date_str, 'tags': tags, 'abstract': abstract}


# ── Transcript extractor ──────────────────────────────────────────────────────

class TranscriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_block = False
        self.skip_blurb = False   # skip BLURB heading on newer episodes
        self.depth = 0
        self.block_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get('class', '')
        id_ = d.get('id', '')
        if 'tab-view' in cls and 'transcript' in cls:
            self.in_block = True
            self.block_depth = self.depth
        if self.in_block:
            if tag == 'h3' and id_ == 'blurb':
                self.skip_blurb = True   # skip BLURB heading + its paragraph
            elif tag == 'h1':
                self.parts.append('<h3 class="speaker">')
            elif tag == 'h2':
                self.parts.append('<span class="ts">')
            elif tag == 'p' and not self.skip_blurb:
                self.parts.append('<p>')
            elif tag == 'br':
                self.parts.append('<br>')
        self.depth += 1

    def handle_endtag(self, tag):
        self.depth -= 1
        if self.in_block:
            if tag == 'h3':
                self.skip_blurb = False  # BLURB heading ended; next <p> is abstract, skip it once
                self._skip_next_p = True
            elif tag == 'h1':
                self.parts.append('</h3>')
            elif tag == 'h2':
                self.parts.append('</span>')
            elif tag == 'p':
                if not self.skip_blurb:
                    self.parts.append('</p>')
                self.skip_blurb = False  # after first post-BLURB <p>, resume
            if self.depth <= self.block_depth:
                self.in_block = False

    def handle_data(self, data):
        if self.in_block and not self.skip_blurb:
            self.parts.append(data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

    def handle_entityref(self, name):
        if self.in_block:
            self.parts.append(f'&{name};')

    def handle_charref(self, name):
        if self.in_block:
            self.parts.append(f'&#{name};')

    def result(self):
        return ''.join(self.parts)


def fetch_transcript_html(slug):
    data = curl(f'https://signalsandthreads.com/{slug}/')
    ex = TranscriptExtractor()
    ex.feed(data)
    return ex.result()


# ── MP3 from RSS ──────────────────────────────────────────────────────────────

def get_rss_mp3s():
    """Try to fetch RSS and return {slug: mp3_url}. Returns {} on failure."""
    data = curl('https://feeds.simplecast.com/L9810DOa', timeout=20)
    if len(data) < 1000:
        return {}
    items = re.findall(r'<item>(.*?)</item>', data, re.DOTALL)
    result = {}
    for item in items:
        title_m = re.search(r'<title>(.*?)</title>', item)
        enc_m   = re.search(r'<enclosure[^>]+url="([^"]+)"', item)
        slug_m  = re.search(r'signalsandthreads\.com/([a-z0-9][a-z0-9-]+)/', item)
        if title_m and enc_m and slug_m:
            result[slug_m.group(1)] = html_mod.unescape(enc_m.group(1)).split('?')[0]
    return result


# ── HTML templates ────────────────────────────────────────────────────────────

EPISODE_CSS = '''
  body  { font-family: Georgia, serif; max-width: 800px; margin: 40px auto;
          padding: 0 24px; background: #fafaf8; color: #1a1a1a; line-height: 1.75; }
  h1   { font-size: 1.55em; margin-bottom: 4px; line-height: 1.3; }
  .meta { color: #777; font-size: 0.88em; margin-bottom: 18px; }
  .meta a { color: #777; }
  audio { width: 100%; margin-bottom: 28px; }
  hr   { border: none; border-top: 1px solid #ddd; margin: 28px 0; }
  .ts  { display: block; color: #aaa; font-size: 0.78em; font-family: monospace;
          margin-top: 1.6em; margin-bottom: 3px; }
  h3.speaker { margin: 0 0 5px 0; font-size: 0.95em; color: #c05800;
                text-transform: uppercase; letter-spacing: 0.06em; }
  p    { margin: 0 0 0.9em 0; }
'''

def write_episode_html(slug, title, transcript_html, mp3_rel, output_dir):
    url = f'https://signalsandthreads.com/{slug}/'
    audio = (f'<audio controls preload="none">\n  <source src="{mp3_rel}" type="audio/mpeg">\n</audio>'
             if mp3_rel else '<p style="color:#aaa;font-size:.85em">Audio not downloaded.</p>')
    html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>{html_mod.escape(title)}</title>\n'
        f'<style>{EPISODE_CSS}</style>\n'
        '</head>\n<body>\n'
        f'<h1>{html_mod.escape(title)}</h1>\n'
        f'<p class="meta">Signals &amp; Threads &nbsp;&middot;&nbsp; Jane Street &nbsp;&middot;&nbsp;'
        f'<a href="{url}" target="_blank">signalsandthreads.com</a></p>\n'
        f'{audio}\n<hr>\n{transcript_html}\n'
        '</body>\n</html>\n'
    )
    with open(os.path.join(output_dir, f'{slug}.html'), 'w', encoding='utf-8') as f:
        f.write(html)


# ── Index ─────────────────────────────────────────────────────────────────────

TAG_COLORS = {
    'Trading and Research': '#4a6fa5', 'Performance': '#c05800',
    'Systems Design': '#2d6a4f',       'Programming Languages': '#6b4c9a',
    'Hardware': '#8b5e3c',             'Machine Learning': '#1d6986',
    'Ways of Working': '#5a6a5a',      'UI/UX': '#c06090',
    'Build Systems': '#5c6bc0',        'Networking': '#2d6a4f',
    'OCaml': '#b05000',                'Compilers': '#6b4c9a',
}

def _tag_span(t):
    c = TAG_COLORS.get(t, '#888')
    return f'<span class="tag" style="border-color:{c};color:{c}">{html_mod.escape(t)}</span>'

def build_index(episodes, meta, output_dir):
    """Rebuild index.html from episodes list and meta dict."""
    cards = []
    for slug, title in episodes:
        m = meta.get(slug, {})
        ep_label  = f'Episode {m["ep_num"]}' if m.get('ep_num') else ''
        date_str  = m.get('date', '')
        abstract  = m.get('abstract', '')
        tags      = m.get('tags', [])
        exists    = os.path.exists(os.path.join(output_dir, f'{slug}.html'))

        meta_parts = ' &nbsp;&middot;&nbsp; '.join(p for p in [ep_label, date_str] if p)

        if exists:
            title_html = f'<a href="{slug}.html">{html_mod.escape(title)}</a>'
        else:
            title_html = f'<span class="no-link">{html_mod.escape(title)}</span>'

        card = (
            f'<div class="card">'
            f'<div class="card-title">{title_html}</div>'
            f'<div class="card-meta">{meta_parts}</div>'
        )
        if tags:
            card += '<div class="card-tags">' + ''.join(_tag_span(t) for t in tags) + '</div>'
        if abstract:
            card += f'<p class="abstract">{html_mod.escape(abstract)}</p>'
        card += '</div>'
        cards.append(card)

    n = len(episodes)
    html = (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<title>Signals &amp; Threads — All Episodes</title>\n'
        '<style>\n'
        '  * { box-sizing: border-box; margin: 0; padding: 0; }\n'
        '  body { font-family: -apple-system, "Segoe UI", sans-serif;\n'
        '         background: #f5f4f0; color: #1a1a1a;\n'
        '         max-width: 860px; margin: 0 auto; padding: 40px 24px; }\n'
        '  header { margin-bottom: 36px; border-bottom: 2px solid #1a1a1a; padding-bottom: 16px; }\n'
        '  header h1 { font-size: 1.8em; letter-spacing: -0.02em; }\n'
        '  header p  { color: #666; margin-top: 4px; font-size: 0.9em; }\n'
        '  .card { background: #fff; border-radius: 6px; padding: 20px 24px;\n'
        '          margin-bottom: 16px; border: 1px solid #e0ddd8; }\n'
        '  .card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.08); }\n'
        '  .card-title a { font-size: 1.12em; font-weight: 600; color: #1a1a1a;\n'
        '                  text-decoration: none; }\n'
        '  .card-title a:hover { color: #c05800; }\n'
        '  .no-link { font-size: 1.12em; font-weight: 600; color: #bbb; }\n'
        '  .card-meta { font-size: 0.8em; color: #999; margin-top: 5px; }\n'
        '  .card-tags { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }\n'
        '  .tag { font-size: 0.73em; padding: 2px 10px; border-radius: 999px;\n'
        '         border: 1px solid; font-weight: 500; }\n'
        '  .abstract { margin-top: 10px; font-size: 0.87em; color: #555; line-height: 1.65; }\n'
        '</style>\n</head>\n<body>\n'
        '<header>\n'
        '  <h1>Signals &amp; Threads</h1>\n'
        f'  <p>Jane Street Engineering Podcast &mdash; {n} episodes &mdash; local archive</p>\n'
        '</header>\n'
        + '\n'.join(cards) +
        '\n</body>\n</html>\n'
    )
    path = os.path.join(output_dir, 'index.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'index.html written ({len(html)//1024} KB, {n} episodes)')


# ── Load / save metadata cache ────────────────────────────────────────────────

def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_meta(meta):
    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    index_only = '--index-only' in sys.argv
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(AUDIO_DIR, exist_ok=True)

    print('Fetching episode list from signalsandthreads.com...')
    episodes = get_all_episodes()
    print(f'  Found {len(episodes)} episodes on site')

    meta = load_meta()

    if not index_only:
        # find episodes not yet downloaded
        new_eps = [(s, t) for s, t in episodes
                   if not os.path.exists(os.path.join(OUT_DIR, f'{s}.html'))]
        print(f'  {len(new_eps)} new episode(s) to download')

        if new_eps:
            print('Fetching MP3 URLs from RSS...')
            rss_mp3s = get_rss_mp3s()
            print(f'  Got {len(rss_mp3s)} MP3 URLs from RSS')

            for slug, title in new_eps:
                print(f'\n  Downloading: {title}')

                # transcript
                transcript_html = fetch_transcript_html(slug)
                if not transcript_html.strip():
                    print('    WARNING: no transcript found, skipping')
                    continue

                # metadata
                m = get_episode_meta(slug)
                meta[slug] = m
                print(f'    Episode {m.get("ep_num","?")} | {m.get("date","?")} | tags: {m.get("tags",[])}')

                # MP3
                mp3_rel = None
                mp3_url = rss_mp3s.get(slug)
                if mp3_url:
                    mp3_path = os.path.join(AUDIO_DIR, f'{slug}.mp3')
                    try:
                        print(f'    Downloading MP3...')
                        data = curl(mp3_url, binary=True, timeout=120)
                        if len(data) > 100_000:
                            with open(mp3_path, 'wb') as f:
                                f.write(data)
                            print(f'    Audio saved ({len(data)//1024//1024} MB)')
                            mp3_rel = f'audio/{slug}.mp3'
                        else:
                            print(f'    MP3 too small, skipping')
                    except Exception as e:
                        print(f'    MP3 failed: {e}')
                else:
                    print('    No MP3 URL in RSS for this episode')
                    # check if already downloaded from a previous run
                    if os.path.exists(os.path.join(AUDIO_DIR, f'{slug}.mp3')):
                        mp3_rel = f'audio/{slug}.mp3'

                write_episode_html(slug, title, transcript_html, mp3_rel, OUT_DIR)
                print(f'    HTML saved: {slug}.html')
                time.sleep(0.5)

        # refresh metadata for episodes that are missing it
        missing_meta = [s for s, _ in episodes if s not in meta]
        if missing_meta:
            print(f'\nFetching metadata for {len(missing_meta)} episodes...')
            for i, slug in enumerate(missing_meta):
                print(f'  [{i+1}/{len(missing_meta)}] {slug}')
                m = get_episode_meta(slug)
                if m:
                    meta[slug] = m
                time.sleep(0.3)

    else:
        # index-only: refresh all metadata from pages
        print(f'Refreshing metadata for {len(episodes)} episodes...')
        for i, (slug, _) in enumerate(episodes):
            print(f'  [{i+1}/{len(episodes)}] {slug}')
            m = get_episode_meta(slug)
            if m:
                meta[slug] = m
            time.sleep(0.3)

    save_meta(meta)
    print('\nBuilding index.html...')
    build_index(episodes, meta, OUT_DIR)
    print(f'\nDone. Open: {OUT_DIR}/index.html')


if __name__ == '__main__':
    main()
