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
| `a1` | ¿Cuántos drones necesitas para fumigar todo este campo? |
| `a2` | Para saberlo, primero hay que encontrar la ruta más corta que lo cubra todo. |

## Problema

| Archivo | Frase |
|---|---|
| `b1` | El dron rocía un círculo debajo de él. Todo lo que toca ese círculo queda cubierto. |
| `b2` | Los matemáticos lo llaman el problema de cortar el césped. Y es difícil: el campo tiene infinitos puntos, y el dron puede ir por donde quiera. |

## Simplificar

| Archivo | Frase |
|---|---|
| `c1` | El truco es simplificar. Cubrimos el campo con cuadritos del ancho del círculo. |
| `c2` | Cada cuadrito se vuelve un punto, y unimos a los vecinos. Esto es un grafo de cuadrícula. |
| `c3` | Ahora el problema es finito: pasar por todos los puntos con el recorrido más corto. El famoso problema del viajante. |

## Giros

| Archivo | Frase |
|---|---|
| `d1` | Pero el dron no es un punto. Si gira justo en el centro, una esquina se queda sin rociar. |
| `d2` | Por eso, en cada cuadrito el algoritmo elige una pieza: recto, giro o vuelta en U. |
| `d3` | En el giro, el camino se abre para alcanzar la esquina. Cada giro cuesta como un tercio de cuadrito extra. |

## Algoritmo

| Archivo | Frase |
|---|---|
| `e1` | Así decide el algoritmo de Fekete y sus coautores. Paso uno: un recorrido del viajante. |
| `e2` | Paso dos: la pieza correcta en cada cuadrito. Ya no queda ninguna esquina sin cubrir. |
| `e3` | Paso tres: toma una ventana pequeña, busca cómo girar menos, y repite por todo el campo. |
| `e4` | Menos giros, ruta más corta. |

## Drones

| Archivo | Frase |
|---|---|
| `f1` | Ahora lo práctico. Estiramos la ruta y la medimos. |
| `f2` | Un dron vuela cierta distancia con una batería. Partimos la ruta en tramos de ese largo, y los contamos. |
| `f3` | Eso estima cuántos drones, o cuántas recargas, hacen falta. Y como cada giro gasta batería, girar menos puede ahorrar un dron entero. |

## Cierre

| Archivo | Frase |
|---|---|
| `g1` | Sirve para fumigar cultivos, inspeccionar con cámaras, buscar personas, o robots que podan. |
| `g2` | Y el siguiente paso: probarlo en un cuadricóptero real. |
| `g3` | Simplificar el terreno. Decidir bien cada giro. Cubrir todo, con el camino más corto. |
