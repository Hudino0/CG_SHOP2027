// Animación del video corto en estilo risografía.
// Cada tinta se dibuja en su propia capa (sólo forma y alfa). Al final, cada capa
// se tiñe con su color, pierde tinta con un grano de papel, se desplaza un poco
// (mal registro) y se imprime sobre el papel con "multiply", como en una riso.
// render(t) dibuja el cuadro del segundo t; no guarda estado entre cuadros.
'use strict';

const W = 1080, H = 1920;
// cada capa tiene un papel fijo: yellow = claro (rociado, marcador), green = campo,
// pink = acento (#e4007c), blue = tinta de texto y líneas. La paleta sólo cambia los colores.
const PALETAS = {
  riso: { paper: '#f3ecdc', yellow: '#ffe800', green: '#00a95c', pink: '#e4007c', blue: '#3255a4' },
  // colores de la paleta del rosa mexicano: complementario, monocromático y análogos
  malaquita: { paper: '#f3ecdc', yellow: '#ffb1db', green: '#00e468', pink: '#e4007c', blue: '#4b0029' },
  turquesa: { paper: '#f3ecdc', yellow: '#ffb1db', green: '#00e4da', pink: '#e4007c', blue: '#6800e4' },
  // esquema complementario de colorxs.com: verde pasto 009845, rosa FF7EC4, vino 4B0029
  complementaria: { paper: '#f3ecdc', yellow: '#ff7ec4', green: '#009845', pink: '#e4007c', blue: '#4b0029' },
  mixta: { paper: '#f3ecdc', yellow: '#ff7ec4', green: '#00e4da', pink: '#e4007c', blue: '#4b0029' },
};
const INK = PALETAS[new URLSearchParams(location.search).get('pal') || window.PALETA || 'complementaria'];
const ORDER = ['yellow', 'green', 'pink', 'blue'];
const MIS = { yellow: [-3, 2], green: [2, 3], pink: [4, -2], blue: [-1, -1] };
const DISPLAY = '800 {s}px Bricolage, sans-serif';
const MONO = '700 {s}px "Space Mono", "DejaVu Sans Mono", monospace';
const font = (f, s) => f.replace('{s}', s);

const TL = window.TL, CAMPO = window.CAMPO;
const K = Object.fromEntries(TL.lines.map(l => [l.key, l]));
const SC = TL.scenes;
let T = 0;

