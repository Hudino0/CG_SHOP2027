# Fable el genio — los teoremas y dónde se usan

Este archivo es un índice para explicar el trabajo. Cada entrada dice **qué
se afirma**, **por qué es cierto** en una o dos frases, **qué estado tiene**
(demostrado, conjetura, medido) y **qué código lo usa**. Las demostraciones
completas están en `docs/algoritmo.md`; los números, en `docs/resultados.md`.

Notación: `R` es la región (celdas), `C` la cortadora (celdas relativas al
centro), `k` el número de tours, `w` el ancho de la cortadora, `χ(C)` el
mayor número de celdas nuevas que un paso puede añadir. `A ⊕ C` es todo lo
que barren los puntos `A`. Un tour es factible si `R ⊆ A ⊕ C`. El objetivo
es el tour más largo.

## 1. Factibilidad (por qué las soluciones siempre son válidas)

| Nombre | Enunciado corto | Por qué es cierto | Estado | Lo usa |
|---|---|---|---|---|
| Lema 1 (levantamiento) | Si se agranda la región a una retícula gruesa y se achica la cortadora, un tour factible en la retícula gruesa, escalado, es factible en la original. | Cada celda fina cae en un bloque grueso barrido; el bloque escalado cabe en `C`. | Demostrado | `solvers/scale.py` (`scaled`): envuelve a `fekete`, `lanes`, `anchors`. `cli.py` (`polish`, etapa 1). |
| Corolario (caso exacto) | Con el paso `g` propio de la instancia no se pierde nada. | Las dos inclusiones son igualdades. | Demostrado | Igual que el Lema 1. |
| Lema 2 y 2′ (fila) | Un carril horizontal con centros `a..b` barre `a+lo .. b+hi` de la fila; vale también con huecos si el carril es más largo que el hueco. | Unión de intervalos trasladados. | Demostrado | `solvers/lanes.py` (`_demands`, `_partition`). |
| Teorema 3 | La partición en franjas de `lanes` cubre toda la región. | Cada fila queda asignada a una fila de la cortadora y el Lema 2 cubre sus rachas. | Demostrado | `solvers/lanes.py` (`solve`). |
| Lema 9 (traspaso) | Pasar un tramo de un tour a otro no descubre ninguna celda. | El conjunto de puntos visitados solo crece. | Demostrado | `solvers/refine.py` (`balance`, `_trade`, `_apply_transfer`, `_apply_exchange`). |
| Teorema 10 | La cubierta voraz de `anchors` termina y un tour por todas las anclas es factible. | Cada vuelta barre al menos una celda nueva. | Demostrado | `solvers/anchors.py` (`_cover`, `solve`); `refine.py` (`lns`). |
| Invariante del refinador | Ningún movimiento deja una celda sin barrer. | Un contador exacto por celda; cada movimiento se prueba contra él. | Demostrado por construcción, y además se recuenta | `solvers/refine.py` (`Refiner`, `_recount`). |

Además, toda solución pasa por el verificador oficial antes de guardarse
(`evaluate.keep_best`), y nunca se reemplaza una mejor.

## 2. Cotas inferiores (cuánto falta, como mucho)

| Nombre | Enunciado corto | Por qué es cierto | Estado | Lo usa |
|---|---|---|---|---|
| Teorema 4 (área) | `OPT ≥ (|R| − k·|C|)/(k·χ(C))`. | Un paso añade a lo sumo `χ(C)` celdas. | Demostrado | `catalog.py` (`area_lower_bound`). |
| Teorema 5 (monotonía) | Una cortadora más grande nunca empeora el óptimo. | Lo factible para `C` lo es para `C′ ⊇ C`. | Demostrado | `catalog.py` (`lower_bound`), `bounds.py`. |
| Corolario 6 (envolvente) | La cota de área vale con la envolvente ortoconvexa de `C`. | Teoremas 4 y 5. | Demostrado | `catalog.py` (`orthoconvex_hull`). |
| Teorema 7 (paridad) | Todo tour tiene longitud par. | Tantos pasos a la derecha como a la izquierda; igual arriba y abajo. | Demostrado | `catalog.py`, `bounds.py` (redondeo a par). |
| Observación 8 (escalera) | Con cortadora cuadrada, una escalera añade `w` celdas por paso, igual que una recta. | Cada paso añade una fila o una columna entera. | Demostrado | Justifica los movimientos `reroute` y `drift` de `refine.py`. |
| **Teorema 11 (área ponderada)** | Si un peso `u ≥ 0` cumple que ningún paso añade peso mayor que 1, entonces `OPT ≥ (u(R) − k·M)/k + 1`, con `M` el mayor peso de un sello. | Un tour de `ℓ` pasos barre peso `≤ M + ℓ − 1`. | Demostrado | `bounds.py` (`weights`, `weighted_bound`), orden `cg27 bound`, `cg27 report`. |
| **Lema 12 (retícula)** | El peso de la instancia gruesa, dividido por `g`, es factible en la fina. | Un paso fino es combinación convexa de dos pasos gruesos. | Demostrado | `bounds.py` (el programa se resuelve en la retícula gruesa). |
| **Corolario 13 (barras)** | El menor número de «barras» que cubren `R` también acota el óptimo; el Teorema 11 es su relajación lineal. | Los pasos de un tour son una cubierta por barras. | Demostrado; no se calcula | Ninguno todavía. |
| **Proposición 14 (desperdicio)** | La longitud total es `u(R)` más una constante más la suma de `1 − u(celdas nuevas)` por paso. | Cada celda se cuenta una vez, en el paso que la barre primero. | Demostrado | `refine.py` (`set_price`, `_waste`, sorteo de ventanas en `lns`); `cli.py` (`polish`). |

