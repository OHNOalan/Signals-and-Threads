#!/usr/bin/env python3
"""
CI-safe episode updater for GitHub Actions.
Checks for new episodes, generates HTML + translations, rebuilds index.
Does NOT download audio — uses Simplecast CDN URLs instead.

Usage: python3 scripts/update_ci.py [transcripts_dir]
Exit code 0 always. Prints "NO_NEW_EPISODES" when nothing changed.
"""
import sys, os, json, subprocess, re, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.join(SCRIPT_DIR, '..')
sys.path.insert(0, SCRIPT_DIR)

out_dir  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, 'transcripts')
data_dir = os.path.join(out_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  fetch error {url}: {e}')
        return ''


def run(*args):
    subprocess.run([sys.executable, *args], check=True)


# ── 1. Find which slugs are new ───────────────────────────────────────────────
print('Fetching homepage...')
from update import get_all_episodes
all_episodes = get_all_episodes()   # [(slug, title), ...] newest-first

existing = {f[:-5] for f in os.listdir(data_dir) if f.endswith('.json')}
new_episodes = [(s, t) for s, t in all_episodes if s not in existing]

if not new_episodes:
    print('NO_NEW_EPISODES')
    sys.exit(0)

print(f'{len(new_episodes)} new episode(s): {[s for s,_ in new_episodes]}')

# ── 2. Scrape + generate HTML for each new episode ────────────────────────────
import tempfile, html as hm
for slug, title in new_episodes:
    print(f'  Processing: {slug}')
    page_url = f'https://signalsandthreads.com/{slug}/'
    page_html = fetch(page_url)
    if len(page_html) < 500:
        print(f'  SKIP: empty page for {slug}')
        continue

    # Write page to temp file so gen_html.py can scrape it
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(page_html)
        tmp = f.name

    try:
        # gen_html.py scrape mode: page_file slug mp3_rel out_dir
        # mp3_rel is empty — CDN URL will be added by fetch_audio_urls.py
        run(os.path.join(SCRIPT_DIR, 'gen_html.py'), tmp, slug, '', out_dir)
    finally:
        os.unlink(tmp)

# ── 3. Fetch CDN audio URLs for new episodes ──────────────────────────────────
print('Fetching CDN audio URLs...')
run(os.path.join(SCRIPT_DIR, 'fetch_audio_urls.py'), out_dir)

# ── 4. Translate new episodes ─────────────────────────────────────────────────
trans_script = os.path.join(SCRIPT_DIR, 'translate_google.py')
for slug, _ in new_episodes:
    data_path = os.path.join(data_dir, f'{slug}.json')
    if not os.path.exists(data_path):
        continue
    print(f'  Translating: {slug}')
    run(trans_script, slug)

# ── 5. Bake translations into HTML + rebuild index ────────────────────────────
print('Rendering all HTML...')
run(os.path.join(SCRIPT_DIR, 'render_all.py'), out_dir)

# ── 6. Update episodes.json with new episode metadata ─────────────────────────
print('Updating episodes.json...')
eps_path = os.path.join(out_dir, 'episodes.json')
episodes_list = json.load(open(eps_path, encoding='utf-8')) if os.path.exists(eps_path) else []
existing_slugs = {e['slug'] for e in episodes_list}

from update import get_episode_meta
for slug, title in new_episodes:
    if slug in existing_slugs:
        continue
    meta = get_episode_meta(slug)
    entry = {
        'slug':     slug,
        'title':    title,
        'guest':    meta.get('guest', ''),
        'ep_num':   meta.get('ep_num', ''),
        'date':     meta.get('date', ''),
        'tags':     meta.get('tags', []),
        'abstract': meta.get('abstract', ''),
        'has_html': os.path.exists(os.path.join(out_dir, f'{slug}.html')),
    }
    episodes_list.insert(0, entry)   # newest first

with open(eps_path, 'w', encoding='utf-8') as f:
    json.dump(episodes_list, f, ensure_ascii=False, indent=2)

# ── 7. Rebuild index.html ─────────────────────────────────────────────────────
print('Rebuilding index.html...')
run(os.path.join(SCRIPT_DIR, 'build_index.py'), out_dir)

print(f'Done. Added {len(new_episodes)} episode(s).')
