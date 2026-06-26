#!/usr/bin/env python3
"""
Called by update.sh — reads pre-fetched HTML files, writes episodes.json.

Usage:
  python3 scripts/parse_episodes.py <homepage.html> <pages_dir> <out_dir>
"""
import sys, re, os, json
import html as hm

homepage_file, pages_dir, out_dir = sys.argv[1:]

# ── 1. Extract slug + short title from homepage hrefs (newest first) ──────────
data = open(homepage_file, encoding='utf-8', errors='replace').read()
pairs = re.findall(r'href="/([a-z][a-z0-9-]+)/"[^>]*>\s*([^<\n]+?)\s*</a>', data)
seen = {}
for slug, title in pairs:
    t = title.strip()
    if slug not in seen and t:
        seen[slug] = t
slug_titles = dict(seen)

if not slug_titles:
    sys.exit("ERROR: no episode slugs found in homepage")

print(f"  {len(slug_titles)} episodes found on homepage")

# ── 2. Parse each episode page for metadata ───────────────────────────────────
def parse_page(slug):
    path = os.path.join(pages_dir, f"{slug}.html")
    if not os.path.exists(path):
        return {}
    data = open(path, encoding='utf-8', errors='replace').read()
    if len(data) < 500:
        return {}

    # full title from <title> tag
    m = re.search(r'<title>Signals and Threads \| (.*?)</title>', data)
    full_title = hm.unescape(m.group(1)) if m else ''

    # guest from <h4>with ...</h4>
    g = re.search(r'<h4>with\s+(.*?)</h4>', data, re.DOTALL)
    guest = re.sub(r'<[^>]+>', '', hm.unescape(g.group(1))).strip() if g else ''

    # episode number + date from <h5 class="season-episode-section">
    ep_num = date_str = ''
    h5 = re.search(r'class="season-episode-section"[^>]*>(.*?)</h5>', data, re.DOTALL)
    if h5:
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', hm.unescape(h5.group(1)))).strip()
        em = re.search(r'Episode\s*(\d+)', text)
        dm = re.search(r'\|\s*(.+)', text)
        ep_num   = em.group(1) if em else ''
        date_str = dm.group(1).strip() if dm else ''

    # tags
    tm = re.search(r'data-tags="([^"]+)"', data)
    tags = [t.strip() for t in tm.group(1).split(',')] if tm else []

    # abstract: newer episodes have BLURB section; older have <p> after </h5>
    abstract = ''
    blurb = re.search(r'id="blurb"[^>]*>BLURB</h3>\s*<p>(.*?)</p>', data, re.DOTALL)
    if blurb:
        abstract = re.sub(r'<[^>]+>', '', hm.unescape(blurb.group(1))).strip()
    else:
        after = re.search(r'</h5>(?:\s*<div[^>]*>.*?</div>)?\s*<p>(.*?)</p>', data, re.DOTALL)
        if after:
            abstract = re.sub(r'<[^>]+>', '', hm.unescape(after.group(1))).strip()

    return {'full_title': full_title, 'guest': guest,
            'ep_num': ep_num, 'date': date_str, 'tags': tags, 'abstract': abstract}

# ── 3. Build episode list ─────────────────────────────────────────────────────
episodes = []
for slug, homepage_title in slug_titles.items():
    page = parse_page(slug)
    has_html = os.path.exists(os.path.join(out_dir, f"{slug}.html"))

    title = page.get('full_title') or homepage_title
    guest = page.get('guest', '')
    if guest and ' with ' not in title:
        title = f"{title} with {guest}"

    ep = {
        'slug':     slug,
        'title':    title,
        'guest':    guest,
        'ep_num':   page.get('ep_num', ''),
        'date':     page.get('date', ''),
        'tags':     page.get('tags', []),
        'abstract': page.get('abstract', ''),
        'has_html': has_html,
    }
    episodes.append(ep)
    label = f"E{ep['ep_num']:>2}" if ep['ep_num'] else '    '
    print(f"  {label} {slug[:50]:<50} {','.join(ep['tags'])}")

# ── 4. Write episodes.json ────────────────────────────────────────────────────
out_path = os.path.join(out_dir, 'episodes.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(episodes, f, ensure_ascii=False, indent=2)
print(f"\nepisodes.json → {out_path} ({len(episodes)} eps, {os.path.getsize(out_path)//1024}KB)")
