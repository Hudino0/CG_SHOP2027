# Algoritmo y rigor — CG:SHOP 2027

Estado: **en curso**. Este documento separa lo que está demostrado, lo que es
heurística y lo que solo está medido. Cada número lleva la orden que lo
reproduce.

## 1. El problema

- La retícula es `Z²`. La celda `(x, y)` es el cuadrado `[x, x+1] × [y, y+1]`.
- `R` es un conjunto finito de celdas (la región). `C` es un conjunto finito
  de celdas, escrito relativo al centro de la cortadora. `k ∈ {1, 2, 3}`.
- Un tour `T` es un camino cerrado, de aristas paralelas a los ejes y vértices
  enteros. `A(T)` son los puntos enteros por los que pasa. `ℓ(T)` es su
  longitud Manhattan, que es el número de pasos unitarios.
- `k` tours son **factibles** si `R ⊆ ⋃ᵢ A(Tᵢ) ⊕ C`, con `A ⊕ C = { p + c }`.
- Objetivo: minimizar `max ℓ(Tᵢ)`. `OPT(R, C, k)` es el óptimo.

El verificador oficial calcula justo eso (`verify.py` de `pyutils27`): junta
los puntos de todos los tours y comprueba `R ⊆ A ⊕ C`. La cobertura depende
solo del conjunto de puntos, no del orden.

## 2. Estructura de las instancias (medido)

Orden: `cg27 index -j 4`, y `solvers/scale.py::lattice_pitch`.

- Las 250 instancias de competencia tienen todas las coordenadas de la región
  y de la cortadora sobre una retícula de paso `g = k!` (1, 2 o 6; 85/83/82
  instancias). En unidades de `g` ("macro-celdas") el área va de 4 008 a
  1 000 137 (mediana 25 626) y el ancho de la cortadora de 2 a 12.
- Todas las regiones son conexas. Los huecos van de 0 a 8 577 (mediana 25).
- 52 instancias tienen cortadora con muescas (forma de X, nombre `…x…`).

## 3. Factibilidad por construcción

### 3.1 Lema de levantamiento (`solvers/scale.py`)

Para un conjunto `X` de celdas gruesas, `f·X + t` son las celdas finas
`[f·i + tₓ, f·i + tₓ + f) × [f·j + t_y, f·j + t_y + f)` con `(i, j) ∈ X`.

**Lema 1.** Sean `R′, C′` conjuntos de celdas gruesas con
`R ⊆ f·R′ + o` y `f·C′ + p ⊆ C`. Si unos tours gruesos pasan por los puntos
`A′` y `R′ ⊆ A′ ⊕ C′`, entonces los tours `P ↦ f·P + (o − p)` son factibles
para `(R, C)`.

*Demostración.* Sea `z` una celda de `R`. Está en el bloque de una celda
gruesa `q ∈ R′`, y `q = a + c` con `a ∈ A′`, `c ∈ C′`. El bloque de `q` es
`f·a + o + f·c + [0, f)² = (f·a + o − p) + (f·c + p + [0, f)²)`. El primer
sumando es un punto levantado; el segundo está en `C`. Una arista paralela a
un eje se levanta a una arista paralela a ese eje que contiene las imágenes
de sus puntos enteros, así que el tour levantado pasa por `f·a + o − p`. ∎

**Corolario (caso exacto).** Con `f = g` las dos inclusiones son igualdades:
la instancia gruesa es la instancia original antes de escalarla. Lo único que
se pierde son los tours con vértices fuera de la retícula `g`; el refinador
(3.4) trabaja en la retícula fina y puede recuperarlos.

La longitud se multiplica por `f`.

### 3.2 Lema de fila y solver `lanes` (`solvers/lanes.py`)

**Lema 2.** Sea `[lo, hi]` una fila de la cortadora (intervalo de
desplazamientos en `x`) y un carril horizontal con centros `a..b` en la recta
que pone esa fila sobre una fila de la región. El carril barre exactamente
las celdas `a+lo .. b+hi` de esa fila. Por tanto una racha `u..v` queda
barrida si `a ≤ u−lo` y `b ≥ v−hi`. Si `u−lo > v−hi`, un solo centro en
`[v−hi, u−lo]` barre toda la racha.

*Demostración.* El centro `c` barre `c+lo .. c+hi`. La unión para `c = a..b`
es un intervalo porque centros consecutivos lo desplazan una celda. ∎

