(function(){
  const EW = window.EW = {};
  const NS = 'http://www.w3.org/2000/svg';
  EW.ease = t => t <= 0 ? 0 : t >= 1 ? 1 : 1 - Math.pow(1 - t, 3);
  EW.back = t => { if (t <= 0) return 0; if (t >= 1) return 1; const c = 1.55; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
  EW.rand = s => { s = s || 7; return () => (s = (s * 16807) % 2147483647) / 2147483647; };
  const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  EW.el = el;

  EW.FACES = {
    blue:   {top:'#FFFFFF', left:'#0B64DD', right:'#0A4FB0'},
    pink:   {top:'#FFFFFF', left:'#F04E98', right:'#343741'},
    orange: {top:'#FFFFFF', left:'#FF7E62', right:'#343741'},
    teal:   {top:'#FFFFFF', left:'#48EFCF', right:'#02BCB7'},
    yellow: {top:'#FFFFFF', left:'#FEC514', right:'#343741'},
    ink:    {top:'#FFFFFF', left:'#343741', right:'#1D1E24'},
    slate:  {top:'#F5F7FA', left:'#DDE3EC', right:'#B5BFCE'},
    white:  {top:'#FFFFFF', left:'#F5F7FA', right:'#DDE3EC'},
    glass:  {top:'rgba(255,255,255,.35)', left:'rgba(52,55,65,.55)', right:'rgba(52,55,65,.35)'}
  };

  // Isometric scene. x runs right-down, y runs left-down, z up. Units are px at scale s.
  EW.iso = function(svg, o){
    o = Object.assign({ox: 0, oy: 0, s: 1}, o || {});
    const C = .8660254, S = .5, items = [], t0 = performance.now();
    const defs = el('defs', {}, svg);
    const blur = el('filter', {id: 'ewblur' + Math.random().toString(36).slice(2, 7), x: '-50%', y: '-50%', width: '200%', height: '200%'}, defs);
    el('feGaussianBlur', {stdDeviation: 9}, blur);
    const floor = el('g', {}, svg), body = el('g', {}, svg), top = el('g', {}, svg);
    const P = (x, y, z) => [o.ox + (x - y) * C * o.s, o.oy + ((x + y) * S - z) * o.s];
    const poly = pts => pts.map(p => P(...p).map(v => v.toFixed(1)).join(',')).join(' ');
    const scene = {P, svg, floor, body, top};

    scene.box = function(b){
      b = Object.assign({x: 0, y: 0, z: 0, w: 60, d: 60, h: 60, c: 'blue', stroke: '#1D1E24', sw: 1, delay: 0, drop: 70, dur: .7}, b);
      const F = typeof b.c === 'string' ? EW.FACES[b.c] : b.c, zt = b.z + b.h, {x, y, w, d} = b;
      const g = el('g', {}, body);
      if (b.shadow !== false && b.z < 1){
        const sh = el('polygon', {points: poly([[x + 8, y + 8, 0], [x + w + 14, y + 8, 0], [x + w + 14, y + d + 14, 0], [x + 8, y + d + 14, 0]]), fill: 'rgba(40,55,90,.16)', filter: `url(#${blur.id})`}, floor);
        b.sh = sh;
      }
      const st = b.stroke ? {stroke: b.stroke, 'stroke-width': b.sw, 'stroke-linejoin': 'round'} : {};
      if (b.dash) st['stroke-dasharray'] = b.dash;
      const fl = f => b.wire ? 'none' : f;
      el('polygon', Object.assign({points: poly([[x, y + d, zt], [x + w, y + d, zt], [x + w, y + d, b.z], [x, y + d, b.z]]), fill: fl(F.left)}, st), g);
      el('polygon', Object.assign({points: poly([[x + w, y, zt], [x + w, y + d, zt], [x + w, y + d, b.z], [x + w, y, b.z]]), fill: fl(F.right)}, st), g);
      el('polygon', Object.assign({points: poly([[x, y, zt], [x + w, y, zt], [x + w, y + d, zt], [x, y + d, zt]]), fill: fl(F.top)}, st), g);
      if (b.wire && b.inner){ const [ax, ay] = P(x, y, zt), [bx, by] = P(x, y, b.z), [cx, cy] = P(x + w, y + d, b.z), [dx, dy] = P(x, y + d, b.z), [ex, ey] = P(x + w, y, b.z);
        el('path', Object.assign({d: `M${ax},${ay}L${bx},${by}M${bx},${by}L${dx},${dy}M${bx},${by}L${ex},${ey}`, fill: 'none'}, st, {'stroke-opacity': .45}), g); }
      if (b.label) { b.label.at = b.label.at || [x + w / 2, y + d, b.z + b.h / 2]; }
      b.g = g; b.kind = 'box'; b.key = (x + w / 2) + (y + d / 2) + b.z * .01 + (b.order || 0);
      items.push(b); return b;
    };

    scene.rect = function(r){
      r = Object.assign({x: 0, y: 0, z: 0, w: 100, d: 100, stroke: '#1D1E24', sw: 1.4, dash: '2 4', fill: 'none', delay: 0, drop: 0, dur: .6}, r);
      const g = el('g', {}, r.layer === 'top' ? top : floor);
      el('polygon', {points: poly([[r.x, r.y, r.z], [r.x + r.w, r.y, r.z], [r.x + r.w, r.y + r.d, r.z], [r.x, r.y + r.d, r.z]]), fill: r.fill, stroke: r.stroke, 'stroke-width': r.sw, 'stroke-dasharray': r.dash}, g);
      r.g = g; r.kind = 'rect'; items.push(r); return r;
    };

    scene.label = function(l){
      l = Object.assign({side: 'r', len: 90, delay: .8, dur: .5, title: '', sub: '', size: 12}, l);
      const [ax, ay] = Array.isArray(l.at) && l.at.length === 3 ? P(...l.at) : l.at;
      const ex = ax + (l.side === 'r' ? l.len : -l.len);
      const g = el('g', {}, top);
      const ln = el('line', {x1: ax, y1: ay, x2: ex, y2: ay, stroke: '#1D1E24', 'stroke-width': 1}, g);
      const L = Math.abs(ex - ax); ln.setAttribute('stroke-dasharray', L); ln.setAttribute('stroke-dashoffset', L);
      const anchor = l.side === 'r' ? 'start' : 'end', tx = ex + (l.side === 'r' ? 10 : -10);
      const lines = [].concat(l.title ? [[l.title, 600]] : [], l.sub ? [].concat(l.sub).map(s => [s, 400]) : []);
      const txt = el('g', {opacity: 0}, g);
      const y0 = ay + 4 - (lines.length - 1) * (l.size * 1.45) / 2;
      lines.forEach(([t, wgt], i) => { const e = el('text', {x: tx, y: y0 + i * l.size * 1.45, 'text-anchor': anchor, 'font-size': l.size, 'font-weight': wgt, fill: wgt > 500 ? '#1D1E24' : '#343741', 'letter-spacing': '.06em', stroke: l.halo || '#fff', 'stroke-width': 5, 'paint-order': 'stroke', 'stroke-linejoin': 'round'}, txt); e.textContent = l.raw ? t : t.toUpperCase(); if (l.raw) e.setAttribute('letter-spacing', '.01em'); });
      l.g = g; l.ln = ln; l.L = L; l.txt = txt; l.kind = 'label'; items.push(l); return l;
    };

    // Painter's order: anything resting above a box's footprint draws after it; otherwise back-to-front.
    scene.order = function(){
      const bx = items.filter(i => i.kind === 'box');
      const over = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.d && b.y < a.y + a.d;
      const lvl = b => bx.filter(a => a !== b && over(a, b) && a.z + a.h <= b.z + .5 && (a.w * a.d) >= (b.w * b.d) * .25).length;
      bx.forEach(b => { b.lvl = lvl(b); });
      bx.sort((a, b) => (a.lvl - b.lvl) || (a.key - b.key)).forEach(b => body.appendChild(b.g));
    };

    scene.frame = function(t){
      for (const it of items){
        const k = (t - it.delay) / it.dur;
        if (it.kind === 'label'){ const e = EW.ease(k); it.ln.setAttribute('stroke-dashoffset', it.L * (1 - e)); it.txt.setAttribute('opacity', EW.ease((t - it.delay - it.dur * .6) / .4)); continue; }
        const e = it.snap === false ? EW.ease(k) : EW.back(k), op = Math.min(1, Math.max(0, k * 2.5));
        let dy = -it.drop * (1 - e) * o.s;
        if (it.float && k > 1) dy += Math.sin((t - it.delay - it.dur) * (it.floatSpeed || 1.4) + (it.phase || 0)) * it.float;
        it.g.setAttribute('transform', `translate(0,${dy.toFixed(2)})`);
        it.g.setAttribute('opacity', (it.op === undefined ? 1 : it.op) * op);
        if (it.sh) it.sh.setAttribute('opacity', op);
        if (it.onFrame) it.onFrame(t, it);
      }
      if (o.onFrame) o.onFrame(t);
    };
    scene.run = function(){ scene.order(); const f = now => { scene.frame((now - t0) / 1000); requestAnimationFrame(f); }; requestAnimationFrame(f); return scene; };
    return scene;
  };

  // Organic dot-matrix field with a slow shimmer wave.
  EW.dots = function(o){
    o = Object.assign({x: 0, y: 0, w: 1280, h: 720, gap: 11, r: 1.05, color: [197, 204, 216], hi: [11, 100, 221], seed: 3, blobs: 7, thr: .55, wave: true, parent: document.body, z: 0}, o);
    const cv = document.createElement('canvas'); cv.className = 'ew-dots';
    Object.assign(cv.style, {left: o.x + 'px', top: o.y + 'px', width: o.w + 'px', height: o.h + 'px', zIndex: o.z});
    o.parent.insertBefore(cv, o.parent.firstChild);
    const dpr = 2; cv.width = o.w * dpr; cv.height = o.h * dpr; const c = cv.getContext('2d'); c.scale(dpr, dpr);
    const R = EW.rand(o.seed), B = o.blobsList || Array.from({length: o.blobs}, () => ({x: R() * o.w, y: R() * o.h, r: (.18 + R() * .28) * Math.min(o.w, o.h) * 1.4}));
    const pts = [];
    for (let y = o.gap / 2; y < o.h; y += o.gap) for (let x = o.gap / 2; x < o.w; x += o.gap){
      let f = 0; for (const b of B){ const dx = (x - b.x) / b.r, dy = (y - b.y) / b.r; f += Math.exp(-(dx * dx + dy * dy) * 2.2); }
      const edge = f - o.thr; if (edge < -.12) continue; if (edge < .12 && R() > (edge + .12) / .24) continue;
      pts.push([x, y, R()]);
    }
    const draw = t => {
      c.clearRect(0, 0, o.w, o.h);
      const wx = ((t * .09) % 1.6 - .3) * (o.w + o.h);
      for (const [x, y, q] of pts){
        let k = 0; if (o.wave){ const d = Math.abs((x + y * .7) - wx); k = Math.max(0, 1 - d / 90) * (.55 + .45 * q); }
        const col = o.color.map((v, i) => Math.round(v + (o.hi[i] - v) * k * .75));
        c.fillStyle = `rgb(${col})`; c.beginPath(); c.arc(x, y, o.r + k * .5, 0, 6.283); c.fill();
      }
    };
    if (o.wave){ const t0 = performance.now(); const f = now => { draw((now - t0) / 1000); requestAnimationFrame(f); }; requestAnimationFrame(f); } else draw(0);
    return cv;
  };

  EW.count = function(node, to, o){
    o = Object.assign({dur: 1.2, delay: .3, dec: 0, pre: '', post: ''}, o || {});
    const t0 = performance.now();
    const f = now => { const k = EW.ease(((now - t0) / 1000 - o.delay) / o.dur); node.textContent = o.pre + (to * k).toFixed(o.dec) + o.post; if (k < 1) requestAnimationFrame(f); };
    requestAnimationFrame(f);
  };

  EW.loop = function(fn){ const t0 = performance.now(); const f = now => { fn((now - t0) / 1000); requestAnimationFrame(f); }; requestAnimationFrame(f); };

  EW.MARK = '<svg viewBox="0 0 236.6 235.6" xmlns="http://www.w3.org/2000/svg"><path d="M236.6 123.5a46.54 46.54 0 0 0-30.8-43.9A67 67 0 0 0 140.2 0 66.72 66.72 0 0 0 86 27.7a35.5 35.5 0 0 0-57.2 28.1A36.77 36.77 0 0 0 31 68.2a46.75 46.75 0 0 0-.1 88 66.66 66.66 0 0 0 119.6 51.6 35 35 0 0 0 21.7 7.6 35.51 35.51 0 0 0 35.5-35.5 36.77 36.77 0 0 0-2.2-12.4 47.08 47.08 0 0 0 31.1-44" fill="#fff"/><path d="M93 101.5l51.8 23.6L197 79.3a54.71 54.71 0 0 0 1.1-11.5 58.35 58.35 0 0 0-106.5-33l-8.7 45.1L93 101.5z" fill="#fed10a"/><path d="M39.4 156.3a56.62 56.62 0 0 0-1.1 11.7 58.58 58.58 0 0 0 107 32.9l8.6-44.9-11.5-22-52-23.7z" fill="#24bbb1"/><path d="M39.1 66.7l35.5 8.4 7.8-40.3a28 28 0 0 0-43.3 31.9" fill="#ef5098"/><path d="M36 75.2a39.1 39.1 0 0 0-1.7 73.7l49.8-45L75 84.4z" fill="#17a8e0"/><path d="M154.3 200.9a28 28 0 0 0 43.2-31.9l-35.4-8.3z" fill="#93c83e"/><path d="M161.5 151.4l39 9.1a39.1 39.1 0 0 0 1.7-73.7l-51 44.7z" fill="#0779a1"/></svg>';

  function chrome(){
    const f = document.body.dataset.foot; if (f === undefined || f === 'none') return;
    const d = document.createElement('div'); d.className = 'ew-foot';
    d.innerHTML = `<span class="lg">${EW.MARK}elastic</span><span>${f}</span>`;
    document.body.appendChild(d);
  }
  function fit(){
    if (window !== window.top) return;
    const f = () => { const s = Math.min(innerWidth / 1280, innerHeight / 720);
      Object.assign(document.body.style, {transform: `scale(${s})`, transformOrigin: '0 0', left: (innerWidth - 1280 * s) / 2 + 'px', top: (innerHeight - 720 * s) / 2 + 'px'}); };
    f(); addEventListener('resize', f);
  }
  document.addEventListener('DOMContentLoaded', () => { chrome(); fit(); });
})();