// ---------- utilidades ----------
const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const eout = t => 1 - Math.pow(1 - t, 3);
const back = t => { const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
const P = (t0, d) => clamp((T - t0) / d);
const st = k => K[k].start, en = k => K[k].end;
// momento aproximado en que se dice una palabra de la frase k
const wordT = (k, w) => { const l = K[k]; const i = l.text.toLowerCase().indexOf(w.toLowerCase()); return lerp(l.start, l.end, Math.max(0, i) / l.text.length); };
// opacidad de un elemento que vive entre a y b
const life = (a, b, fi = .3, fo = .3) => Math.min(P(a, fi), 1 - P(b, fo));
function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

// ---------- capas de tinta ----------
const cv = document.getElementById('c');
const main = cv.getContext('2d');
const mk = () => { const c = document.createElement('canvas'); c.width = W; c.height = H; return c; };
const L = {};
for (const k of ORDER) { const c = mk(); L[k] = c.getContext('2d'); }
const tmp = mk(), tctx = tmp.getContext('2d');
const scratch = mk(), sctx = scratch.getContext('2d');

function texture(seed, fn) {
  const c = mk(), x = c.getContext('2d'), img = x.createImageData(W, H), r = rng(seed);
  fn(img.data, r);
  x.putImageData(img, 0, 0);
  return c;
}
const paper = texture(3, (d, r) => {
  const base = [1, 3, 5].map(i => parseInt(INK.paper.slice(i, i + 2), 16));
  for (let i = 0; i < d.length; i += 4) {
    const n = (r() - .5) * 10 + (r() < .004 ? -18 : 0);
    d[i] = base[0] + n; d[i + 1] = base[1] + n; d[i + 2] = base[2] + n * 1.2; d[i + 3] = 255;
  }
});
// motas donde la tinta no agarra
const grains = [11, 12, 13].map(s => texture(s, (d, r) => {
  for (let i = 0; i < d.length; i += 4) {
    const v = r();
    d[i + 3] = v < .05 ? 255 : v < .16 ? 110 : 0;
  }
}));

// tramas de medios tonos, una por nivel y tinta
const HT = {};
function halftone(ctx, level, angle = 45, cell = 9) {
  const q = Math.round(clamp(level) * 10);
  const key = q + ':' + angle + ':' + cell;
  if (!HT[key]) {
    const c = document.createElement('canvas'); c.width = c.height = cell;
    const x = c.getContext('2d');
    x.fillStyle = '#000';
    x.beginPath(); x.arc(cell / 2, cell / 2, cell * Math.sqrt(q / 10 / Math.PI) * 1.05, 0, 7); x.fill();
    const p = ctx.createPattern(c, 'repeat');
    p.setTransform(new DOMMatrix().rotate(angle));
    HT[key] = p;
  }
  return HT[key];
}

function composite() {
  main.globalCompositeOperation = 'source-over';
  main.globalAlpha = 1;
  main.drawImage(paper, 0, 0);
  const g = grains[Math.floor(T * 1.5) % 3];  // el grano cambia poco: mantiene el MP4 pequeño
  ORDER.forEach((k, i) => {
    tctx.globalCompositeOperation = 'source-over';
    tctx.clearRect(0, 0, W, H);
    tctx.drawImage(L[k].canvas, 0, 0);
    // lo rociado ya no es pasto: la tinta clara borra al campo debajo
    if (k === 'green') { tctx.globalCompositeOperation = 'destination-out'; tctx.drawImage(L.yellow.canvas, 0, 0); }
    tctx.globalCompositeOperation = 'source-in';
    tctx.fillStyle = INK[k];
    tctx.fillRect(0, 0, W, H);
    tctx.globalCompositeOperation = 'destination-out';
    tctx.drawImage(g, (i * 37) % 13 - 6, (i * 53) % 11 - 5);
    main.globalCompositeOperation = 'multiply';
    main.drawImage(tmp, MIS[k][0], MIS[k][1]);
  });
  main.globalCompositeOperation = 'source-over';
}

// ---------- texto ----------
function txt(ctx, s, x, y, size, opt = {}) {
  ctx.save();
  ctx.font = font(opt.mono ? MONO : DISPLAY, size);
  ctx.textAlign = opt.align || 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.globalAlpha *= opt.alpha ?? 1;
  ctx.fillStyle = '#000';
  if (opt.spacing) ctx.letterSpacing = opt.spacing + 'px';
  ctx.fillText(s, x, y);
  ctx.restore();
}
function fitSize(s, size, maxW, mono) {
  const c = L.blue; c.save(); c.font = font(mono ? MONO : DISPLAY, size);
  const w = c.measureText(s).width; c.restore();
  return w > maxW ? size * maxW / w : size;
}
function wrap(s, size, maxW) {
  const c = L.blue; c.save(); c.font = font(DISPLAY, size);
  const out = []; let line = '';
  for (const w of s.split(' ')) {
    const t = line ? line + ' ' + w : w;
    if (c.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t;
  }
  out.push(line); c.restore();
  return out;
}

// ---------- geometría del campo ----------
const S = 120;
const X0 = (W - CAMPO.cols * S) / 2, Y0 = 450;
const cells = CAMPO.cells;
const inSet = new Set(cells.map(([x, y]) => x + ',' + y));
const has = (x, y) => inSet.has(x + ',' + y);
const cen = ([x, y]) => [X0 + (x + .5) * S, Y0 + (y + .5) * S];
const fieldPath = new Path2D();
for (const [x, y] of cells) fieldPath.rect(X0 + x * S, Y0 + y * S, S, S);
const gridEdges = [];
for (const [x, y] of cells) { if (has(x + 1, y)) gridEdges.push([[x, y], [x + 1, y]]); if (has(x, y + 1)) gridEdges.push([[x, y], [x, y + 1]]); }

// contorno suave del "campo real": el borde del poliominó, inflado y suavizado
const blob = (() => {
  const next = new Map();
  const add = (a, b) => next.set(a.join(), b);
  for (const [x, y] of cells) {
    if (!has(x, y - 1)) add([x, y], [x + 1, y]);
    if (!has(x + 1, y)) add([x + 1, y], [x + 1, y + 1]);
    if (!has(x, y + 1)) add([x + 1, y + 1], [x, y + 1]);
    if (!has(x - 1, y)) add([x, y + 1], [x, y]);
  }
  const start = next.keys().next().value;
  let pts = [], k = start;
  do { pts.push(k.split(',').map(Number)); k = next.get(k).join(); } while (k !== start);
  // inflar cada vértice hacia afuera
  const n = pts.length;
  pts = pts.map((p, i) => {
    const a = pts[(i - 1 + n) % n], b = pts[(i + 1) % n];
    const d1 = [p[0] - a[0], p[1] - a[1]], d2 = [b[0] - p[0], b[1] - p[1]];
    const nx = Math.sign(d1[1]) + Math.sign(d2[1]), ny = -Math.sign(d1[0]) - Math.sign(d2[0]);
    return [p[0] + .2 * nx, p[1] + .2 * ny];
  });
  for (let it = 0; it < 4; it++) {
    const q = [];
    pts.forEach((p, i) => { const b = pts[(i + 1) % pts.length]; q.push([lerp(p[0], b[0], .25), lerp(p[1], b[1], .25)], [lerp(p[0], b[0], .75), lerp(p[1], b[1], .75)]); });
    pts = q;
  }
  const cx = CAMPO.cols / 2, cy = CAMPO.rows / 2;
  pts = pts.map(([x, y]) => {
    const a = Math.atan2(y - cy, x - cx), f = 1 + .025 * Math.sin(3 * a + 1) + .015 * Math.sin(7 * a);
    return [X0 + (cx + (x - cx) * f) * S, Y0 + (cy + (y - cy) * f) * S];
  });
  const p = new Path2D(); pts.forEach(([x, y], i) => i ? p.lineTo(x, y) : p.moveTo(x, y)); p.closePath();
  // comprobación: el contorno contiene justo los centros de los cuadritos
  const ok = [];
  for (let y = 0; y < CAMPO.rows; y++) for (let x = 0; x < CAMPO.cols; x++) {
    const [a, b] = cen([x, y]);
    if (main.isPointInPath(p, a, b) !== has(x, y)) ok.push([x, y]);
  }
  if (ok.length) console.warn('contorno no coincide en', JSON.stringify(ok));
  return p;
})();

// ---------- tours ----------
const sub = (a, b) => [a[0] - b[0], a[1] - b[1]];
const eqv = (a, b) => a[0] === b[0] && a[1] === b[1];
const K_P = 1 - Math.SQRT1_2;  // la pieza "giro" pasa a 1/2 de la esquina: a esta fracción del centro a la esquina
function tourPts(tour, mode) {
  const n = tour.length, pts = [];
  for (let i = 0; i < n; i++) {
    const a = tour[(i - 1 + n) % n], b = tour[i], c = tour[(i + 1) % n];
    const cb = cen(b), mi = [(cen(a)[0] + cb[0]) / 2, (cen(a)[1] + cb[1]) / 2], mo = [(cb[0] + cen(c)[0]) / 2, (cb[1] + cen(c)[1]) / 2];
    if (i === 0) pts.push(mi);
    const din = sub(b, a), dout = sub(c, b);
    if (!eqv(din, dout)) {
      const corner = [cb[0] + .5 * S * (din[0] - dout[0]), cb[1] + .5 * S * (din[1] - dout[1])];
      pts.push([lerp(cb[0], cb[0] + K_P * (corner[0] - cb[0]), mode), lerp(cb[1], cb[1] + K_P * (corner[1] - cb[1]), mode)]);
    } else pts.push(cb);
    pts.push(mo);
  }
  return pts;
}
function arcs(pts) { const a = [0]; for (let i = 1; i < pts.length; i++) a.push(a[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); return a; }
function pointAt(pts, A, s) {
  s = clamp(s, 0, A[A.length - 1]);
  let i = 1; while (i < A.length - 1 && A[i] < s) i++;
  const f = (s - A[i - 1]) / ((A[i] - A[i - 1]) || 1);
  return [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f), Math.atan2(pts[i][1] - pts[i - 1][1], pts[i][0] - pts[i - 1][0])];
}
function partial(pts, A, s) {
  const out = [pts[0]];
  for (let i = 1; i < pts.length && A[i] < s; i++) out.push(pts[i]);
  if (s < A[A.length - 1]) { const p = pointAt(pts, A, s); out.push([p[0], p[1]]); }
  return out;
}
function poly(ctx, pts, close) { ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); if (close) ctx.closePath(); }
const CH = CAMPO.chain;
const TURN_EXTRA = 2 * Math.hypot(.5 * K_P, .5 * (1 + K_P)) - 1;  // ≈ 0.326
const lengthOf = c => cells.length + c.turns * TURN_EXTRA;
const NAIVE = tourPts(CH[0].tour, 0);
// esquinas que el tour por los centros deja sin cubrir
const naiveMissing = (() => {
  const verts = new Set();
  for (const [x, y] of cells) for (const [dx, dy] of [[0, 0], [1, 0], [0, 1], [1, 1]]) verts.add((x + dx) + ',' + (y + dy));
  let n = 0;
  for (const v of verts) {
    const [x, y] = v.split(',').map(Number), px = X0 + x * S, py = Y0 + y * S;
    let best = 1e9;
    for (let i = 1; i < NAIVE.length; i++) {
      const [ax, ay] = NAIVE[i - 1], [bx, by] = NAIVE[i];
      const dx = bx - ax, dy = by - ay, f = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy));
      best = Math.min(best, Math.hypot(ax + f * dx - px, ay + f * dy - py));
    }
    if (best > S / 2 + .5) n++;
  }
  return n;
})();

