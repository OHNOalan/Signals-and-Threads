#!/usr/bin/env python3
"""
Translate episode transcripts using Google Translate (free, no API key needed).
Reads from data/{slug}.json, writes to translations/{slug}.json.

Usage:
  .venv/bin/python scripts/translate_google.py                  # all untranslated
  .venv/bin/python scripts/translate_google.py <slug> [<slug>]  # specific episodes
  .venv/bin/python scripts/translate_google.py --all            # overwrite all
  .venv/bin/python scripts/translate_google.py --fix-gaps       # fill empty zh only
  .venv/bin/python scripts/translate_google.py --list           # show status
"""
import sys, os, json, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.join(SCRIPT_DIR, '..')
OUT_DIR    = os.path.join(BASE_DIR, 'transcripts')
DATA_DIR   = os.path.join(OUT_DIR, 'data')
TRANS_DIR  = os.path.join(OUT_DIR, 'translations')
os.makedirs(TRANS_DIR, exist_ok=True)

CHAR_LIMIT = 4000   # conservative — Google unofficial API limit
DELAY      = 0.2    # seconds between API calls


def translate_text(translator, text):
    """Translate one paragraph with retry logic for short/colloquial failures."""
    text = text.strip()
    if not text:
        return ''

    def _call(t):
        result = translator.translate(t)
        # deep-translator returns the source text when it can't translate
        if result and result != t:
            return result
        return None

    # Split into chunks if over char limit
    if len(text) > CHAR_LIMIT:
        sentences = []
        for sep in ['? ', '. ', '! ', '\n']:
            text = text.replace(sep, sep[0] + '\n')
        raw_sents = text.split('\n')
        chunks, cur = [], ''
        for s in raw_sents:
            if len(cur) + len(s) > CHAR_LIMIT:
                if cur: chunks.append(cur.strip())
                cur = s + ' '
            else:
                cur += s + ' '
        if cur.strip(): chunks.append(cur.strip())
        parts = []
        for chunk in chunks:
            r = _call(chunk)
            if not r: r = chunk   # keep original on failure
            parts.append(r)
            time.sleep(DELAY)
        return ' '.join(parts)

    # Normal case: single call with retry
    result = _call(text)
    if result:
        return result

    # Retry 1: append period (helps with very short/question sentences)
    time.sleep(0.5)
    result = _call(text + '.')
    if result:
        return result.rstrip('。.')

    # Retry 2: longer back-off
    time.sleep(2)
    result = _call(text)
    if result:
        return result

    # Give up — leave blank so --fix-gaps can retry later
    print(f'      WARN: could not translate: {text[:60]}')
    return ''


def translate_episode(slug, force=False, fix_gaps=False):
    data_path  = os.path.join(DATA_DIR,  f'{slug}.json')
    trans_path = os.path.join(TRANS_DIR, f'{slug}.json')

    if not os.path.exists(data_path):
        print(f'  SKIP {slug}: no data file (run extract_data.py first)')
        return

    # Load existing translation if fixing gaps
    existing = {}
    if fix_gaps and os.path.exists(trans_path):
        try:
            old = json.load(open(trans_path, encoding='utf-8'))
            existing = {p['idx']: p['zh'] for p in old['paragraphs'] if p.get('zh')}
        except Exception:
            pass
    elif not force and os.path.exists(trans_path):
        # Check if fully translated
        try:
            old = json.load(open(trans_path, encoding='utf-8'))
            empty = [p for p in old['paragraphs'] if not p.get('zh')]
            if not empty:
                print(f'  SKIP {slug}: already complete')
                return
            # Has gaps — fix them automatically
            existing = {p['idx']: p['zh'] for p in old['paragraphs'] if p.get('zh')}
            fix_gaps = True
            print(f'  {slug}: resuming ({len(empty)} gaps to fill)')
        except Exception:
            pass  # broken JSON — re-translate

    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source='en', target='zh-CN')

    data  = json.load(open(data_path, encoding='utf-8'))
    paras = [b for b in data['transcript'] if b['type'] == 'p']
    total = len(paras)

    # Determine which to translate
    to_do = [i for i, b in enumerate(paras) if i not in existing] if fix_gaps else range(total)
    if not to_do:
        print(f'  SKIP {slug}: nothing to do')
        return

    print(f'  {slug}: {len(to_do)}/{total} paragraphs to translate', flush=True)

    paragraphs = []
    errors = 0
    for idx, block in enumerate(paras):
        en = block['text']
        if idx in existing:
            zh = existing[idx]
        else:
            try:
                zh = translate_text(translator, en)
                time.sleep(DELAY)
            except Exception as e:
                print(f'\n    ERROR idx={idx}: {en[:60]} --> {e}')
                zh = ''
                errors += 1
                time.sleep(3)
        paragraphs.append({'idx': idx, 'en': en, 'zh': zh})
        done = sum(1 for p in paragraphs if p.get('zh'))
        if done % 20 == 0 or idx == total - 1:
            print(f'    {done}/{total}', flush=True)

    result = {'slug': slug, 'source': 'google-translate', 'paragraphs': paragraphs}
    with open(trans_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    remaining = sum(1 for p in paragraphs if not p.get('zh'))
    status = f'{errors} errors, {remaining} still empty' if errors else 'clean'
    print(f'  → {slug} saved ({status})')


def main():
    args      = sys.argv[1:]
    force     = '--all' in args
    list_mode = '--list' in args
    fix_gaps  = '--fix-gaps' in args
    slugs     = [a for a in args if not a.startswith('--')]

    eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))

    if list_mode:
        for e in eps:
            s = e['slug']
            t = os.path.join(TRANS_DIR, f'{s}.json')
            if os.path.exists(t):
                try:
                    d = json.load(open(t))
                    n     = sum(1 for p in d['paragraphs'] if p.get('zh'))
                    total = len(d['paragraphs'])
                    gaps  = total - n
                    mark  = '✓' if not gaps else f'⚠ {gaps} gaps'
                    print(f"  {mark:12} E{e.get('ep_num','??'):>2}  {s}")
                except Exception:
                    print(f"  ✗ broken     E{e.get('ep_num','??'):>2}  {s}")
            else:
                print(f"  ✗ missing    E{e.get('ep_num','??'):>2}  {s}")
        return

    targets = slugs if slugs else [e['slug'] for e in eps if e.get('has_html')]
    for slug in targets:
        translate_episode(slug, force=force, fix_gaps=fix_gaps)

    print('\nDone. Run: python3 scripts/render_all.py')


if __name__ == '__main__':
    main()
