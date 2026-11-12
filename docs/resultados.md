# Resultados medidos — 250 instancias de competencia

Máquina: 4 núcleos, 15 GB. Estado: 12-nov-2026, después de la primera ronda
larga de `polish`.

## Cómo se regenera

```bash
cg27 campaign -j 4                 # índice, baseline, fekete, lanes, anchors, polish, zip, tabla
cg27 polish -j 4 --run best_coarse --into best --coarse-into best_coarse \
     --instances instances/competition --time-limit 60 --time-max 600 --seed 21
cg27 submit --run best --check competition
cg27 report --run baseline --run fekete --run lanes --run round_anchors --run best
```

`campaign` da el punto de partida (brecha mediana 1.310). La orden `polish`
es la ronda larga: 60 s por instancia chica y hasta 600 s por instancia
grande; 2 h 12 min en total. Se puede repetir con otra semilla: `polish`
nunca empeora una instancia guardada. La tabla por instancia (objetivo,
cota, brecha, tiempo, memoria) queda en `out/results.csv`.

## Tabla general

| Run | Válidas | Brecha mín | Mediana | Máx | Puntaje local |
|---|---|---|---|---|---|
| `baseline` | 250/250 | 1.176 | 1.828 | 3.882 | 130.66 |
| `fekete` (30 s) | 250/250 | 1.102 | 1.391 | 2.792 | 209.80 |
| `lanes` (20 s) | 250/250 | 1.099 | 1.387 | 2.358 | 215.72 |
| `round_anchors` (8–60 s) | 250/250 | 1.109 | 1.368 | 2.180 | 223.20 |
| `best` (mejor por instancia + `polish` con LNS) | 250/250 | 1.078 | 1.280 | 2.087 | 250.00 |

La brecha es objetivo ÷ cota inferior demostrada (`docs/algoritmo.md`, §4).
El puntaje local usa la fórmula del concurso, Σ (B/B_G)², con el mejor
objetivo propio como referencia; 250 es el máximo.

`out/submission_best.zip` pasa el verificador oficial
(`cg27 submit --run best --check competition`): 250/250.

Evolución de la brecha mediana de `best`: 1.361 (mejor de
`fekete`/`lanes` + refinador) → 1.350 (una ronda de `grind`) → 1.310
(`anchors` + LNS corto) → 1.280 (ronda larga de LNS).

## `best` contra `fekete` (longitud máxima, % más corta)

| Grupo | n | Mediana | Peor | Mejor | Gana |
|---|---|---|---|---|---|
| Todas | 250 | 6.68 % | 0.17 % | 33.10 % | 250 |
| Cortadora < 8 | 81 | 5.54 % | 0.17 % | 14.38 % | 81 |
| Cortadora ≥ 8 | 169 | 7.17 % | 0.72 % | 33.10 % | 169 |
| k = 1 | 85 | 6.56 % | 0.17 % | 32.71 % | 85 |
| k = 2 | 83 | 5.84 % | 0.72 % | 31.85 % | 83 |
| k = 3 | 82 | 7.28 % | 1.35 % | 33.10 % | 82 |
| Subconjunto representativo (24) | 24 | 7.49 % | 2.30 % | 31.85 % | 24 |

El ancho de la cortadora está en celdas finas. `best` contra `baseline`:
mediana 27.96 %, peor 4.18 %, mejor 60.75 %.

**La meta de 5 % de mejora mediana sobre la mejor línea anterior (`fekete`)
está cumplida**: 6.68 % en las 250 y 7.49 % en el subconjunto de 24.

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

`iso3131_107k_2x10` 2.09, `srpg41087_15k_1d7` 2.07, `smo64863_393k_3p6`
2.05, `octa84581_128k_2l6` 2.04, `smo4975_26k_1p9` 2.04,
`srpg5461_82k_1s11` 1.99.

Son regiones tipo fractal, con rasgos más finos que la cortadora. Ahí la
cota de área es floja: la brecha alta no prueba que el tour sea malo.

Brecha mediana por número de cortadoras: k = 1: 1.275, k = 2: 1.253,
k = 3: 1.298.