Cómo se calcula el Teorema 11: gradiente híbrido primal-dual
(Chambolle–Pock) con `scipy.sparse`. El iterado se divide por su mayor suma
de fila y queda factible; el dual dice cuándo parar. El certificado es
numérico (coma flotante), no exacto.

## 3. Estructura de los tours (qué forma conviene)

Girar es gratis en este modelo. Por eso el desperdicio solo viene de
(a) redondeo y (b) conexión. Un «pasillo» es una zona de ancho `H` y
largo `X`.

| Nombre | Enunciado corto | Por qué es cierto | Estado | Lo usa |
|---|---|---|---|---|
| **Lema A (carriles a lo largo)** | Carriles a lo largo de un pasillo cuestan `⌈H/w⌉·X`; la cota pide `X·H/w`. La razón es `⌈H/w⌉·w/H`. | Cuenta directa de carriles. | Demostrado | Motiva `_comb_cover`. |
| **Teorema B (peine)** | En un rectángulo con `H ≥ 2w` y `w | X` hay un tour cerrado de longitud `X·H/w + O(w)`: un carril de vuelta junto a una pared y un zigzag de través con dientes de largo `H − 2w`. Iguala la cota. | Cada paso añade una barra entera nueva: desperdicio cero en la Proposición 14. | Demostrado para rectángulos | `refine.py` (`_comb_cover`). |
| Consecuencia | El redondeo solo existe en la dirección perpendicular a los carriles. De través es `≤ w` en total. | Lema A y Teorema B. | Demostrado para rectángulos | `_comb_cover` prueba las dos orientaciones. |
| Costo de fase | Con paredes irregulares, una orientación y una fase cuestan `Σ franjas (extensión + conector)`. Se calcula exacto para las `2w` opciones. | Definición. | Fórmula exacta; que el tour final la alcance es heurístico | `refine.py` (`_comb_cover`). |
| **Conjetura C (T-join)** | Un pasillo con `H < 2w` no admite ida y vuelta eficiente. Sobre el grafo de pasillos, el óptimo es la cota más un T-join de peso mínimo: se duplican solo los pasillos finos necesarios para que todo grado sea par. | Falta demostrar. | **Conjetura** | Ninguno todavía. |

## 4. Qué está medido y qué no

- La cota del Teorema 11 sube en 235 de 250 instancias (mediana +1.3 %,
  máximo +30 %). Brecha mediana de `best`: 1.237; máxima: 1.716.
- Proposición 14 medida en tres tours: el traslado vacío es 2–11 % de la
  longitud; el resto de la pérdida son pasos parciales.
- Sorteo de ventanas por desperdicio: ganancia dentro del ruido.
- Peine (`_comb_cover`): una prueba, 6 instancias, 60 s, 2 semillas, desde el
  tour de `best` (longitud del tour más largo; menos es mejor):

| Instancia | Tipo | Inicio | Actual s1 | Actual s2 | Peine s1 | Peine s2 |
|---|---|---|---|---|---|---|
| `bck2217_18k_1d6` | gorda, k=1 | 3388 | 3388 | 3388 | 3384 | 3386 |
| `bva2144_231k_2d5` | gorda, k=2 | 12444 | 12444 | 12436 | 12444 | 12440 |
| `smo1523_400k_3x3` | gorda, k=3 | 8460 | 8412 | 8400 | 8400 | 8376 |
| `smo4975_26k_1p9` | fractal, k=1 | 5530 | 5502 | 5498 | 5498 | 5502 |
| `iso3131_107k_2x10` | fractal, k=2 | 5292 | 5284 | 5280 | 5264 | 5272 |
| `smo64863_393k_3p6` | fractal, k=3 | 7404 | 7404 | 7392 | 7368 | 7380 |

  El peine es igual o mejor en la media de 5 de 6 instancias, pero la
  diferencia (0.0–0.4 %) es del mismo tamaño que la diferencia entre
  semillas. **Está dentro del ruido.** Por eso `Refiner.comb` está apagado
  por defecto y ninguna solución guardada cambió con esta prueba.

## 5. Lo que queda abierto

1. Demostrar o refutar la Conjetura C y construir desde el T-join.
2. Teorema B con paredes irregulares: acotar el exceso por la rugosidad.
3. Una cota que vea la conexión (cortes de subtour), para saber si la brecha
   1.7 de las regiones fractales es margen real.
