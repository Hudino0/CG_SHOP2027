"""El problema de cortar el césped — Fekete, Krupke, Perk, Rieck, Scheffer (2023).

Video al estilo 3Blue1Brown con Manim Community. Ejecutar con build.py.
"""
import json
from pathlib import Path

import numpy as np
from manim import *

import sfx as SFX

ROOT = Path(__file__).parent
AUD = ROOT / "build" / "audio"
SFXD = ROOT / "build" / "sfx"
DURS = json.loads((AUD / "durations.json").read_text())

BG = "#14171c"
LAWN = "#2e6b35"
LAWN_DARK = "#24552a"
MOWED = "#9ad67f"
EDGE = "#cfe8c4"
CUT = "#58C4DD"      # azul 3b1b
ACCENT = "#FFD166"   # amarillo
BAD = "#FF5A5F"
GREY = "#8a8f98"
FONT = "Segoe UI"

TURN = 0.32566                                   # τ: coste extra de un giro
Q_TURN = np.array([2 ** .5 / 4, 1 - 2 ** .5 / 4])  # vértice de la pieza de giro
Q_U = (np.array([.383, .678]), np.array([.617, .678]))

# capas
Z_LAWN, Z_TRAIL, Z_PATCH, Z_TRAIL2, Z_MASK, Z_EDGE, Z_PATH, Z_CUTTER, Z_LABEL = range(9)

config.background_color = BG

# Tours hamiltonianos del poliominó de ejemplo (calculados por búsqueda exhaustiva)
CELLS = {(x, y) for y, xs in {0: range(0, 4), 1: range(0, 6), 2: range(0, 6),
                               3: range(2, 6), 4: range(2, 6)}.items() for x in xs}
TOUR_MIN = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (3, 3), (4, 3), (4, 2), (4, 1), (5, 1), (5, 2),
            (5, 3), (5, 4), (4, 4), (3, 4), (2, 4), (2, 3), (2, 2), (2, 1), (1, 1), (1, 2), (0, 2), (0, 1)]
