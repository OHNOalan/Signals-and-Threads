/* Bilingual translation UI for Signals & Threads local archive.
   Loaded by every episode HTML page.
   Translation data is either baked into the page as window.__ZH (offline),
   or fetched from translations/{slug}.json (http server). */
(function () {
  'use strict';

  const slug = location.pathname.split('/').filter(Boolean).pop()
                 .replace(/\.html$/, '');

  /* ── Toolbar ────────────────────────────────────────────────── */
  const bar = document.createElement('div');
  bar.className = 'translate-bar';
  bar.innerHTML =
    '<button id="btn-en">隐藏原文</button>' +
    '<button id="btn-zh">折叠译文</button>' +
    '<span class="tbar-status" id="tstatus">加载中…</span>';

  const hr = document.querySelector('hr');
  if (hr) hr.after(bar); else document.body.prepend(bar);

  let enHidden = false, zhFolded = false;

  document.getElementById('btn-en').addEventListener('click', function () {
    enHidden = !enHidden;
    document.querySelectorAll('p[data-p]').forEach(p => p.classList.toggle('en-hidden', enHidden));
    document.querySelectorAll('.en-toggle').forEach(b => b.classList.toggle('active', enHidden));
    this.textContent = enHidden ? '显示原文' : '隐藏原文';
    this.classList.toggle('active', enHidden);
  });

  document.getElementById('btn-zh').addEventListener('click', function () {
    zhFolded = !zhFolded;
    document.querySelectorAll('.zh-block').forEach(el => el.classList.toggle('zh-folded', zhFolded));
    document.querySelectorAll('.zh-toggle').forEach(b => b.classList.toggle('active', zhFolded));
    this.textContent = zhFolded ? '展开译文' : '折叠译文';
    this.classList.toggle('active', zhFolded);
  });

  /* ── Copy helper ─────────────────────────────────────────────── */
  function copyText(text, btn) {
    const orig = btn.textContent;
    const done = () => { btn.textContent = '✓'; setTimeout(() => btn.textContent = orig, 1500); };
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(done).catch(() => execCopy(text, done));
    } else {
      execCopy(text, done);
    }
  }
  function execCopy(text, done) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;pointer-events:none';
      document.body.appendChild(ta); ta.focus(); ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta); done();
    } catch (e) {
      window.prompt('请手动复制:', text);
    }
  }

  /* ── Apply translations ───────────────────────────────────────── */
  function applyTranslations(data) {
    const map = {};
    data.paragraphs.forEach(item => { map[item.idx] = item.zh; });
    let count = 0;

    document.querySelectorAll('p[data-p]').forEach(p => {
      const idx = parseInt(p.dataset.p, 10);
      const zh = map[idx];
      if (!zh) return;

      /* Controls bar: [EN] [中] [⎘] — inserted before the <p> */
      const controls = document.createElement('div');
      controls.className = 'para-controls';

      const enBtn = document.createElement('button');
      enBtn.className = 'en-toggle';
      enBtn.title = '折叠/展开原文';
      enBtn.textContent = 'EN';
      enBtn.addEventListener('click', () => {
        const hidden = p.classList.toggle('en-hidden');
        enBtn.classList.toggle('active', hidden);
      });

      const enCpBtn = document.createElement('button');
      enCpBtn.className = 'para-copy';
      enCpBtn.title = '复制原文';
      enCpBtn.textContent = '⎘';
      enCpBtn.addEventListener('click', () => copyText(p.textContent.trim(), enCpBtn));

      const zhBtn = document.createElement('button');
      zhBtn.className = 'zh-toggle';
      zhBtn.title = '折叠/展开译文';
      zhBtn.textContent = '中';

      const zhCpBtn = document.createElement('button');
      zhCpBtn.className = 'para-copy';
      zhCpBtn.title = '复制译文';
      zhCpBtn.textContent = '⎘';
      zhCpBtn.addEventListener('click', () => copyText(zh, zhCpBtn));

      controls.appendChild(enBtn);
      controls.appendChild(enCpBtn);
      controls.appendChild(zhBtn);
      controls.appendChild(zhCpBtn);
      p.parentNode.insertBefore(controls, p);

      /* ZH block — inserted after the <p>, no click handler on block itself */
      const block = document.createElement('div');
      block.className = 'zh-block';
      block.dataset.p = idx;
      block.textContent = zh;
      p.after(block);

      zhBtn.addEventListener('click', () => {
        const folded = block.classList.toggle('zh-folded');
        zhBtn.classList.toggle('active', folded);
      });

      count++;
    });

    document.getElementById('tstatus').textContent = count + ' 段已翻译';
  }

  /* Prefer inline window.__ZH (baked in, works offline via file://).
     Fall back to fetch for http:// when not yet baked. */
  if (typeof window.__ZH !== 'undefined') {
    applyTranslations(window.__ZH);
  } else {
    fetch('translations/' + slug + '.json')
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(applyTranslations)
      .catch(() => { document.getElementById('tstatus').textContent = '译文未找到'; });
  }
})();
