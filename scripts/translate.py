#!/usr/bin/env python3
"""
Translate episode transcripts to Chinese using Claude API.

Usage:
  python3 scripts/translate.py                  # translate all episodes missing translations
  python3 scripts/translate.py <slug>           # translate specific episode
  python3 scripts/translate.py --all            # re-translate everything (overwrites)
  python3 scripts/translate.py --list           # show status of all translations

Requires: pip install anthropic
API key:  export ANTHROPIC_API_KEY=sk-ant-...

Output: transcripts/translations/{slug}.json
"""
import sys, os, re, json, time
import html as hm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
OUT_DIR     = os.path.join(BASE_DIR, 'transcripts')
DATA_DIR    = os.path.join(OUT_DIR, 'data')
TRANS_DIR   = os.path.join(OUT_DIR, 'translations')
MODEL       = 'claude-haiku-4-5-20251001'
BATCH_SIZE  = 12   # paragraphs per API call

os.makedirs(TRANS_DIR, exist_ok=True)

# ── helpers ───────────────────────────────────────────────────────────────────

def extract_paragraphs(slug):
    """Return list of plain-text paragraphs from data/{slug}.json (preferred)
    or fall back to parsing the episode HTML."""
    data_path = os.path.join(DATA_DIR, f'{slug}.json')
    if os.path.exists(data_path):
        d = json.load(open(data_path, encoding='utf-8'))
        return [b['text'] for b in d['transcript'] if b['type'] == 'p']
    # fallback: parse generated HTML
    html_path = os.path.join(OUT_DIR, f'{slug}.html')
    if not os.path.exists(html_path):
        return []
    raw = open(html_path, encoding='utf-8').read()
    chunks = re.findall(r'<p[^>]*data-p[^>]*>(.*?)</p>', raw, re.DOTALL)
    result = []
    for chunk in chunks:
        text = re.sub(r'<[^>]+>', '', chunk)
        text = hm.unescape(text).strip()
        if text:
            result.append(text)
    return result

def translate_batch(client, paragraphs, slug_hint=''):
    """Translate a list of English paragraphs. Returns list of Chinese strings."""
    numbered = '\n\n'.join(f'[{i}] {p}' for i, p in enumerate(paragraphs))
    prompt = f"""You are translating an engineering podcast transcript (Jane Street "Signals and Threads") into Simplified Chinese.

Rules:
- Translate each numbered paragraph accurately, keeping the same [index] prefix.
- Keep technical terms natural (e.g. multicast, OCaml, latency — use transliterations or common Chinese equivalents as appropriate).
- Match the conversational register of the original.
- Output ONLY the translated numbered paragraphs, one per block, no extra commentary.

Paragraphs to translate:

{numbered}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}]
    )
    raw = msg.content[0].text
    translations = [''] * len(paragraphs)
    for m in re.finditer(r'\[(\d+)\]\s*(.*?)(?=\n\n\[\d+\]|\Z)', raw, re.DOTALL):
        idx, text = int(m.group(1)), m.group(2).strip()
        if 0 <= idx < len(paragraphs):
            translations[idx] = text
    return translations

def translate_episode(client, slug, force=False):
    out_path = os.path.join(TRANS_DIR, f'{slug}.json')
    if os.path.exists(out_path) and not force:
        print(f'  SKIP {slug} (already done)')
        return

    paras = extract_paragraphs(slug)
    if not paras:
        print(f'  SKIP {slug} (no HTML or empty transcript)')
        return

    print(f'  {slug}: {len(paras)} paragraphs…', flush=True)
    translations = []
    for i in range(0, len(paras), BATCH_SIZE):
        batch = paras[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(paras) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f'    batch {batch_num}/{total_batches}', end='', flush=True)
        result = translate_batch(client, batch, slug)
        translations.extend(result)
        print(f' ✓', flush=True)
        if i + BATCH_SIZE < len(paras):
            time.sleep(0.5)   # be gentle with rate limits

    data = {
        'slug': slug,
        'model': MODEL,
        'paragraphs': [
            {'idx': i, 'en': p, 'zh': translations[i] if i < len(translations) else ''}
            for i, p in enumerate(paras)
        ]
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'  → saved {out_path}')

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    force = '--all' in args
    list_mode = '--list' in args
    slugs_arg = [a for a in args if not a.startswith('--')]

    if list_mode:
        eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))
        for e in eps:
            s = e['slug']
            done = os.path.exists(os.path.join(TRANS_DIR, f'{s}.json'))
            has = '✓' if done else '✗'
            html = '✓' if e.get('has_html') else '✗'
            print(f'  HTML:{html} ZH:{has}  E{e.get("ep_num","??"):>2}  {s}')
        return

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print('ERROR: set ANTHROPIC_API_KEY environment variable')
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    if slugs_arg:
        for slug in slugs_arg:
            translate_episode(client, slug, force=True)
    else:
        eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))
        for e in eps:
            if not e.get('has_html'):
                continue
            translate_episode(client, e['slug'], force=force)

if __name__ == '__main__':
    main()
