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

### 3.4.1 Solver `anchors` (`solvers/anchors.py`)

1. **Cubierta.** Se recorren las celdas de la región en orden de barrido. Para
   la primera celda aún sin barrer se toma, entre los sellos (`C + p`) que la
   contienen, el de mayor `celdas nuevas de la región − λ · celdas nuevas
   fuera de la región`. Su centro `p` es un *ancla*. Se repite hasta que no
   queda celda sin barrer.
2. **Tour.** Las anclas son carriles de longitud cero para el enrutador de
   `lanes`.
3. **Refinado** (3.4), que aquí hace la mayor parte del trabajo.

**Teorema 10 (factibilidad de `anchors`).** El paso 1 termina y `R` queda
dentro de la unión de los sellos de las anclas; un tour que visita todas las
anclas es factible.

*Demostración.* Cada iteración barre al menos la celda que la motivó (todos
los candidatos la contienen), así que el número de celdas sin barrer baja
estrictamente y el proceso termina con cero. Las anclas son puntos del tour.
La poda posterior (`_prune`) quita un sello solo si cada una de sus celdas de
la región está en otro sello que se queda. ∎

### 3.4.2 Búsqueda de vecindario grande (`Refiner.lns`)

Un paso: (a) se elige una ventana sobre el tour más largo; (b) se calcula una
cubierta nueva de las celdas de la región en la ventana (paso 1 de `anchors`,
con `λ` al azar); (c) el tour que pasa más cerca visita cada ancla nueva con
un camino de ida y vuelta; (d) atajo y reroute sobre todos los tramos de tour
en la ventana; (e) el paso se conserva si el tour más largo bajó, o quedó
igual y bajó la suma; si no, se restaura el estado.

**Por qué conserva la factibilidad.** (c) solo añade puntos. (d) usa los
movimientos de 3.4, que no dejan ninguna celda en cero. (e) restaura tours y
contador. Como guarda extra, al final de cada llamada el contador se
reconstruye desde los tours y, si alguna celda quedara sin barrer, se deshace
la llamada entera.

Es heurística: no hay garantía de mejora, solo de no empeorar.

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
  rebanada que un paso puede añadir). Lo descarté por razonamiento y fue un
  error: medido, sube la cota en casi todas las instancias. Ahora es el
  Teorema 11 (§4.2).
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

### 4.2 Cota de área ponderada (demostrada, implementada)

Implementación: `bounds.py`, orden `cg27 bound`.

Sea `D_d = (C + d) ∖ C` el conjunto de celdas que añade un paso unitario en
la dirección `d` (una de las cuatro).

**Teorema 11 (cota de área ponderada).** Sea `u ≥ 0` un peso sobre las celdas
de `R` (cero fuera) tal que

    u(p + D_d) ≤ 1     para todo punto p de la retícula y toda dirección d,

y sea `M = max_p u(p + C)`. Entonces
`OPT(R, C, k) ≥ (u(R) − k·M) / k + 1` (cuando la cota es mayor que 1).

*Demostración.* Un tour cerrado de longitud `ℓ ≥ 1` visita `p₀, …, p_{ℓ−1}` y
vuelve a `p₀`. Las celdas que barre están en `p₀ + C` y en los conjuntos
`(pᵢ + C) ∖ (pᵢ₋₁ + C) = pᵢ₋₁ + D_d`, `i = 1 … ℓ−1`. El peso que barre es
entonces `≤ M + (ℓ − 1)`. Los `k` tours barren todo `R`, así que
`u(R) ≤ k·(M + max ℓ − 1)`. ∎

Con `u ≡ 1/χ(C)` sale el Teorema 4. El mejor `u` es el óptimo de un programa
lineal de empaquetado: maximizar `u(R)` con esas restricciones. Su dual es
cubrir `R` de forma fraccionaria con «barras» (los conjuntos `p + D_d`): un
tour es una cubierta entera por barras que además es un camino cerrado.

**Por qué gana.** Donde la región es más fina que la cortadora, un paso barre
pocas celdas de `R`, y esas celdas pueden llevar más peso. En una región
gorda `u` queda cerca de `1/χ` y la cota casi no cambia.

**Lema 12 (retícula).** Sea la instancia `(R, C)` la instancia gruesa
`(R′, C′)` escalada por `g` (todas las del concurso lo son, §2). Si `u′` es
factible para `(R′, C′)`, entonces `u = u′/g` en cada celda fina es factible
para `(R, C)`, con `u(R) = g·u′(R′)` y `M ≤ g·M′`.