TOUR_MAX = [(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (4, 1), (5, 1), (5, 2), (4, 2), (4, 3), (5, 3), (5, 4),
            (4, 4), (3, 4), (2, 4), (2, 3), (3, 3), (3, 2), (2, 2), (2, 1), (1, 1), (1, 2), (0, 2), (0, 1)]


def T(text, size=32, color=WHITE, **kw):
    return Text(text, font=FONT, font_size=size, color=color, **kw).set_z_index(Z_LABEL)


def M(tex, size=40, color=WHITE, **kw):
    return MathTex(tex, font_size=size, color=color, **kw).set_z_index(Z_LABEL)


class Frame:
    """Coordenadas del problema -> coordenadas de pantalla."""

    def __init__(self, s, origin):
        self.s = s
        self.o = np.array([*origin, 0.0])[:3]

    def __call__(self, x, y=None):
        if y is None:
            x, y = x
        return self.o + self.s * np.array([x, y, 0.0])


# ---------------------------------------------------------------- geometría

def quarter_path(delta):
    """Camino óptimo en un cuarto del cuadrado 2x2 para un delta dado (Lema 4)."""
    th = np.linspace(-np.pi / 2, 0, 3001)
    circ = np.c_[.5 * np.cos(th), 1 + .5 * np.sin(th)]
    a, b = np.array([.5, delta]), np.array([1, .5 + delta])
    s = np.linalg.norm(circ - a, axis=1) + np.linalg.norm(circ - b, axis=1)
    i = s.argmin()
    return a, circ[i], b, delta + s[i]


def tour_points(cells, puzzle):
    """Puntos del tour: punto medio, centro (o vértice de la pieza), punto medio, ..."""
    n = len(cells)
    c = [np.array(p, float) + .5 for p in cells]
    mid = [(c[i] + c[(i + 1) % n]) / 2 for i in range(n)]
    pts, turns = [mid[-1]], []
    for i in range(n):
        e, x = mid[i - 1], mid[i]
        d1, d2 = c[i] - e, x - c[i]
        is_turn = abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-9
        if is_turn:
            corner = c[i] + d1 - d2
            turns.append((c[i], corner))
            pts.append(c[i] + (1 - 1 / 2 ** .5) * (corner - c[i]) if puzzle else c[i])
        else:
            pts.append(c[i])
        pts.append(x)
    return pts, turns


def polyline_len(pts):
    return sum(np.linalg.norm(np.array(b) - np.array(a)) for a, b in zip(pts, pts[1:]))


def in_poly(p, poly):
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


# ---------------------------------------------------------------- escena base

class VScene(Scene):
    def now(self):
        return self.renderer.time

    def voice(self, key, offset=0.0):
        """Empieza la frase `key`; devuelve el instante en que termina."""
        self.add_sound(str(AUD / f"{key}.wav"), time_offset=offset)
        return self.now() + offset + DURS[key]

    def until(self, t_end, pad=0.35):
        rest = t_end + pad - self.now()
        if rest > 1 / 30:
            self.wait(rest)

    def fx(self, name, gain=0.0, offset=0.0):
        self.add_sound(str(SFXD / f"{name}.wav"), time_offset=offset, gain=gain)

    def cutter(self, r, square=False):
        if square:
            body = Square(2 * r, color=CUT, stroke_width=3, fill_color=CUT, fill_opacity=.25)
        else:
            body = Circle(r, color=CUT, stroke_width=3, fill_color=CUT, fill_opacity=.25)
        dot = Dot(radius=.05, color=WHITE)
        return VGroup(body, dot).set_z_index(Z_CUTTER)

    def new_trail(self, z=Z_TRAIL):
        tr = VGroup().set_z_index(z)
        self.add(tr)
        return tr

    def mow(self, cutter, pts, run_time, r, trail, spacing=None, square=False, color=MOWED,
            sound=True, rate_func=linear, extra=()):
        """Mueve el cortador por la poligonal `pts` estampando su huella en `trail`."""
        pts = [np.array(p, float) for p in pts]
        seg = [np.linalg.norm(b - a) for a, b in zip(pts, pts[1:])]
        cum = np.concatenate([[0], np.cumsum(seg)])
        total = cum[-1]
        spacing = spacing or r / 6
        samples = []
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            n = max(1, int(np.ceil(seg[i] / spacing)))
            samples += [(cum[i] + seg[i] * k / n, a + (b - a) * k / n) for k in range(n)]
        samples.append((total, pts[-1]))

        def at(s):
            i = min(int(np.searchsorted(cum, s, side="right")) - 1, len(seg) - 1)
            f = 0 if seg[i] == 0 else (s - cum[i]) / seg[i]
            return pts[i] + (pts[i + 1] - pts[i]) * min(max(f, 0), 1)

        z = trail.z_index
        tr = ValueTracker(0)
        idx = [0]

        def stamp(p):
            m = (Square(2 * r) if square else Circle(r, num_components=24))
            return m.set_stroke(width=0).set_fill(color, 1).move_to(p).set_z_index(z)

        def upd_trail(m):
            s = tr.get_value()
            while idx[0] < len(samples) and samples[idx[0]][0] <= s + 1e-9:
                m.add(stamp(samples[idx[0]][1]))
                idx[0] += 1

        cutter.move_to(pts[0])
        cutter.add_updater(lambda m: m.move_to(at(tr.get_value())))
        trail.add_updater(upd_trail)
        if sound:
            self.add_sound(str(SFX.mower(run_time)), gain=-9)
        self.play(tr.animate.set_value(total), *extra, run_time=run_time, rate_func=rate_func)
        upd_trail(trail)
        cutter.clear_updaters()
        trail.clear_updaters()

    def clear_all(self, run_time=.8, sound=True):
        if sound:
            self.fx("whoosh", -4)
        mobs = [m for m in self.mobjects]
        if mobs:
            self.play(*[FadeOut(m) for m in mobs], run_time=run_time)
        self.remove(*self.mobjects)


# ================================================================ 1. El problema

class S1Problema(VScene):
    def construct(self):
        F = Frame(.78, (-3.12, -2.05))
        poly = [(0, 0), (8, 0), (8, 3), (6, 4.8), (2.5, 4.8), (0, 3)]
        lawn = Polygon(*[F(p) for p in poly], stroke_width=0, fill_color=LAWN, fill_opacity=1).set_z_index(Z_LAWN)
        edge = Polygon(*[F(p) for p in poly], color=EDGE, stroke_width=4).set_z_index(Z_EDGE)
        rng = np.random.default_rng(3)
        blades = VGroup()
        while len(blades) < 170:
            p = rng.uniform([0, 0], [8, 4.8])
            if in_poly(p, poly):
                a = rng.uniform(-.4, .4)
                blades.add(Line(F(p), F(p) + .13 * np.array([np.sin(a), np.cos(a), 0]),
                                color=LAWN_DARK, stroke_width=2.5))
        blades.set_z_index(Z_LAWN)
        box = Rectangle(width=8 * F.s + 3, height=4.8 * F.s + 3).move_to(F(4, 2.4))
        mask = Difference(box, lawn.copy()).set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)

        t = self.voice("n1_1")
        self.play(DrawBorderThenFill(lawn), Create(edge), run_time=2)
        self.play(LaggedStart(*[FadeIn(b) for b in blades], lag_ratio=.01), run_time=1)
        self.add(mask)
        self.until(t)

        # el cortador
        t = self.voice("n1_2")
        r = .5 * F.s
        cut = self.cutter(r).move_to(F(.5, .5))
        self.fx("pop")
        self.play(GrowFromCenter(cut), run_time=.6)
        diam = Line(cut.get_left(), cut.get_right(), color=ACCENT, stroke_width=3).set_z_index(Z_LABEL)
        lab = M("1", 36, ACCENT).next_to(cut, UP, buff=.12)
        self.play(Create(diam), FadeIn(lab), run_time=.6)
        self.wait(.8)
        self.play(FadeOut(diam), FadeOut(lab), run_time=.4)
        self.until(t)  # que "n1_2" termine antes de que empiece "n1_3"

        def top(x):
            return 3 + 1.8 * x / 2.5 if x < 2.5 else (4.8 if x <= 6 else 4.8 - 1.8 * (x - 6) / 2)

        pts = []
        for k in range(8):
            x = .5 + k
            y1 = top(x) - .42
            pts += [(x, .5), (x, y1)] if k % 2 == 0 else [(x, y1), (x, .5)]
        pts.append((.5, .5))
        trail = self.new_trail()
        q_end = self.voice("n1_3", offset=0.4)
        question = T("¿Cuál es el recorrido cerrado más corto?", 34).to_edge(UP, buff=.3)
        self.mow(cut, [F(p) for p in pts], 8.5, r, trail,
                 extra=[Succession(Wait(.6), FadeIn(question, shift=DOWN * .2, run_time=1))])
        self.until(q_end, .2)

        # distancia 1/2
        t = self.voice("n1_4")
        path = VMobject(color=CUT, stroke_width=3).set_points_as_corners([F(p) for p in pts]).set_z_index(Z_PATH)
        self.play(FadeOut(cut), Create(path), run_time=1.5)
        p = F(3.1, 2.05)
        near = F(3.5, 2.05)
        pdot = Dot(p, color=ACCENT).set_z_index(Z_LABEL)
        seg = DashedLine(p, near, color=ACCENT).set_z_index(Z_LABEL)
        half = M(r"\le \tfrac12", 34, ACCENT).next_to(seg, UP, buff=.08).shift(LEFT * .25)
        self.fx("pop")
        self.play(FadeIn(pdot, scale=2), run_time=.4)
        self.play(Create(seg), Write(half), run_time=.8)
        formula = M(r"\text{tour } T \text{ m\'as corto con } \operatorname{dist}(p, T) \le \tfrac12 \;\; \forall p \in P",
                    38).to_edge(DOWN, buff=.25)
        self.play(FadeIn(formula, shift=UP * .2), run_time=.8)
        self.until(t)

        # TSP vs LMP
        t = self.voice("n1_5")
        lmp = VGroup(lawn, blades, trail, mask, edge, path, pdot, seg, half)
        self.play(FadeOut(formula), FadeOut(question), lmp.animate.scale(.62).to_edge(LEFT, buff=.5).shift(DOWN * .3),
                  run_time=1.2)
        cities = [np.array([x, y, 0]) for x, y in [(1.4, 1.3), (3.2, 1.9), (5.4, 1.1), (6, -.7), (4.3, -1.8), (2.1, -1.4), (3.3, -.2)]]
        cdots = VGroup(*[Dot(c, radius=.09, color=ACCENT) for c in cities]).set_z_index(Z_LABEL)
        order = [0, 1, 2, 3, 4, 6, 5, 0]
        ctour = VMobject(color=CUT, stroke_width=4).set_points_as_corners([cities[i] for i in order])
        tsp_lab = T("Viajante (TSP)", 30).next_to(cdots, UP, buff=.5).set_x(3.7)
        self.play(LaggedStart(*[FadeIn(d, scale=2) for d in cdots], lag_ratio=.12), run_time=.9)
        for k in range(3):
            self.fx("click", offset=k * .25)
        self.play(Create(ctour), FadeIn(tsp_lab), run_time=1.5)
        self.until(t)

        t = self.voice("n1_6")
        lmp_lab = T("Cortar el césped (LMP)", 30).next_to(lmp, UP, buff=.35)
        self.play(FadeIn(lmp_lab), run_time=.6)
        # una rejilla de "ciudades", sólo dentro del jardín ya escalado
        lb = lawn.get_corner(DL)
        pl = [v[:2] for v in lawn.get_vertices()]
        grid = [lb + np.array([(i + .5) * lawn.width / 34, (j + .5) * lawn.height / 22, 0])
                for i in range(34) for j in range(22)]
        dots = VGroup(*[Dot(p, radius=.028, color=ACCENT) for p in grid if in_poly(p[:2], pl)]).set_z_index(Z_LABEL)
        self.fx("pop", -3)
        self.play(LaggedStart(*[FadeIn(d) for d in dots], lag_ratio=.002), run_time=2)
        inf = M(r"\infty \text{ ciudades}", 40, ACCENT).next_to(lmp, DOWN, buff=.3)
        self.play(Write(inf), run_time=.8)
        self.until(t)

        t = self.voice("n1_7")
        np_hard = T("NP-difícil", 44, BAD).move_to(RIGHT * 3.7 + DOWN * 2.6)
        self.fx("boom", -6)
        self.play(FadeIn(np_hard, scale=1.3), run_time=.7)
        years = T("1993 → 2023: sin soluciones exactas", 26, GREY).next_to(np_hard, DOWN, buff=.2)
        self.play(FadeIn(years), run_time=.6)
        self.until(t)

        # título del artículo
        t = self.voice("n1_8")
        self.clear_all(.8)
        title = T("The Lawn Mowing Problem:", 52).shift(UP * 1.2)
        sub = T("From Algebra to Algorithms", 52, ACCENT).next_to(title, DOWN, buff=.25)
        authors = T("Sándor P. Fekete · Dominik Krupke · Michael Perk · Christian Rieck · Christian Scheffer",
                    22, GREY).next_to(sub, DOWN, buff=.6)
        ref = T("ESA 2023 · arXiv:2307.01092", 22, GREY).next_to(authors, DOWN, buff=.2)
        self.play(Write(title), run_time=1.2)
        self.play(Write(sub), run_time=1.2)
        self.play(FadeIn(authors, shift=UP * .2), FadeIn(ref, shift=UP * .2), run_time=1)
        self.fx("ding", -6)
        self.until(t, .8)
        self.clear_all()


