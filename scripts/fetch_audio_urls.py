#!/usr/bin/env python3
"""
Fetch Simplecast CDN audio URLs from the RSS feed and store them in
each data/{slug}.json as mp3_url.

Usage: python3 scripts/fetch_audio_urls.py [transcripts_dir]
"""
import sys, os, re, json
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.join(SCRIPT_DIR, '..')
out_dir    = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, 'transcripts')
data_dir   = os.path.join(out_dir, 'data')

RSS_URL = 'https://feeds.simplecast.com/L9810DOa'

print(f'Fetching {RSS_URL}...')
with urllib.request.urlopen(RSS_URL, timeout=20) as r:
    feed = r.read().decode('utf-8')

items = re.findall(r'<item>(.*?)</item>', feed, re.DOTALL)
print(f'Found {len(items)} RSS items')

# Build {slug: cdn_url} map by extracting the signalsandthreads.com URL from each item
# Load all known slugs and their titles for fallback matching
known_slugs = {}
for fname in os.listdir(data_dir):
    if not fname.endswith('.json'):
        continue
    slug = fname[:-5]
    d = json.load(open(os.path.join(data_dir, fname)))
    known_slugs[slug] = d.get('title', '').lower()

slug_to_url = {}
for item in items:
    # CDN mp3 URL from <enclosure>
    em = re.search(r'<enclosure[^>]+url="([^"]+)"', item)
    if not em:
        continue
    cdn_url = em.group(1).replace('&amp;', '&')

    # Strategy 1: match via signalsandthreads.com href in description
    sm = re.search(r'href="https://signalsandthreads\.com/([a-z][a-z0-9-]+)/?["\s]', item)
    if sm:
        slug_to_url[sm.group(1)] = cdn_url
        continue

    # Strategy 2: title-based fuzzy match against our known slugs
    tm = re.search(r'<title>(.*?)</title>', item)
    if not tm:
        continue
    rss_title = re.sub(r'&amp;', '&', re.sub(r'&apos;', "'", tm.group(1))).lower()
    best_slug = None
    for slug, our_title in known_slugs.items():
        words = slug.replace('-', ' ').split()[:4]
        if all(w in rss_title for w in words):
            best_slug = slug
            break
    if best_slug:
        slug_to_url[best_slug] = cdn_url

print(f'Matched {len(slug_to_url)} slug→URL pairs')

updated = 0
for slug, cdn_url in slug_to_url.items():
    path = os.path.join(data_dir, f'{slug}.json')
    if not os.path.exists(path):
        continue
    data = json.load(open(path, encoding='utf-8'))
    if data.get('mp3_url') == cdn_url:
        continue
    data['mp3_url'] = cdn_url
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  {slug}: stored CDN URL')
    updated += 1

print(f'{updated} data files updated')