// ---------- dibujos ----------
function drone(x, y, s, rot, alpha = 1) {
  const c = L.blue;
  c.save(); c.globalAlpha *= alpha; c.translate(x, y); c.rotate(rot + Math.PI / 4); c.scale(s, s);
  c.strokeStyle = c.fillStyle = '#000'; c.lineCap = 'round';
  c.lineWidth = 7; c.beginPath(); c.moveTo(-30, -30); c.lineTo(30, 30); c.moveTo(30, -30); c.lineTo(-30, 30); c.stroke();
  c.beginPath(); c.roundRect(-14, -14, 28, 28, 6); c.fill();
  for (const [a, b] of [[-30, -30], [30, -30], [30, 30], [-30, 30]]) {
    c.lineWidth = 3; c.beginPath(); c.arc(a, b, 19, 0, 7); c.stroke();
    const sp = T * 37 + a * .1 + b * .07;
    c.lineWidth = 4; c.beginPath(); c.moveTo(a + 15 * Math.cos(sp), b + 15 * Math.sin(sp)); c.lineTo(a - 15 * Math.cos(sp), b - 15 * Math.sin(sp)); c.stroke();
  }
  c.restore();
  const p = L.pink; p.save(); p.globalAlpha *= alpha * .9; p.translate(x, y); p.rotate(rot + Math.PI / 4); p.scale(s, s);
  p.fillStyle = '#000'; for (const [a, b] of [[-30, -30], [30, -30], [30, 30], [-30, 30]]) { p.beginPath(); p.arc(a, b, 17, 0, 7); p.fillStyle = halftone(p, .35, 15, 6); p.fill(); }
  p.beginPath(); p.arc(0, 0, 6, 0, 7); p.fillStyle = '#000'; p.fill();
  p.restore();
}
function sprayDisk(x, y, r, alpha) {
  const c = L.yellow; c.save(); c.globalAlpha *= alpha; c.fillStyle = '#000'; c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.restore();
  const b = L.blue; b.save(); b.globalAlpha *= alpha; b.setLineDash([10, 9]); b.lineWidth = 3; b.strokeStyle = '#000'; b.beginPath(); b.arc(x, y, r, 0, 7); b.stroke(); b.restore();
}
// rociado: gotas que salen del dron hacia el borde del círculo y anillos que se abren
function sprayFx(x, y, r, alpha) {
  if (alpha <= 0) return;
  // bajo la nube el pasto se aclara, para que el rociado se lea
  const g = L.green; g.save(); g.globalCompositeOperation = 'destination-out'; g.globalAlpha = alpha * .6;
  g.beginPath(); g.arc(x, y, r, 0, 7); g.fill(); g.restore();
  const p = L.pink; p.save(); p.fillStyle = p.strokeStyle = '#000';
  const h = n => { const s = Math.sin(n * 127.1) * 43758.5453; return s - Math.floor(s); };
  for (let i = 0; i < 120; i++) {
    const f = (T * .8 + h(i)) % 1, a = h(i + 500) * 6.2832 + .3 * f;
    const d = r * (.35 + .7 * h(i + 900)) * eout(f);
    p.globalAlpha = alpha * (1 - f * f);
    p.beginPath(); p.arc(x + d * Math.cos(a), y + d * Math.sin(a), lerp(11, 3, f) * Math.max(.45, r / 180), 0, 7); p.fill();
  }
  for (let k = 0; k < 3; k++) {
    const f = (T * .6 + k / 3) % 1;
    p.globalAlpha = alpha * .7 * (1 - f); p.lineWidth = 6 * (1 - f) + 2;
    p.beginPath(); p.arc(x, y, r * (.2 + .8 * eout(f)), 0, 7); p.stroke();
  }
  p.restore();
}
// titular legible: tinta azul limpia sobre un trazo de marcador amarillo
function headline(s, x, y, size, alpha, mark = 1) {
  const c = L.blue; c.save(); c.font = font(DISPLAY, size); const w = c.measureText(s).width; c.restore();
  if (mark > 0) {
    const yl = L.yellow, x0 = x - w / 2 - 16, ww = (w + 32) * mark;
    yl.save(); yl.globalAlpha = alpha * .95; yl.fillStyle = '#000'; yl.beginPath();
    yl.moveTo(x0, y - size * .34); yl.lineTo(x0 + ww, y - size * .39); yl.lineTo(x0 + ww, y + size * .09); yl.lineTo(x0, y + size * .12);
    yl.fill(); yl.restore();
  }
  txt(L.blue, s, x, y, size, { alpha });
}
// etiqueta: píldora rosa con el texto calado, se ve el papel
function tag(s, x, y, size, alpha) {
  if (alpha <= 0) return;
  const p = L.pink; p.save(); p.font = font(MONO, size); p.letterSpacing = '4px';
  const w = p.measureText(s).width;
  p.globalAlpha = alpha; p.fillStyle = '#000';
  p.beginPath(); p.roundRect(x - w / 2 - 24, y - size * 1.08, w + 44, size * 1.62, size * .81); p.fill();
  p.globalCompositeOperation = 'destination-out'; p.globalAlpha = 1; p.textAlign = 'center';
  p.fillText(s, x + 2, y); p.restore();
}
function grass(path, alpha, level = .5) {
  const g = L.green; g.save(); g.globalAlpha *= alpha; g.fillStyle = halftone(g, level, 45, 9); g.fill(path); g.restore();
}
// pinta en la capa `ink` la zona `fill` que el trazo `pts` (ancho w) no cubre
function uncovered(ink, fill, pts, w, alpha) {
  sctx.globalCompositeOperation = 'source-over'; sctx.clearRect(0, 0, W, H);
  sctx.fillStyle = '#000'; sctx.fill(fill);
  sctx.globalCompositeOperation = 'destination-out';
  sctx.lineWidth = w + 3; sctx.lineJoin = 'round'; sctx.lineCap = 'round';
  poly(sctx, pts); sctx.stroke();
  sctx.globalCompositeOperation = 'source-over';
  const c = L[ink]; c.save(); c.globalAlpha *= alpha; c.drawImage(scratch, 0, 0); c.restore();
}
function strokePts(ink, pts, w, alpha = 1, opt = {}) {
  const c = L[ink]; c.save(); c.globalAlpha *= alpha; c.strokeStyle = '#000'; c.lineWidth = w;
  c.lineJoin = 'round'; c.lineCap = 'round'; if (opt.dash) c.setLineDash(opt.dash); if (opt.clip) c.clip(opt.clip);
  poly(c, pts, opt.close); c.stroke(); c.restore();
}
function regMark(x, y) {
  for (const k of ['blue', 'pink']) {
    const c = L[k]; c.save(); c.globalAlpha = .8; c.strokeStyle = '#000'; c.lineWidth = 2;
    c.beginPath(); c.arc(x, y, 13, 0, 7); c.moveTo(x - 22, y); c.lineTo(x + 22, y); c.moveTo(x, y - 22); c.lineTo(x, y + 22); c.stroke(); c.restore();
  }
}

// ---------- títulos y subtítulos ----------
const TITLES = [
  ['a1', '01 · fumigación', ['¿Cuántos drones', 'necesitas?']],
  ['b1', '01 · el problema', ['El dron rocía', 'un círculo']],
  ['b2', '01 · el problema', ['Cortar el césped']],
  ['c1', '02 · simplificar', ['Cuadritos']],
  ['c2', '02 · simplificar', ['Grafo de', 'cuadrícula']],
  ['c3', '02 · simplificar', ['= problema del', 'viajante']],
  ['d1', '03 · decidir cada giro', ['Los giros', 'cuestan']],
  ['d2', '03 · decidir cada giro', ['Tres piezas']],
  ['e1', '04 · el algoritmo', ['Paso 1:', 'viajante']],
  ['e2', '04 · el algoritmo', ['Paso 2:', 'piezas']],
  ['e3', '04 · el algoritmo', ['Paso 3:', 'ventanas']],
  ['e4', '04 · el algoritmo', ['Menos giros,', 'ruta más corta']],
  ['f1', '05 · ¿cuántos drones?', ['Estirar', 'la ruta']],
  ['f2', '05 · ¿cuántos drones?', ['Partirla por', 'batería']],
  ['f3', '05 · ¿cuántos drones?', ['La cuenta']],
  ['g1', '06 · aplicaciones', ['¿Para qué', 'sirve?']],
  ['g2', '07 · en resumen', ['La receta']],
].map(([k, kick, lines]) => ({ t: st(k) - .15, kick, lines }));

