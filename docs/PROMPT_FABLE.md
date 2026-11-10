# Prompt para Fable — CG:SHOP 2027

Pégalo tal cual en una sesión nueva de Claude Code abierta en este repo.
Está escrito con los patrones de la
[Prompt library](https://code.claude.com/docs/en/prompt-library): resultado en
vez de pasos, forma de verificarse, referencias, meta medible, artefactos
adjuntos y formato de respuesta.

---

## Objetivo

Obtén el mejor algoritmo posible, con rigor matemático, para el reto CG:SHOP
2027 (*Multi-Robot Lawn Mowing for Polyominoes*), y úsalo para producir un
`submission` válido de las **250 instancias de competencia** con la menor
longitud máxima de tour que logres. Cierra el 31-ene-2027 (AoE). Tienes esta
semana de cómputo: úsala entera, pero guarda siempre lo mejor que ya tengas.

## El problema (fuente oficial; léela antes de empezar)

<https://cgshop.ibr.cs.tu-bs.de/competition/cg-shop-2027/> y sus pestañas:
`/problem-description`, `/rules`, `/instance-format`. Paquete oficial:
<https://github.com/CG-SHOP/pyutils27> (ya es dependencia; su verificador es
el árbitro).

- Entrada: región `R` (polyomino con huecos), cortadora `C` (polígono
  rectilineal simple con centro `c`), y `k ∈ {1,2,3}`.
- Salida: `k` tours cerrados rectilineales con vértices enteros. `R` debe
  quedar dentro de la unión de `C + p` para todo punto entero `p` por el que
  pasa algún tour.
- Se permite salirse de `R`, solaparse y colisionar. No hay punto de inicio.
- Objetivo: minimizar la longitud del tour más largo (distancia Manhattan).
- Puntaje de equipo: `Σ_I B(I)² / B_G(I)²`, con `B(I)` el mejor de todos los
  equipos. Cada instancia pesa igual y el cuadrado castiga fuerte: bajar 10 %
  una longitud sube ese término ≈ 23 %. Una instancia sin solución válida vale 0.
- Ojo: `docs/revision_sistematica_literatura.pdf` supone cortadora 1×1, longitud
  euclidiana y sin colisiones. Eso **no** es el reto real. Úsalo solo como
  mapa de literatura.

## Lo que ya existe (no lo reescribas; mídelo y mejóralo)

Lee `README.md`; el código está en `src/cgshop27/`.

- Instancias versionadas en `instances/test/` (75, no puntúan) e
  `instances/competition/` (250, las que puntúan). `cg27 index -j 4` crea
  `out/catalog.csv`; `cg27 gallery` las muestra y distingue por `suite`.
- Las 250 de competencia: área hasta ~7.1 M celdas, caja hasta 5244×6366,
  hasta 56 458 vértices, `k` = 1/2/3 (85/83/82), cortadoras de 3×3 a 36×36,
  algunas **no convexas** (nombre `…x10`).
- `boustrophedon` (línea base): 250/250 válidas en 3 s, brecha mediana 1.93×
  sobre la cota inferior por área.
- `fekete` (ESA 2023 + búsqueda local + refinado celda a celda): brecha mediana
  1.55× en los 75 ejemplos, **pero no escala a la competencia**:
  - `OverflowError: Python int too large to convert to C long` en
    `_blockls.piece_table`: las piezas usan máscaras de bits `int64` por bloque
    y se desbordan con bloques de lado ≥ 8 (cortadoras grandes). Falló en
    `sun0100000_1000k_1p8`, `iso252735_2982k_2l4`, `bna56769_1471k_2x10`.
  - Se queda sin memoria (15 GB) en `pla85900_7154k_3p8`.
  - Funcionó en `monalisa100k_389k_1l4` (27 s, 0.46 GB).
  Hay que arreglar o reemplazar esto: es lo primero que te cuesta puntos.
