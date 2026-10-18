# Guion para grabar

Graba **cada frase en un archivo aparte**. El nombre del archivo es la clave de la frase: `a1.m4a`, `a2.m4a`, …
Sirve cualquier formato que lea ffmpeg (`.wav`, `.m4a` del celular, `.mp3`, `.ogg`). Guarda los archivos en esta carpeta (`video/corto/grabacion/`).

Consejos:

- Habla un poco más rápido que en una plática normal. El video debe durar menos de 2 minutos.
- Deja medio segundo de silencio al inicio y al final. El programa recorta el silencio.
- Graba en un cuarto sin eco, con el celular a unos 20 cm de la boca.
- Si te equivocas, vuelve a grabar sólo esa frase.
- Si no grabas una frase, el video usa la voz provisional para esa frase.

Después corre `python build.py`. La animación se ajusta sola a la duración de tu voz.

## Gancho

| Archivo | Frase |
|---|---|
| `a1` | ¿Cuántos drones harían falta para fumigar un campo entero como este? |
| `a2` | Para responder eso, primero hay que encontrar la ruta más corta que lo cubra por completo. |

## Problema

| Archivo | Frase |
|---|---|
| `b1` | El dron rocía un círculo justo debajo de él; todo lo que toca ese círculo queda cubierto. |
| `b2` | Este es el problema de cortar el césped, y es difícil: el campo tiene infinitos puntos y el dron puede moverse como quiera. |

## Simplificar

| Archivo | Frase |
|---|---|
| `c1` | El truco está en simplificar. Cubrimos el campo con cuadritos del mismo ancho que el círculo. |
| `c2` | Cada cuadrito se convierte en un punto, y unimos los puntos vecinos. Así se forma un grafo de cuadrícula. |
| `c3` | Ahora el problema es finito: pasar por todos los puntos con el recorrido más corto. El famoso problema del viajante. |

## Giros

| Archivo | Frase |
|---|---|
| `d1` | Pero el dron no es un punto. Si gira justo en el centro, una esquina se queda sin rociar. |
| `d2` | Por eso, en cada cuadrito el algoritmo elige una pieza: recto, giro o vuelta en U. |
| `d3` | En el giro, el camino se ensancha para alcanzar la esquina. Y cada giro cuesta más o menos un tercio de cuadrito extra. |

## Algoritmo

| Archivo | Frase |
|---|---|
| `e1` | Así decide el algoritmo de Fekete y sus coautores. Paso uno: un recorrido del viajante. |
| `e2` | Paso dos: elegir la pieza correcta en cada cuadrito. Así ya no queda ninguna esquina sin cubrir. |
| `e3` | Paso tres: tomar una ventana pequeña, buscar cómo girar menos y repetirlo por todo el campo. |
| `e4` | Menos giros equivalen a una ruta más corta. |

## Drones

| Archivo | Frase |
|---|---|
| `f1` | Ahora viene lo práctico. Estiramos la ruta y la medimos. |
| `f2` | Un dron recorre cierta distancia con cada batería. Partimos la ruta en tramos de ese largo y los contamos. |
| `f3` | Con eso estimamos cuántos drones o cuántas recargas hacen falta. Y como cada giro consume batería, girar menos puede ahorrar un dron entero. |

## Cierre

| Archivo | Frase |
|---|---|
| `g1` | Esto sirve para fumigar cultivos, inspeccionar con cámaras, buscar personas, o guiar robots que podan. |
| `g2` | De vuelta a nuestro campo: cada dron toma su tramo de la ruta, y entre los cuatro lo cubren todo. |
| `g3` | Simplificar el terreno, decidir bien cada giro, cubrir todo con el camino más corto. |