function titles() {
  for (let i = 0; i < TITLES.length; i++) {
    const a = TITLES[i], b = TITLES[i + 1];
    const tin = P(a.t, .45), tout = b ? P(b.t - .25, .25) : 0;
    const al = Math.min(tin, 1 - tout);
    if (al <= 0) continue;
    const sameKick = i > 0 && TITLES[i - 1].kick === a.kick, nextSame = b && b.kick === a.kick;
    const ka = Math.min(sameKick ? 1 : tin, nextSame ? 1 : 1 - tout);
    const dy = (1 - eout(tin)) * 40 - eout(tout) * 30;
    tag(a.kick.toUpperCase(), W / 2, 152, 28, ka);
    a.lines.forEach((s, j) => {
      const size = fitSize(s, 100, 920);
      headline(s, W / 2, 272 + j * 106 + dy, size, al, eout(P(a.t + .1 + j * .12, .45)));
    });
  }
}
function subtitles() {
  TL.lines.forEach((l, i) => {
    const next = TL.lines[i + 1];
    const end = next ? Math.min(l.end + .15, next.start - .3) : l.end + .15;
    const al = life(l.start - .1, end, .1, .2);
    if (al <= 0) return;
    const lines = wrap(l.text, 44, 900);
    const y0 = 1690 - (lines.length - 1) * 30;
    lines.forEach((s, j) => {
      const y = y0 + j * 60;
      const c = L.blue; c.save(); c.font = font(DISPLAY, 44); const w = c.measureText(s).width; c.restore();
      const yl = L.yellow; yl.save(); yl.globalAlpha = al; yl.fillStyle = '#000'; yl.fillRect(W / 2 - w / 2 - 14, y - 40, w + 28, 54); yl.restore();
      txt(L.blue, s, W / 2, y, 44, { alpha: al });
    });
  });
}
function stats(lines, alpha) {
  lines.forEach(([s, ink], j) => txt(L[ink || 'blue'], s, W / 2, 1500 + j * 50, 38, { mono: true, alpha }));
}

// ---------- escenas ----------
const R = rng(5);
const DOTS = []; while (DOTS.length < 520) { const x = X0 + R() * CAMPO.cols * S, y = Y0 + R() * CAMPO.rows * S; if (main.isPointInPath(blob, x, y)) DOTS.push([x, y]); }
const SQUIG = [0, 1, 2].map(k => { const r = rng(40 + k); const pts = []; let x = X0 + 2.5 * S, y = Y0 + 4 * S, a = r() * 6; for (let i = 0; i < 90; i++) { a += (r() - .5) * .7; x += Math.cos(a) * 16; y += Math.sin(a) * 16; if (!main.isPointInPath(blob, x, y)) { a += Math.PI * .8; } pts.push([x, y]); } return pts; });
// barrido del gancho: ida y vuelta por filas
const MOW = (() => { const pts = []; for (let r = 0; r < CAMPO.rows; r++) { const y = Y0 + (r + .5) * S, a = X0 - .2 * S, b = X0 + (CAMPO.cols + .2) * S; if (r % 2) pts.push([b, y], [a, y]); else pts.push([a, y], [b, y]); } return pts; })();
const MOW_A = arcs(MOW);

function sceneField() {
  // contorno real: del inicio hasta que aparecen los cuadritos
  const blobA = life(-1, st('c1') + .8, .01, .7);
  const cellsOn = (x, y) => eout(P(st('c1') + .6 + (x + y) * .06, .35));
  const fieldA = Math.min(life(-1, SC.giros.start, .01, .35), 1) + life(SC.algoritmo.start - .1, st('f1') + 1.2, .35, .6);
  if (blobA > 0) {
    grass(blob, blobA, .55);
    const b = L.blue; b.save(); b.globalAlpha = blobA; b.lineWidth = 5; b.strokeStyle = '#000'; b.stroke(blob); b.restore();
  }
  // gancho: el dron barre por filas
  const flyA = life(st('a1') - .3, st('b1') + .4, .3, .5);
  if (flyA > 0) {
    const s = lerp(0, MOW_A[MOW_A.length - 1] * .62, P(st('a1') - .2, en('a2') - st('a1') + .6));
    const done = partial(MOW, MOW_A, s);
    const y = L.yellow; y.save(); y.globalAlpha = flyA * blobA; y.clip(blob); y.lineWidth = S; y.lineCap = 'round'; y.lineJoin = 'round'; y.strokeStyle = '#000'; poly(y, done); y.stroke(); y.restore();
    const [x, yy, a] = pointAt(MOW, MOW_A, s);
    const hold = P(st('b1'), .6), cx = W / 2, cy = Y0 + 3.6 * S;
    sprayDisk(lerp(x, cx, ease(hold)), lerp(yy, cy, ease(hold)), lerp(S / 2, S * 1.5, ease(hold)), lerp(.55, .8, hold));
    drone(lerp(x, cx, ease(hold)), lerp(yy, cy, ease(hold)), lerp(.8, 1.6, ease(hold)), lerp(a, 0, hold), Math.max(flyA, life(st('b1'), st('b2') + 1.2)));
  }
  // problema: el círculo y su etiqueta
  const diskA = life(st('b1'), st('b2') + 1.2, .3, .5);
  if (diskA > 0 && T > st('b1')) {
    const cx = W / 2, cy = Y0 + 3.6 * S;
    sprayDisk(cx, cy, S * 1.5, diskA * .85);
    sprayFx(cx, cy, S * 1.5, diskA * P(st('b1') + .5, .4));
    drone(cx, cy, 1.6, 0, diskA);
  }
  // infinitos puntos y caminos libres
  const dotsA = life(wordT('b2', 'infinitos') - .2, st('c1') + .4, .2, .4);
  if (dotsA > 0) {
    const n = Math.floor(DOTS.length * eout(P(wordT('b2', 'infinitos') - .2, 1.6)));
    const p = L.pink; p.save(); p.globalAlpha = dotsA; p.fillStyle = '#000';
    for (let i = 0; i < n; i++) { p.beginPath(); p.arc(DOTS[i][0], DOTS[i][1], 6, 0, 7); p.fill(); }
    p.restore();
    stats([['∞ puntos', 'pink']], dotsA * P(wordT('b2', 'infinitos'), .3) * (1 - P(st('c1') + .6, .3)));
    SQUIG.forEach((sq, k) => {
      const t0 = wordT('b2', 'moverse') + k * .3, A = arcs(sq);
      if (T > t0) strokePts('blue', partial(sq, A, A[A.length - 1] * eout(P(t0, 1.2))), 5, dotsA, { dash: [14, 10] });
    });
  }
  // cuadrícula
  const gridA = Math.max(life(st('c1'), SC.giros.start, .2, .35), life(SC.algoritmo.start, st('f1') + 1.2, .35, .6));
  if (gridA > 0) {
    const g = P(st('c1'), .9), b = L.blue;
    b.save(); b.globalAlpha = gridA * .55; b.lineWidth = 2; b.strokeStyle = '#000'; b.beginPath();
    for (let x = 0; x <= CAMPO.cols; x++) { b.moveTo(X0 + x * S, Y0); b.lineTo(X0 + x * S, Y0 + CAMPO.rows * S * ease(g)); }
    for (let y = 0; y <= CAMPO.rows; y++) { b.moveTo(X0, Y0 + y * S); b.lineTo(X0 + CAMPO.cols * S * ease(g), Y0 + y * S); }
    b.stroke(); b.restore();
  }
  // cuadritos
  if (fieldA > 0 && T > st('c1')) {
    const dense = lerp(.6, .3, P(st('c2'), .8));
    const g = L.green; g.save(); g.fillStyle = halftone(g, dense, 45, 9);
    for (const [x, y] of cells) {
      const k = cellsOn(x, y); if (k <= 0) continue;
      const m = S * (1 - back(k)) / 2;
      g.globalAlpha = fieldA; g.fillRect(X0 + x * S + m + 3, Y0 + y * S + m + 3, S - 2 * m - 6, S - 2 * m - 6);
    }
    g.restore();
    const cntA = life(st('c1') + 1.4, st('c2'), .3, .3);
    if (cntA > 0) stats([[cells.length + ' cuadritos']], cntA);
  }
  // nodos y aristas
  const nodeA = life(st('c2'), SC.giros.start, .3, .35);
  if (nodeA > 0) {
    const b = L.blue; b.save(); b.globalAlpha = nodeA; b.fillStyle = b.strokeStyle = '#000'; b.lineWidth = 5; b.lineCap = 'round';
    gridEdges.forEach(([a, c], i) => {
      const k = ease(P(st('c2') + 1.1 + i * .012, .4)); if (k <= 0) return;
      const p = cen(a), q = cen(c); b.beginPath(); b.moveTo(...p); b.lineTo(lerp(p[0], q[0], k), lerp(p[1], q[1], k)); b.stroke();
    });
    cells.forEach(([x, y], i) => { const k = back(P(st('c2') + i * .015, .35)); if (k > 0) { const [a, c] = cen([x, y]); b.beginPath(); b.arc(a, c, 13 * k, 0, 7); b.fill(); } });
    b.restore();
    const sA = life(st('c2') + 1.4, SC.giros.start, .3, .3);
    if (sA > 0) stats([[`${cells.length} nodos · ${gridEdges.length} aristas`]], sA * (1 - P(st('c3'), .3)));
  }
  // el viajante
  const tspA = life(st('c3'), SC.giros.start, .2, .35);
  if (tspA > 0) {
    const A = arcs(NAIVE);
    strokePts('pink', partial(NAIVE, A, A[A.length - 1] * ease(P(st('c3') + .2, 3))), 10, tspA);
    stats([['visitar los ' + cells.length + ' puntos', 'pink']], tspA * P(st('c3') + 1, .4));
  }
  // el algoritmo
  if (T > SC.algoritmo.start - .2 && T < st('f1') + 2) algorithm(fieldA);
}