**Lema 2′ (filas con huecos).** Si la fila de la cortadora no es un
intervalo, sea `[lo, hi]` su envolvente y `G` su hueco más ancho. Un carril
de longitud `b − a ≥ G` barre también `a+lo .. b+hi` completo.

*Demostración.* Sea `D ⊆ [lo, hi]` la fila, con `lo, hi ∈ D`, y sea
`z ∈ [a+lo, b+hi]`. El centro `c` barre `z` si `z − c ∈ D`. Para `c = a..b`,
`z − c` recorre el intervalo `[z−b, z−a]`, de `b − a + 1 ≥ G + 1` valores.
Sea `I = [max(z−b, lo), min(z−a, hi)]`; no es vacío porque `z−a ≥ lo` y
`z−b ≤ hi`. Si `I` contiene `lo` o `hi`, contiene una celda de `D`. Si no,
`I = [z−b, z−a]` está estrictamente dentro de `(lo, hi)` y tiene `G + 1`
valores consecutivos; un hueco tiene a lo más `G`, así que `I` toca `D`. ∎

**Teorema 3 (factibilidad de `lanes`).** Las filas de la región se parten en
franjas consecutivas de a lo más `H` filas (`H` = alto de la cortadora). Cada
franja de `h` filas se asigna a `h` filas consecutivas de la cortadora, lo que
fija la recta de centros. En cada franja los carriles cumplen la condición
del Lema 2 (o 2′) para toda racha de toda fila. Un tour que recorre cada
carril de punta a punta es factible.

*Demostración.* Cada celda de `R` está en una fila, cada fila en una franja, y
en su franja la racha que la contiene queda barrida por el Lema 2 o 2′. Un
tour que recorre el carril visita todos sus centros. ∎

El programa dinámico elige la partición en franjas de menor costo (longitud
de carriles + saltos acotados + un paso entre franjas). Es **exacto para ese
modelo de costo**; el costo real depende además del enrutado, que es
heurístico (2-opt y Or-opt sobre segmentos).

### 3.3 Solver `fekete`

Las piezas de cada bloque se buscan por enumeración y se aceptan solo si su
barrido cubre las celdas del bloque (`_Pieces._cover`). Cada bloque con celdas
de la región es visitado. Si la validación falla, `_repair` añade desvíos. Es
factible por construcción en el mismo sentido, sobre la retícula gruesa, y se
levanta con el Lema 1.

### 3.4 Refinador (`solvers/refine.py`)

Estado: cada tour es su caminata paso a paso; un contador guarda, por celda,
cuántos puntos de las caminatas la barren (con multiplicidad).

**Invariante.** Toda celda de la región tiene contador `> 0`.

Movimientos y por qué conservan el invariante:

- **Atajo** y **reroute**: quitan puntos y ponen otros. Se aceptan solo si
  ninguna celda de la región baja a cero. El reroute decide si un segmento
  barre una celda con las rachas de cada fila y columna de la cortadora
  (`_seg_covers`): el centro `x` barre la celda `q` por la racha `[lo, hi]`
  si y solo si `q − x ∈ [lo, hi]`. La prueba es exacta para cualquier forma,
  también para las cortadoras en X.
- **Deriva**: un reroute de la misma longitud, elegido al azar. Mismo criterio
  de cobertura; ningún tour se alarga.
- **Ceder** y **permutar** entre tours (`_find_transfer`, `_find_exchange`):

**Lema 9 (traspaso).** Sea `A[i..j]` un tramo del tour `A`. Si `A` une
`A[i−1]` con `A[j+1]` por un camino cualquiera y otro tour `B` intercala
`A[i..j]` entre dos de sus puntos consecutivos, uniendo los extremos por
caminos cualesquiera, el conjunto de puntos visitados por todos los tours solo
crece. La solución sigue siendo factible. Lo mismo vale si a cambio `A` recibe
un tramo `B[p..q]`.

*Demostración.* Todo punto de `A[i..j]` pasa a `B`; todo punto de `B[p..q]`
pasa a `A`; los demás puntos siguen en su tour; los caminos de unión solo
añaden puntos. La cobertura depende solo de la unión de los puntos. ∎

El traspaso no acorta la suma: mueve longitud del tour más largo a otro, a
cambio de las uniones. Se acepta si el mayor de los dos tours baja.