- Ya corregí un bug en la cota inferior de `catalog.max_cross_section`
  (cortadoras con muescas daban cota inválida). Mantén toda cota que uses
  *demostrablemente* válida.

## Qué quiero que entregues

1. **Piso de seguridad.** Un `submission` con las 250 válidas desde el primer
   día (`cg27 submit`), y después una versión nueva cada vez que mejore. Nunca
   se escribe una solución sin verificar; nunca empeora una instancia ya
   guardada (conserva el mejor por instancia).
2. **Un algoritmo mejor que `fekete` en toda la distribución**, no solo en las
   instancias pequeñas. Debe terminar en memoria y tiempo acotados en las 250
   (define y documenta un presupuesto por instancia). Piensa en el reparto
   entre los `k` robots como parte del problema, no como un posproceso.
3. **Rigor matemático**, en `docs/algoritmo.md`:
   - Enunciado formal y justificación de que cada solución producida es
     factible por construcción (además del verificador).
   - Cotas inferiores válidas y más fuertes que la de área (por ejemplo,
     relajación LP sobre un conjunto de testigos, estilo primal-dual de
     Fekete–Mitchell–Schmidt; o cotas por componentes y cuellos de botella).
     Demuestra cada una. Reporta la brecha *certificada* por instancia.
   - Garantía de aproximación o análisis de dónde se pierde longitud (bordes,
     huecos, esquinas, desbalance entre robots), con medidas, no suposiciones.
   - Declara qué es teoremas, qué es heurística y qué es empírico.
4. **Resultados reproducibles.** Una sola orden regenera todo desde
   `cg27 fetch`. Fija semillas. Guarda en `out/` la tabla por instancia
   (objetivo, cota, brecha, tiempo, memoria).

## Cómo verificarte (hazlo en cada iteración, no al final)

- `cg27 verify --run <run> --run baseline` debe mostrar 250/250 factibles y el
  puntaje local contra la mejor solución propia. Cualquier infeasible es un bug
  tuyo, no un dato.
- Prueba también con el verificador oficial de `pyutils27`
  (`check_for_errors`) sobre el zip final.
- Antes de gastar horas de cómputo, mide en un subconjunto representativo de
  ~20 instancias (pequeñas, enormes, `k`=1/2/3, cortadora no convexa, con muchos
  huecos, componentes sueltas) y compara contra `baseline` y `fekete`.
- Cada afirmación del tipo "esto mejora X %" debe venir con el número medido y
  el comando que lo reproduce.

## Meta medible

- 250/250 válidas, sin excepciones, con memoria < 12 GB y sin fallos.
- Menor longitud máxima que `fekete` en el mayor número posible de instancias,
  con mejora mediana ≥ 5 % sobre la mejor línea actual en el subconjunto
  representativo, y sin regresiones en pequeñas.
- Brecha certificada contra tu propia cota inferior reportada para todas.
- Prioriza por ganancia marginal: el término es `(B/B_G)²`, así que mira primero
  las instancias con mayor brecha y mayor margen de mejora por hora de cómputo.

## Cómo trabajar

- Lee primero, planea después; usa modo plan para el diseño del algoritmo y
  enséñame la propuesta antes de escribir mucho código.
- Reutiliza lo que sirve: `_tour.py` (conversión segura a tours),
  `refine.py` (acorte celda a celda), el contrato `solve(instance) ->
  CGSHOP2027Solution` de `solvers/__init__.py`.
- Si necesitas un paquete o un host nuevo, dime qué y por qué; no instales a
  ciegas. La red del entorno es limitada.
- Haz commits chicos en la rama de trabajo, con el resultado medido en el
  mensaje. No subas `out/` ni soluciones pesadas.

## Cómo quiero la respuesta final

Un resumen de una pantalla: qué algoritmo, tabla (mediana/mín/máx de brecha y
puntaje local frente a `baseline` y `fekete`), qué está demostrado y qué no, qué
instancias siguen flojas y por qué, y el siguiente paso con mayor retorno.