function algorithm(fieldA) {
  const t1 = st('e1') + .3, fly = Math.max(2.4, en('e1') - t1 - .2);
  const morph = ease(P(st('e2') + .2, 1.2));
  // paso 3: una ventana por mejora, repartidas entre e3 y e4
  const steps = CH.length - 1, t3 = st('e3') + .2, D = (st('e4') - .2 - t3) / steps;
  let k = 0, f = 1;
  for (let i = 1; i <= steps; i++) if (T > t3 + (i - 1) * D + .45 * D) { k = i; f = clamp((T - (t3 + (i - 1) * D + .45 * D)) / (.3 * D)); }
  const cur = CH[k], prev = CH[Math.max(0, k - 1)];
  const ptsNow = k === 0 ? tourPts(CH[0].tour, morph) : tourPts(cur.tour, 1);
  const A = arcs(ptsNow), total = A[A.length - 1];
  const s = total * ease(P(t1, fly));
  const flying = T < t1 + fly + .3;
  const unroll = P(st('f1') + .2, 1.8);

  if (unroll <= 0) {
    // cobertura
    const covered = T < st('e2') ? partial(ptsNow, A, s) : ptsNow;
    const y = L.yellow; y.save(); y.globalAlpha = fieldA * .9; y.clip(fieldPath); y.lineWidth = S; y.lineCap = 'round'; y.lineJoin = 'round'; y.strokeStyle = '#000'; poly(y, covered); y.stroke(); y.restore();
    // esquinas sin cubrir
    const missA = P(t1 + fly - .2, .3) * (1 - P(st('e2') + 1.2, .3));
    if (missA > 0) uncovered('pink', fieldPath, ptsNow, S, fieldA * missA * (.75 + .25 * Math.sin(T * 9)));
    // ventana
    const wA = life(t3 - .1, st('e4') - .1, .3, .3);
    if (wA > 0) {
      const nk = Math.min(steps, k + 1), tt = t3 + (nk - 1) * D;
      const mv = ease(P(tt, .4 * D));
      const wx = k === 0 ? CH[1].window : [lerp(CH[k].window[0], CH[nk].window[0], k < steps ? mv : 0), lerp(CH[k].window[1], CH[nk].window[1], k < steps ? mv : 0)];
      const r = [X0 + wx[0] * S - 6, Y0 + wx[1] * S - 6, CAMPO.window * S + 12, CAMPO.window * S + 12];
      const p = L.pink; p.save(); p.globalAlpha = wA; p.strokeStyle = '#000'; p.lineWidth = 8; p.setLineDash([22, 12]); p.strokeRect(...r); p.restore();
      txt(L.pink, 'ventana', r[0] + r[2] / 2, r[1] - 16, 32, { mono: true, alpha: wA });
    }
    // el tour
    if (k > 0 && f < 1) {
      const w = CH[k].window, clip = new Path2D(); clip.rect(X0 + w[0] * S, Y0 + w[1] * S, CAMPO.window * S, CAMPO.window * S);
      strokePts('blue', tourPts(prev.tour, 1), 7, fieldA * (1 - f), { clip });
      strokePts('blue', ptsNow, 7, fieldA * f, { clip });
      strokePts('blue', ptsNow, 7, fieldA, { clip: outside(w) });
      const fl = L.pink; fl.save(); fl.globalAlpha = (1 - f) * .45; fl.fillStyle = '#000'; fl.fill(clip); fl.restore();
    } else {
      strokePts('blue', T < st('e2') ? partial(ptsNow, A, s) : ptsNow, 7, fieldA);
    }
    if (flying && T > t1 - .3) { const [x, yy, a] = pointAt(ptsNow, A, s); sprayDisk(x, yy, S / 2, .5); drone(x, yy, .75, a); }
    // contadores
    const turns = k === 0 ? CH[0].turns : (f > .5 ? cur.turns : prev.turns);
    const lenNow = k === 0 ? cells.length + CH[0].turns * TURN_EXTRA * morph : cells.length + turns * TURN_EXTRA;
    const sa = life(t1, st('f1'), .3, .3);
    if (T < st('e2')) stats([[`giros = ${turns}`], [`${naiveMissing} esquinas sin cubrir`, 'pink']], sa * P(t1 + fly - .1, .3));
    else if (T < st('e4')) stats([[`giros = ${turns}   longitud ≈ ${lenNow.toFixed(1)}`], ['0 esquinas sin cubrir', 'pink']], sa);
    else {
      const a0 = CH[0], a1 = CH[CH.length - 1];
      stats([[`giros ${a0.turns} → ${a1.turns}`], [`longitud ${lengthOf(a0).toFixed(1)} → ${lengthOf(a1).toFixed(1)}`, 'pink']], sa);
    }
  }
}
function outside(w) {
  const p = new Path2D();
  p.rect(0, 0, W, H);
  p.rect(X0 + w[0] * S + CAMPO.window * S, Y0 + w[1] * S, -CAMPO.window * S, CAMPO.window * S);
  return p;
}

