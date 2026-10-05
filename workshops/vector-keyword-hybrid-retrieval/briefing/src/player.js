/* Minimal deck player: steps, slides, #N[.S] deep links, fit-to-viewport, N toggles speaker notes. No toolbar. */
(function(){
  const stage = document.getElementById('stage');
  const slides = Array.from(stage.querySelectorAll('.slide'));
  const panel = document.getElementById('notes');
  const nbody = document.getElementById('notes-body');
  const ntitle = document.getElementById('notes-n');
  let cur = 0, step = 1, notesOn = false;
  const max = s => +s.dataset.steps || 1;
  const NOTES_W = 380, BAR_H = 44;
  const $ = id => document.getElementById(id);
  const ov = $('overview'), ovg = $('ovg');

  function fit(){
    const aw = innerWidth - (notesOn ? NOTES_W : 0), ah = innerHeight - BAR_H;     // the bar and the notes panel never overlap the stage
    const s = Math.min(aw / 1280, ah / 720);
    stage.style.transform = 'translate(' + ((aw - 1280 * s) / 2) + 'px,' + ((ah - 720 * s) / 2) + 'px) scale(' + s + ')';
  }

  function runInit(s){
    if (s.dataset.inited) return;
    s.dataset.inited = '1';
    const sc = s.querySelector('script.init');
    if (sc) { try { (new Function('slide', sc.textContent))(s); } catch (e) { console.error('init failed', s.id, e); } }
  }

  function render(){
    slides.forEach((s, i) => s.classList.toggle('on', i === cur));
    const s = slides[cur];
    runInit(s);
    s.dataset.step = step;
    s.dispatchEvent(new CustomEvent('stepchange', {detail: step}));
    s.querySelectorAll('[data-s]').forEach(e => e.classList.toggle('show', step >= +e.dataset.s));
    s.querySelectorAll('[data-at]').forEach(e => e.classList.toggle('show', step === +e.dataset.at));
    s.querySelectorAll('[data-eq]').forEach(e => e.classList.toggle('on', step === +e.dataset.eq));
    $('count').textContent = (cur + 1) + ' / ' + slides.length;
    $('btn-prev').disabled = cur === 0 && step === 1;
    $('btn-next').disabled = cur === slides.length - 1 && step === max(s);
    ovg.querySelectorAll('.tile').forEach((t, i) => t.classList.toggle('cur', i === cur));
    const n = s.querySelector('aside.nt');
    nbody.innerHTML = n ? n.innerHTML : '<p><em>No notes for this slide.</em></p>';
    ntitle.textContent = (cur + 1) + ' / ' + slides.length;
    try { history.replaceState(null, '', '#' + (cur + 1) + (step > 1 ? '.' + step : '')); } catch (e) {}
  }

  function go(i, st){
    cur = Math.max(0, Math.min(slides.length - 1, i));
    step = Math.max(1, Math.min(max(slides[cur]), st || 1));
    render();
  }
  function next(){ if (step < max(slides[cur])) { step++; render(); } else if (cur < slides.length - 1) go(cur + 1, 1); }
  function prev(){ if (step > 1) { step--; render(); } else if (cur > 0) go(cur - 1, max(slides[cur - 1])); }
  /* overview grid: plain DOM tiles, number + title */
  slides.forEach((s, i) => {
    const h = s.querySelector('h1'), t = (h ? h.innerHTML.replace(/<br\s*\/?>/g, ' ').replace(/<[^>]+>/g, '') : s.dataset.foot || '').replace(/\s+/g, ' ').trim();
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tile'; b.setAttribute('aria-label', 'Slide ' + (i + 1) + ': ' + t);
    b.innerHTML = '<i>' + String(i + 1).padStart(2, '0') + '</i><span></span>';
    b.lastChild.textContent = t;
    b.addEventListener('click', () => { closeOv(); go(i, 1); b.blur(); });
    ovg.appendChild(b);
  });
  function openOv(){ ov.hidden = false; const c = ovg.querySelector('.tile.cur') || ovg.firstChild; c.focus(); }
  function closeOv(){ ov.hidden = true; if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }
  const ovOpen = () => !ov.hidden;
  function toggleNotes(){ notesOn = !notesOn; document.body.classList.toggle('notes-on', notesOn); fit(); }

  document.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (k === 'Escape' && ovOpen()) { e.preventDefault(); closeOv(); return; }
    if (k === 'o' || k === 'O') { e.preventDefault(); ovOpen() ? closeOv() : openOv(); return; }
    if (ovOpen()) { if (k === 'Tab') return; if (k === 'Enter' || k === ' ') return; return; }          // overview: tiles handle their own clicks
    if ((k === ' ' || k === 'Enter') && e.target.closest && e.target.closest('#bar')) return;      // focused nav buttons activate natively, once
    if (k === 'ArrowRight' || k === ' ' || k === 'PageDown' || k === 'ArrowDown') { e.preventDefault(); next(); }
    else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'ArrowUp') { e.preventDefault(); prev(); }
    else if (k === 'Home') { go(0, 1); }
    else if (k === 'End') { go(slides.length - 1, max(slides[slides.length - 1])); }
    else if (k === 'n' || k === 'N') { toggleNotes(); }
  });

  /* on-slide controls: any element with data-goto="N" jumps to step N of the current slide */
  stage.addEventListener('click', e => {
    const t = e.target.closest('[data-goto]');
    if (!t) return;
    step = Math.min(max(slides[cur]), +t.dataset.goto);
    render();
  });

  $('btn-prev').addEventListener('click', e => { prev(); e.currentTarget.blur(); });
  $('btn-next').addEventListener('click', e => { next(); e.currentTarget.blur(); });
  $('btn-overview').addEventListener('click', e => { ovOpen() ? closeOv() : openOv(); });
  ov.addEventListener('click', e => { if (e.target === ov) closeOv(); });
  function fromHash(){
    const m = /^#(\d+)(?:\.(\d+))?$/.exec(location.hash);
    if (m) go(+m[1] - 1, m[2] ? +m[2] : 1); else go(0, 1);
  }
  addEventListener('hashchange', fromHash);
  addEventListener('resize', fit);
  fit(); fromHash();
})();