# ================================================================ 2. La mala noticia

class S2Algebra(VScene):
    def construct(self):
        F = Frame(2.1, (-5.3, -.4))       # cuadrado [0,2]x[-1,1]
        s = F.s
        head = T("La mala noticia", 40, BAD).to_edge(UP, buff=.3)
        sq = Polygon(F(0, -1), F(2, -1), F(2, 1), F(0, 1), stroke_width=0, fill_color=LAWN, fill_opacity=1).set_z_index(Z_LAWN)
        edge = Polygon(F(0, -1), F(2, -1), F(2, 1), F(0, 1), color=EDGE, stroke_width=4).set_z_index(Z_EDGE)
        dim = M(r"2 \times 2", 40).next_to(edge, DOWN, buff=.2)
        ref_disk = Circle(.5 * s, color=CUT, fill_color=CUT, fill_opacity=.25).next_to(edge, RIGHT, buff=.6).shift(DOWN * .6)
        ref_lab = M(r"\varnothing = 1", 32, CUT).next_to(ref_disk, DOWN, buff=.15)

        t = self.voice("n2_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.6)
        self.play(DrawBorderThenFill(sq), Create(edge), run_time=1.5)
        self.play(Write(dim), FadeIn(ref_disk), FadeIn(ref_lab), run_time=1)
        self.until(t)

        # esquinas
        t = self.voice("n2_2")
        corners = [(0, 1), (2, 1), (2, -1), (0, -1)]
        starts = [-PI / 2, PI, PI / 2, 0]
        arcs = VGroup(*[Arc(.5 * s, st, PI / 2, arc_center=F(c), color=ACCENT, stroke_width=4)
                        for c, st in zip(corners, starts)]).set_z_index(Z_PATH)
        cdots = VGroup(*[Dot(F(c), color=ACCENT, radius=.07) for c in corners]).set_z_index(Z_LABEL)
        self.play(LaggedStart(*[FadeIn(d, scale=2) for d in cdots], lag_ratio=.15), run_time=.8)
        self.fx("pop")
        self.play(LaggedStart(*[Create(a) for a in arcs], lag_ratio=.15), run_time=1.2)
        demo = self.cutter(.5 * s).move_to(F(.6, .3))
        self.play(FadeIn(demo), run_time=.3)
        self.play(demo.animate.move_to(F(.5 * np.cos(-PI / 4), 1 + .5 * np.sin(-PI / 4))), run_time=1)
        self.play(Flash(cdots[0], color=ACCENT), run_time=.6)
        self.until(t)

        t = self.voice("n2_3")
        center_dot = Dot(F(1, 0), color=ACCENT, radius=.07).set_z_index(Z_LABEL)
        center_c = DashedVMobject(Circle(.5 * s, color=ACCENT).move_to(F(1, 0)), num_dashes=30).set_z_index(Z_PATH)
        self.play(FadeIn(center_dot, scale=2), run_time=.4)
        self.play(Create(center_c), demo.animate.move_to(F(1.3, .2)), run_time=1.2)
        self.play(Flash(center_dot, color=ACCENT), run_time=.6)
        self.play(FadeOut(demo), run_time=.4)
        self.until(t)

        # un cuarto
        t = self.voice("n2_4")
        shade = VGroup(*[Polygon(F(a, b), F(a + 1, b), F(a + 1, b + 1), F(a, b + 1), stroke_width=0,
                                 fill_color=BG, fill_opacity=.6).set_z_index(Z_MASK)
                         for a, b in [(1, 0), (1, -1), (0, -1)]])
        s0 = Polygon(F(0, 0), F(1, 0), F(1, 1), F(0, 1), color=WHITE, stroke_width=3).set_z_index(Z_EDGE)
        self.play(FadeIn(shade), Create(s0), FadeOut(center_c), run_time=1)
        delta = ValueTracker(0.1679)

        def path_mob():
            a, q, b, _ = quarter_path(delta.get_value())
            return VMobject(color=CUT, stroke_width=5).set_points_as_corners(
                [F(.5, 0), F(a), F(q), F(b)]).set_z_index(Z_PATH)

        a, q, b, L = quarter_path(.1679)
        ps = Dot(F(.5, 0), color=WHITE).set_z_index(Z_LABEL)
        ps_l = M("p_s", 30).next_to(ps, DOWN, buff=.1)
        seg1 = Line(F(.5, 0), F(a), color=CUT, stroke_width=5).set_z_index(Z_PATH)
        br = BraceBetweenPoints(F(.5, 0), F(a), LEFT, buff=.05).set_z_index(Z_LABEL)
        br_l = M(r"\delta", 32, ACCENT).next_to(br, LEFT, buff=.08)
        self.play(FadeIn(ps), Write(ps_l), run_time=.6)
        self.play(Create(seg1), run_time=1.2)
        self.play(GrowFromCenter(br), Write(br_l), run_time=.8)
        self.until(t, .1)

        t = self.voice("n2_5")
        seg2 = VMobject(color=CUT, stroke_width=5).set_points_as_corners([F(a), F(q), F(b)]).set_z_index(Z_PATH)
        self.play(Create(seg2), run_time=2)
        qd = Dot(F(q), color=ACCENT).set_z_index(Z_LABEL)
        ptd = Dot(F(b), color=WHITE).set_z_index(Z_LABEL)
        q_l = M("q", 30, ACCENT).next_to(qd, DR, buff=.05)
        pt_l = M("p_t", 30).next_to(ptd, RIGHT, buff=.1)
        self.play(FadeIn(qd), FadeIn(ptd), Write(q_l), Write(pt_l), run_time=.6)
        self.until(t)

        # delta variable + elipse + gráfica
        t = self.voice("n2_6")
        path = always_redraw(path_mob)
        self.remove(seg1, seg2)
        self.add(path)
        br_g = always_redraw(lambda: VGroup(
            BraceBetweenPoints(F(.5, 0), F(.5, max(delta.get_value(), .02)), LEFT, buff=.05),
            M(r"\delta", 32, ACCENT)).arrange(LEFT, buff=.08).next_to(F(.5, delta.get_value() / 2), LEFT, buff=.05)
                             .set_z_index(Z_LABEL))
        dots = always_redraw(lambda: VGroup(
            Dot(F(quarter_path(delta.get_value())[1]), color=ACCENT),
            Dot(F(quarter_path(delta.get_value())[2]), color=WHITE)).set_z_index(Z_LABEL))
        self.remove(br, br_l, qd, ptd, q_l, pt_l)
        self.add(br_g, dots)

        def ellipse():
            a, q, b, L = quarter_path(delta.get_value())
            c = L - delta.get_value()
            f = np.linalg.norm(b - a) / 2
            A = c / 2
            B = np.sqrt(max(A * A - f * f, 1e-6))
            ang = np.arctan2(b[1] - a[1], b[0] - a[0])
            return Ellipse(2 * A * s, 2 * B * s, color=ACCENT, stroke_width=2.5, stroke_opacity=.8) \
                .rotate(ang).move_to(F((a + b) / 2)).set_z_index(Z_PATH)

        ell = always_redraw(ellipse)
        ax = Axes(x_range=[0, .45, .1], y_range=[1.3, 1.37, .02], x_length=5, y_length=3.2,
                  axis_config={"color": GREY, "include_ticks": True}, tips=False).move_to(RIGHT * 3.6 + DOWN * .1)
        xl = M(r"\delta", 32).next_to(ax.x_axis, DOWN, buff=.15)
        yl = M(r"L(\delta)", 32).next_to(ax.y_axis, UP, buff=.15)
        xs = VGroup(*[M(f"{v:.1f}", 22, GREY).next_to(ax.c2p(v, 1.3), DOWN, buff=.1) for v in [0, .1, .2, .3, .4]])
        ys = VGroup(*[M(f"{v:.2f}", 22, GREY).next_to(ax.c2p(0, v), LEFT, buff=.1) for v in [1.30, 1.32, 1.34, 1.36]])
        ds = np.linspace(0, .45, 80)
        curve = VMobject(color=CUT, stroke_width=4).set_points_smoothly([ax.c2p(d, quarter_path(d)[3]) for d in ds])
        gdot = always_redraw(lambda: Dot(ax.c2p(delta.get_value(), quarter_path(delta.get_value())[3]), color=ACCENT,
                                         radius=.09).set_z_index(Z_LABEL))
        self.play(FadeOut(head), FadeOut(ref_disk), FadeOut(ref_lab), Create(ax), FadeIn(xl), FadeIn(yl), FadeIn(xs),
                  FadeIn(ys), run_time=1)
        self.play(Create(curve), FadeIn(gdot), run_time=1.2)
        self.play(delta.animate.set_value(.02), run_time=1.6)
        self.play(delta.animate.set_value(.42), run_time=2.4)
        self.add(ell)
        self.play(FadeIn(ell), run_time=.4)
        self.play(delta.animate.set_value(.1679), run_time=2.2)
        self.until(t)

        t = self.voice("n2_7")
        vline = DashedLine(ax.c2p(.1679, 1.3), ax.c2p(.1679, L), color=ACCENT).set_z_index(Z_LABEL)
        val = M(r"\delta \approx 0.1679", 34, ACCENT).next_to(ax, UP, buff=.35).shift(LEFT * .9)
        lval = M(r"L_{S_0} \approx 1.309", 34).next_to(val, RIGHT, buff=.6)
        self.fx("ding", -6)
        self.play(Create(vline), Write(val), run_time=1)
        self.play(Write(lval), run_time=.8)
        self.wait(.6)
        # tour completo con reflexiones
        self.remove(ell)
        fixed = path_mob()
        self.remove(path)
        self.add(fixed)
        self.play(FadeOut(shade), FadeOut(s0), FadeOut(br_g), FadeOut(ps), FadeOut(ps_l), FadeOut(dots),
                  FadeOut(VGroup(ax, xl, yl, xs, ys, curve, vline, gdot)), run_time=.8)
        self.remove(gdot, dots, br_g)
        R = [lambda p: (2 - p[0], p[1]), lambda p: (2 - p[0], -p[1]), lambda p: (p[0], -p[1])]
        full = [(.5, 0), tuple(a), tuple(q), tuple(b), R[0](q), R[0](a), (1.5, 0), R[1](a), R[1](q), R[1](b),
                R[2](q), R[2](a), (.5, 0)]
        others = VGroup(*[VMobject(color=CUT, stroke_width=5).set_points_as_corners(
            [F(f((.5, 0))), F(f(a)), F(f(q)), F(f(b))]) for f in R]).set_z_index(Z_PATH)
        self.play(*[TransformFromCopy(fixed, o) for o in others], run_time=1.2)
        cut = self.cutter(.5 * s)
        trail = self.new_trail()
        sq_mask = Difference(Rectangle(width=2 * s + 3, height=2 * s + 3).move_to(F(1, 0)), sq.copy()).set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)
        self.add(sq_mask)
        self.play(FadeIn(cut), run_time=.3)
        total = M(r"L = 4\,L_{S_0} \approx 5.235", 40).move_to(RIGHT * 3.4 + DOWN * .4)
        self.mow(cut, [F(p) for p in full], 4.2, .5 * s, trail, spacing=.05)
        self.fx("success", -6)
        self.play(Write(total), FadeOut(cut), run_time=1)
        self.until(t, .2)

        # el polinomio
        t = self.voice("n2_8")
        self.remove(sq_mask)
        square_grp = VGroup(sq, edge, trail, fixed, others, arcs, cdots, center_dot, dim)
        self.fx("whoosh", -6)
        self.play(FadeOut(square_grp), FadeOut(total), val.animate.move_to(UP * 3.1).scale(1.2),
                  FadeOut(lval), run_time=1)
        lines = [
            r"f_\delta(x) = 589\,824x^{16} - 7\,077\,888x^{15} + 41\,189\,376x^{14} - 154\,386\,432x^{13}",
            r"+\,416\,788\,480x^{12} - 857\,112\,576x^{11} + 1\,383\,417\,856x^{10} - 1\,779\,354\,624x^{9}",
            r"+\,1\,834\,437\,632x^{8} - 1\,514\,108\,928x^{7} + 992\,782\,336x^{6} - 509\,312\,064x^{5}",
            r"+\,199\,354\,208x^{4} - 57\,160\,752x^{3} + 11\,200\,088x^{2} - 1\,313\,928x + 67\,417",
        ]
        poly = VGroup(*[M(l, 30) for l in lines]).arrange(DOWN, aligned_edge=RIGHT, buff=.18).move_to(UP * 1.2)
        poly[0].align_to(poly, LEFT)
        self.fx("boom", -4)
        self.play(LaggedStart(*[Write(l) for l in poly], lag_ratio=.35), run_time=3.2)
        deg = SurroundingRectangle(poly[0][0][12:15], color=ACCENT, buff=.06)
        self.play(Create(deg), run_time=.6)
        self.until(t)

        # Galois
        t = self.voice("n2_9")
        self.play(FadeOut(deg), poly.animate.scale(.72).move_to(UP * 1.9), run_time=.8)
        rows = VGroup()
        u = .34
        for prime, degs, col in [(23, [16], CUT), (47, [1, 2, 13], ACCENT), (59, [1, 15], MOWED)]:
            lab = M(rf"\bmod {prime}", 34).set_width(1.5)
            blocks = VGroup()
            for d in degs:
                rct = Rectangle(width=d * u, height=.45, color=col, fill_color=col, fill_opacity=.35, stroke_width=2)
                num = M(str(d), 26).move_to(rct)
                blocks.add(VGroup(rct, num))
            blocks.arrange(RIGHT, buff=.06)
            rows.add(VGroup(lab, blocks).arrange(RIGHT, buff=.4))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=.25).move_to(DOWN * .9 + LEFT * 1.4)
        for k, row in enumerate(rows):
            self.fx("click", offset=.1)
            self.play(FadeIn(row[0]), LaggedStart(*[GrowFromEdge(b, LEFT) for b in row[1]], lag_ratio=.3),
                      run_time=1.1)
        arrow = Arrow(rows.get_right() + RIGHT * .1, rows.get_right() + RIGHT * 1.3, color=WHITE)
        gal = M(r"\mathrm{Gal}(f_\delta) = S_{16}", 44, ACCENT).next_to(arrow, RIGHT, buff=.2)
        self.play(GrowArrow(arrow), Write(gal), run_time=1.2)
        self.fx("ding", -6)
        self.until(t)

        t = self.voice("n2_10")
        self.play(FadeOut(rows), FadeOut(arrow), gal.animate.move_to(UP * .2), run_time=.9)
        nsolv = T("no es resoluble", 34, BAD).next_to(gal, DOWN, buff=.3)
        self.play(FadeIn(nsolv, shift=UP * .2), run_time=.7)
        formula = M(r"\delta \;=\; \frac{\,a + \sqrt[3]{b - \sqrt{c}}\,}{d + \sqrt[5]{e}} \;\;?", 44).move_to(DOWN * 1.9 + LEFT * 2.8)
        quint = M(r"x^5 - x - 1 = 0", 40, GREY).move_to(DOWN * 1.9 + RIGHT * 3)
        quint_l = T("Abel–Ruffini (1824)", 24, GREY).next_to(quint, DOWN, buff=.2)
        self.play(Write(formula), run_time=1.4)
        cross = Cross(formula, stroke_color=BAD, stroke_width=8)
        self.fx("error", -2)
        self.play(Create(cross), run_time=.6)
        self.play(FadeIn(quint), FadeIn(quint_l), run_time=.8)
        self.until(t)

        t = self.voice("n2_11")
        self.play(*[FadeOut(m) for m in [poly, val, nsolv, formula, cross, quint, quint_l, gal]], run_time=.8)
        concl = T("Algebraicamente difícil", 54, BAD)
        box = SurroundingRectangle(concl, color=BAD, buff=.35)
        sub = T("ni siquiera para un cuadrado 2×2 existe una fórmula exacta", 28, GREY).next_to(box, DOWN, buff=.35)
        self.fx("boom", -4)
        self.play(Write(concl), Create(box), run_time=1.3)
        self.play(FadeIn(sub), run_time=.8)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 3. Píxeles y giros