// ---------- giros (una celda grande) ----------
function piece(kind, x, y, s, open) {
  // celda unitaria con entrada abajo; devuelve el camino en pixeles
  const U = (a, b) => [x + a * s, y + b * s];
  if (kind === 'recto') return [U(.5, 1), U(.5, 0)];
  if (kind === 'giro') { const q = lerp(.5, .5 - K_P / 2, open); return [U(.5, 1), U(q, q), U(1, .5)]; }
  return [U(.5, 1), U(.3825, .322), U(.6175, .322), U(.5, 1)];
}
function sceneTurns() {
  const a = life(SC.giros.start - .1, SC.giros.end, .35, .35);
  if (a <= 0) return;
  // d1: un giro por el centro deja una esquina
  const a1 = a * (1 - P(st('d2') - .2, .35));
  if (a1 > 0) {
    const s = 440, x = W / 2 - s / 2, y = Y0 + 70;
    const cell = new Path2D(); cell.rect(x, y, s, s);
    grass(cell, a1, .55);
    const b = L.blue; b.save(); b.globalAlpha = a1; b.lineWidth = 4; b.strokeStyle = '#000'; b.strokeRect(x, y, s, s); b.restore();
    const path = [[x + s / 2, y + s + 30], [x + s / 2, y + s / 2], [x + s + 30, y + s / 2]], A = arcs(path);
    const pr = ease(P(st('d1') + .3, 2)), sNow = A[2] * pr;
    const yl = L.yellow; yl.save(); yl.globalAlpha = a1; yl.clip(cell); yl.lineWidth = s; yl.lineCap = 'round'; yl.lineJoin = 'round'; yl.strokeStyle = '#000'; poly(yl, partial(path, A, sNow)); yl.stroke(); yl.restore();
    strokePts('blue', partial(path, A, sNow), 8, a1);
    const [dx, dy, ang] = pointAt(path, A, sNow);
    if (pr < 1) { sprayDisk(dx, dy, s / 2, .45 * a1); drone(dx, dy, 1.5, ang, a1); }
    const miss = P(st('d1') + 2.2, .3);
    if (miss > 0) {
      uncovered('pink', cell, path, s, a1 * miss * (.75 + .25 * Math.sin(T * 9)));
      txt(L.pink, '¡sin rociar!', x + 60, y - 22, 40, { mono: true, align: 'left', alpha: a1 * miss });
    }
  }
  // d2/d3: las tres piezas
  const a2 = a * P(st('d2') - .1, .3);
  if (a2 > 0) {
    const s = 270, gap = 45, y = Y0 + 160, kinds = ['recto', 'giro', 'vuelta U'];
    const words = ['recto', 'giro', 'vuelta'];
    const open = ease(P(st('d3') + .2, 1.2));
    kinds.forEach((kd, i) => {
      const k = back(P(Math.min(wordT('d2', words[i]) - .15, st('d2') + .5 + i * .45), .4)); if (k <= 0) return;
      const x = W / 2 + (i - 1) * (s + gap) - s / 2;
      const c = L.blue; const cell = new Path2D(); cell.rect(x, y, s, s);
      const al = a2 * clamp(k);
      const sc = lerp(.6, 1, k);
      for (const ink of ORDER) { L[ink].save(); L[ink].translate(x + s / 2, y + s / 2); L[ink].scale(sc, sc); L[ink].translate(-(x + s / 2), -(y + s / 2)); }
      grass(cell, al, .35);
      c.save(); c.globalAlpha = al; c.lineWidth = 4; c.strokeStyle = '#000'; c.strokeRect(x, y, s, s); c.restore();
      const path = piece(kd === 'vuelta U' ? 'u' : kd, x, y, s, kd === 'giro' ? open : 1);
      if (kd === 'giro') {
        if (open < 1) uncovered('pink', cell, path, s, al * (1 - open) * (.75 + .25 * Math.sin(T * 9)));
        const da = al * P(st('d3') + .1, .3);
        if (da > 0) { const b = L.blue; b.save(); b.globalAlpha = da; b.setLineDash([9, 8]); b.lineWidth = 3; b.strokeStyle = '#000'; b.beginPath(); b.arc(x, y, s / 2, 0, Math.PI / 2); b.stroke(); b.restore(); }
      }
      if (kd === 'vuelta U') { const b = L.blue; b.save(); b.globalAlpha = al * .8; b.setLineDash([9, 8]); b.lineWidth = 3; b.strokeStyle = '#000'; b.beginPath(); b.arc(x, y, s / 2, 0, Math.PI / 2); b.stroke(); b.beginPath(); b.arc(x + s, y, s / 2, Math.PI / 2, Math.PI); b.stroke(); b.restore(); }
      strokePts('pink', path, 10, al);
      for (const ink of ORDER) L[ink].restore();
      txt(L.blue, kd, x + s / 2, y + s + 58, 36, { mono: true, alpha: al });
      const lab = ['= 1', '≈ 1.33', '≈ 1.61'][i];
      txt(L.pink, lab, x + s / 2, y + s + 112, 40, { mono: true, alpha: a2 * P(st('d3') + 1.3 + i * .25, .3) });
    });
    const fa = a2 * P(wordT('d3', 'Cada giro'), .4);
    if (fa > 0) {
      headline('cada giro ≈ +⅓', W / 2, Y0 + 720, 84, fa, eout(fa));
      txt(L.blue, 'de cuadrito extra', W / 2, Y0 + 790, 36, { mono: true, alpha: fa });
    }
  }
}

