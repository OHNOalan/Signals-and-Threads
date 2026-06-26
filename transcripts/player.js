/* Fixed bottom audio player — Signals & Threads local archive */
(function () {
  const audio = document.querySelector('audio');
  if (!audio) return;

  audio.removeAttribute('controls');
  audio.style.cssText = 'position:fixed;left:-9999px;width:1px;height:1px;';

  function fmt(s) {
    s = Math.floor(s) || 0;
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sc = s % 60;
    if (h) return `${h}:${String(m).padStart(2,'0')}:${String(sc).padStart(2,'0')}`;
    return `${String(m).padStart(2,'0')}:${String(sc).padStart(2,'0')}`;
  }

  const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

  const bar = document.createElement('div');
  bar.className = 'ap-bar';
  bar.innerHTML = `
    <button class="ap-btn ap-play" title="播放/暂停 (空格)">▶</button>
    <span class="ap-time" id="ap-cur">00:00</span>
    <div class="ap-track">
      <div class="ap-fill"></div>
      <input class="ap-scrubber" type="range" min="0" max="10000" value="0" step="1">
    </div>
    <span class="ap-time" id="ap-dur">--:--</span>
    <button class="ap-btn ap-skip" id="ap-back" title="后退15秒 (←)">
      <svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H5c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg><span>15</span>
    </button>
    <button class="ap-btn ap-skip" id="ap-fwd" title="前进15秒 (→)">
      <span>15</span><svg viewBox="0 0 24 24"><path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/></svg>
    </button>
    <div class="ap-speed-wrap">
      <button class="ap-btn ap-speed-btn" id="ap-speed">1×</button>
      <div class="ap-speed-menu" id="ap-speed-menu">
        ${SPEEDS.map(r => `<label><input type="radio" name="ap-spd" value="${r}"${r === 1 ? ' checked' : ''}> ${r}×</label>`).join('')}
      </div>
    </div>`;
  document.body.appendChild(bar);

  const playBtn   = bar.querySelector('.ap-play');
  const curEl     = document.getElementById('ap-cur');
  const durEl     = document.getElementById('ap-dur');
  const fill      = bar.querySelector('.ap-fill');
  const scrubber  = bar.querySelector('.ap-scrubber');
  const speedBtn  = document.getElementById('ap-speed');
  const speedMenu = document.getElementById('ap-speed-menu');

  // Play / pause
  const toggle = () => audio.paused ? audio.play() : audio.pause();
  playBtn.addEventListener('click', toggle);
  audio.addEventListener('play',  () => playBtn.textContent = '⏸');
  audio.addEventListener('pause', () => playBtn.textContent = '▶');
  audio.addEventListener('ended', () => playBtn.textContent = '▶');
  audio.addEventListener('loadedmetadata', () => durEl.textContent = fmt(audio.duration));

  // Progress — scrubber is an invisible <input type="range"> overlaid on the track.
  // During drag: update fill + time visually only. On release (change): actually seek.
  let scrubbing = false;
  audio.addEventListener('timeupdate', () => {
    if (scrubbing) return;
    const pct = audio.duration ? audio.currentTime / audio.duration : 0;
    curEl.textContent = fmt(audio.currentTime);
    fill.style.width = (pct * 100) + '%';
    scrubber.value = Math.round(pct * 10000);
  });
  scrubber.addEventListener('input', () => {
    scrubbing = true;
    const pct = scrubber.value / 10000;
    fill.style.width = (pct * 100) + '%';
    curEl.textContent = fmt(pct * (audio.duration || 0));
  });
  scrubber.addEventListener('change', () => {
    scrubbing = false;
    audio.currentTime = (scrubber.value / 10000) * audio.duration;
  });

  // Skip ±15s
  document.getElementById('ap-back').addEventListener('click', () => audio.currentTime = Math.max(0, audio.currentTime - 15));
  document.getElementById('ap-fwd').addEventListener('click',  () => audio.currentTime = Math.min(audio.duration, audio.currentTime + 15));

  // Speed
  speedBtn.addEventListener('click', e => { speedMenu.classList.toggle('open'); e.stopPropagation(); });
  document.addEventListener('click', () => speedMenu.classList.remove('open'));
  speedMenu.querySelectorAll('input[type=radio]').forEach(r =>
    r.addEventListener('change', () => {
      audio.playbackRate = parseFloat(r.value);
      speedBtn.textContent = r.value + '×';
      speedMenu.classList.remove('open');
    })
  );

  // Keyboard shortcuts
  document.addEventListener('keydown', e => {
    if (['INPUT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement?.tagName)) return;
    if (e.code === 'Space')      { e.preventDefault(); toggle(); }
    if (e.code === 'ArrowLeft')  audio.currentTime = Math.max(0, audio.currentTime - 15);
    if (e.code === 'ArrowRight') audio.currentTime = Math.min(audio.duration, audio.currentTime + 15);
  });
})();
