#!/usr/bin/env python3
"""
Rebuild transcripts/index.html with episodes.json inlined as a JS variable.
This makes index.html work via file:// without any HTTP server.

Called by update.sh after parse_episodes.py.
Usage: python3 scripts/build_index.py <out_dir>
"""
import sys, os, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
out_dir     = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, 'transcripts')

episodes = json.load(open(os.path.join(out_dir, 'episodes.json'), encoding='utf-8'))
episodes_js = json.dumps(episodes, ensure_ascii=False)

TAG_COLORS = {
  'Trading and Research': '#4a6fa5',
  'Performance':          '#c05800',
  'Systems Design':       '#2d6a4f',
  'Programming Languages':'#6b4c9a',
  'Hardware':             '#8b5e3c',
  'Machine Learning':     '#1d6986',
  'Ways of Working':      '#5a6a5a',
  'UI/UX':               '#c06090',
  'Build Systems':        '#5c6bc0',
  'Networking':           '#2d6a4f',
  'OCaml':               '#b05000',
  'Compilers':            '#6b4c9a',
}
tag_colors_js = json.dumps(TAG_COLORS, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Signals &amp; Threads</title>
<script>(function(){{var s=localStorage.getItem('dark'),d=window.matchMedia('(prefers-color-scheme:dark)').matches;if(s==='1'||(s===null&&d)){{document.documentElement.className='dark';document.documentElement.style.background='#13161f';}}}})();</script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, "Segoe UI", sans-serif;
         background: #f5f4f0; color: #1a1a1a;
         max-width: 860px; margin: 0 auto; padding: 40px 24px; }}
  header {{ margin-bottom: 28px; border-bottom: 2px solid #1a1a1a; padding-bottom: 16px;
           display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; }}
  header h1 {{ font-size: 1.8em; letter-spacing: -.02em; flex-shrink: 0; }}
  header p  {{ color: #666; font-size: .88em; }}
  #search {{ border: 1px solid #ccc; border-radius: 6px; padding: 7px 12px;
            font-size: .9em; width: 200px; outline: none; background: #fff; color: inherit; }}
  #search:focus {{ border-color: #c05800; }}
  #dark-btn {{ font-size: .78em; padding: 4px 12px; border-radius: 999px;
              border: 1px solid #c05800; color: #c05800; background: transparent;
              cursor: pointer; font-family: inherit; flex-shrink: 0;
              transition: background .15s, color .15s; }}
  #dark-btn:hover, #dark-btn.active {{ background: #c05800; color: #fff; }}
  #count {{ color: #999; font-size: .82em; margin-bottom: 16px; min-height: 1.2em; }}
  .card {{ background: #fff; border-radius: 6px; padding: 20px 24px;
          margin-bottom: 14px; border: 1px solid #e0ddd8;
          transition: box-shadow .15s; }}
  .card:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  .card-title a {{ font-size: 1.1em; font-weight: 600; color: #1a1a1a;
                  text-decoration: none; line-height: 1.35; }}
  .card-title a:hover {{ color: #c05800; }}
  .card-title .no-link {{ font-size: 1.1em; font-weight: 600; color: #bbb; }}
  .card-meta {{ font-size: .78em; color: #999; margin-top: 5px; }}
  .card-tags {{ margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }}
  .tag {{ font-size: .72em; padding: 2px 10px; border-radius: 999px;
         border: 1px solid; font-weight: 500; cursor: pointer; }}
  .tag:hover {{ opacity: .75; }}
  .abstract {{ margin-top: 10px; font-size: .86em; color: #555; line-height: 1.65; }}
  .hidden {{ display: none; }}
  #no-results {{ text-align: center; color: #999; padding: 60px 0; font-size: .95em; }}
  /* Dark mode — html.dark body beats the explicit body{{}} rule above */
  html.dark body {{ background: #13161f; color: #c8ccd8; color-scheme: dark; }}
  html.dark header {{ border-bottom-color: #1e2235; }}
  html.dark header h1 {{ color: #dde0ea; }}
  html.dark header p {{ color: #454a5e; }}
  html.dark #search {{ background: #1a1e2e; border-color: #2a2e42; color: #c8ccd8; }}
  html.dark #search:focus {{ border-color: #c05800; }}
  html.dark #count {{ color: #454a5e; }}
  html.dark .card {{ background: #1a1e2e; border-color: #1e2235; }}
  html.dark .card:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,.3); }}
  html.dark .card-title a {{ color: #dde0ea; }}
  html.dark .card-title a:hover {{ color: #e07040; }}
  html.dark .card-meta {{ color: #454a5e; }}
  html.dark .abstract {{ color: #7a8098; }}
  html.dark #no-results {{ color: #454a5e; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Signals &amp; Threads</h1>
    <p>Jane Street Engineering Podcast — local archive</p>
  </div>
  <input id="search" type="search" placeholder="Search episodes…" autocomplete="off">
  <button id="dark-btn">夜间</button>
</header>
<div id="count"></div>
<div id="cards"></div>
<div id="no-results" class="hidden">No episodes match your search.</div>

<script>
// Dark mode — shared localStorage key with episode pages
(function() {{
  const btn = document.getElementById('dark-btn');
  const sys = window.matchMedia('(prefers-color-scheme: dark)');
  function apply() {{
    const stored = localStorage.getItem('dark');
    const on = stored !== null ? stored === '1' : sys.matches;
    document.documentElement.classList.toggle('dark', on);
    btn.textContent = on ? '日间' : '夜间';
    btn.classList.toggle('active', on);
    btn.title = stored !== null ? '双击重置为跟随系统' : '跟随系统';
  }}
  apply();
  sys.addEventListener('change', function() {{ if (localStorage.getItem('dark') === null) apply(); }});
  btn.addEventListener('click', function() {{
    localStorage.setItem('dark', document.documentElement.classList.contains('dark') ? '0' : '1');
    apply();
  }});
  btn.addEventListener('dblclick', function() {{ localStorage.removeItem('dark'); apply(); }});
}})();

const TAG_COLORS = {tag_colors_js};
const episodes = {episodes_js};

let activeTag = null;

function esc(s) {{
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function tagSpan(t) {{
  const c = TAG_COLORS[t] || '#888';
  return `<span class="tag" style="border-color:${{c}};color:${{c}}" data-tag="${{esc(t)}}">${{esc(t)}}</span>`;
}}

function renderCard(ep) {{
  const metaParts = [ep.ep_num ? `Episode ${{ep.ep_num}}` : '', ep.date || ''].filter(Boolean);
  const metaLine = metaParts.join(' &nbsp;&middot;&nbsp; ');
  const tagsHtml = (ep.tags || []).map(tagSpan).join('');
  const titleHtml = ep.has_html
    ? `<a href="${{esc(ep.slug)}}.html">${{esc(ep.title)}}</a>`
    : `<span class="no-link">${{esc(ep.title)}}</span>`;
  return `<div class="card"
    data-title="${{esc(ep.title.toLowerCase())}}"
    data-abstract="${{esc((ep.abstract||'').toLowerCase())}}"
    data-tags="${{esc((ep.tags||[]).join(' ').toLowerCase())}}">
    <div class="card-title">${{titleHtml}}</div>
    ${{metaLine ? `<div class="card-meta">${{metaLine}}</div>` : ''}}
    ${{tagsHtml ? `<div class="card-tags">${{tagsHtml}}</div>` : ''}}
    ${{ep.abstract ? `<p class="abstract">${{esc(ep.abstract)}}</p>` : ''}}
  </div>`;
}}

function applyFilter() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  const cards = document.querySelectorAll('#cards .card');
  let visible = 0;
  cards.forEach(card => {{
    const matchQ = !q || card.dataset.title.includes(q)
                      || card.dataset.abstract.includes(q)
                      || card.dataset.tags.includes(q);
    const matchTag = !activeTag || card.dataset.tags.includes(activeTag.toLowerCase());
    const show = matchQ && matchTag;
    card.classList.toggle('hidden', !show);
    if (show) visible++;
  }});
  document.getElementById('count').textContent =
    visible === episodes.length ? `${{visible}} episodes`
    : `${{visible}} of ${{episodes.length}} episodes`;
  document.getElementById('no-results').classList.toggle('hidden', visible > 0);
}}

(function init() {{
  const container = document.getElementById('cards');
  container.innerHTML = episodes.map(renderCard).join('\\n');
  document.getElementById('count').textContent = `${{episodes.length}} episodes`;
  document.getElementById('search').addEventListener('input', applyFilter);
  container.addEventListener('click', e => {{
    const tag = e.target.closest('.tag');
    if (!tag) return;
    const t = tag.dataset.tag;
    activeTag = activeTag === t ? null : t;
    document.querySelectorAll('.tag').forEach(el => {{
      el.style.opacity = (!activeTag || el.dataset.tag === activeTag) ? '1' : '0.35';
    }});
    applyFilter();
  }});
}})();
</script>
</body>
</html>"""

out_path = os.path.join(out_dir, 'index.html')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"index.html rebuilt ({len(episodes)} episodes, {os.path.getsize(out_path)//1024}KB)")