// ---------- drones por batería ----------
const FINAL = tourPts(CH[CH.length - 1].tour, 1);
const UNOPT = tourPts(CH[0].tour, 1);
const BATT = 11.8;   // cuadritos que vuela un dron con una batería (ejemplo)
const BX = 90, BW = W - 180, UNIT = BW / lengthOf(CH[0]);
function resample(pts, n) { const A = arcs(pts), out = []; for (let i = 0; i <= n; i++) { const s = A[A.length - 1] * i / n; const p = pointAt(pts, A, s); out.push([p[0], p[1], s]); } return out; }
const FIN_R = resample(FINAL, 700), UNO_R = resample(UNOPT, 700);
function bar(samples, by, e, ink, alpha) {
  const pts = samples.map(([x, y, s]) => [lerp(x, BX + s / S * UNIT, e), lerp(y, by, e)]);
  strokePts(ink, pts, lerp(7, 16, e), alpha);
}
function segments(L0, by, t0, alpha, label) {
  const n = Math.ceil(L0 / BATT);
  for (let i = 0; i < n; i++) {
    const k = back(P(t0 + i * .35, .4)); if (k <= 0) continue;
    const x0 = BX + i * BATT * UNIT, x1 = BX + Math.min(L0, (i + 1) * BATT) * UNIT;
    const y = L.yellow; y.save(); y.globalAlpha = alpha * clamp(k); y.fillStyle = '#000'; y.fillRect(x0 + 3, by - 22, x1 - x0 - 6, 44); y.restore();
    const p = L.pink; p.save(); p.globalAlpha = alpha * clamp(k); p.fillStyle = '#000'; p.fillRect(x0 - 3, by - 40, 6, 80); p.restore();
    drone(x0 + Math.min(BATT * UNIT / 2, (x1 - x0) / 2 + 40), by - 92, .62 * clamp(k), 0, alpha);
  }
  const k = P(t0 + n * .35 + .1, .4);
  txt(L.pink, `${n} drones`, W - BX, by + 96, 52, { align: 'right', alpha: alpha * k });
  if (label) txt(L.blue, label, BX, by + 96, 30, { mono: true, align: 'left', alpha: alpha * k });
  return n;
}
function sceneDrones() {
  const a = life(SC.drones.start - .1, SC.drones.end, .2, .4);
  if (a <= 0) return;
  const e = ease(P(st('f1') + .2, 1.8));
  const by = 760;
  bar(FIN_R, by, e, 'blue', a);
  const la = P(st('f1') + 1.8, .4);
  txt(L.blue, `L = ${lengthOf(CH[CH.length - 1]).toFixed(1)} cuadritos`, BX, by - 160, 40, { mono: true, align: 'left', alpha: a * la * (1 - P(st('f2'), .3)) });
  // la batería
  const ba = a * life(st('f2') - .1, st('f3') + .2, .3, .4);
  if (ba > 0) {
    const x = BX, y = by + 190, w = BATT * UNIT;
    const b = L.blue; b.save(); b.globalAlpha = ba; b.lineWidth = 5; b.strokeStyle = b.fillStyle = '#000';
    b.strokeRect(x, y, w, 64); b.fillRect(x + w, y + 18, 14, 28); b.restore();
    const yl = L.yellow; yl.save(); yl.globalAlpha = ba; yl.fillStyle = '#000'; yl.fillRect(x + 8, y + 8, (w - 16) * eout(P(st('f2') + .1, .8)), 48); yl.restore();
    txt(L.blue, `1 batería ≈ ${BATT} cuadritos`, x + w + 40, y + 46, 32, { mono: true, align: 'left', alpha: ba });
  }
  if (T > wordT('f2', 'Partimos') - .2) segments(lengthOf(CH[CH.length - 1]), by, wordT('f2', 'Partimos'), a, 'ruta optimizada');
  // la cuenta y el dron que se ahorra
  const fa = a * P(st('f3') + .1, .4);
  if (fa > 0) {
    headline('drones = ⌈ L ÷ batería ⌉', W / 2, 1060, 58, fa, eout(fa));
  }
  const t2 = wordT('f3', 'como');
  if (T > t2 - .2) {
    const e2 = ease(P(t2 - .2, 1));
    bar(UNO_R, 1250, 1, 'blue', a * e2);
    segments(lengthOf(CH[0]), 1250, t2 + .5, a, `sin optimizar · L = ${lengthOf(CH[0]).toFixed(1)}`);
    const k = back(P(t2 + 2.6, .5));
    if (k > 0) {
      const p = L.pink; p.save(); p.globalAlpha = a; p.translate(W / 2, 1460); p.rotate(-.08); p.scale(k, k);
      p.lineWidth = 7; p.strokeStyle = '#000'; p.strokeRect(-190, -62, 380, 108); p.restore();
      L.pink.save(); L.pink.translate(W / 2, 1460); L.pink.rotate(-.08); L.pink.scale(k, k);
      txt(L.pink, '−1 dron', 0, 22, 76, { alpha: a }); L.pink.restore();
    }
  }
}

// ---------- cierre ----------
function icon(kind, x, y, s, al) {
  const b = L.blue, p = L.pink, g = L.green, yl = L.yellow;
  for (const c of [b, p, g, yl]) { c.save(); c.globalAlpha *= al; c.translate(x, y); c.scale(s, s); c.fillStyle = c.strokeStyle = '#000'; c.lineCap = 'round'; }
  if (kind === 0) {
    for (let i = 0; i < 9; i++) { yl.beginPath(); yl.arc(-40 + i * 10, 55 + (i % 3) * 14, 6, 0, 7); yl.fill(); }
    g.fillStyle = halftone(g, .6, 45, 8); g.fillRect(-80, 70, 160, 40);
  } else if (kind === 1) {
    b.lineWidth = 7; b.beginPath(); b.roundRect(-70, -40, 140, 95, 14); b.stroke(); b.fillRect(-28, -58, 56, 20);
    p.beginPath(); p.arc(0, 8, 30, 0, 7); p.fill(); b.lineWidth = 6; b.beginPath(); b.arc(0, 8, 34, 0, 7); b.stroke();
  } else if (kind === 2) {
    p.lineWidth = 34; for (let i = 0; i < 4; i++) { p.beginPath(); p.arc(0, 0, 55, i * Math.PI / 2 + .1, i * Math.PI / 2 + Math.PI / 4); p.stroke(); }
    b.lineWidth = 5; b.beginPath(); b.arc(0, 0, 72, 0, 7); b.stroke(); b.beginPath(); b.arc(0, 0, 38, 0, 7); b.stroke();
  } else {
    g.fillStyle = halftone(g, .6, 45, 8); g.fillRect(-85, 30, 170, 45);
    b.lineWidth = 6; b.beginPath(); b.roundRect(-60, -40, 120, 70, 20); b.stroke();
    b.beginPath(); b.arc(-38, 36, 16, 0, 7); b.arc(38, 36, 16, 0, 7); b.fill();
    p.beginPath(); p.arc(0, -5, 16, 0, 7); p.fill();
  }
  for (const c of [b, p, g, yl]) c.restore();
  if (kind === 0) drone(x, y - 20 * s, 1.1 * s, 0, al);
}
function sceneEnd() {
  const a = life(SC.cierre.start - .1, TL.total + 1, .3, .3);
  if (a <= 0) return;
  // g1: cuatro tarjetas
  const join = ease(P(st('g2'), .9)), ca = a * (1 - P(st('g2') + .55, .35));
  const TX = W / 2, TY = Y0 + 200;  // dónde queda la miniatura del campo
  const cards = [['fumigar', 'cultivos', 'fumigar'], ['inspeccionar', 'con cámaras', 'inspeccionar'], ['buscar', 'personas', 'buscar'], ['robots', 'que podan', 'robots']];
  if (ca > 0) cards.forEach(([l1, l2, w], i) => {
    const k = back(P(wordT('g1', w) - .2, .45)); if (k <= 0) return;
    const x0 = W / 2 + (i % 2 ? 1 : -1) * 235, y0 = Y0 + 230 + Math.floor(i / 2) * 470;
    const x = lerp(x0, TX, join), y = lerp(y0, TY, join), rot = [-.04, .03, .025, -.035][i] * (1 + 4 * join);
    const sc = k * lerp(1, .35, join);
    for (const c of Object.values(L)) { c.save(); c.translate(x, y); c.rotate(rot); c.scale(sc, sc); c.translate(-x, -y); }
    const p = L.pink; p.save(); p.globalAlpha = ca; p.fillStyle = halftone(p, .35, 15, 8); p.fillRect(x - 190 + 14, y - 200 + 14, 380, 400); p.restore();
    const b = L.blue; b.save(); b.globalAlpha = ca; b.lineWidth = 5; b.strokeStyle = '#000'; b.strokeRect(x - 190, y - 200, 380, 400); b.restore();
    icon(i, x, y - 40, 1, ca);
    txt(L.blue, l1, x, y + 120, 44, { alpha: ca });
    txt(L.blue, l2, x, y + 165, 30, { mono: true, alpha: ca });
    for (const c of Object.values(L)) c.restore();
  });
  // g2: de las tarjetas sale el campo con su ruta: la misma receta para todos
  const ma = a * P(st('g2') + .5, .35);
  if (ma > 0) {
    const k = .4 * back(P(st('g2') + .5, .5)), cx = X0 + CAMPO.cols * S / 2, cy = Y0 + CAMPO.rows * S / 2;
    for (const c of Object.values(L)) { c.save(); c.translate(TX, TY); c.scale(k, k); c.translate(-cx, -cy); }
    const y = L.yellow; y.save(); y.globalAlpha = ma; y.fillStyle = '#000'; y.fill(fieldPath); y.restore();
    const b = L.blue; b.save(); b.globalAlpha = ma; b.lineWidth = 8; b.strokeStyle = '#000'; b.stroke(fieldPath); b.restore();
    strokePts('blue', FINAL, 14, ma);
    for (const c of Object.values(L)) c.restore();
  }
  // g3: resumen y créditos
  const ra = a * P(st('g3') - .2, .3);
  if (ra > 0) {
    const items = [['Simplificar', 'el terreno → grafo', 'Simplificar'], ['Decidir', 'cada giro → piezas', 'Decidir'], ['Cubrir todo', 'con el camino más corto', 'Cubrir']];
    items.forEach(([h, s2, w], i) => {
      const k = eout(P(wordT('g3', w) - .15, .45)); if (k <= 0) return;
      const y = Y0 + 520 + i * 190, x = 150 + (1 - k) * 60;
      const yl = L.yellow; yl.save(); yl.globalAlpha = ra * k; yl.fillStyle = '#000'; yl.beginPath(); yl.arc(x + 40, y - 20, 50, 0, 7); yl.fill(); yl.restore();
      const p = L.pink; p.save(); p.globalAlpha = ra * k; p.lineWidth = 6; p.strokeStyle = '#000'; p.beginPath(); p.arc(x + 40, y - 20, 50, 0, 7); p.stroke(); p.restore();
      txt(L.blue, String(i + 1), x + 40, y + 2, 64, { alpha: ra * k });
      txt(L.blue, h, x + 130, y, 70, { align: 'left', alpha: ra * k });
      txt(L.blue, s2, x + 130, y + 52, 32, { mono: true, align: 'left', alpha: ra * k });
    });
    const cr = ra * P(en('g3') + .2, .6);
    if (cr > 0) {
      const lines = ['Basado en: S. P. Fekete, D. Krupke, M. Perk,', 'C. Rieck y C. Scheffer (2023).', 'The Lawn Mowing Problem:', 'From Algebra to Algorithms. ESA 2023.'];
      lines.forEach((s, i) => txt(L.blue, s, W / 2, Y0 + 1045 + i * 36, 26, { mono: true, alpha: cr }));
    }
  }
}

