"""A Closer Cut: Computing Near-Optimal Lawn Mowing Tours — Fekete, Krupke, Perk, Rieck, Scheffer.

ALENEX 2023, arXiv:2211.05891. Video al estilo 3Blue1Brown con Manim Community.
Ejecutar con `python build.py -v closer`. Reutiliza el estilo y las utilidades
del video anterior (fekete.py).
"""
import json
from pathlib import Path

import numpy as np
from manim import *

import closer_geo as G
from fekete import (ACCENT, BAD, BG, CELLS, CUT, EDGE, GREY, LAWN, LAWN_DARK, MOWED, TOUR_MIN,
                    Z_CUTTER, Z_EDGE, Z_LABEL, Z_LAWN, Z_MASK, Z_PATCH, Z_PATH, Z_TRAIL, Frame, M, T,
                    VScene, tour_points)

ROOT = Path(__file__).parent
AUD = ROOT / "build" / "audio_closer"
DURS = json.loads((AUD / "durations.json").read_text())
GEO = G.load()
ITERS = GEO["iters"]

ORANGE = "#FF8C1A"
WITNESS = "#7CE38B"

config.background_color = BG


class CScene(VScene):
    def voice(self, key, offset=0.0):
        self.add_sound(str(AUD / f"{key}.wav"), time_offset=offset)
        return self.now() + offset + DURS[key]


# ---------------------------------------------------------------- utilidades

def strip(points, r, color, z=Z_TRAIL, spacing=None, opacity=1.0):
    """La huella de un disco de radio r que recorre la poligonal `points`."""
    pts = [np.array(p, float) for p in points]
    spacing = spacing or r / 5
    out = VGroup()
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / spacing)))
        for k in range(n):
            out.add(Circle(r, num_components=20).move_to(a + (b - a) * k / n))
    out.add(Circle(r, num_components=20).move_to(pts[-1]))
    return out.set_stroke(width=0).set_fill(color, opacity).set_z_index(z)