class S3Pixeles(VScene):
    def construct(self):
        F = Frame(1.0, (-3, -2.9))
        head = T("La buena idea", 40, MOWED).to_edge(UP, buff=.3)

        def cell(x, y, f=F, **kw):
            return Polygon(f(x, y), f(x + 1, y), f(x + 1, y + 1), f(x, y + 1), **kw)

        cells = VGroup(*[cell(x, y, stroke_color=LAWN_DARK, stroke_width=2, fill_color=LAWN, fill_opacity=1)
                         for (x, y) in sorted(CELLS, key=lambda c: (c[1], c[0]))]).set_z_index(Z_LAWN)
        blob = VMobject(color=EDGE, stroke_width=4).set_points_smoothly(
            [F(p) for p in [(.3, .2), (3.6, -.1), (4.2, .9), (5.9, 1.2), (5.8, 4.7), (2.2, 4.8), (2.4, 3.1), (.1, 2.8), (.3, .2)]])

        t = self.voice("n3_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.6)
        self.play(Create(blob), run_time=1.5)
        for k in range(6):
            self.fx("tick", offset=k * .12)
        self.play(LaggedStart(*[FadeIn(c, scale=.6) for c in cells], lag_ratio=.05), blob.animate.set_stroke(opacity=.35),
                  run_time=2)
        self.play(FadeOut(blob), run_time=.5)
        lab = T("poliominó", 32).next_to(cells, RIGHT, buff=.6).shift(UP * .8)
        px = cells[2]
        px_lab = T("píxel", 30, ACCENT).next_to(cells, RIGHT, buff=.6).shift(DOWN * 1.4)
        arr = Arrow(px_lab.get_left(), px.get_center(), color=ACCENT, buff=.15)
        self.play(FadeIn(lab), run_time=.5)
        self.play(px.animate.set_fill(ACCENT, .6), FadeIn(px_lab), GrowArrow(arr), run_time=.8)
        self.until(t)

        # cortadora cuadrada = TSP en la cuadrícula
        t = self.voice("n3_2")
        self.play(px.animate.set_fill(LAWN, 1), FadeOut(px_lab), FadeOut(arr), FadeOut(lab), run_time=.5)
        centers = VGroup(*[Dot(F(x + .5, y + .5), radius=.06, color=WHITE) for (x, y) in CELLS]).set_z_index(Z_LABEL)
        edges = VGroup(*[Line(F(x + .5, y + .5), F(x + 1.5, y + .5), color=GREY, stroke_width=1.5)
                         for (x, y) in CELLS if (x + 1, y) in CELLS] +
                       [Line(F(x + .5, y + .5), F(x + .5, y + 1.5), color=GREY, stroke_width=1.5)
                        for (x, y) in CELLS if (x, y + 1) in CELLS]).set_z_index(Z_EDGE)
        self.play(FadeIn(centers), Create(edges), run_time=1)
        cut = self.cutter(.5, square=True).move_to(F(.5, .5))
        self.play(FadeIn(cut), run_time=.3)
        trail = self.new_trail()
        tour = [F(x + .5, y + .5) for (x, y) in TOUR_MIN + TOUR_MIN[:1]]
        tsp_lab = T("= viajante (TSP)\nen la cuadrícula", 28).next_to(cells, RIGHT, buff=.4)
        self.mow(cut, tour, 4.5, .5, trail, square=True, spacing=.08,
                 extra=[Succession(Wait(1.5), FadeIn(tsp_lab, run_time=1))])
        self.until(t)

        # zoom: un píxel en recta
        t = self.voice("n3_3")
        self.clear_all(.6)
        s = 2.6
        A = Frame(s, (-5.1, -1.6))
        B = Frame(s, (1.4, -1.6))
        pa = cell(0, 0, A, stroke_width=0, fill_color=LAWN, fill_opacity=1).set_z_index(Z_LAWN)
        pa_e = cell(0, 0, A, color=EDGE, stroke_width=4).set_z_index(Z_EDGE)
        pb = cell(0, 0, B, stroke_width=0, fill_color=LAWN, fill_opacity=1).set_z_index(Z_LAWN)
        pb_e = cell(0, 0, B, color=EDGE, stroke_width=4).set_z_index(Z_EDGE)
        box = Rectangle(width=14.5, height=8.5)
        mask = Difference(box, Union(pa.copy(), pb.copy())).set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)
        self.add(mask)
        self.play(FadeIn(pa), Create(pa_e), run_time=.6)
        ca = self.cutter(.5 * s).move_to(A(.5, -.2))
        tra = self.new_trail()
        self.play(FadeIn(ca), run_time=.3)
        pth_a = VMobject(color=CUT, stroke_width=4).set_points_as_corners([A(.5, -.2), A(.5, 1.2)]).set_z_index(Z_PATH)
        self.mow(ca, [A(.5, -.2), A(.5, 1.2)], 2.2, .5 * s, tra, extra=[Create(pth_a)])
        ok = T("✓", 60, MOWED).next_to(pa_e, UP, buff=.25)
        self.fx("ding", -8)
        self.play(FadeOut(ca), FadeIn(ok, scale=1.5), run_time=.5)
        self.until(t)

        # un giro en el centro
        t = self.voice("n3_4")
        self.play(FadeIn(pb), Create(pb_e), run_time=.6)
        cb = self.cutter(.5 * s).move_to(B(.5, -.2))
        trb = self.new_trail()
        self.play(FadeIn(cb), run_time=.3)
        pts = [B(.5, -.2), B(.5, .5), B(1.2, .5)]
        pth_b = VMobject(color=CUT, stroke_width=4).set_points_as_corners(pts).set_z_index(Z_PATH)
        self.mow(cb, pts, 2.4, .5 * s, trb, extra=[Create(pth_b)])
        quad = Polygon(B(0, .5), B(.5, .5), B(.5, 1), B(0, 1))
        patch = Difference(quad, Circle(.5 * s).move_to(B(.5, .5))).set_stroke(width=0).set_fill(BAD, .9).set_z_index(Z_PATCH)
        self.fx("error", -2)
        self.play(FadeOut(cb), FadeIn(patch), run_time=.5)
        self.play(Indicate(patch, color=BAD, scale_factor=1.3), run_time=.8)
        bad = T("✗", 60, BAD).next_to(pb_e, UP, buff=.25)
        self.play(FadeIn(bad, scale=1.5), run_time=.4)
        self.until(t)

        t = self.voice("n3_5")
        lesson = T("Los giros cuestan", 46, ACCENT).to_edge(UP, buff=.35)
        self.play(Write(lesson), run_time=1.2)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 4. Piezas de rompecabezas