// ---------- cuadro ----------
function render(t) {
  T = t;
  for (const k of ORDER) { L[k].setTransform(1, 0, 0, 1, 0, 0); L[k].globalAlpha = 1; L[k].clearRect(0, 0, W, H); }
  regMark(60, 60); regMark(W - 60, 60); regMark(60, H - 60); regMark(W - 60, H - 60);
  sceneField();
  sceneTurns();
  sceneDrones();
  sceneEnd();
  titles();
  subtitles();
  composite();
}

// efectos de sonido: [segundo, nombre, volumen]
function sfxCues() {
  const c = [];
  for (const [n, s] of Object.entries(SC)) if (n !== 'gancho') c.push([s.start - .2, 'whoosh', .5]);
  c.push([st('a1') - .2, 'hum:' + (en('a2') - st('a1') + 1).toFixed(2), .35]);
  c.push([wordT('b2', 'infinitos'), 'tick', .4], [wordT('b2', 'infinitos') + .4, 'tick', .4], [wordT('b2', 'infinitos') + .8, 'tick', .4]);
  for (let i = 0; i < 8; i++) c.push([st('c1') + .6 + i * .12, 'click', .5]);
  c.push([st('c2') + .2, 'pop', .6], [st('c2') + 1.2, 'pop', .5]);
  c.push([st('d1') + 2.2, 'error', .5]);
  ['recto', 'giro', 'vuelta'].forEach((w, i) => c.push([Math.min(wordT('d2', w) - .15, st('d2') + .5 + i * .45), 'pop', .6]));
  c.push([st('d3') + 1.3, 'ding', .45]);
  const t1 = st('e1') + .3, fly = Math.max(2.4, en('e1') - t1 - .2);
  c.push([t1, 'hum:' + fly.toFixed(2), .3], [t1 + fly - .2, 'error', .45], [st('e2') + 1.4, 'success', .5]);
  const steps = CH.length - 1, t3 = st('e3') + .2, D = (st('e4') - .2 - t3) / steps;
  for (let i = 1; i <= steps; i++) c.push([t3 + (i - 1) * D + .45 * D, 'tick', .6]);
  c.push([st('e4'), 'ding', .5]);
  const segT = wordT('f2', 'Partimos');
  for (let i = 0; i < Math.ceil(lengthOf(CH[CH.length - 1]) / BATT); i++) c.push([segT + i * .35, 'pop', .5]);
  const t2 = wordT('f3', 'como');
  for (let i = 0; i < Math.ceil(lengthOf(CH[0]) / BATT); i++) c.push([t2 + .5 + i * .35, 'pop', .45]);
  c.push([t2 + 2.6, 'boom', .6]);
  ['fumigar', 'inspeccionar', 'buscar', 'robots'].forEach(w => c.push([wordT('g1', w) - .2, 'pop', .55]));
  c.push([st('g2'), 'whoosh', .4], [st('g2') + .5, 'pop', .6]);
  ['Simplificar', 'Decidir', 'Cubrir'].forEach(w => c.push([wordT('g3', w) - .15, 'click', .6]));
  c.push([en('g3') + .2, 'success', .5]);
  return c.filter(x => x[0] >= 0).map(([t, n, v]) => ({ t: +t.toFixed(3), name: n, vol: v }));
}

window.render = render;
window.sfxCues = sfxCues;
window.READY = document.fonts.ready.then(() => Promise.all([document.fonts.load(font(DISPLAY, 40)), document.fonts.load(font(MONO, 40))]));

// ---------- vista previa en el navegador ----------
if (!new URLSearchParams(location.search).has('render')) {
  const audio = document.getElementById('audio'), seek = document.getElementById('seek'), time = document.getElementById('time'), play = document.getElementById('play');
  seek.max = TL.total;
  let playing = false, t0 = 0, base = 0;
  const now = () => playing ? (audio.readyState > 1 && !audio.paused ? audio.currentTime : base + (performance.now() - t0) / 1000) : base;
  play.onclick = () => {
    playing = !playing; play.textContent = playing ? '⏸' : '▶';
    if (playing) { t0 = performance.now(); audio.currentTime = base; audio.play().catch(() => {}); } else { base = now(); audio.pause(); }
  };
  seek.oninput = () => { base = +seek.value; t0 = performance.now(); audio.currentTime = base; };
  const tick = () => {
    let t = now(); if (t > TL.total) { t = 0; base = 0; t0 = performance.now(); audio.currentTime = 0; }
    if (playing) { seek.value = t; }
    render(t); time.textContent = t.toFixed(1) + ' s';
    requestAnimationFrame(tick);
  };
  window.READY.then(tick);
} else document.body.classList.add('render');