def coverage_image(F, tour, step=0.025, covered=MOWED, missed=BAD):
    """Imagen del polígono de ejemplo: verde lo cubierto por el tour, rojo lo demás."""
    inside, cov = G.fine_masks(np.asarray(tour, float), step)
    rgba = np.zeros(inside.shape + (4,), np.uint8)
    cc = np.array(color_to_int_rgba(ManimColor(covered), 1.0), np.uint8)
    mc = np.array(color_to_int_rgba(ManimColor(missed), .85), np.uint8)
    rgba[inside] = mc
    rgba[cov] = cc
    img = ImageMobject(rgba[::-1])
    img.set_resampling_algorithm(RESAMPLING_ALGORITHMS["linear"])
    xs = [p[0] for p in G.POLY]
    ys = [p[1] for p in G.POLY]
    img.stretch_to_fit_width((max(xs) - min(xs)) * F.s)
    img.stretch_to_fit_height((max(ys) - min(ys)) * F.s)
    img.move_to(F((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    return img.set_z_index(Z_PATCH)


def closed(pts):
    pts = [np.asarray(p, float) for p in pts]
    return pts + [pts[0]]


def tour_mob(F, tour, color=CUT, width=4, z=Z_PATH):
    return VMobject(color=color, stroke_width=width).set_points_as_corners(
        [F(p) for p in closed(tour)]).set_z_index(z)


def poly_mobs(F, fill=LAWN):
    lawn = Polygon(*[F(p) for p in G.POLY], stroke_width=0, fill_color=fill, fill_opacity=1).set_z_index(Z_LAWN)
    edge = Polygon(*[F(p) for p in G.POLY], color=EDGE, stroke_width=4).set_z_index(Z_EDGE)
    return lawn, edge


def outside_mask(F, poly_mob, pad=3):
    box = Rectangle(width=poly_mob.width + pad, height=poly_mob.height + pad).move_to(poly_mob)
    return Difference(box, poly_mob.copy()).set_stroke(width=0).set_fill(BG, 1).set_z_index(Z_MASK)


def witness_dots(F, W, color=WITNESS, radius=.06):
    return VGroup(*[Dot(F(p), radius=radius, color=color) for p in W]).set_z_index(Z_LABEL)


def witness_disks(F, W, color=WITNESS):
    return VGroup(*[Circle(G.R * F.s, color=color, stroke_width=2, fill_color=color, fill_opacity=.12).move_to(F(p))
                    for p in W]).set_z_index(Z_PATH - 1)


# ================================================================ 1. Introducción

class C1Intro(CScene):
    def construct(self):
        # la semana pasada: poliominó con su tour de piezas
        P = Frame(.62, (-5.6, -1.4))
        cells = VGroup(*[Square(P.s).move_to(P(x + .5, y + .5)) for x, y in CELLS]) \
            .set_stroke(EDGE, 2).set_fill(LAWN, 1).set_z_index(Z_LAWN)
        pts, _ = tour_points(TOUR_MIN, puzzle=True)
        ptour = VMobject(color=CUT, stroke_width=3).set_points_as_corners([P(p) for p in pts]).set_z_index(Z_PATH)
        prev = T("La semana pasada: poliominós", 30, GREY).to_edge(UP, buff=.4)
        t = self.voice("c1_1")
        self.play(FadeIn(prev, shift=DOWN * .2), FadeIn(cells, lag_ratio=.05), run_time=1.2)
        self.play(Create(ptour), run_time=2)
        self.until(t)

        # hoy: un polígono cualquiera
        F = Frame(.72, (-3.6, -2.4))
        lawn, edge = poly_mobs(F)
        t = self.voice("c1_2")
        today = T("Hoy: cualquier polígono", 30, ACCENT).to_edge(UP, buff=.4)
        self.fx("whoosh", -6)
        self.play(FadeOut(cells, shift=LEFT * .3), FadeOut(ptour, shift=LEFT * .3), FadeIn(lawn),
                  ReplacementTransform(prev, today), Create(edge), run_time=1.5)
        r = G.R * F.s
        cut = self.cutter(r).move_to(F(1.2, 1.2))
        self.fx("pop")
        self.play(GrowFromCenter(cut), run_time=.6)
        rad = Line(cut.get_center(), cut.get_center() + RIGHT * r, color=ACCENT, stroke_width=3).set_z_index(Z_LABEL)
        rl = M("r", 34, ACCENT).next_to(rad, UP, buff=.06)
        self.play(Create(rad), Write(rl), run_time=.7)
        self.until(t)

        # recorrido que lo corta todo
        t = self.voice("c1_3")
        self.play(FadeOut(rad), FadeOut(rl), run_time=.3)
        mask = outside_mask(F, lawn)
        self.add(mask)
        best = min(ITERS, key=lambda it: it["ub_length"])
        ub = [F(p) for p in closed(best["ub_tour"])]
        trail = self.new_trail()
        formula = M(r"\min \ell(T) \quad\text{tal que}\quad \operatorname{dist}(p, T) \le r \;\; \forall p \in P",
                    36).to_edge(DOWN, buff=.3)
        self.mow(cut, ub, 7.5, r, trail, extra=[Succession(Wait(1), FadeIn(formula, shift=UP * .2, run_time=1))])
        self.until(t, .2)

        # tres problemas difíciles
        t = self.voice("c1_4")
        self.play(FadeOut(trail), FadeOut(cut), run_time=.3)
        self.clear_all(.7)
        # viajante
        pts = [np.array([*p, 0]) for p in [(-5.6, .2), (-4.8, 1.1), (-3.7, .6), (-3.9, -.5), (-5.0, -.7)]]
        tsp = VGroup(VMobject(color=CUT, stroke_width=3).set_points_as_corners(closed(pts)),
                     *[Dot(p, color=ACCENT) for p in pts])
        # cubrir con discos
        sq = Square(1.8, color=EDGE, stroke_width=3, fill_color=LAWN, fill_opacity=1)
        disks = VGroup(*[Circle(.64, color=CUT, stroke_width=2, fill_color=CUT, fill_opacity=.25).move_to(
            sq.get_center() + np.array([dx, dy, 0])) for dx in (-.45, .45) for dy in (-.45, .45)])
        cover = VGroup(sq, disks)
        # galería de arte
        gal = Polygon(*[np.array(p + (0,)) for p in [(-1, -1), (1, -1), (1, .2), (.2, .2), (.2, 1), (-1, 1)]],
                      color=EDGE, stroke_width=3, fill_color=LAWN, fill_opacity=1)
        guard = Dot([-.6, -.6, 0], color=ACCENT)
        vis = Polygon(*[np.array(p + (0,)) for p in [(-.6, -.6), (1, -1), (1, .2), (.2, .2), (.2, 1), (-1, 1), (-1, -1)]],
                      stroke_width=0, fill_color=ACCENT, fill_opacity=.2)
        art = VGroup(gal, vis, guard)
        icons = VGroup(tsp, cover, art)
        for m, x in zip(icons, (-4.2, 0, 4.2)):
            m.move_to([x, .3, 0])
        names = VGroup(T("Viajante (TSP)", 28), T("Cubrir con discos", 28), T("Galería de arte", 28))
        for n, m in zip(names, icons):
            n.next_to(m, DOWN, buff=.45)
        for m, n in zip(icons, names):
            self.fx("pop", -3)
            self.play(FadeIn(m, scale=.8), FadeIn(n, shift=UP * .2), run_time=.8)
            self.wait(.9)
        self.until(t)

        # lo que se sabía
        t = self.voice("c1_5")
        self.play(FadeOut(icons), FadeOut(names), run_time=.6)
        apx = M(r"\ell(T_{\text{aprox}}) \;\le\; 2\sqrt3\,\rho_{\text{TSP}} \cdot \text{OPT} \;\approx\; 3.46\cdot\text{OPT}",
                48).shift(UP * .8)
        self.play(Write(apx), run_time=1.8)
        ref = T("Arkin, Fekete, Mitchell (2000)", 24, GREY).next_to(apx, DOWN, buff=.3)
        self.play(FadeIn(ref), run_time=.5)
        self.wait(1.6)
        q = T("¿Y para una instancia concreta? ¿Qué tan lejos del óptimo?", 34, BAD).shift(DOWN * 1.6)
        self.fx("error", -6)
        self.play(FadeIn(q, shift=UP * .2), run_time=.8)
        self.until(t)

        # el artículo
        t = self.voice("c1_6")
        self.play(FadeOut(apx), FadeOut(ref), FadeOut(q), run_time=.6)
        title = T("A Closer Cut:", 56).shift(UP * 1.6)
        sub = T("Computing Near-Optimal Lawn Mowing Tours", 44, ACCENT).next_to(title, DOWN, buff=.25)
        authors = T("Sándor P. Fekete · Dominik Krupke · Michael Perk · Christian Rieck · Christian Scheffer",
                    22, GREY).next_to(sub, DOWN, buff=.5)
        venue = T("ALENEX 2023 · arXiv:2211.05891", 22, GREY).next_to(authors, DOWN, buff=.2)
        self.play(Write(title), run_time=1)
        self.play(Write(sub), run_time=1.4)
        self.play(FadeIn(authors, shift=UP * .2), FadeIn(venue, shift=UP * .2), run_time=.8)
        # solución + garantía
        line = NumberLine(x_range=[0, 10, 1], length=8, include_ticks=False, color=GREY).shift(DOWN * 2.3)
        lb, ub = line.n2p(3), line.n2p(7.2)
        opt = line.n2p(5.4)
        lbm = VGroup(Line(lb + UP * .25, lb + DOWN * .25, color=WITNESS, stroke_width=6), T("cota inferior", 22, WITNESS).next_to(lb, DOWN, buff=.35))
        ubm = VGroup(Line(ub + UP * .25, ub + DOWN * .25, color=ORANGE, stroke_width=6), T("solución", 22, ORANGE).next_to(ub, DOWN, buff=.35))
        optm = VGroup(Dot(opt, color=WHITE), M(r"\text{OPT}", 26).next_to(opt, UP, buff=.2))
        self.play(Create(line), run_time=.5)
        self.play(FadeIn(ubm, shift=DOWN * .2), run_time=.5)
        self.play(FadeIn(lbm, shift=DOWN * .2), run_time=.5)
        self.fx("ding", -6)
        self.play(FadeIn(optm), run_time=.5)
        self.until(t, .8)
        self.clear_all()


# ================================================================ 2. Tours rectos

class C2Rectos(CScene):
    def construct(self):
        thm = T("Teorema: un tour óptimo sólo tiene segmentos rectos", 34, ACCENT).to_edge(UP, buff=.35)
        t = self.voice("c2_1")
        self.play(Write(thm), run_time=1.6)
        self.until(t)

        # un arco curvo y su franja
        t = self.voice("c2_2")
        O, R0, r = np.array([0, 2.4, 0]), 3.0, .55
        a0, a1 = np.radians(222), np.radians(318)
        arc_pts = [O + R0 * np.array([np.cos(a), np.sin(a), 0]) for a in np.linspace(a0, a1, 60)]
        arc = VMobject(color=CUT, stroke_width=5).set_points_smoothly(arc_pts).set_z_index(Z_PATH)
        lab_t = M("t", 38, CUT).next_to(arc_pts[0], LEFT, buff=.2)
        self.play(Create(arc), Write(lab_t), run_time=1)
        cut = self.cutter(r)
        trail = self.new_trail()
        self.mow(cut, arc_pts, 3.2, r, trail, color=LAWN)
        self.play(FadeOut(cut), run_time=.3)
        self.until(t)

        # el lado convexo
        t = self.voice("c2_3")
        outer = Arc(radius=R0 + r, start_angle=a0, angle=a1 - a0, arc_center=O, color=ACCENT, stroke_width=6).set_z_index(Z_LABEL)
        sp = M("S^+", 40, ACCENT).next_to(outer.point_from_proportion(.5), DOWN, buff=.15)
        self.play(Create(outer), Write(sp), run_time=1.2)
        self.until(t)

        # otro tramo ya cubre parte del lado convexo -> atajo
        t = self.voice("c2_4")
        yb = O[1] - R0 - r     # fondo del lado convexo
        y2 = yb - .05          # su franja cubre la parte del lado convexo que el atajo deja
        other = [np.array([-3.8, y2, 0]), np.array([3.8, y2, 0])]
        other_strip = strip(other, r, MOWED, z=Z_TRAIL + 1, opacity=.5)
        other_line = Line(*other, color=CUT, stroke_width=4).set_z_index(Z_PATH)
        self.play(FadeIn(other_strip), Create(other_line), sp.animate.shift(DOWN * .9 + RIGHT * 2.6), run_time=1.2)
        ca, cb = np.radians(246), np.radians(294)
        A = O + R0 * np.array([np.cos(ca), np.sin(ca), 0])
        B = O + R0 * np.array([np.cos(cb), np.sin(cb), 0])
        na, nb = Dot(A, color=WHITE).set_z_index(Z_LABEL), Dot(B, color=WHITE).set_z_index(Z_LABEL)
        self.play(FadeIn(na), FadeIn(nb), run_time=.4)
        sub = [O + R0 * np.array([np.cos(a), np.sin(a), 0]) for a in np.linspace(ca, cb, 30)]
        bit = VMobject(color=BAD, stroke_width=6).set_points_smoothly(sub).set_z_index(Z_PATH + 1)
        self.play(Create(bit), run_time=.6)
        chord = Line(A, B, color=WHITE, stroke_width=6).set_z_index(Z_PATH + 1)
        self.fx("whoosh", -6)
        self.play(Transform(bit, chord), run_time=1.2)
        chord_strip = strip([A, B], r, CUT, z=Z_TRAIL + 2, opacity=.35)
        self.play(FadeIn(chord_strip), run_time=.6)
        shorter = M(r"|AB| < \ell(\text{arco})", 34, WHITE).to_edge(RIGHT, buff=.6).shift(UP * 1.6)
        ok = T("todo sigue cubierto", 28, MOWED).next_to(shorter, DOWN, buff=.2)
        self.fx("ding", -6)
        self.play(Write(shorter), FadeIn(ok), run_time=1)
        self.until(t)

        t = self.voice("c2_5")
        self.play(*[FadeOut(m) for m in self.mobjects if m is not thm], run_time=.8)
        poly = [np.array([*p, 0]) for p in [(-3, -1.5), (-1.2, .8), (.6, -.4), (2.2, 1.3), (3.4, -1.2), (.4, -2.2)]]
        ptour = VMobject(color=CUT, stroke_width=4).set_points_as_corners(closed(poly))
        dots = VGroup(*[Dot(p, color=ACCENT) for p in poly])
        msg = T("⇒ basta buscar entre polígonos", 36, MOWED).shift(UP * 1.6)
        self.play(Create(ptour), FadeIn(dots), FadeIn(msg, shift=UP * .2), run_time=1.5)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 3. Coordenadas irracionales

class C3Irracional(CScene):
    def construct(self):
        head = T("La mala noticia", 40, BAD).to_edge(UP, buff=.3)
        F = Frame(1.55, (-4.6, -2.6))
        a, b, c = np.array([0, 0.]), np.array([1, 0.]), np.array([.5, 2.])
        tri = Polygon(F(a), F(b), F(c), color=EDGE, stroke_width=4, fill_color=LAWN, fill_opacity=1).set_z_index(Z_LAWN)
        labs = VGroup(M("a", 32).next_to(F(a), DL, buff=.1), M("b", 32).next_to(F(b), DR, buff=.1),
                      M("c", 32).next_to(F(c), UP, buff=.1)).set_z_index(Z_LABEL)
        t = self.voice("c3_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.5)
        self.play(DrawBorderThenFill(tri), FadeIn(labs), run_time=1.4)
        coords = M(r"a=(0,0)\quad b=(\alpha,0)\quad c=(\tfrac{\alpha}{2},2)", 32).move_to([2.6, 2.2, 0])
        self.play(Write(coords), run_time=1.2)
        self.until(t)

        t = self.voice("c3_2")
        circ = VGroup(*[Circle(F.s, color=col, stroke_width=3).move_to(F(p)) for p, col in
                        ((a, CUT), (b, CUT), (c, ACCENT))]).set_z_index(Z_PATH)
        self.play(LaggedStart(*[Create(m) for m in circ], lag_ratio=.3), run_time=2)
        self.until(t)

        t = self.voice("c3_3")
        h = (1 - .25) ** .5
        p, q = np.array([.5, h]), np.array([.5, 1.])
        pd = Dot(F(p), radius=.08, color=WHITE).set_z_index(Z_CUTTER)
        pl = M("p", 34).next_to(F(p), RIGHT, buff=.12).set_z_index(Z_LABEL)
        self.fx("pop")
        self.play(FadeIn(pd, scale=3), Write(pl), run_time=.6)
        self.play(Indicate(circ[0], color=WHITE), Indicate(circ[1], color=WHITE), run_time=1.2)
        seg = Line(F(p), F(q), color=WHITE, stroke_width=6).set_z_index(Z_CUTTER)
        qd = Dot(F(q), radius=.07, color=ACCENT).set_z_index(Z_CUTTER)
        ql = M("q", 32, ACCENT).next_to(F(q), LEFT, buff=.12).set_z_index(Z_LABEL)
        self.play(Create(seg), FadeIn(qd), Write(ql), run_time=.8)
        opt = T("tour óptimo: p → q → p", 28, GREY).next_to(coords, DOWN, buff=.5)
        self.play(FadeIn(opt), run_time=.5)
        self.until(t)

        t = self.voice("c3_4")
        hf = M(r"p_y = \sqrt{1 - (\alpha/2)^2}", 46).next_to(opt, DOWN, buff=.5)
        self.play(Write(hf), run_time=1.3)
        self.wait(1.2)
        hv = M(r"\alpha = 1 \;\Rightarrow\; p_y = \frac{\sqrt3}{2} \notin \mathbb{Q}", 46, BAD).next_to(hf, DOWN, buff=.4)
        self.fx("boom", -8)
        self.play(Write(hv), run_time=1.3)
        self.until(t)

        t = self.voice("c3_5")
        self.play(FadeOut(VGroup(coords, opt, hf)), hv.animate.move_to([2.6, 1.6, 0]),
                  run_time=.8)
        ag = T("Como en la galería de arte:", 28, GREY).next_to(hv, DOWN, buff=.6)
        ag2 = T("guardias irracionales (Abrahamsen et al. 2017)", 24, GREY).next_to(ag, DOWN, buff=.15)
        self.play(FadeIn(ag), FadeIn(ag2), run_time=.8)
        self.wait(1.5)
        prob = M(r"\text{Problema abierto: } \;\exists\mathbb{R}\text{-completo?}", 40, ACCENT).next_to(ag2, DOWN, buff=.6)
        self.play(Write(prob), run_time=1.2)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 4. Testigos

class C4Testigos(CScene):
    def construct(self):
        F = Frame(.82, (-4.1, -2.7))
        lawn, edge = poly_mobs(F)
        it0 = ITERS[0]
        W = it0["witnesses"]
        head = T("Testigos", 40, WITNESS).to_edge(UP, buff=.3)
        t = self.voice("c4_1")
        self.play(FadeIn(head, shift=DOWN * .2), FadeIn(lawn), Create(edge), run_time=1.2)
        self.until(t)

        t = self.voice("c4_2")
        dots = witness_dots(F, W)
        self.fx("pop", -3)
        self.play(LaggedStart(*[FadeIn(d, scale=3) for d in dots], lag_ratio=.12), run_time=2)
        w_lab = M(r"W = \{w_1, \dots, w_{15}\} \subset P", 36, WITNESS).to_edge(DOWN, buff=.35)
        self.play(Write(w_lab), run_time=1)
        self.until(t)

        t = self.voice("c4_3")
        disks = witness_disks(F, W)
        self.play(LaggedStart(*[GrowFromCenter(d) for d in disks], lag_ratio=.06), run_time=1.6)
        tour = tour_mob(F, it0["tour"])
        self.wait(1.5)
        self.play(Create(tour), run_time=2.5)
        cet = T("Close-Enough TSP", 32, CUT).next_to(head, DOWN, buff=.15)
        self.play(FadeIn(cet), run_time=.5)
        self.until(t)

        t = self.voice("c4_4")
        self.play(FadeOut(w_lab), run_time=.4)
        ineq = M(r"W \subset P \;\Longrightarrow\; \ell(T^*_W) \;\le\; \ell(T^*_P) = \text{OPT}", 40).to_edge(DOWN, buff=.35)
        self.play(Write(ineq), run_time=1.6)
        self.wait(2)
        box = SurroundingRectangle(ineq, color=WITNESS, buff=.12)
        lb = T("cota inferior", 28, WITNESS).next_to(box, UP, buff=.15)
        self.fx("ding", -6)
        self.play(Create(box), FadeIn(lb), run_time=.8)
        self.until(t)

        t = self.voice("c4_5")
        group = VGroup(lawn, edge, dots, disks, tour)
        self.play(FadeOut(VGroup(ineq, box, lb, cet)), group.animate.scale(.6).to_edge(LEFT, buff=.4), run_time=1)
        # árbol de ramificación
        root = Dot([3, 1.6, 0], color=WHITE)
        lvl1 = [Dot([x, .5, 0], color=WHITE) for x in (1.8, 3, 4.2)]
        lvl2 = [Dot([x, -.6, 0], color=WHITE) for x in (1.4, 2.2, 3.8, 4.6)]
        edges = VGroup(*[Line(root.get_center(), d.get_center(), color=GREY) for d in lvl1],
                       Line(lvl1[0].get_center(), lvl2[0].get_center(), color=GREY),
                       Line(lvl1[0].get_center(), lvl2[1].get_center(), color=GREY),
                       Line(lvl1[2].get_center(), lvl2[2].get_center(), color=GREY),
                       Line(lvl1[2].get_center(), lvl2[3].get_center(), color=GREY))
        tree = VGroup(edges, root, *lvl1, *lvl2)
        bb = T("branch-and-bound", 30).next_to(tree, DOWN, buff=.4)
        soc = M(r"+\;\text{SOCP:}\; \sqrt{w_k^2 + u_k^2} \le z_k", 34, CUT).next_to(bb, DOWN, buff=.25)
        cite = T("Coutinho et al. (2016)", 22, GREY).next_to(soc, DOWN, buff=.25)
        self.play(Create(tree), run_time=1.5)
        self.play(FadeIn(bb), run_time=.5)
        self.play(Write(soc), FadeIn(cite), run_time=1.2)
        self.until(t, .5)
        self.clear_all()


# ================================================================ 5. Primal-dual

class C5PrimalDual(CScene):
    def construct(self):
        F = Frame(.78, (-6.4, -2.6))
        lawn, edge = poly_mobs(F)
        self.add(lawn, edge)
        tag = T("ejemplo ilustrativo", 18, GREY).next_to(edge, DOWN, buff=.2).align_to(edge, LEFT)

        # panel de cotas a la derecha
        nl = NumberLine(x_range=[0, 70, 10], length=5.6, rotation=PI / 2, include_numbers=True,
                        label_direction=LEFT, font_size=22, color=GREY).move_to([3.4, -.2, 0])
        nl_lab = T("longitud", 22, GREY).next_to(nl, UP, buff=.2)

        def mark(v, col, text):
            p = nl.n2p(v)
            return VGroup(Line(p + LEFT * .25, p + RIGHT * .25, color=col, stroke_width=6),
                          T(text, 22, col).next_to(p + RIGHT * .3, RIGHT, buff=.1)).set_z_index(Z_LABEL)

        it = ITERS[0]
        t = self.voice("c5_1")
        self.play(FadeIn(nl), FadeIn(nl_lab), FadeIn(tag), run_time=.8)
        dots = witness_dots(F, it["witnesses"])
        self.fx("pop", -3)
        self.play(LaggedStart(*[FadeIn(d, scale=3) for d in dots], lag_ratio=.1), run_time=1.8)
        self.until(t)

        t = self.voice("c5_2")
        tour = tour_mob(F, it["tour"])
        self.play(Create(tour), run_time=1.8)
        img = coverage_image(F, it["tour"])
        self.play(FadeIn(img), run_time=1)
        cov_lab = T(f"cubierto: {it['coverage']:.0%}", 26, MOWED).next_to(edge, UP, buff=.2).align_to(edge, LEFT)
        self.play(FadeIn(cov_lab), run_time=.4)
        lbm = mark(it["length"], WITNESS, "cota inf.")
        self.play(FadeIn(lbm, shift=LEFT * .2), run_time=.6)
        self.until(t)

        # reparar: cota superior
        t = self.voice("c5_3")
        cur = np.array(it["tour"])
        ext_mobs = VGroup()
        for stage in it["ub_stages"]:
            for sub in stage:
                m = tour_mob(F, sub, ORANGE, 5, Z_PATH + 1)
                ext_mobs.add(m)
                self.play(Create(m), run_time=.5)
                cur = G.splice(cur, np.array(sub), np.array(sub[0]))
            new_img = coverage_image(F, cur)
            self.play(FadeIn(new_img), FadeOut(img), run_time=.6)
            img = new_img
        self.until(t)

        t = self.voice("c5_4")
        best_ub = it["ub_length"]
        cov_new = T("cubierto: 100%", 26, MOWED).move_to(cov_lab, aligned_edge=LEFT)
        self.play(Transform(cov_lab, cov_new), run_time=.4)
        ubm = mark(best_ub, ORANGE, "cota sup.")
        self.fx("ding", -6)
        self.play(FadeIn(ubm, shift=LEFT * .2), run_time=.6)
        self.until(t)

        # iteraciones
        t = self.voice("c5_5")
        lb_img = coverage_image(F, it["tour"])
        self.play(FadeOut(ext_mobs), FadeIn(lb_img), FadeOut(img), run_time=.8)
        img = lb_img
        cov_back = T(f"cubierto: {it['coverage']:.0%}", 26, MOWED).move_to(cov_lab, aligned_edge=LEFT)
        self.play(Transform(cov_lab, cov_back), run_time=.3)
        new = witness_dots(F, it["new"], color=BAD, radius=.075)
        self.fx("pop", -3)
        self.play(LaggedStart(*[FadeIn(d, scale=3) for d in new], lag_ratio=.12), run_time=1.4)
        self.play(new.animate.set_color(WITNESS).scale(.8), run_time=.6)
        dots.add(*new)
        self.until(t)

        t = self.voice("c5_6")
        lb_trace = VGroup()
        for i in range(1, len(ITERS)):
            nxt = ITERS[i]
            new_tour = tour_mob(F, nxt["tour"])
            new_img = coverage_image(F, nxt["tour"])
            cov_txt = T(f"cubierto: {nxt['coverage']:.0%}", 26, MOWED).move_to(cov_lab, aligned_edge=LEFT)
            old_lb = lbm[0].copy().set_opacity(.3)
            lb_trace.add(old_lb)
            best_ub = min(best_ub, nxt["ub_length"])
            anims = [Transform(tour, new_tour), FadeIn(new_img), FadeOut(img), Transform(cov_lab, cov_txt),
                     Transform(lbm, mark(nxt["length"], WITNESS, "cota inf."))]
            self.add(old_lb)
            self.fx("tick", -4)
            self.play(*anims, run_time=1.2)
            img = new_img
            if "new" in nxt and i < len(ITERS) - 1:
                nd = witness_dots(F, nxt["new"], color=BAD, radius=.075)
                self.play(FadeIn(nd, lag_ratio=.1), run_time=.6)
                self.play(nd.animate.set_color(WITNESS).scale(.8), run_time=.3)
                dots.add(*nd)
        self.until(t)

        t = self.voice("c5_7")
        lo, hi = nl.n2p(ITERS[-1]["length"]), nl.n2p(best_ub)
        brace = BraceBetweenPoints(hi + RIGHT * 1.75, lo + RIGHT * 1.75, direction=RIGHT, color=ACCENT)
        gap = M(r"\text{OPT} \in [\text{LB}, \text{UB}]", 32, ACCENT).to_corner(UR, buff=.35)
        gap_v = T("el óptimo está en el hueco", 22, GREY).next_to(gap, DOWN, buff=.12).align_to(gap, RIGHT)
        self.play(GrowFromCenter(brace), run_time=.7)
        self.fx("ding", -6)
        self.play(FadeOut(nl_lab), Write(gap), FadeIn(gap_v), run_time=1)
        self.until(t)

        t = self.voice("c5_8")
        conv = M(r"\text{testigos densos} \;\Rightarrow\; \text{\'area}(P \setminus (T_W \oplus C)) \to 0", 32) \
            .to_edge(DOWN, buff=.25)
        self.play(FadeOut(tag), Write(conv), run_time=1.5)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 6. Resultados

def _random_poly(kind, rng, n=40):
    if kind == "fpg":
        ang = np.sort(rng.uniform(0, 2 * np.pi, n))
        rad = rng.uniform(.45, 1, n)
        return [np.array([r * np.cos(a), r * np.sin(a), 0]) for a, r in zip(ang, rad)]
    # ortogonal (iso) u octogonal (octa) a partir de una "escalera" en cada cuadrante
    pts = []
    for q in range(4):
        steps = rng.integers(3, 6)
        xs = np.sort(rng.uniform(.15, 1, steps))[::-1]
        ys = np.sort(rng.uniform(.15, 1, steps))
        cur = []
        for x, y in zip(xs, ys):
            if kind == "iso":
                cur += [(x, y * .6), (x, y)]
            else:
                cur += [(x, y * .7), (x - .08, y)]
        rot = np.array([[np.cos(q * np.pi / 2), -np.sin(q * np.pi / 2)], [np.sin(q * np.pi / 2), np.cos(q * np.pi / 2)]])
        pts += [np.array([*(rot @ np.array(c)), 0]) for c in cur]
    return pts


class C6Resultados(CScene):
    def construct(self):
        head = T("¿Funciona?", 40, ACCENT).to_edge(UP, buff=.3)
        rng = np.random.default_rng(11)
        t = self.voice("c6_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.5)
        shapes = VGroup()
        for kind, name, x in (("fpg", "FPG", -4.2), ("iso", "SRPG iso", 0), ("octa", "SRPG octa", 4.2)):
            p = Polygon(*_random_poly(kind, rng), color=EDGE, stroke_width=3, fill_color=LAWN, fill_opacity=1).scale(1.5)
            p.move_to([x, .4, 0])
            shapes.add(VGroup(p, T(name, 26).next_to(p, DOWN, buff=.3)))
        self.play(LaggedStart(*[FadeIn(s, shift=UP * .3) for s in shapes], lag_ratio=.3), run_time=1.6)
        salz = T("Salzburg Database of Geometric Inputs · hasta 2000 vértices", 26, GREY).to_edge(DOWN, buff=.6)
        self.play(FadeIn(salz), run_time=.6)
        self.until(t)

        # área relativa
        t = self.voice("c6_2")
        self.play(FadeOut(shapes[0]), FadeOut(shapes[2]), FadeOut(salz), shapes[1].animate.move_to([-3.5, -.2, 0]),
                  run_time=.8)
        poly = shapes[1][0]
        verts = [tuple(v[:2]) for v in poly.get_vertices()]
        cen = np.array([poly.get_center() + np.array([x, y, 0]) for x in np.arange(-1.5, 1.6, .44)
                        for y in np.arange(-1.5, 1.6, .44)])
        cen = cen[G.inside(cen[:, :2], verts)]
        disks = VGroup(*[Circle(.22, color=CUT, stroke_width=1.5, fill_color=CUT, fill_opacity=.3).move_to(c)
                         for c in cen])
        ra = M(r"\text{\'area relativa} = \frac{\text{\'area}(\operatorname{conv} P)}{\text{\'area}(C)}", 40) \
            .move_to([2.6, .3, 0])
        self.play(Write(ra), run_time=1.5)
        self.play(FadeIn(disks, lag_ratio=.02), run_time=1.2)
        self.until(t)

        # gráfico (esquemático) objetivo / cota
        t = self.voice("c6_3")
        self.play(FadeOut(VGroup(shapes[1], disks, ra)), run_time=.6)
        ax = Axes(x_range=[0, 40, 10], y_range=[1, 2.6, .5], x_length=8.5, y_length=4.3,
                  axis_config={"color": GREY, "include_numbers": True, "font_size": 22},
                  tips=False).shift(DOWN * .3 + LEFT * .6)
        xl = T("área relativa", 22, GREY).next_to(ax.x_axis, DOWN, buff=.45)
        yl = T("tour / cota inferior", 22, GREY).rotate(PI / 2).next_to(ax.y_axis, LEFT, buff=.55)
        sch = T("esquema de la Fig. 13a del artículo", 18, GREY).next_to(ax, UP, buff=.05).align_to(ax, RIGHT)
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), FadeIn(sch), run_time=1.2)
        xs = np.sort(rng.uniform(1, 38, 60))

        def cetsp_y(x):
            return 1 + (0.02 if x < 6 else min(.5, .016 * (x - 6) + .05))

        pts_c = VGroup(*[Dot(ax.c2p(x, max(1, cetsp_y(x) + rng.normal(0, .025 if x < 6 else .06))),
                             radius=.05, color=WITNESS) for x in xs])
        zone = ax.get_area(ax.plot(lambda x: 1.03, x_range=[0, 6]), x_range=[0, 6], color=WITNESS, opacity=.25)
        self.play(LaggedStart(*[FadeIn(d) for d in pts_c if ax.p2c(d.get_center())[0] < 6], lag_ratio=.1), run_time=.8)
        z_lab = T("≈ óptimo", 22, WITNESS).next_to(ax.c2p(3, 1.1), UP, buff=.1)
        self.play(FadeIn(zone), FadeIn(z_lab), run_time=.6)
        self.until(t)

        t = self.voice("c6_4")
        self.play(LaggedStart(*[FadeIn(d) for d in pts_c if ax.p2c(d.get_center())[0] >= 6], lag_ratio=.03),
                  run_time=1.5)
        line15 = DashedLine(ax.c2p(0, 1.5), ax.c2p(30, 1.5), color=WITNESS)
        l15 = M(r"+50\%", 26, WITNESS).next_to(ax.c2p(30, 1.5), RIGHT, buff=.1)
        self.play(Create(line15), Write(l15), run_time=.8)
        pts_a = VGroup(*[Dot(ax.c2p(x, 2 + rng.normal(0, .08)), radius=.05, color=BAD) for x in xs[::2]])
        self.wait(.6)
        self.play(LaggedStart(*[FadeIn(d) for d in pts_a], lag_ratio=.03), run_time=1.2)
        leg = VGroup(VGroup(Dot(color=WITNESS), T("CETSP (este artículo)", 22)).arrange(RIGHT, buff=.15),
                     VGroup(Dot(color=BAD), T("aproximación clásica", 22)).arrange(RIGHT, buff=.15)) \
            .arrange(DOWN, aligned_edge=LEFT, buff=.15).next_to(ax, RIGHT, buff=.1).shift(UP * .8)
        self.play(FadeIn(leg), run_time=.5)
        self.until(t)

        # un ejemplo: 65.35 vs 88.33
        t = self.voice("c6_5")
        self.play(FadeOut(VGroup(ax, xl, yl, sch, pts_c, pts_a, zone, z_lab, line15, l15, leg)), run_time=.6)
        base = DOWN * 2.3
        bars = VGroup()
        for i, (name, v, col) in enumerate([("este artículo", 65.35, WITNESS), ("aproximación", 88.33, BAD)]):
            b = Rectangle(width=2, height=v * .05, color=col, fill_color=col, fill_opacity=.7, stroke_width=2)
            b.move_to(np.array([-2 + 4 * i, 0, 0]) + base, aligned_edge=DOWN)
            bars.add(VGroup(b, T(name, 26).next_to(b, DOWN, buff=.2), M(f"{v}", 36).next_to(b, UP, buff=.15)))
        for bar in bars:
            self.fx("pop", -3)
            self.play(GrowFromEdge(bar[0], DOWN), FadeIn(bar[1]), run_time=.8)
            self.play(FadeIn(bar[2]), run_time=.3)
        d = M(r"-26\%", 40, WITNESS).move_to([0, 1.1, 0])
        self.fx("ding", -6)
        self.play(Write(d), run_time=.6)
        self.until(t)

        t = self.voice("c6_6")
        self.play(FadeOut(VGroup(bars, d)), run_time=.6)
        lbl = T("calidad de la cota inferior", 28, GREY).shift(UP * 1.6)
        rows = VGroup()
        for name, v, col in (("área / diámetro", .78, GREY), ("CETSP con testigos", 1.0, WITNESS)):
            b = Rectangle(width=v * 6, height=.6, color=col, fill_color=col, fill_opacity=.7, stroke_width=2)
            rows.add(VGroup(T(name, 26), b).arrange(RIGHT, buff=.3))
        rows.arrange(DOWN, aligned_edge=RIGHT, buff=.4)
        self.play(FadeIn(lbl), run_time=.4)
        for row in rows:
            self.play(FadeIn(row[0]), GrowFromEdge(row[1], LEFT), run_time=.8)
        plus = M(r"> 20\%\ \text{mejor}", 36, WITNESS).next_to(rows, DOWN, buff=.5)
        self.fx("success", -6)
        self.play(Write(plus), run_time=.8)
        self.until(t, .6)
        self.clear_all()


# ================================================================ 7. CG:SHOP y cierre

class C7Cierre(CScene):
    def construct(self):
        head = T("¿Y en CG:SHOP 2027?", 40, ACCENT).to_edge(UP, buff=.3)
        t = self.voice("c7_1")
        self.play(FadeIn(head, shift=DOWN * .2), run_time=.5)
        bound = M(r"L \;\ge\; \frac{|R| - k\,|C|}{k \cdot \text{ancho}(C)}", 48).shift(UP * .5)
        self.play(Write(bound), run_time=1.5)
        weak = T("cota de área: floja", 30, BAD).next_to(bound, DOWN, buff=.5)
        self.fx("error", -6)
        self.play(FadeIn(weak, shift=UP * .2), run_time=.6)
        self.until(t)

        # testigos discretos
        t = self.voice("c7_2")
        self.play(FadeOut(bound), FadeOut(weak), run_time=.5)
        Fd = Frame(.42, (-6.2, -3.0))
        region = {(x, y) for x in range(14) for y in range(11)
                  if not (x >= 9 and y >= 7) and not (x <= 3 and y <= 2)}
        cells = VGroup(*[Square(Fd.s).move_to(Fd(x + .5, y + .5)) for x, y in region]) \
            .set_stroke(EDGE, 1).set_fill(LAWN, 1).set_z_index(Z_LAWN)
        self.play(FadeIn(cells, lag_ratio=.002), run_time=.8)
        wit = [(1, 9), (7, 9), (12, 5), (7, 4), (1, 4), (12, 1)]
        wmob = VGroup(*[Square(Fd.s).move_to(Fd(x + .5, y + .5)) for x, y in wit]) \
            .set_stroke(WHITE, 2).set_fill(WITNESS, 1).set_z_index(Z_PATCH)
        self.fx("pop", -3)
        self.play(LaggedStart(*[FadeIn(m, scale=1.5) for m in wmob], lag_ratio=.15), run_time=1.2)
        # cortador 3x3 centrado: posiciones que cubren la celda (x,y) = esquinas (x-1..x+1, y-1..y+1) desplazadas
        cand = VGroup()
        for x, y in wit:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand.add(Dot(Fd(x + .5 + dx, y + .5 + dy), radius=.045, color=ACCENT))
        cand.set_z_index(Z_LABEL)
        self.play(FadeIn(cand, lag_ratio=.01), run_time=1)
        # tour que visita un punto de cada grupo (camino en la retícula)
        order = [(2, 8), (6, 8), (11, 6), (11, 2), (8, 5), (2, 5)]
        lattice = []
        for (ax_, ay), (bx, by) in zip(order, order[1:] + order[:1]):
            lattice += [Fd(ax_ + .5, ay + .5), Fd(bx + .5, ay + .5)]
        tour = VMobject(color=CUT, stroke_width=4).set_points_as_corners(lattice + [lattice[0]]).set_z_index(Z_CUTTER)
        self.play(Create(tour), run_time=2.2)
        gt = M(r"L \;\ge\; \text{GTSP}(\text{testigos})", 40, WITNESS).move_to([3.6, .8, 0])
        gt2 = T("visitar un punto de cada grupo", 24, GREY).next_to(gt, DOWN, buff=.25)
        self.fx("ding", -6)
        self.play(Write(gt), FadeIn(gt2), run_time=1.2)
        self.until(t)

        # resumen
        t = self.voice("c7_3")
        self.clear_all(.7)
        items = [
            ("1", "Los tours óptimos son rectos", r"\text{sin arcos}", CUT),
            ("2", "pero pueden ser irracionales", r"p_y = \tfrac{\sqrt3}{2}", BAD),
            ("3", "Testigos + CETSP", r"\text{LB} \le \text{OPT} \le \text{UB}", WITNESS),
        ]
        rows = VGroup()
        for n, txt, tex, col in items:
            num = VGroup(Circle(.28, color=col, stroke_width=3), T(n, 26, col))
            num[1].move_to(num[0])
            rows.add(VGroup(num, T(txt, 30), M(tex, 36, col)).arrange(RIGHT, buff=.35))
        rows.arrange(DOWN, aligned_edge=LEFT, buff=.6).move_to(UP * .3)
        self.fx("pop")
        self.play(FadeIn(rows[0], shift=RIGHT * .3), run_time=.8)
        self.wait(1)
        self.fx("pop")
        self.play(FadeIn(rows[1], shift=RIGHT * .3), run_time=.8)
        self.until(t, .1)
        t = self.voice("c7_4")
        self.fx("pop")
        self.play(FadeIn(rows[2], shift=RIGHT * .3), run_time=.8)
        self.until(t, .2)

        t = self.voice("c7_5")
        self.play(FadeOut(rows), run_time=.6)
        fin = T("Un corte más cercano", 56, ACCENT)
        self.fx("success", -4)
        self.play(Write(fin), run_time=1.6)
        self.until(t, 1.2)
        credits = VGroup(
            T("Basado en: S. P. Fekete, D. Krupke, M. Perk, C. Rieck, C. Scheffer.", 22, GREY),
            T("A Closer Cut: Computing Near-Optimal Lawn Mowing Tours. ALENEX 2023 · arXiv:2211.05891", 22, GREY),
            T("Animación: Manim Community · Voz: edge-tts · Sonido sintetizado con NumPy", 20, GREY),
        ).arrange(DOWN, buff=.15).to_edge(DOWN, buff=.5)
        self.play(fin.animate.shift(UP * .6), FadeIn(credits), run_time=1)
        self.wait(3)
        self.play(FadeOut(fin), FadeOut(credits), run_time=1.5)
        self.wait(.5)


SCENES = ["C1Intro", "C2Rectos", "C3Irracional", "C4Testigos", "C5PrimalDual", "C6Resultados", "C7Cierre"]
