"""Prepara los datos del campo para la animación: build/campo.json.

El campo es un poliominó. Se buscan todos sus ciclos hamiltonianos (tours del
viajante por los centros de los cuadritos), y se arma una cadena de mejoras
locales: cada paso cambia el tour sólo dentro de una ventana de 3x3 y quita
giros. Es la búsqueda en vecindarios grandes de Fekete et al., en pequeño.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "build" / "campo.json"

SHAPE = """
...###
.#####
######
######
####..
####..
#####.
#####.
"""
WINDOW = 3


def cells():
    rows = [r for r in SHAPE.strip("\n").splitlines()]
    return [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "#"]


def neighbors(c, s):
    x, y = c
    return [n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if n in s]


def all_cycles(cs, cap=400000):
    s = set(cs)
    start = cs[0]
    n = len(cs)
    found = []
    path = [start]
    seen = {start}

    def dfs():
        if len(found) >= cap:
            return
        cur = path[-1]
        if len(path) == n:
            if start in neighbors(cur, s):
                found.append(tuple(path))
            return
        for nb in neighbors(cur, s):
            if nb in seen:
                continue
            # poda: ninguna celda libre puede quedar con menos de 2 vecinos libres
            path.append(nb)
            seen.add(nb)
            ok = True
            for q in neighbors(nb, s) + neighbors(cur, s):
                if q in seen:
                    continue
                free = sum(1 for r in neighbors(q, s) if r not in seen or r in (nb, start))
                if free < 2:
                    ok = False
                    break
            if ok:
                dfs()
            path.pop()
            seen.discard(nb)

    dfs()
    # cada ciclo aparece en los dos sentidos: quedarse con uno
    uniq = {}
    for c in found:
        uniq.setdefault(frozenset(edges(c)), c)
    return list(uniq.values())


def edges(cyc):
    return {frozenset((cyc[i], cyc[(i + 1) % len(cyc)])) for i in range(len(cyc))}


def turns(cyc):
    n = len(cyc)
    t = 0
    for i in range(n):
        a, b, c = cyc[i - 1], cyc[i], cyc[(i + 1) % n]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            t += 1
    return t


def window_of(diff):
    """La ventana WINDOW x WINDOW que contiene todas las aristas cambiadas, o None."""
    pts = [p for e in diff for p in e]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    if x1 - x0 >= WINDOW or y1 - y0 >= WINDOW:
        return None
    return [min(x0, x1 - WINDOW + 1), min(y0, y1 - WINDOW + 1)]


def main():
    cs = cells()
    cyc = all_cycles(cs)
    print(len(cs), "cuadritos,", len(cyc), "tours")
    info = [(turns(c), edges(c), c) for c in cyc]
    tmin = min(i[0] for i in info)
    tmax = max(i[0] for i in info)
    print("giros: min", tmin, "max", tmax)

    # cadena de mejoras: desde el peor tour, cada paso cambia sólo una ventana
    # y quita la menor cantidad posible de giros (para que se vean varios pasos)
    best_chain = []
    for t0, e0, c0 in sorted(info, key=lambda i: -i[0])[:60]:
        chain = [(t0, e0, c0, None)]
        while True:
            t, e, _, _ = chain[-1]
            moves = []
            for t2, e2, c2 in info:
                if t2 >= t:
                    continue
                w = window_of(e ^ e2)
                if w:
                    moves.append((t - t2, t2, e2, c2, w))
            if not moves:
                break
            moves.sort(key=lambda m: m[0])
            _, t2, e2, c2, w = moves[0]
            chain.append((t2, e2, c2, w))
        if chain[-1][0] == tmin and len(chain) > len(best_chain):
            best_chain = chain
    print("cadena:", [c[0] for c in best_chain], "ventanas:", [c[3] for c in best_chain])

    data = {
        "cells": cs,
        "cols": max(x for x, _ in cs) + 1,
        "rows": max(y for _, y in cs) + 1,
        "window": WINDOW,
        "chain": [{"tour": list(c), "turns": t, "window": w} for t, _, c, w in best_chain],
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data))
    print("listo:", OUT)


if __name__ == "__main__":
    main()