class S4Piezas(VScene):
    def construct(self):
        s = 2.1
        Fs = [Frame(s, (x - s / 2, -.1)) for x in (-4.4, 0, 4.4)]
        head = T("Piezas de rompecabezas", 40, ACCENT).to_edge(UP, buff=.3)

        def cell(f, **kw):
            return Polygon(f(0, 0), f(1, 0), f(1, 1), f(0, 1), **kw)

        pix = VGroup(*[cell(f, stroke_width=0, fill_color=LAWN, fill_opacity=1) for f in Fs]).set_z_index(Z_LAWN)
        edges = VGroup(*[cell(f, color=EDGE, stroke_width=4) for f in Fs]).set_z_index(Z_EDGE)
        mask = Difference(Rectangle(width=14.5, height=8.5), Union(*[p.copy() for p in pix])) \
            .set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)
        mids = VGroup(*[Dot(f(*m), radius=.07, color=WHITE) for f in Fs
                        for m in [(.5, 0), (1, .5), (.5, 1), (0, .5)]]).set_z_index(Z_LABEL)

        t = self.voice("n4_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.6)
        self.add(mask)
        self.play(LaggedStart(*[FadeIn(p) for p in pix], lag_ratio=.2), Create(edges), run_time=1.2)
        self.fx("pop")
        self.play(LaggedStart(*[FadeIn(d, scale=2) for d in mids], lag_ratio=.05), run_time=1.2)
        tp = T("puntos de transición", 26, GREY).next_to(edges[0], DOWN, buff=.35)
        self.play(FadeIn(tp), run_time=.5)
        nums = VGroup(*[T(n, 30, GREY).next_to(e, UP, buff=.25) for n, e in zip(["(i)", "(ii)", "(iii)"], edges)])
        self.play(FadeIn(nums), run_time=.6)
        self.until(t)
        self.play(FadeOut(tp), run_time=.3)

        r = .5 * s
        # (i) recto
        t = self.voice("n4_2")
        f = Fs[0]
        c0 = self.cutter(r)
        tr0 = self.new_trail()
        p0 = [f(.5, -.15), f(.5, 0), f(.5, 1), f(.5, 1.15)]
        line0 = VMobject(color=CUT, stroke_width=5).set_points_as_corners(p0[1:3]).set_z_index(Z_PATH)
        self.add(c0.move_to(p0[0]))
        self.mow(c0, p0, 1.3, r, tr0, extra=[Create(line0)])
        l0 = M("1", 40).next_to(edges[0], DOWN, buff=.3)
        self.play(FadeOut(c0), Write(l0), run_time=.4)
        self.until(t, .15)

        # (ii) giro
        t = self.voice("n4_3")
        f = Fs[1]
        arc = Arc(r, -PI / 2, PI / 2, arc_center=f(0, 1), color=ACCENT, stroke_width=4).set_z_index(Z_PATH)
        cdot = Dot(f(0, 1), color=ACCENT).set_z_index(Z_LABEL)
        self.play(FadeIn(cdot, scale=2), Create(arc), run_time=.8)
        naive = DashedVMobject(VMobject().set_points_as_corners([f(.5, 0), f(.5, .5), f(1, .5)]), num_dashes=16) \
            .set_color(GREY).set_z_index(Z_PATH)
        p1 = [f(.5, -.15), f(.5, 0), f(*Q_TURN), f(1, .5), f(1.15, .5)]
        line1 = VMobject(color=CUT, stroke_width=5).set_points_as_corners(p1[1:4]).set_z_index(Z_PATH)
        self.play(Create(naive), run_time=.6)
        self.play(Transform(naive, line1.copy().set_color(CUT)), run_time=1)
        self.remove(naive)
        c1 = self.cutter(r)
        tr1 = self.new_trail()
        self.add(c1.move_to(p1[0]))
        self.mow(c1, p1, 2.2, r, tr1, extra=[Create(line1)])
        qd = Dot(f(*Q_TURN), color=ACCENT).set_z_index(Z_LABEL)
        self.play(Flash(cdot, color=ACCENT), FadeIn(qd), FadeOut(c1), run_time=.6)
        l1 = M(r"\approx 1.326", 40).next_to(edges[1], DOWN, buff=.3)
        self.play(Write(l1), run_time=.6)
        self.until(t, .15)

        # (iii) vuelta en U
        t = self.voice("n4_4")
        f = Fs[2]
        arcs = VGroup(Arc(r, -PI / 2, PI / 2, arc_center=f(0, 1)), Arc(r, PI, PI / 2, arc_center=f(1, 1))) \
            .set_color(ACCENT).set_stroke(width=4).set_z_index(Z_PATH)
        p2 = [f(.5, -.15), f(.5, 0), f(*Q_U[0]), f(*Q_U[1]), f(.5, 0), f(.5, -.15)]
        line2 = VMobject(color=CUT, stroke_width=5).set_points_as_corners(p2[1:5]).set_z_index(Z_PATH)
        self.play(Create(arcs), run_time=.5)
        c2 = self.cutter(r)
        tr2 = self.new_trail()
        self.add(c2.move_to(p2[0]))
        self.mow(c2, p2, 2, r, tr2, extra=[Create(line2)])
        l2 = M(r"\approx 1.611", 40).next_to(edges[2], DOWN, buff=.3)
        self.play(FadeOut(c2), Write(l2), run_time=.5)
        self.until(t, .15)

        # coste de los giros
        t = self.voice("n4_5")
        tau = M(r"\tau \approx 0.326", 44, ACCENT).move_to(DOWN * 2.35 + LEFT * 3.6)
        br = BraceBetweenPoints(l1.get_corner(DL) + DOWN * .05, l1.get_corner(DR) + DOWN * .05, DOWN)
        self.play(Write(tau), run_time=.9)
        cost = M(r"\text{costo} \;\approx\; \text{longitud} \;+\; \tau \cdot \#\text{giros}", 44).move_to(DOWN * 3.2)
        self.play(Write(cost), run_time=1.6)
        self.fx("ding", -8)
        self.until(t)

        # teorema
        t = self.voice("n4_6")
        grp = VGroup(pix, edges, mids, nums, l0, l1, l2, line0, line1, line2, arc, arcs, cdot, qd, tr0, tr1, tr2)
        self.play(FadeOut(grp), FadeOut(tau), FadeOut(mask), cost.animate.move_to(UP * 1.9).scale(.9), run_time=1)
        thm = M(r"|T_{\text{válido}}| \;\le\; L\,(1+\tau)", 56).move_to(UP * .3)
        thm_l = T("L = longitud de un tour en la cuadrícula", 26, GREY).next_to(thm, DOWN, buff=.3)
        box = SurroundingRectangle(VGroup(thm, thm_l), color=ACCENT, buff=.3)
        self.play(Write(thm), run_time=1.5)
        self.play(FadeIn(thm_l), Create(box), run_time=1)
        self.wait(1.5)
        apx = M(r"\Rightarrow\;\; 1.59\text{-aproximación}", 46, MOWED).next_to(box, DOWN, buff=.5)
        apx_l = T("para poliominós simples (antes: 2√3·α_TSP ≈ 3.46·α_TSP)", 24, GREY).next_to(apx, DOWN, buff=.2)
        self.play(Write(apx), run_time=1.2)
        self.play(FadeIn(apx_l), run_time=.6)
        self.fx("success", -6)
        self.until(t, .5)
        self.clear_all()


# ================================================================ 5. El algoritmo

class S5Algoritmo(VScene):
    def construct(self):
        F = Frame(.95, (-6.3, -2.75))
        r = .5 * F.s

        def cell(x, y, **kw):
            return Polygon(F(x, y), F(x + 1, y), F(x + 1, y + 1), F(x, y + 1), **kw)

        cells = VGroup(*[cell(x, y, stroke_width=0, fill_color=LAWN, fill_opacity=1) for (x, y) in CELLS]).set_z_index(Z_LAWN)
        grid = VGroup(*[cell(x, y, stroke_color=LAWN_DARK, stroke_width=1.5) for (x, y) in CELLS]).set_z_index(Z_LAWN)
        outline = Union(*[c.copy() for c in cells]).set_fill(opacity=0).set_stroke(EDGE, 4).set_z_index(Z_EDGE)
        mask = Difference(Rectangle(width=8, height=7).move_to(outline), Union(*[c.copy() for c in cells])) \
            .set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)
        steps = VGroup(
            T("A.  Tour del viajante en la cuadrícula", 26),
            T("B.  Poner piezas de rompecabezas", 26),
            T("C.  Reducir giros (LNS + programa entero)", 26),
        ).arrange(DOWN, aligned_edge=LEFT, buff=.35).move_to(RIGHT * 3.35 + UP * 2.2)

        t = self.voice("n5_1")
        self.play(FadeIn(cells), FadeIn(grid), Create(outline), run_time=1)
        self.add(mask)
        self.play(LaggedStart(*[FadeIn(s_, shift=LEFT * .3) for s_ in steps], lag_ratio=.3), run_time=1.2)
        self.until(t, .1)

        def highlight(i):
            return [s_.animate.set_opacity(1 if k == i else .35) for k, s_ in enumerate(steps)]

        # A
        t = self.voice("n5_2")
        self.play(*highlight(0), run_time=.5)
        centers = VGroup(*[Dot(F(x + .5, y + .5), radius=.05) for (x, y) in CELLS]).set_z_index(Z_LABEL)
        self.play(FadeIn(centers), run_time=.5)
        naive_pts, turns = tour_points(TOUR_MAX, puzzle=False)
        puzzle_pts, _ = tour_points(TOUR_MAX, puzzle=True)
        path = VMobject(color=CUT, stroke_width=4).set_points_as_corners([F(p) for p in naive_pts]).set_z_index(Z_PATH)
        for k in range(8):
            self.fx("tick", offset=k * .3)
        self.play(Create(path), run_time=2.6)
        info = VGroup(M(r"\text{giros} = 18", 36), M(r"\text{longitud} = 24", 36)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=.25).move_to(RIGHT * 3 + DOWN * .6)
        self.play(FadeIn(info), run_time=.6)
        self.until(t)

        # recorrerlo con el disco: esquinas sin cortar
        t = self.voice("n5_3")
        cut = self.cutter(r)
        trail = self.new_trail(Z_TRAIL)
        self.add(cut.move_to(F(naive_pts[0])))
        self.mow(cut, [F(p) for p in naive_pts], 3.2, r, trail, spacing=.05)
        patches = VGroup()
        for c, corner in turns:
            quad = Polygon(F(c), F(corner[0], c[1]), F(corner), F(c[0], corner[1]))
            patches.add(Difference(quad, Circle(r).move_to(F(c))).set_stroke(width=0).set_fill(BAD, .95))
        patches.set_z_index(Z_PATCH)
        self.fx("error", -2)
        self.play(FadeIn(patches, lag_ratio=.05), run_time=.8)
        bad = M(r"18 \text{ esquinas sin cortar}", 32, BAD).next_to(info, DOWN, buff=.4, aligned_edge=LEFT)
        self.play(Write(bad), run_time=.6)
        self.until(t, .1)

        # B
        t = self.voice("n5_4")
        self.play(*highlight(1), run_time=.5)
        puzzle = VMobject(color=CUT, stroke_width=4).set_points_as_corners([F(p) for p in puzzle_pts]).set_z_index(Z_PATH)
        self.play(Transform(path, puzzle), run_time=1.5)
        trail2 = self.new_trail(Z_TRAIL2)
        self.mow(cut, [F(p) for p in puzzle_pts], 3.6, r, trail2, spacing=.05)
        L1 = polyline_len(puzzle_pts)
        info_b = VGroup(M(r"\text{giros} = 18", 36), M(rf"\text{{longitud}} \approx {L1:.2f}", 36)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=.25).move_to(info, aligned_edge=LEFT)
        ok = M(r"\text{todo cortado } \checkmark", 32, MOWED).move_to(bad, aligned_edge=LEFT)
        self.fx("success", -6)
        self.play(FadeOut(cut), ReplacementTransform(info, info_b), ReplacementTransform(bad, ok), run_time=.8)
        self.until(t)

        # C
        t = self.voice("n5_5")
        self.play(*highlight(2), FadeOut(trail), FadeOut(trail2), FadeOut(patches), FadeOut(ok), run_time=.8)
        win = Square(3 * F.s, color=ACCENT, stroke_width=5).set_z_index(Z_LABEL)
        ip = T("programa entero", 22, ACCENT).set_z_index(Z_LABEL)
        spots = [(1.5, 1.5), (4.5, 2.5), (3.5, 3.5), (2.5, 1.5), (4.5, 1.5)]
        win.move_to(F(*spots[0]))
        ip.add_updater(lambda m: m.next_to(win, UP, buff=.08))
        self.play(Create(win), FadeIn(ip), run_time=.6)
        for sp in spots[1:]:
            self.fx("tick")
            self.play(win.animate.move_to(F(*sp)), run_time=.55)
            self.play(Indicate(win, color=WHITE, scale_factor=1.05), run_time=.45)
        best_pts, _ = tour_points(TOUR_MIN, puzzle=True)
        best = VMobject(color=CUT, stroke_width=4).set_points_as_corners([F(p) for p in best_pts]).set_z_index(Z_PATH)
        self.fx("whoosh", -8)
        self.play(Transform(path, best), win.animate.move_to(F(3, 2.5)).scale(1.9).set_stroke(opacity=0), run_time=2)
        ip.clear_updaters()
        self.remove(win, ip)
        L2 = polyline_len(best_pts)
        info_c = VGroup(M(r"\text{giros} = 12", 36, ACCENT), M(rf"\text{{longitud}} \approx {L2:.2f}", 36, ACCENT)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=.25).move_to(info_b, aligned_edge=LEFT)
        self.play(ReplacementTransform(info_b, info_c), run_time=.8)
        cut = self.cutter(r)
        trail3 = self.new_trail(Z_TRAIL)
        self.add(cut.move_to(F(best_pts[0])))
        self.mow(cut, [F(p) for p in best_pts], 3, r, trail3, spacing=.05)
        self.play(FadeOut(cut), run_time=.3)
        self.until(t, .1)

        t = self.voice("n5_6")
        gain = M(rf"-{(1 - L2 / L1) * 100:.1f}\,\%", 54, MOWED).next_to(info_c, DOWN, buff=.5, aligned_edge=LEFT)
        self.fx("ding", -4)
        self.play(FadeIn(gain, scale=1.4), run_time=.6)
        self.until(t, 1)
        self.clear_all()


