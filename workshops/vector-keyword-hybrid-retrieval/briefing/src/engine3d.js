/* Tiny 3D point-cloud engine on <canvas>. No libraries, no WebGL.
   Perspective projection, slow auto-rotation, floor grid + axes, depth-sorted draw list.
   Used by slide 05 (62 docs) and slide 07 (416 chunks). */
(function(){
  const REDUCE = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const MONO = "'IBM Plex Mono',ui-monospace,Menlo,monospace";

  function Cloud(canvas, o){
    o = Object.assign({W: 708, H: 410, D: 3.5, F: null, pitch: .42, spin: .17, floorY: -.86, ox: 0, oy: 6}, o || {});
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = o.W * dpr; canvas.height = o.H * dpr;
    canvas.style.width = o.W + 'px'; canvas.style.height = o.H + 'px';
    const g = canvas.getContext('2d');
    g.scale(dpr, dpr);
    const F = o.F || o.H * 2.15;
    const self = {g, W: o.W, H: o.H, reduce: REDUCE, yaw: .5, time: 0, onFrame: null, queue: [], opts: o};
    const cp = Math.cos(o.pitch), sp = Math.sin(o.pitch);

    self.project = function(x, y, z){
      const cy = Math.cos(self.yaw), sy = Math.sin(self.yaw);
      const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;          // yaw about Y
      const y2 = y * cp + z1 * sp, z2 = z1 * cp - y * sp;         // pitch about X: camera ABOVE the floor, looking down
      const zc = z2 + o.D, k = F / zc;
      return [o.W / 2 + o.ox + x1 * k, o.H / 2 + o.oy - y2 * k, k, zc];
    };
    self.add = (z, fn) => self.queue.push([z, fn]);

    self.floor = function(alpha){
      g.save(); g.lineWidth = 1; g.strokeStyle = '#D3DAE6';
      const y = o.floorY, e = 1.5, step = .25;
      g.globalAlpha = alpha == null ? .9 : alpha;
      g.beginPath();
      for (let v = -e; v <= e + 1e-6; v += step){
        let a = self.project(-e, y, v), b = self.project(e, y, v); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]);
        a = self.project(v, y, -e); b = self.project(v, y, e); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]);
      }
      g.stroke(); g.restore();
    };
    self.axes = function(alpha){
      const defs = [[1.25, 0, 0, '#F04E98', 'X'], [0, 1.25, 0, '#02BCB7', 'Y'], [0, 0, 1.25, '#0B64DD', 'Z']];
      const org = self.project(0, o.floorY, 0);
      g.save(); g.globalAlpha = alpha == null ? .38 : alpha; g.lineWidth = 1.3; g.font = '600 11px ' + MONO; g.textAlign = 'center';
      defs.forEach(([x, y, z, col, lab]) => {
        const p = self.project(x, o.floorY + y, z);
        g.strokeStyle = col; g.fillStyle = col;
        g.beginPath(); g.moveTo(org[0], org[1]); g.lineTo(p[0], p[1]); g.stroke();
        g.beginPath(); g.arc(p[0], p[1], 2.4, 0, 6.283); g.fill();
        g.fillText(lab, p[0] + (p[0] > org[0] ? 9 : -9), p[1] + 4);
      });
      g.restore();
    };
    self.dot = function(sx, sy, r, col, a){
      g.globalAlpha = a; g.fillStyle = col; g.beginPath(); g.arc(sx, sy, r, 0, 6.283); g.fill();
    };
    self.line = function(a, b, col, alpha, w){
      g.globalAlpha = alpha; g.strokeStyle = col; g.lineWidth = w || 1; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke();
    };
    self.text = function(s, x, y, col, size, weight, align, halo){
      g.save(); g.font = (weight || 600) + ' ' + (size || 12) + 'px ' + MONO; g.textAlign = align || 'center';
      if (halo !== false){ g.lineWidth = 4; g.strokeStyle = '#fff'; g.lineJoin = 'round'; g.globalAlpha = 1; g.strokeText(s, x, y); }
      g.fillStyle = col; g.globalAlpha = 1; g.fillText(s, x, y); g.restore();
    };
    self.diamond = function(sx, sy, r, fill, stroke, a){
      g.save(); g.globalAlpha = a; g.beginPath(); g.moveTo(sx, sy - r); g.lineTo(sx + r, sy); g.lineTo(sx, sy + r); g.lineTo(sx - r, sy); g.closePath();
      g.fillStyle = fill; g.fill(); g.lineWidth = 1.8; g.strokeStyle = stroke; g.stroke(); g.restore();
    };

    let last = performance.now(), t0 = last;
    function loop(now){
      requestAnimationFrame(loop);
      if (!canvas.offsetParent) { last = now; return; }              // slide hidden: do nothing
      const dt = Math.min(.1, (now - last) / 1000); last = now;
      self.time += dt;
      if (!REDUCE) self.yaw += dt * o.spin;
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      g.clearRect(0, 0, o.W, o.H);
      self.queue.length = 0;
      self.floor(); self.axes();
      if (self.onFrame) self.onFrame(self.time, dt);
      self.queue.sort((a, b) => b[0] - a[0]);
      for (const [, fn] of self.queue) fn();
      g.globalAlpha = 1;
    }
    requestAnimationFrame(loop);
    return self;
  }

  const ease = t => t <= 0 ? 0 : t >= 1 ? 1 : 1 - Math.pow(1 - t, 3);
  const easeIO = t => t <= 0 ? 0 : t >= 1 ? 1 : (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const back = t => { if (t <= 0) return 0; if (t >= 1) return 1; const c = 1.7; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
  const clamp01 = v => Math.max(0, Math.min(1, v));
  window.PM3 = {Cloud, ease, easeIO, back, clamp01, REDUCE};
})();
