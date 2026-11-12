# Resultados medidos — 250 instancias de competencia

Máquina: 4 núcleos, 15 GB. Estado: 12-nov-2026, después de tres rondas
largas de `polish` (semillas 21, 22, 23).

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

| Run | Válidas | Brecha mín | Mediana | Máx | Puntaje local |
|---|---|---|---|---|---|
| `baseline` | 250/250 | 1.176 | 1.828 | 3.882 | 128.71 |
| `fekete` (30 s) | 250/250 | 1.102 | 1.391 | 2.792 | 206.57 |
| `lanes` (20 s) | 250/250 | 1.099 | 1.387 | 2.358 | 212.37 |
| `round_anchors` (8–60 s) | 250/250 | 1.109 | 1.368 | 2.180 | — |
| `best` (mejor por instancia + `polish` con LNS) | 250/250 | 1.075 | 1.268 | 2.053 | 250.00 |

La brecha es objetivo ÷ cota inferior demostrada (`docs/algoritmo.md`, §4).
El puntaje local usa la fórmula del concurso, Σ (B/B_G)², con el mejor
objetivo propio como referencia; 250 es el máximo. La fila de
`round_anchors` es la de la primera ronda de `anchors` (su puntaje no se
volvió a calcular contra el `best` final).

`out/submission_best.zip` pasa el verificador oficial
(`cg27 submit --run best --check competition`): 250/250.

Evolución de la brecha mediana de `best`: 1.361 (mejor de
`fekete`/`lanes` + refinador) → 1.350 (una ronda de `grind`) → 1.310
(`anchors` + LNS corto) → 1.280 → 1.272 → 1.268 (tres rondas largas de LNS;
ganancia mediana por ronda 1.63 %, 0.44 %, 0.24 %: el pulido se satura).

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

## Instancias más flojas (brecha de `best`)

`srpg41087_15k_1d7` 2.05, `iso3131_107k_2x10` 2.05, `smo64863_393k_3p6`
2.04, `octa84581_128k_2l6` 2.02, `smo4975_26k_1p9` 2.02,
`srpg5461_82k_1s11` 1.98.

Son regiones tipo fractal, con rasgos más finos que la cortadora. Ahí la
cota de área es floja: la brecha alta no prueba que el tour sea malo.

Brecha mediana por número de cortadoras: k = 1: 1.267, k = 2: 1.244,
k = 3: 1.291.