# ================================================================ 6. Resultados

class S6Resultados(VScene):
    def construct(self):
        head = T("¿Funciona?", 40, ACCENT).to_edge(UP, buff=.3)
        t = self.voice("n6_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.6)
        R = 1.5
        disk = Circle(R, color=CUT, fill_color=CUT, fill_opacity=.2, stroke_width=4).move_to(LEFT * 3.5 + DOWN * .3)
        sqr = Square(R * 2 ** .5, color=ACCENT, stroke_width=4, fill_color=ACCENT, fill_opacity=.25).move_to(disk)
        lab = M(r"\ell = \tfrac{\sqrt2}{2}", 40, ACCENT).next_to(disk, DOWN, buff=.3)
        self.play(Create(disk), run_time=.8)
        self.fx("pop")
        self.play(GrowFromCenter(sqr), Write(lab), run_time=1.2)
        # cuadrícula fina vs normal
        G = Frame(1.0, (1.3, -1.8))
        coarse = VGroup(*[Square(1).move_to(G(x + .5, y + .5)) for x in range(4) for y in range(3)]) \
            .set_stroke(EDGE, 2).set_fill(LAWN, 1)
        k = 2 ** .5 / 2
        fine = VGroup(*[Line(G(k * i, 0), G(k * i, 3)) for i in range(1, 6) if k * i < 4] +
                       [Line(G(0, k * j), G(4, k * j)) for j in range(1, 5) if k * j < 3]).set_stroke(ACCENT, 2)
        self.play(FadeIn(coarse), run_time=.8)
        self.play(Create(fine), run_time=1.6)
        self.wait(1.5)
        waste = M(r"\text{hasta } +41\,\%", 48, BAD).next_to(coarse, UP, buff=.4)
        self.fx("error", -4)
        self.play(FadeIn(waste, scale=1.3), run_time=.8)
        self.until(t)

        # barras
        t = self.voice("n6_2")
        self.play(*[FadeOut(m) for m in [disk, sqr, lab, coarse, fine, waste]], run_time=.7)
        base = DOWN * 2.4
        data = [("TSPSmall", 100, GREY), ("TSPCov", 73, CUT), ("TSPTurn", 68, MOWED)]
        bars = VGroup()
        for i, (name, v, col) in enumerate(data):
            x = -3 + 3 * i
            b = Rectangle(width=1.6, height=v * .045, color=col, fill_color=col, fill_opacity=.7, stroke_width=2)
            b.move_to(np.array([x, 0, 0]) + base, aligned_edge=DOWN)
            n = T(name, 26).next_to(b, DOWN, buff=.2)
            val = M(("" if v == 100 else r"\approx ") + f"{v}\\,\\%", 34).next_to(b, UP, buff=.15)
            bars.add(VGroup(b, n, val))
        ylab = T("longitud media del tour (poliominós)", 24, GREY).to_edge(UP, buff=1.1)
        self.play(FadeIn(ylab), GrowFromEdge(bars[0][0], DOWN), FadeIn(bars[0][1]), run_time=1)
        self.play(FadeIn(bars[0][2]), run_time=.4)
        self.fx("pop")
        self.play(GrowFromEdge(bars[1][0], DOWN), FadeIn(bars[1][1]), run_time=1)
        self.play(FadeIn(bars[1][2]), run_time=.4)
        d1 = M(r"-27\,\%", 36, CUT).move_to(np.array([-1.5, 1.3, 0]))
        self.play(Write(d1), run_time=.6)
        self.wait(1.2)
        self.fx("pop")
        self.play(GrowFromEdge(bars[2][0], DOWN), FadeIn(bars[2][1]), run_time=1)
        self.play(FadeIn(bars[2][2]), run_time=.4)
        d2 = M(r"-5\,\%", 36, MOWED).move_to(np.array([1.5, 1.0, 0]))
        self.fx("ding", -6)
        self.play(Write(d2), run_time=.6)
        self.until(t)

        # 20x
        t = self.voice("n6_3")
        self.play(FadeOut(VGroup(bars, ylab, d1, d2)), run_time=.7)
        small = Square(.62, color=GREY, fill_color=GREY, fill_opacity=.4).move_to(LEFT * 3.3 + DOWN * .6)
        big = Square(.62 * 20 ** .5, color=MOWED, fill_color=MOWED, fill_opacity=.3).move_to(RIGHT * 1.8 + DOWN * .6)
        ls = T("antes", 26, GREY).next_to(small, DOWN, buff=.25)
        lb = T("este artículo", 26, MOWED).next_to(big, DOWN, buff=.25)
        self.play(FadeIn(small), FadeIn(ls), run_time=.6)
        self.fx("whoosh", -6)
        self.play(TransformFromCopy(small, big), FadeIn(lb), run_time=1.4)
        x20 = T("20×", 72, MOWED).move_to(big)
        self.fx("success", -6)
        self.play(FadeIn(x20, scale=1.5), run_time=.6)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 7. Cierre

class S7Cierre(VScene):
    def construct(self):
        items = [
            ("1", "El óptimo exacto no tiene fórmula:", r"\mathrm{Gal}(f_\delta) = S_{16}", BAD),
            ("2", "Los giros cuestan:", r"\tau \approx 0.326", ACCENT),
            ("3", "Tour TSP + piezas + LNS:", r"1.59\text{-aprox. y tours más cortos}", MOWED),
        ]
        rows = VGroup()
        for n, txt, tex, col in items:
            num = VGroup(Circle(.28, color=col, stroke_width=3), T(n, 26, col))
            num[1].move_to(num[0])
            rows.add(VGroup(num, T(txt, 30), M(tex, 36, col)).arrange(RIGHT, buff=.35))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=.6).move_to(UP * .3)

        t = self.voice("n7_1")
        self.fx("pop")
        self.play(FadeIn(rows[0], shift=RIGHT * .3), run_time=.8)
        self.until(t, .1)
        t = self.voice("n7_2")
        self.fx("pop")
        self.play(FadeIn(rows[1], shift=RIGHT * .3), run_time=.8)
        self.wait(2.2)
        self.fx("pop")
        self.play(FadeIn(rows[2], shift=RIGHT * .3), run_time=.8)
        self.until(t, .2)

        t = self.voice("n7_3")
        self.play(FadeOut(rows), run_time=.6)
        fin = T("Del álgebra a los algoritmos", 56, ACCENT)
        self.fx("success", -4)
        self.play(Write(fin), run_time=1.6)
        self.until(t, 1.2)
        credits = VGroup(
            T("Basado en: S. P. Fekete, D. Krupke, M. Perk, C. Rieck, C. Scheffer.", 22, GREY),
            T("The Lawn Mowing Problem: From Algebra to Algorithms. ESA 2023 · arXiv:2307.01092", 22, GREY),
            T("Animación: Manim Community · Voz: edge-tts · Sonido sintetizado con NumPy", 20, GREY),
        ).arrange(DOWN, buff=.15).to_edge(DOWN, buff=.5)
        self.play(fin.animate.shift(UP * .6), FadeIn(credits), run_time=1)
        self.wait(3)
        self.play(FadeOut(fin), FadeOut(credits), run_time=1.5)
        self.wait(.5)


SCENES = ["S1Problema", "S2Algebra", "S3Pixeles", "S4Piezas", "S5Algoritmo", "S6Resultados", "S7Cierre"]