### 3.5 Red de seguridad

Nada de lo anterior se da por bueno sin comprobar: `cg27 solve`, `cg27 best` y
`cg27 polish` pasan cada solución por el verificador oficial antes de
escribirla, y `cg27 submit --check` vuelve a leer el zip y lo verifica.

## 4. Cotas inferiores (todas demostradas)

Implementación: `catalog.lower_bound`.

Sea `h(C)` el número de rachas horizontales de `C`, `v(C)` el de rachas
verticales y `χ(C) = max(h(C), v(C))`.

**Teorema 4 (cota de área).**
`OPT(R, C, k) ≥ (|R| − k·|C|) / (k·χ(C))`.

*Demostración.* Sea `p₀, p₁, …` el recorrido paso a paso de un tour y `Sⱼ` la
unión de `C + p_t` para `t ≤ j`. `|S₀| = |C|`. Un paso `e` añade a lo sumo
`|(C + e) ∖ C|` celdas, que es el número de rachas en la dirección de `e`
(una celda nueva por cada extremo de racha), es decir `≤ χ(C)`. Un tour de
longitud `ℓ` barre entonces a lo sumo `|C| + ℓ·χ(C)` celdas. Sumando los `k`
tours, `|R| ≤ k·|C| + k·χ(C)·max ℓ`. ∎

**Teorema 5 (monotonía).** Si `C ⊆ C′`, entonces
`OPT(R, C, k) ≥ OPT(R, C′, k)`.

*Demostración.* `A ⊕ C ⊆ A ⊕ C′`: todo conjunto de tours factible para `C` lo
es para `C′`. ∎

**Corolario 6 (envolvente ortoconvexa).** Sea `Ĉ` el menor superconjunto de
`C` cuyas filas y columnas son intervalos. Entonces
`OPT(R, C, k) ≥ (|R| − k·|Ĉ|) / (k·χ(Ĉ))`.

Para las cortadoras en X, `χ(C)` llega a `1.67·ancho` mientras
`χ(Ĉ) = ancho`. Medido: en `dca1389_49k_1x12` la cota pasa de 2 731 a 4 094
(+50 %). La cota anterior no era falsa, solo floja.

**Teorema 7 (paridad).** `ℓ(T)` es par.

*Demostración.* En un camino cerrado el desplazamiento total en `x` es cero,
así que hay tantos pasos a la derecha como a la izquierda; igual en `y`. ∎

La cota usada es el máximo de las de los Teoremas 4 y 6, redondeado hacia
arriba a par.

### 4.1 Cotas que estudié y descarté (razonado, no implementado)

- **Empaquetado por ventanas** (pesos `u` en las celdas con suma `≤ 1` en cada
  rebanada que un paso puede añadir): generaliza el Teorema 4, pero en una
  región con una línea de `w` celdas dentro de `R` por cada celda no supera
  `|R|/w`. Solo gana en puntas más estrechas que la cortadora en ambos ejes.
- **Testigos con vecindades disjuntas** (estilo Fekete–Mitchell–Schmidt): en
  regiones gordas da `≈ |R|/(2w)`, la mitad de la cota de área. Solo sirve en
  regiones tipo esqueleto.
- **Relajación LP con conservación de flujo**: sin restricciones de
  conectividad su valor es la cota de área (ciclos de longitud 2 la alcanzan).
  Con cortes de subtour sería una cota tipo Held–Karp, más fuerte; requiere un
  solver LP y es el paso pendiente si se quiere certificar brechas menores.

Consecuencia honesta: la **brecha certificada** que reporto es contra la cota
de área. En regiones con borde irregular esa cota no es alcanzable, así que una
brecha de 1.15 no significa 15 % de mejora posible.

## 5. Dónde se pierde longitud (medido)

Un hecho que guía el diseño:

**Observación 8 (escalera, cortadora cuadrada).** Con una cortadora `w × w`,
todo camino monótono en `x` y en `y` (una escalera) añade exactamente `w`
celdas nuevas por paso. La cota de área es justa para cualquier escalera, no
solo para rectas.

*Demostración.* Tras un paso a la derecha la columna nueva está a la derecha
de todos los cuadrados anteriores; tras un paso hacia arriba la fila nueva
está por encima de todos. ∎

Para una cortadora en rombo no vale: en diagonal barre `w/2` por paso.

