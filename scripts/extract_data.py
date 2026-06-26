#!/usr/bin/env python3
"""
One-time script: extract structured transcript data from existing generated HTML files.
Writes transcripts/data/{slug}.json for every episode that has an HTML file.

The data JSON is the canonical local source — gen_html.py renders from it,
translate.py translates from it. No network access needed after this runs.

Usage: python3 scripts/extract_data.py
"""
import os, re, json
import html as hm
from html.parser import HTMLParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
OUT_DIR     = os.path.join(BASE_DIR, 'transcripts')
DATA_DIR    = os.path.join(OUT_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)


class EpisodeParser(HTMLParser):
    """Extract title, mp3_rel, and ordered transcript blocks from generated HTML."""

    def __init__(self):
        super().__init__()
        self.title = ''
        self.mp3_rel = ''
        self.transcript = []      # list of {type, text}
        self._in_h1 = self._in_speaker = self._in_ts = self._in_p = False
        self._buf = []
        self._past_hr = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'h1':
            self._in_h1 = True; self._buf = []
        elif tag == 'source' and 'src' in d:
            src = d['src']
            if src.endswith('.mp3'):
                self.mp3_rel = src
        elif tag == 'hr':
            self._past_hr = True
        elif self._past_hr:
            cls = d.get('class', '')
            if tag == 'h3' and 'speaker' in cls:
                self._in_speaker = True; self._buf = []
            elif tag == 'span' and 'ts' in cls:
                self._in_ts = True; self._buf = []
            elif tag == 'p' and 'data-p' in d:
                self._in_p = True; self._buf = []

    def handle_endtag(self, tag):
        if tag == 'h1' and self._in_h1:
            self.title = hm.unescape(''.join(self._buf)).strip()
            self._in_h1 = False
        elif tag == 'h3' and self._in_speaker:
            text = hm.unescape(''.join(self._buf)).strip()
            if text:
                self.transcript.append({'type': 'speaker', 'text': text})
            self._in_speaker = False
        elif tag == 'span' and self._in_ts:
            text = hm.unescape(''.join(self._buf)).strip()
            if text:
                self.transcript.append({'type': 'ts', 'text': text})
            self._in_ts = False
        elif tag == 'p' and self._in_p:
            text = hm.unescape(''.join(self._buf)).strip()
            if text:
                self.transcript.append({'type': 'p', 'text': text})
            self._in_p = False

    def handle_data(self, d):
        if self._in_h1 or self._in_speaker or self._in_ts or self._in_p:
            self._buf.append(d)

    def handle_entityref(self, name):
        if self._in_h1 or self._in_speaker or self._in_ts or self._in_p:
            self._buf.append(f'&{name};')

    def handle_charref(self, name):
        if self._in_h1 or self._in_speaker or self._in_ts or self._in_p:
            self._buf.append(f'&#{name};')


def extract_episode(slug):
    html_path = os.path.join(OUT_DIR, f'{slug}.html')
    out_path   = os.path.join(DATA_DIR, f'{slug}.json')

    data = open(html_path, encoding='utf-8').read()
    parser = EpisodeParser()
    parser.feed(data)

    p_count = sum(1 for b in parser.transcript if b['type'] == 'p')
    result = {
        'slug':       slug,
        'title':      parser.title,
        'mp3_rel':    parser.mp3_rel,
        'transcript': parser.transcript,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return p_count


if __name__ == '__main__':
    import sys
    eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))
    target = sys.argv[1] if len(sys.argv) > 1 else None
    for e in eps:
        slug = e['slug']
        if not e.get('has_html'):
            continue
        if target and slug != target:
            continue
        count = extract_episode(slug)
        print(f'  {slug}: {count} paragraphs → data/{slug}.json')
    print('Done.')
