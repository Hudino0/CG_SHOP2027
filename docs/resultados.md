# Resultados medidos — 250 instancias de competencia

Máquina: 4 núcleos, 15 GB. Estado: 13-nov-2026, después de tres rondas
largas de `polish` (semillas 21, 22, 23), dos rondas de arranques nuevos y
la cota de área ponderada. Los archivos medidos están en `results/`.

## Cómo se regenera

```bash
cg27 campaign -j 4                 # índice, baseline, fekete, lanes, anchors, polish, zip, tabla
cg27 polish -j 4 --run best_coarse --into best --coarse-into best_coarse \
     --instances instances/competition --time-limit 60 --time-max 600 --seed 21
cg27 submit --run best --check competition
cg27 report --run baseline --run fekete --run lanes --run round_anchors --run best
```

`campaign` da el punto de partida (brecha mediana 1.310). La orden `polish`
es una ronda larga: 60 s por instancia chica y hasta 600 s por instancia
grande; 2 h 12 min por ronda. Se repite con otra semilla: `polish`
nunca empeora una instancia guardada. La tabla por instancia (objetivo,
cota, brecha, tiempo, memoria) queda en `out/results.csv`.

## Tabla general

La brecha es objetivo ÷ mejor cota inferior demostrada. Desde el 13-nov la
cota es el máximo de la cota de área y la **cota de área ponderada**
(`docs/algoritmo.md`, Teorema 11; `cg27 bound`).

| Run | Válidas | Brecha mín | Mediana | Máx | Puntaje local |
|---|---|---|---|---|---|
| `baseline` | 250/250 | 1.172 | 1.790 | 3.331 | 128.41 |
| `fekete` (30 s) | 250/250 | 1.101 | 1.369 | 2.409 | 206.05 |
| `lanes` (20 s) | 250/250 | 1.099 | 1.364 | 1.991 | 211.82 |
| `best` (mejor por instancia + `polish` con LNS) | 250/250 | 1.073 | 1.241 | 1.722 | 250.00 |

Con solo la cota de área, `best` tenía brecha 1.075 / 1.268 / 2.053: los
tours son los mismos, lo que mejoró es el certificado. 87 instancias tienen
brecha certificada menor que 1.2 y 13 menor que 1.1.

El puntaje local usa la fórmula del concurso, Σ (B/B_G)², con el mejor
objetivo propio como referencia; 250 es el máximo.

`results/submission_best.zip` pasa el verificador oficial
(`cg27 submit --run best --check competition`): 250/250.

Evolución de la brecha mediana de `best` (contra la cota de área): 1.361
(mejor de `fekete`/`lanes` + refinador) → 1.350 (una ronda de `grind`) →
1.310 (`anchors` + LNS corto) → 1.280 → 1.272 → 1.268 (tres rondas largas de
LNS; ganancia mediana por ronda 1.63 %, 0.44 %, 0.24 %: el pulido se satura).

## La cota de área ponderada (medida en las 250)

```bash
cg27 bound -j 4      # 250 instancias, 4 núcleos; la más lenta 627 s
```

| | Mín | Mediana | Máx |
|---|---|---|---|
| Cota ponderada ÷ cota de área | 1.000 | 1.013 | 1.302 |
| Lo que el óptimo del programa lineal añadiría aún | — | 0.19 % | 0.28 % |

Sube en 235 de 250 instancias y nunca baja. La mejora es chica en la mediana
(1.3 %) y grande en las regiones con rasgos finos (hasta 30 %): la brecha
máxima baja de 2.053 a 1.722. La segunda fila sale de la cota superior dual:
el método de primer orden deja menos de 0.3 % sin recoger.

## `best` contra `fekete` (longitud máxima, % más corta)

| Grupo | n | Mediana | Peor | Mejor | Gana |
|---|---|---|---|---|---|
| Todas | 250 | 7.65 % | 0.31 % | 34.23 % | 250 |
| Cortadora < 8 | 81 | 6.27 % | 0.31 % | 14.92 % | 81 |
| Cortadora ≥ 8 | 169 | 8.21 % | 0.87 % | 34.23 % | 169 |
| k = 1 | 85 | 7.52 % | 0.31 % | 33.51 % | 85 |
| k = 2 | 83 | 6.50 % | 0.87 % | 32.09 % | 83 |
| k = 3 | 82 | 8.22 % | 1.78 % | 34.23 % | 82 |
| Subconjunto representativo (24) | 24 | 8.13 % | 2.47 % | 32.09 % | 24 |

El ancho de la cortadora está en celdas finas. `best` contra `baseline`:
mediana 28.63 %, peor 4.31 %, mejor 61.35 %.

**La meta de 5 % de mejora mediana sobre la mejor línea anterior (`fekete`)
está cumplida**: 7.65 % en las 250 y 8.13 % en el subconjunto de 24.

Los solvers solos, sin `polish` largo, contra `fekete` (mediana de las 250):
`lanes` 0.39 % (gana 143), `anchors` 3.17 % (gana 172). Ninguno de los dos
gana en todas: el peor caso de `anchors` es −35.89 %. Por eso la campaña
guarda el mejor por instancia.

## Presupuesto

- `fekete`: 30 s por instancia.
- `lanes`: 20 s por instancia, memoria máxima 2.94 GB.
- `anchors`: 8 s a 60 s según el tamaño, memoria máxima 0.45 GB.
- `polish` largo: 60 s a 600 s por instancia, memoria máxima 1.10 GB.
- Todo queda muy por debajo de 12 GB.

## Instancias más flojas (brecha de `best`, cota nueva)

`smo4975_26k_1p9` 1.72, `smo64863_393k_3p6` 1.72, `srpg41087_15k_1d7` 1.72,
`srpg5461_82k_1s11` 1.70, `srpg2991_27k_1l5` 1.69, `octa6025_3600k_3p12` 1.69.

Son regiones tipo fractal, con rasgos más finos que la cortadora. El tour ahí
es casi un viajante sobre una nube de puntos. La cota no ve la conexión
(ida y vuelta por pasillos finos), así que la brecha alta no prueba que el
tour sea malo.

Brecha mediana por número de cortadoras: k = 1: 1.233, k = 2: 1.238,
k = 3: 1.264.

## Arranques nuevos después del pulido (medido, sin ganancia útil)

```bash
cg27 grind -j 4 --suite competition --solver anchors --first 5 --rounds 2 \
     --time-limit 20 --time-max 240 --polish-limit 40 --polish-max 300
```

Dos rondas de `anchors` con semillas 5 y 6, cada una con su `polish`
(4 h 17 min en total). Mejoraron unas 35 de las 250 instancias; la brecha
mediana de `best` no cambió (1.268) y la mejora mediana contra `fekete`
pasó de 7.65 % a 7.68 %. Conclusión empírica: con este vecindario, ni más
pulido ni más arranques dan ya más de unas décimas. Para bajar más hace
falta un movimiento nuevo (por ejemplo, rehacer la partición entre tours
para k > 1 o un vecindario que mueva tramos largos) o una cota inferior
mejor para saber cuánto margen queda.