Descomposición en `bck2217_18k_1d6` (cota 3 020), con
`cg27 solve --filter bck2217_18k_1d6 --solver lanes --time-limit 10`:

| Componente | Longitud | Sobre la cota |
|---|---|---|
| Modelo del PD: carriles + saltos en franja + pasos entre franjas | 3 447 | 1.14 |
| + enrutado real (extremos desalineados, cierre) | 3 758 | 1.24 |
| − refinado en retícula | 3 642 | 1.21 |
| `fekete`, 30 s | 3 576 | 1.18 |
| `fekete` + `cg27 polish` | 3 516 | 1.16 |

Las tres primeras filas salen del campo `meta` de la solución (`estimate`,
`unrefined` y la longitud final). Con un script suelto medí además que los
carriles solos suman 3 077 (1.02 de la cota): el barrido es casi perfecto.

La pérdida está en las conexiones: cruzar huecos y concavidades dentro de una
franja (≈ 8 %), los pasos entre franjas (4 %, inevitables: son el alto de la
región) y los extremos de carril desalineados más el cierre (≈ 10 %). La
Observación 8 dice que con cortadoras casi cuadradas los extremos desalineados
se pueden absorber con pasadas en escalera paralelas al borde; ese es el
siguiente paso propuesto.

## 5.1 Lo que probé y no sirvió (medido)

Lo dejo escrito para no repetirlo.

- **Más tiempo.** `fekete` y `lanes` con 150 s en vez de 30 s:
  `bck2217_18k_1d6` 3 510 contra 3 504; `bgb4355_76k_2l3` 8 444 contra 8 444.
  En instancias chicas la búsqueda se agota en segundos.
- **Otra semilla / otro desplazamiento de rejilla.** Dispersión de 1 % a 3 %:
  16 desplazamientos a 8 s en `bck2217_18k_1d6` dan 3 470 … 3 570. Por eso
  `cg27 grind` lanza muchas corridas cortas y guarda la mejor.
- **Pasadas paralelas al borde (cebolla).** Las regiones no son gordas: la
  profundidad máxima es de 1 a 6 anchos de cortadora (`bck2217_18k_1d6`: 2.8;
  `bnd7168_28k_1p7`: 1.0) y entre 6 % y 14 % de las celdas quedan fuera de
  todo anillo. La estimación no baja de lo que ya hay.
- **Franjas por columnas (PD de dos niveles).** Dar a cada columna vertical
  su propia partición en franjas no baja el costo del modelo (entre −0.7 % y
  +2.9 % en seis instancias).
- **Re-optimización exacta de ventanas con CP-SAT** (paridad, cobertura,
  conectividad por cortes). Ventanas de 12 × 12 puntos o más no cierran en
  8 s; las de 8 × 8 se demuestran óptimas y ganan 4 de 3 576. La relajación es
  tan floja como la cota de área.
- **Óptimo exacto** de una instancia de 305 celdas: tras 900 s, CP-SAT deja
  cota 40 y solución 214 (las heurísticas dan 92). No sirve de calibración.

Lectura: el desperdicio principal es barrer fuera de la región (mediana
+26 % de área en las mejores soluciones; el solape es +6 %), y con rasgos del
tamaño de la cortadora ese desperdicio es en buena parte estructural.

## 6. Qué es qué

| Afirmación | Tipo |
|---|---|
| Lemas 1, 2, 2′; Teorema 3 (factibilidad) | Teorema |
| Teoremas 4, 5, 7; Corolario 6 (cotas) | Teorema |
| Observación 8, Lema 9 | Teorema |
| Partición en franjas óptima para su modelo de costo | Teorema (PD exacto) |
| Enrutado de carriles, reparto entre `k`, refinado, deriva, traspasos | Heurística (factibilidad por invariante) |
| Piezas y búsqueda local de `fekete` | Heurística (cobertura comprobada) |
| Garantía de aproximación | **No hay.** Solo brecha certificada por instancia |
| Tablas de resultados | Empírico, con orden que las reproduce |

## 7. Resultados

`cg27 verify --instances instances/competition --run <run>` escribe
`out/verdicts.json` con objetivo, cota y brecha certificada por instancia.
La tabla con tiempo y memoria por instancia (`cg27 report`) está pendiente.
El resumen medido está en `docs/resultados.md`.
