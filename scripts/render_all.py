#!/usr/bin/env python3
"""
Regenerate all episode HTML files from local data/{slug}.json — no network needed.
If translations/{slug}.json exists, bakes translations inline so pages work via file://.

Usage: python3 scripts/render_all.py
"""
import sys, os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
OUT_DIR     = os.path.join(BASE_DIR, 'transcripts')
DATA_DIR    = os.path.join(OUT_DIR, 'data')
TRANS_DIR   = os.path.join(OUT_DIR, 'translations')

sys.path.insert(0, SCRIPT_DIR)
from gen_html import render_html

eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))
done = skipped = translated = 0

for e in eps:
    slug = e['slug']
    data_path  = os.path.join(DATA_DIR,  f'{slug}.json')
    trans_path = os.path.join(TRANS_DIR, f'{slug}.json')

    if not os.path.exists(data_path):
        print(f'  SKIP (no data): {slug}')
        skipped += 1
        continue

    data = json.load(open(data_path, encoding='utf-8'))

    translations = None
    if os.path.exists(trans_path):
        try:
            translations = json.load(open(trans_path, encoding='utf-8'))
            translated += 1
        except Exception:
            pass   # broken JSON — skip, don't crash render

    out_path = os.path.join(OUT_DIR, f'{slug}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(render_html(data, translations))

    p_count = sum(1 for b in data['transcript'] if b['type'] == 'p')
    zh_note = ' +ZH' if translations else ''
    print(f'  {slug} ({p_count}p{zh_note})')
    done += 1

print(f'\n{done} rendered ({translated} with inline translations), {skipped} skipped')