*Demostración.* Un paso fino en `x` desde `p = g·P + t`, `0 ≤ t_x, t_y < g`,
añade una columna fina junto a cada extremo de fila de `C`. Esas columnas
caen en las columnas gruesas del paso grueso desde `P`, y cada una se reparte
entre dos filas gruesas: `g − t_y` celdas finas en la fila `J` y `t_y` en la
`J + 1`. Entonces
`u(p + D_d) = ((g − t_y)·u′(P + D′_d) + t_y·u′(P + (0,1) + D′_d)) / g ≤ 1`.
Igual para un paso en `y`. Un sello fino es, del mismo modo, una combinación
convexa de cuatro sellos gruesos, por `g`. ∎

Por el Lema 12 el programa se resuelve en la retícula gruesa y la cota es
`g·(u′(R′) − k·M′)/k + 1`, redondeada hacia arriba a par (Teorema 7). Por el
Teorema 5 se usa la envolvente ortoconvexa de la cortadora.

**Cálculo y certificado.** Cualquier `u` factible certifica la cota, sea
óptimo o no. Por eso basta un método de primer orden (gradiente híbrido
primal-dual de Chambolle–Pock, solo productos matriz-vector con
`scipy.sparse`): el iterado se divide por su mayor suma de fila, lo que lo
hace factible, y el iterado dual da una cota superior del óptimo que dice
cuándo parar. Medido contra el óptimo exacto de HiGHS en dos instancias: 99.9 %
del óptimo en 5 s (HiGHS: 18 s en una, sin terminar en 120 s en otra). El
certificado es numérico (coma flotante de 64 bits, con un margen de 10⁻⁹);
no está verificado en aritmética exacta.

**Corolario 13 (cubierta entera por barras; no calculada).** Sea `B*` el
menor número de barras `p + D_d` que cubren `R`, y `β` el menor número que
cubre un sello. Entonces `OPT ≥ (B* − k·β)/k + 1`, y `B* ≥ max u(R)`.

*Demostración.* Las `ℓ − 1` barras de los pasos de un tour, más `β` barras
para su primer sello, cubren lo que el tour barre. ∎

`B*` es un problema de cubierta por conjuntos; el Teorema 11 es su relajación
lineal. No lo calculo.

**Lo que esta cota no ve.** No ve la conexión: en una región tipo árbol de
pasillos finos el tour recorre cada pasillo dos veces (ida y vuelta) y la
cota cuenta una. Ahí la brecha certificada seguirá cerca de 2 aunque el tour
sea óptimo.

### 4.3 Identidad del desperdicio (demostrada, medida)

**Proposición 14.** Sea `u` factible y sea `Nᵢ` el conjunto de celdas de `R`
que el paso `i` barre por primera vez (en un orden fijo de los tours, con la
envolvente como cortadora). Entonces

    Σ_t ℓ_t  =  u(R) − Σ_t u(N_{t,0}) + k + Σ_pasos (1 − u(Nᵢ)),

y cada término `1 − u(Nᵢ)` es `≥ 0`.

*Demostración.* Cada celda de `R` está en exactamente un `Nᵢ` o un `N_{t,0}`
(primer sello del tour `t`), así que `u(R) = Σ_t u(N_{t,0}) + Σ u(Nᵢ)`. Cada
tour tiene `ℓ_t − 1` pasos que barren. `Nᵢ ⊆ pᵢ₋₁ + D_d`, luego
`u(Nᵢ) ≤ 1`. ∎

`1 − u(Nᵢ)` es el **desperdicio** del paso `i`: lo que ese paso cuesta de más
respecto de lo que la cota exige. La suma de los desperdicios es exactamente
la distancia entre el tour y la cota. Esto localiza la pérdida paso a paso,
con precios demostrados en vez de con el conteo de celdas de §5.

Medido en los tours de `best` (porcentaje de la longitud):

| Instancia | Brecha nueva | Pasos sin nada nuevo | Pasos con `u(N) < 0.5` | Pasos con `0.5 ≤ u(N) < 0.9` |
|---|---|---|---|---|
| `bck2217_18k_1d6` (gorda) | 1.120 | 2.1 % | 3.2 % | 5.2 % |
| `smo860323_6491_1d3` | 1.371 | 10.8 % | 11.1 % | 4.5 % |
| `srpg41087_15k_1d7` (fractal) | 1.718 | 5.4 % | 22.1 % | 13.9 % |

(Las columnas dan el desperdicio de cada clase de pasos.) Conclusión medida:
el traslado puro pesa poco. Casi toda la pérdida está en **pasos parciales**:
pasos cuyo frente cae en parte sobre celdas ya barridas o fuera de la región.

### 4.4 Búsqueda guiada por el desperdicio (heurística, medida)

`Refiner.set_price` recibe `u`. `lns` calcula por zona
`pasos − peso` (Proposición 14 agregada por bloques) y sortea el 70 % de sus
ventanas en proporción a ese número; el resto sigue uniforme. La
factibilidad no cambia: solo cambia dónde se prueba.

