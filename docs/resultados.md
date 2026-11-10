# Resultados medidos — 250 instancias de competencia

Máquina: 4 núcleos, 15 GB. Órdenes:

```bash
cg27 index -j 4
cg27 solve -j 4 --instances instances/competition --run baseline
cg27 solve -j 4 --instances instances/competition --solver fekete --run fekete --time-limit 30
cg27 solve -j 4 --isolate --memory-gb 10 --instances instances/competition --solver lanes --run lanes --time-limit 20
cg27 best --run lanes --run fekete --run baseline --instances instances/competition
cg27 polish -j 4 --run best --instances instances/competition --time-limit 20
cg27 submit --run best --check competition
cg27 report --run baseline --run fekete --run lanes --run best
```

`cg27 campaign` encadena lo mismo. La tabla por instancia queda en
`out/results.csv`.

| Run | Válidas | Brecha mín | Mediana | Máx | Puntaje local |
|---|---|---|---|---|---|
| `baseline` | 250/250 | 1.176 | 1.828 | 3.882 | 146.14 |
| `fekete` (30 s) | 250/250 | 1.102 | 1.391 | 2.792 | 235.57 |
| `lanes` (20 s) | 250/250 | 1.099 | 1.387 | 2.358 | 242.64 |
| `best` (mejor por instancia + `polish`) | 250/250 | 1.099 | 1.361 | 2.289 | 250.00 |

La brecha es objetivo ÷ cota inferior demostrada (`docs/algoritmo.md`, §4).
El puntaje local usa la fórmula del concurso con el mejor objetivo propio
como referencia; 250 es el máximo.

`out/submission_best.zip` pasa el verificador oficial: 250/250.

## `lanes` contra `fekete` (longitud máxima, % más corta)

| Grupo | n | Mediana | Peor | Mejor | Gana |
|---|---|---|---|---|---|
| Todas | 250 | 0.39 % | −43.84 % | 27.53 % | 143 |
| Cortadora < 8 macro-celdas | 187 | 0.13 % | −43.84 % | 8.28 % | 98 |
| Cortadora ≥ 8 macro-celdas | 63 | 8.10 % | −7.83 % | 27.53 % | 45 |
| Subconjunto representativo (24) | 24 | 0.34 % | −3.84 % | 17.91 % | 15 |

`best` contra `fekete`: mediana 1.10 %, máximo 27.66 %, mejora en 208 de 250.
En el subconjunto representativo: mediana 0.62 %.

**La meta de 5 % de mejora mediana no está cumplida.** Se cumple solo en las
63 instancias de cortadora ancha.

## Presupuesto

- `fekete`: 30 s por instancia.
- `lanes`: 20 s por instancia, memoria máxima medida 2.94 GB. **Cuatro
  instancias pasan del tiempo** (175, 160, 121 y 52 s: `iso2071_2273k_2l3`,
  `iso252735_2982k_2l4`, `smo64863_1931k_2s3`, `iso5009_524k_1d4`). El
  programa dinámico y la tabla de vecinos no miran el reloj. Pendiente.

## Instancias más flojas (brecha de `best`)

`iso3131_107k_2x10` 2.29, `srpg5461_82k_1s11` 2.21, `smo4975_26k_1p9` 2.20,
`srpg41087_15k_1d7` 2.20, `smo64863_393k_3p6` 2.19, `octa6025_952k_3x9` 2.13.
Son regiones tipo fractal, con rasgos más finos que la cortadora. Ahí la cota
de área es floja y los dos solvers barren mucho fuera de la región.
