#!/usr/bin/env python3
"""
Inject bilingual UI into all episode HTML files.

- Adds data-p="N" index to every <p> tag
- Injects JS that loads translations/{slug}.json and renders Chinese below each paragraph
- Adds toolbar: show/hide original English | expand/collapse all translations

Usage:
  python3 scripts/patch_translate_ui.py          # patch all episode HTML files
  python3 scripts/patch_translate_ui.py <slug>   # patch specific episode
"""
import sys, os, re, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
OUT_DIR     = os.path.join(BASE_DIR, 'transcripts')

TRANSLATE_CSS = """
/* ── bilingual translation UI ────────────────────────────────────────── */
.translate-bar {
  position: sticky; top: 0; z-index: 10;
  background: #fafaf8; border-bottom: 1px solid #e0ddd8;
  padding: 8px 0 8px; margin: 0 0 20px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.translate-bar button {
  font-size: .78em; padding: 4px 12px; border-radius: 999px;
  border: 1px solid #c05800; color: #c05800; background: transparent;
  cursor: pointer; font-family: inherit; transition: .15s;
}
.translate-bar button:hover, .translate-bar button.active {
  background: #c05800; color: #fff;
}
.translate-bar .tbar-status {
  font-size: .75em; color: #aaa; margin-left: auto;
}
.zh-block {
  margin: -4px 0 12px 0;
  padding: 8px 14px;
  background: #f0f4ff;
  border-left: 3px solid #6b8fd8;
  border-radius: 0 4px 4px 0;
  font-size: .93em;
  color: #222;
  line-height: 1.8;
  cursor: pointer;
}
.zh-block.collapsed { display: none; }
.zh-block.loading { color: #aaa; font-style: italic; }
p[data-p] { cursor: default; }
p.en-hidden { display: none; }
"""

TRANSLATE_JS = """
(function() {
  const slug = location.pathname.split('/').filter(Boolean).pop().replace(/\\.html$/, '');

  function allParagraphs() { return document.querySelectorAll('p[data-p]'); }

  /* ── build toolbar ───────────────────────────────────────────────── */
  const bar = document.createElement('div');
  bar.className = 'translate-bar';
  bar.innerHTML = `
    <button id="btn-en">隐藏原文</button>
    <button id="btn-expand" class="active">折叠译文</button>
    <span class="tbar-status" id="tstatus">加载中…</span>`;

  const firstHr = document.querySelector('hr');
  if (firstHr) firstHr.after(bar); else document.body.prepend(bar);

  let enHidden = false;
  let zhCollapsed = false;

  document.getElementById('btn-en').addEventListener('click', function() {
    enHidden = !enHidden;
    allParagraphs().forEach(p => p.classList.toggle('en-hidden', enHidden));
    this.textContent = enHidden ? '显示原文' : '隐藏原文';
    this.classList.toggle('active', enHidden);
  });

  document.getElementById('btn-expand').addEventListener('click', function() {
    zhCollapsed = !zhCollapsed;
    document.querySelectorAll('.zh-block').forEach(el => {
      el.classList.toggle('collapsed', zhCollapsed);
    });
    this.textContent = zhCollapsed ? '展开译文' : '折叠译文';
    this.classList.toggle('active', !zhCollapsed);
  });

  /* ── load translations ───────────────────────────────────────────── */
  fetch('translations/' + slug + '.json')
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(data => {
      const map = {};
      data.paragraphs.forEach(function(item) { map[item.idx] = item.zh; });

      let count = 0;
      allParagraphs().forEach(function(p) {
        const idx = parseInt(p.dataset.p, 10);
        const zh = map[idx];
        if (!zh) return;
        const block = document.createElement('div');
        block.className = 'zh-block';
        block.dataset.p = idx;
        block.textContent = zh;
        /* click to toggle single paragraph */
        block.addEventListener('click', function() {
          this.classList.toggle('collapsed');
        });
        p.after(block);
        count++;
      });
      document.getElementById('tstatus').textContent =
        count + ' 段已翻译';
    })
    .catch(function(err) {
      document.getElementById('tstatus').textContent = '译文未找到';
    });
})();
"""

def patch_html(slug, data):
    """Return patched HTML content."""
    # 1. Add data-p indices to <p> tags (only in transcript body, after <hr>)
    #    Strategy: index ALL <p> tags sequentially (simpler, JS mirrors same order)
    p_idx = [0]
    def add_idx(m):
        i = p_idx[0]; p_idx[0] += 1
        return f'<p data-p="{i}">'
    data_new = re.sub(r'<p>', add_idx, data)

    # 2. Inject CSS before </style>
    data_new = data_new.replace('</style>', TRANSLATE_CSS + '</style>', 1)

    # 3. Inject JS before </body>
    script_tag = f'<script>{TRANSLATE_JS}</script>\n</body>'
    data_new = data_new.replace('</body>', script_tag, 1)

    return data_new

def patch_episode(slug):
    path = os.path.join(OUT_DIR, f'{slug}.html')
    if not os.path.exists(path):
        print(f'  SKIP {slug} (no HTML)')
        return
    data = open(path, encoding='utf-8').read()
    # Skip if already patched
    if 'data-p=' in data and 'translate-bar' in data:
        print(f'  SKIP {slug} (already patched)')
        return
    patched = patch_html(slug, data)
    open(path, 'w', encoding='utf-8').write(patched)
    print(f'  PATCHED {slug}.html')

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args:
        for slug in args:
            patch_episode(slug)
    else:
        eps = json.load(open(os.path.join(OUT_DIR, 'episodes.json')))
        for e in eps:
            if e.get('has_html'):
                patch_episode(e['slug'])

if __name__ == '__main__':
    main()
