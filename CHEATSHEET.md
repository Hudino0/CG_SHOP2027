# Cheatsheet: de una instancia a su animación

**Dónde:** el panel Terminal de la app (PowerShell). **Resultado:** se abre en tu navegador.
Escribe cada comando a mano y pulsa Enter.

## 0. Entra en la carpeta

```powershell
cd "D:\CG SHOP"
```

Pon las comillas: el nombre de la carpeta tiene un espacio.

## Los 5 pasos

| # | Comando | Qué hace | Qué debes ver |
|---|---|---|---|
| 1 | `& .\.venv\Scripts\Activate.ps1` | Activa el entorno de Python del proyecto. Así existe el comando `cg27`. | La línea empieza por `(.venv)` |
| 2 | `Get-ChildItem data\instances\test_instances1 -Name` | Lista las 75 instancias. El nombre es lo que va antes de `.instance.json`. | `pla7k_2k_2p.instance.json`, … |
| 3 | `cg27 solve --filter NOMBRE --solver boustrophedon --run prueba` | Resuelve la instancia con un método y guarda la solución, sólo si es válida. | `run 'prueba': 1/1 feasible` |
| 4 | `cg27 verify --run prueba` | Comprueba las soluciones del run y mide la distancia a la cota inferior. | `gap to area lower bound: …x` |
| 5 | `cg27 animate NOMBRE --run prueba --open` | Crea la animación y la abre en el navegador. Tarda ~20 s. | El navegador con el reproductor |

El paso 1 se hace **una vez por terminal**. Para otra instancia, repite 3, 4 y 5 cambiando `NOMBRE`.

## Las piezas del comando `solve`

| Parte | Significado |
|---|---|
| `--filter NOMBRE` | La instancia. Vale un trozo del nombre: `--filter pla7k` coge todas las que lo contienen. |
| `--solver boustrophedon` | **El método.** Hay dos: `boustrophedon` (el sencillo) y `fekete` (el del artículo, mejor y más lento). Un método nuevo se añade en `src\cgshop27\solvers\`. |
| `--time-limit 20` | Segundos por instancia. Sólo para `fekete` (por defecto 30). |
| `--run prueba` | El nombre del experimento. Es la carpeta `data\solutions\prueba\`. |

El `--run` de los pasos 4 y 5 **tiene que ser el mismo** que el del paso 3.

## Cómo leer el `gap`

`gap = tu tour más largo ÷ cota inferior`. La cota inferior es un mínimo que ninguna solución puede bajar. 1.0× sería perfecto.

- La cota es **floja**: ignora los viajes entre partes separadas. Por eso ni el óptimo llega a 1.0×.
- `verify` resume **todo el run**. Si el run tiene varias instancias, ves `min / median / max` de todas.
- En el concurso no cuenta el gap. Cuenta tu tour frente al del mejor equipo: `(mejor / tuyo)²`.

## Dónde queda cada cosa

| Qué | Dónde |
|---|---|
| Instancias | `data\instances\test_instances1\` |
| Soluciones | `data\solutions\<run>\NOMBRE.solution.json` |
| Resultados del último `verify` | `out\verdicts.json` (cada `verify` lo sobrescribe) |
| Animaciones | `out\animations\<run>\NOMBRE.html` |

Para ver la **grid graph** (los bloques que usa `fekete`, sus nodos y aristas, y los tours encima):

```powershell
cg27 grid NOMBRE --run prueba --open
```

Nodo blanco = bloque lleno, nodo amarillo = bloque parcial. La imagen queda en `out\grids\prueba\NOMBRE.png`.

Para abrir una animación que ya existe, sin volver a crearla:

```powershell
start out\animations\prueba\NOMBRE.html
```

## En el reproductor

▶ reproduce · ⏸ pausa · la barra mueve el tiempo · ◀▮ ▮▶ un frame · − + velocidad.
Cada cutter tiene un color. Lo verde ya está cortado.

## Errores frecuentes

| Ves | Causa | Arreglo |
|---|---|---|
| Windows pregunta "¿con qué app lo abro?" | Estás en **cmd**, no en PowerShell. | Usa el terminal PowerShell. En cmd: `.venv\Scripts\activate.bat` |
| `No se encuentra ningún parámetro … 'SHOP'` | Falta poner comillas en la ruta. | `cd "D:\CG SHOP"` |
| `cg27 : El término 'cg27' no se reconoce` | No activaste el entorno. | Paso 1 |
| `no solution at …` | El `--run` del paso 5 no es el del paso 3. | Usa el mismo nombre |
| `no instances found` | Falta descargar las instancias (clon nuevo). | `cg27 fetch` |
