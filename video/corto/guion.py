"""Guion del video corto (vertical). Cada clave es una frase con su propio audio.

Para grabar tu voz: graba cada frase en un archivo con el nombre de la clave
(por ejemplo grabacion/a1.m4a) y vuelve a correr build.py. Ver grabacion/LEEME.md.
"""

# (escena, [(clave, texto), ...])
ESCENAS = [
    ("gancho", [
        ("a1", "¿Cuántos drones harían falta para fumigar un campo entero como este?"),
        ("a2", "Para responder eso, primero hay que encontrar la ruta más corta que lo cubra por completo."),
    ]),
    ("problema", [
        ("b1", "El dron rocía un círculo justo debajo de él; todo lo que toca ese círculo queda cubierto."),
        ("b2", "Este es el problema de cortar el césped, y es difícil: el campo tiene infinitos puntos y el dron puede moverse como quiera."),
    ]),
    ("simplificar", [
        ("c1", "El truco está en simplificar. Cubrimos el campo con cuadritos del mismo ancho que el círculo."),
        ("c2", "Cada cuadrito se convierte en un punto, y unimos los puntos vecinos. Así se forma un grafo de cuadrícula."),
        ("c3", "Ahora el problema es finito: pasar por todos los puntos con el recorrido más corto. El famoso problema del viajante."),
    ]),
    ("giros", [
        ("d1", "Pero el dron no es un punto. Si gira justo en el centro, una esquina se queda sin rociar."),
        ("d2", "Por eso, en cada cuadrito el algoritmo elige una pieza: recto, giro o vuelta en U."),
        ("d3", "En el giro, el camino se ensancha para alcanzar la esquina. Y cada giro cuesta más o menos un tercio de cuadrito extra."),
    ]),
    ("algoritmo", [
        ("e1", "Así decide el algoritmo de Fekete y sus coautores. Paso uno: un recorrido del viajante."),
        ("e2", "Paso dos: elegir la pieza correcta en cada cuadrito. Así ya no queda ninguna esquina sin cubrir."),
        ("e3", "Paso tres: tomar una ventana pequeña, buscar cómo girar menos y repetirlo por todo el campo."),
        ("e4", "Menos giros equivalen a una ruta más corta."),
    ]),
    ("drones", [
        ("f1", "¿Qué aplicaciones tiene esto? Estiramos la ruta y la medimos."),
        ("f2", "Un dron recorre cierta distancia con cada batería. Partimos la ruta en tramos de ese largo y los contamos."),
        ("f3", "Con eso estimamos cuántos drones o cuántas recargas hacen falta. Y como cada giro consume batería, girar menos puede ahorrar un dron entero."),
    ]),
    ("cierre", [
        ("g1", "Esto sirve para fumigar cultivos, inspeccionar con cámaras, buscar personas, o guiar robots que podan."),
        ("g2", "Y en todos estos casos, el algoritmo es el mismo:"),
        ("g3", "Simplificar el terreno, decidir bien cada giro, cubrir todo con el camino más corto."),
    ]),
]

# segundos de silencio entre frases y entre escenas
PAUSA_FRASE = 0.25
PAUSA_ESCENA = 0.4
# segundos extra después de ciertas frases, para que se vea la animación
EXTRA = {"a2": 0.2, "c2": 0.3, "c3": 0.3, "d2": 0.4, "e2": 0.3, "e3": 1.1, "e4": 0.5,
         "f2": 0.4, "f3": 0.6, "g1": 1.3, "g3": 1.2}
# segundos antes de la primera frase y al final (créditos)
INICIO = 0.6
FINAL = 2.5

# velocidad de tu grabación (1 = igual; 1.2 = 20 % más rápida, sin cambiar el tono)
TEMPO_GRABACION = 1.2

# voz provisional (Piper, sin internet): sólo hasta que grabes la tuya
VOZ_PIPER = "es-carlfm-x-low"
VELOCIDAD = 0.85  # < 1 = más rápido