Medido (40 s de `lns` desde el tour de `best`, dos semillas, guiada contra
uniforme): `bck2217_18k_1d6` 3388/3380 contra 3386/3386;
`smo860323_6491_1d3` 3210/3212 contra 3214/3214; `smo4975_26k_1p9` 5504/5516
contra 5510/5512; `srpg41087_15k_1d7` sin cambio en ambas. La guía acepta
algo más de pasos, pero la diferencia es de décimas de punto y está dentro
del ruido. **No es una mejora demostrada ni grande.**

### 4.5 Paridad de vueltas y el constructor `zigzag`

El número de vueltas del tour alrededor de un agujero no cambia con un
movimiento dentro de una ventana que no contiene al agujero (Lema D en
`docs/fable_el_genio.md`). Un pasillo con `w < H < 2w` cuesta `X·H/w` si el
tour lo cruza una vez (dientes de través) y `2X` si lo cruza dos veces (dos
carriles). La búsqueda local no puede pasar de una opción a la otra: la
decisión es del constructor.

`solvers/zigzag.py` hace esto, en cada una de las dos orientaciones:

1. Marca los pasillos finos a lo largo de los carriles: tramo de columna en
   `(h, 2h)` y tramo de fila de al menos `3w`.
2. Construye el grafo de pasillos: los nodos son las zonas finas y las
   componentes del resto; una arista por cada contacto.
3. Conserva las zonas con dos contactos o más que no son puentes del grafo:
   están en un ciclo. Un pasillo puente se cruza siempre un número par de
   veces (Lema E), así que ahí se dejan los dos carriles.
4. Da a esas zonas carriles en la otra orientación (los dientes) y enruta
   todos los carriles juntos con la misma búsqueda de `lanes`.

Si no hay zonas, el resultado es el de `lanes`. La elección de paridad no es
exacta: donde los pasillos impares no forman un subgrafo euleriano, el
enrutado paga el traslado (el T-join de la Conjetura C).

```bash
cg27 solve --solver zigzag --run zz --instances instances/competition -j 4 --time-limit 30
```

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

## 5.2 Lo que sí sirvió (medido)

El desperdicio principal de `fekete` y `lanes` es barrer fuera de la región:
mediana +26 % de área en sus mejores soluciones; el solape es +6 %. Una
cubierta voraz por sellos que penaliza el desperdicio barre solo entre 2 % y
7 % de más (`bck2217_18k_1d6`: 1.016 contra 1.116 del tour;
`bnd7168_28k_1p7`: 1.053 contra 1.323). Ese desperdicio no es estructural.
De ahí salen dos piezas:

- **`anchors`** como tercer constructor. A 20 s y sin pulir, contra el mejor
  ya pulido: `dca1389_49k_1x12` 5 024 contra 5 418, `fjs3649_17k_1x7` 3 274
  contra 3 392, `srpg41087_15k_1d7` 4 710 contra 4 828. Pierde donde 20 s no
  bastan al refinador y en algunas instancias con `k > 1`.
- **LNS por inyección de anclas** sobre cualquier solución. `cg27 polish`,
  40 s, sobre soluciones que ya eran las mejores y estaban pulidas:
  `bck2217_18k_1d6` −2.12 %, `iso3713_144k_3l3` −4.27 %,
  `fjs3649_17k_1x7` −3.60 %, `uniform00030001_94k_2x8` −1.14 %.

Otros dos cambios con efecto grande: el reroute exacto para cortadoras en X
(hasta −10.6 %) y el traspaso entre tours (hasta −4.8 % en el tour más largo).

## 6. Qué es qué

| Afirmación | Tipo |
|---|---|
| Lemas 1, 2, 2′; Teoremas 3 y 10 (factibilidad) | Teorema |
| Teoremas 4, 5, 7; Corolario 6 (cotas) | Teorema |
| Observación 8, Lema 9 | Teorema |
| Partición en franjas óptima para su modelo de costo | Teorema (PD exacto) |
| Enrutado de carriles, reparto entre `k`, refinado, deriva, traspasos, LNS, cubierta de `anchors` | Heurística (factibilidad por invariante) |
| Piezas y búsqueda local de `fekete` | Heurística (cobertura comprobada) |
| Garantía de aproximación | **No hay.** Solo brecha certificada por instancia |
| Tablas de resultados | Empírico, con orden que las reproduce |

## 7. Resultados

`cg27 verify --instances instances/competition --run <run>` escribe
`out/verdicts.json` con objetivo, cota y brecha certificada por instancia.
`cg27 report` escribe `out/results.csv` con objetivo, cota, brecha, tiempo y
memoria por instancia.
El resumen medido está en `docs/resultados.md`.
