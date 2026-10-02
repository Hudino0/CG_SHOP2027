"""Geometría del video "A Closer Cut": el esquema primal-dual en miniatura.

Todo es numpy puro (la venv de Manim no tiene matplotlib ni solver de CETSP):

- `coverage`: qué puntos de una rejilla fina del polígono quedan a distancia
  <= r del tour.
- `cetsp`: un heurístico del Close-Enough TSP. Orden por 2-opt sobre los
  centros y, para ese orden, cada punto de contacto se mueve al sitio del disco
  que acorta más el tour. Los discos que ya toca el tour pierden su punto.
  El artículo resuelve el CETSP de forma exacta (branch-and-bound + SOCP);
  aquí basta un heurístico porque sólo ilustra el método.
- `primal_dual`: las iteraciones del algoritmo A.1 del artículo. Devuelve, por
  iteración, el conjunto de testigos, el tour de cota inferior, su cobertura y
  el tour factible (cota superior) con sus extensiones.

El resultado se guarda en build/closer_geo.json para que las escenas no lo
recalculen.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
CACHE = ROOT / "build" / "closer_geo.json"

# Polígono de ejemplo (estilo srpg-octa: lados a 0° y 45°) y radio del cortador.
POLY = [(0, 0), (5, 0), (6, 1), (10, 1), (10, 4), (8, 6), (5, 6), (5, 4), (3, 4), (2, 5), (0, 5)]
R = 0.8
STEP = 0.05


# ---------------------------------------------------------------- básicos

def inside(pts: np.ndarray, poly=POLY) -> np.ndarray:
    x, y = pts[:, 0], pts[:, 1]
    res = np.zeros(len(pts), bool)
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if y1 == y2:
            continue
        c = ((y1 > y) != (y2 > y)) & (x < x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        res ^= c
    return res


def grid(poly=POLY, step=STEP):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    gx = np.arange(min(xs) + step / 2, max(xs), step)
    gy = np.arange(min(ys) + step / 2, max(ys), step)
    X, Y = np.meshgrid(gx, gy)
    pts = np.c_[X.ravel(), Y.ravel()]
    mask = inside(pts).reshape(X.shape)
    return gx, gy, mask


GX, GY, MASK = grid()
PTS = np.c_[np.meshgrid(GX, GY)[0].ravel(), np.meshgrid(GX, GY)[1].ravel()]


def seg_dist(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = b - a
    L = d @ d
    if L == 0:
        return np.linalg.norm(p - a, axis=1)
    t = np.clip(((p - a) @ d) / L, 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * d), axis=1)


def tour_dist(p: np.ndarray, tour: np.ndarray, closed=True) -> np.ndarray:
    tour = np.asarray(tour, float)
    if len(tour) == 1:
        return np.linalg.norm(p - tour[0], axis=1)
    best = np.full(len(p), np.inf)
    m = len(tour) if closed else len(tour) - 1
    for i in range(m):
        best = np.minimum(best, seg_dist(p, tour[i], tour[(i + 1) % len(tour)]))
    return best


def coverage(tour, r=R) -> np.ndarray:
    """Máscara (forma de MASK) de los puntos del polígono cubiertos."""
    d = tour_dist(PTS, tour).reshape(MASK.shape)
    return MASK & (d <= r)


def length(tour) -> float:
    t = np.asarray(tour, float)
    if len(t) < 2:
        return 0.0
    return float(np.linalg.norm(np.roll(t, -1, 0) - t, axis=1).sum())


def components(mask: np.ndarray) -> list[np.ndarray]:
    """Componentes 4-conexas de una máscara, como listas de índices (fila, col)."""
    seen = np.zeros_like(mask)
    out = []
    H, W = mask.shape
    for start in zip(*np.nonzero(mask)):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        comp = []
        while stack:
            i, j = stack.pop()
            comp.append((i, j))
            for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if 0 <= a < H and 0 <= b < W and mask[a, b] and not seen[a, b]:
                    seen[a, b] = True
                    stack.append((a, b))
        out.append(np.array(comp))
    return out


def cell_point(ij) -> np.ndarray:
    return np.array([GX[ij[1]], GY[ij[0]]])


def dispersion(cands: np.ndarray, k: int, rng, first=None) -> np.ndarray:
    """Selección max-min greedy de k puntos de `cands`."""
    if len(cands) <= k:
        return cands
    idx = [rng.integers(len(cands)) if first is None else first]
    d = np.linalg.norm(cands - cands[idx[0]], axis=1)
    while len(idx) < k:
        j = int(d.argmax())
        idx.append(j)
        d = np.minimum(d, np.linalg.norm(cands - cands[j], axis=1))
    return cands[idx]


# ---------------------------------------------------------------- CETSP

def _best_in_disk(c, r, a, b):
    """Punto del disco (c, r) que minimiza |p-a| + |p-b|."""
    if r == 0:
        return c.copy()
    d = b - a
    L = d @ d
    t = 0.0 if L == 0 else float(np.clip((c - a) @ d / L, 0, 1))
    q = a + t * d
    if np.linalg.norm(q - c) <= r:
        return q
    th = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    for width in (np.pi / 36, np.pi / 360):
        P = c + r * np.c_[np.cos(th), np.sin(th)]
        f = np.linalg.norm(P - a, axis=1) + np.linalg.norm(P - b, axis=1)
        k = int(f.argmin())
        th = th[k] + np.linspace(-width, width, 21)
    P = c + r * np.c_[np.cos(th), np.sin(th)]
    f = np.linalg.norm(P - a, axis=1) + np.linalg.norm(P - b, axis=1)
    return P[int(f.argmin())]


def _two_opt(P: np.ndarray, order: list[int]) -> list[int]:
    n = len(order)
    if n < 4:
        return order
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n - (i == 0)):
                a, b = P[order[i]], P[order[i + 1]]
                c, d = P[order[j]], P[order[(j + 1) % n]]
                delta = (np.linalg.norm(a - c) + np.linalg.norm(b - d)
                         - np.linalg.norm(a - b) - np.linalg.norm(c - d))
                if delta < -1e-9:
                    order[i + 1:j + 1] = order[i + 1:j + 1][::-1]
                    improved = True
    return order


def _insert(C: np.ndarray, order: list[int], new) -> list[int]:
    """Inserción más barata de los índices `new` en el orden."""
    order = list(order)
    for j in new:
        if len(order) < 2:
            order.append(j)
            continue
        best, at = np.inf, 0
        for k in range(len(order)):
            a, b = C[order[k]], C[order[(k + 1) % len(order)]]
            d = np.linalg.norm(a - C[j]) + np.linalg.norm(C[j] - b) - np.linalg.norm(a - b)
            if d < best:
                best, at = d, k + 1
        order.insert(at, j)
    return order


def cetsp(centers, radii, init_order=None, rounds=30, restarts=6, rng=None):
    """Tour cerrado que toca todos los discos. Devuelve (puntos del tour, orden).

    Prueba varios órdenes iniciales (inserción desde `init_order` y aleatorios)
    y se queda con el tour más corto.
    """
    C = np.asarray(centers, float)
    n = len(C)
    if n == 1:
        return C.copy(), [0]
    rng = rng or np.random.default_rng(0)
    starts = []
    if init_order is not None:
        rest = [j for j in range(n) if j not in set(init_order)]
        starts.append(_insert(C, init_order, rest))
    for _ in range(restarts):
        perm = list(rng.permutation(n))
        starts.append(_insert(C, perm[:3], perm[3:]))
    best = None
    for order in starts:
        tour, keep = _cetsp_from(C, np.asarray(radii, float), _two_opt(C, order), rounds)
        if best is None or length(tour) < length(best[0]):
            best = (tour, keep)
    return best


def _cetsp_from(C, rad, order, rounds):
    n = len(C)
    P = C.copy()
    for rnd in range(rounds):
        for pos in range(n):
            i = order[pos]
            a, b = P[order[pos - 1]], P[order[(pos + 1) % n]]
            P[i] = _best_in_disk(C[i], rad[i], a, b)
        if rnd % 5 == 4:
            order = _two_opt(P, order)
    # los discos que el tour ya toca sin su propio punto no necesitan vértice
    keep = list(order)
    for i in list(order):
        if rad[i] == 0 or len(keep) <= 2:
            continue
        others = [k for k in keep if k != i]
        if tour_dist(C[i][None], P[others])[0] <= rad[i] + 1e-9:
            keep = others
    tour = P[keep]
    return tour, order


# ---------------------------------------------------------------- primal-dual

def boundary_candidates(step=0.25):
    out = []
    n = len(POLY)
    for i in range(n):
        a, b = np.array(POLY[i], float), np.array(POLY[(i + 1) % n], float)
        m = max(1, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / m for k in range(m)]
    return np.array(out)


def splice(tour: np.ndarray, sub: np.ndarray, at: np.ndarray) -> np.ndarray:
    """Inserta el subtour cerrado `sub` (que empieza en `at`) en el tour."""
    tour = np.asarray(tour, float)
    # segmento del tour más cercano a `at`
    best, k = np.inf, 0
    for i in range(len(tour)):
        d = seg_dist(at[None], tour[i], tour[(i + 1) % len(tour)])[0]
        if d < best:
            best, k = d, i
    s0 = int(np.argmin(np.linalg.norm(sub - at, axis=1)))
    sub = np.roll(sub, -s0, 0)
    return np.vstack([tour[:k + 1], at[None], sub[1:], at[None], tour[k + 1:]])


def uncovered_regions(cov, min_cells=6):
    return [c for c in components(MASK & ~cov) if len(c) >= min_cells]


def upper_bound(tour, rng, per_region=8, max_loops=6):
    """Extiende el tour hasta cubrir el polígono (sección 4.4 del artículo)."""
    tour = np.asarray(tour, float)
    stages = []
    for _ in range(max_loops):
        regs = uncovered_regions(coverage(tour), min_cells=1)
        if not regs:
            break
        ext = []
        for comp in regs:
            cells = np.array([cell_point(ij) for ij in comp])
            W = dispersion(cells, min(per_region, len(cells)), rng)
            d = tour_dist(cells, tour)
            # punto del tour más cercano a la región
            far = cells[int(d.argmin())]
            best, at = np.inf, tour[0]
            for i in range(len(tour)):
                a, b = tour[i], tour[(i + 1) % len(tour)]
                dd = b - a
                L = dd @ dd
                t = 0 if L == 0 else np.clip((far - a) @ dd / L, 0, 1)
                q = a + t * dd
                if np.linalg.norm(q - far) < best:
                    best, at = np.linalg.norm(q - far), q
            sub, _ = cetsp(np.vstack([at[None], W]), [0] + [R * 0.98] * len(W), restarts=2, rng=rng)
            ext.append(sub)
            tour = splice(tour, sub, at)
        stages.append([e.tolist() for e in ext])
    return tour, stages


def primal_dual(iters=5, seed=7):
    rng = np.random.default_rng(seed)
    hull_cands = boundary_candidates()
    W = dispersion(hull_cands, 15, rng, first=0)
    out = []
    order = None
    for it in range(iters):
        tour, order = cetsp(W, [R] * len(W), init_order=order, rng=rng)
        cov = coverage(tour)
        frac = cov.sum() / MASK.sum()
        regs = uncovered_regions(cov)
        ub, stages = upper_bound(tour, rng)
        out.append({
            "witnesses": W.tolist(),
            "tour": tour.tolist(),
            "length": length(tour),
            "coverage": float(frac),
            "ub_tour": ub.tolist(),
            "ub_length": length(ub),
            "ub_stages": stages,
        })
        # 10 testigos nuevos repartidos entre las regiones sin cubrir
        if not regs:
            break
        sizes = np.array([len(c) for c in regs], float)
        share = rng.multinomial(10, sizes / sizes.sum())
        new = []
        for comp, k in zip(regs, share):
            if k == 0:
                continue
            cells = np.array([cell_point(ij) for ij in comp])
            new.append(dispersion(cells, k, rng))
        W = np.vstack([W, *new])
        out[-1]["new"] = np.vstack(new).tolist()
    return out


def load():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    data = {"poly": POLY, "r": R, "iters": primal_dual()}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data))
    return data


if __name__ == "__main__":
    import time
    t0 = time.time()
    if CACHE.exists():
        CACHE.unlink()
    d = load()
    for i, it in enumerate(d["iters"]):
        print(f"it {i}: |W|={len(it['witnesses'])} LB tour {it['length']:.2f} "
              f"cov {it['coverage']:.0%}  UB {it['ub_length']:.2f}  ext {[len(s) for s in it['ub_stages']]}")
    print(f"{time.time() - t0:.1f} s")


# ---------------------------------------------------------------- para las escenas

_FINE: dict[float, tuple] = {}


def fine_masks(tour, step=0.025, r=R):
    """(dentro, cubierto) en una rejilla más fina, sólo para dibujar."""
    if step not in _FINE:
        gx, gy, mask = grid(step=step)
        X, Y = np.meshgrid(gx, gy)
        _FINE[step] = (np.c_[X.ravel(), Y.ravel()], mask)
    pts, mask = _FINE[step]
    sel = mask.ravel()
    d = np.full(len(pts), np.inf)
    d[sel] = tour_dist(pts[sel], tour)
    return mask, mask & (d.reshape(mask.shape) <= r)
