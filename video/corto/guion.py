"""Guion del video corto (vertical). Cada clave es una frase con su propio audio.

Para grabar tu voz: graba cada frase en un archivo con el nombre de la clave
(por ejemplo grabacion/a1.m4a) y vuelve a correr build.py. Ver grabacion/LEEME.md.
"""

# (escena, [(clave, texto), ...])
ESCENAS = [
    ("gancho", [
        ("a1", "¿Cuántos drones necesitas para fumigar todo este campo?"),
        ("a2", "Para saberlo, primero hay que encontrar la ruta más corta que lo cubra todo."),
    ]),
    ("problema", [
        ("b1", "El dron rocía un círculo debajo de él. Todo lo que toca ese círculo queda cubierto."),
        ("b2", "Los matemáticos lo llaman el problema de cortar el césped. Y es difícil: "
               "el campo tiene infinitos puntos, y el dron puede ir por donde quiera."),
    ]),
    ("simplificar", [
        ("c1", "El truco es simplificar. Cubrimos el campo con cuadritos del ancho del círculo."),
        ("c2", "Cada cuadrito se vuelve un punto, y unimos a los vecinos. Esto es un grafo de cuadrícula."),
        ("c3", "Ahora el problema es finito: pasar por todos los puntos con el recorrido más corto. "
               "El famoso problema del viajante."),
    ]),
    ("giros", [
        ("d1", "Pero el dron no es un punto. Si gira justo en el centro, una esquina se queda sin rociar."),
        ("d2", "Por eso, en cada cuadrito el algoritmo elige una pieza: recto, giro o vuelta en U."),
        ("d3", "En el giro, el camino se abre para alcanzar la esquina. "
               "Cada giro cuesta como un tercio de cuadrito extra."),
    ]),
    ("algoritmo", [
        ("e1", "Así decide el algoritmo de Fekete y sus coautores. Paso uno: un recorrido del viajante."),
        ("e2", "Paso dos: la pieza correcta en cada cuadrito. Ya no queda ninguna esquina sin cubrir."),
        ("e3", "Paso tres: toma una ventana pequeña, busca cómo girar menos, y repite por todo el campo."),
        ("e4", "Menos giros, ruta más corta."),
    ]),
    ("drones", [
        ("f1", "Ahora lo práctico. Estiramos la ruta y la medimos."),
        ("f2", "Un dron vuela cierta distancia con una batería. "
               "Partimos la ruta en tramos de ese largo, y los contamos."),
        ("f3", "Eso estima cuántos drones, o cuántas recargas, hacen falta. "
               "Y como cada giro gasta batería, girar menos puede ahorrar un dron entero."),
    ]),
    ("cierre", [
        ("g1", "Sirve para fumigar cultivos, inspeccionar con cámaras, buscar personas, o robots que podan."),
        ("g2", "Y el siguiente paso: probarlo en un cuadricóptero real."),
        ("g3", "Simplificar el terreno. Decidir bien cada giro. Cubrir todo, con el camino más corto."),
    ]),
]

# segundos de silencio entre frases y entre escenas
PAUSA_FRASE = 0.25
PAUSA_ESCENA = 0.55
# segundos extra después de ciertas frases, para que se vea la animación
EXTRA = {"a2": 0.3, "c2": 0.6, "c3": 0.5, "d2": 0.5, "e2": 0.4, "e3": 2.2, "e4": 0.6,
         "f2": 1.0, "f3": 0.8, "g3": 2.4}
# segundos antes de la primera frase y al final (créditos)
INICIO = 0.6
FINAL = 3.0

# voz provisional (Piper, sin internet): sólo hasta que grabes la tuya
VOZ_PIPER = "es-carlfm-x-low"
VELOCIDAD = 0.85  # < 1 = más rápido
