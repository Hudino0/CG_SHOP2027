"""Guion del video "A Closer Cut" (arXiv:2211.05891). Cada clave se sintetiza en build/audio_closer/<clave>.wav."""

VOICE = "es-MX-JorgeNeural"
RATE = "+0%"

SCRIPT = {
    # 1. Introducción
    "c1_1": "La semana pasada vimos cómo cortar el césped de un poliominó, una región hecha de cuadraditos.",
    "c1_2": "Hoy volvemos al problema original: una región poligonal cualquiera, con lados en cualquier dirección, y un disco cortador de radio r.",
    "c1_3": "Buscamos el tour cerrado más corto que pase a distancia r, como mucho, de cada punto del polígono.",
    "c1_4": "Este problema mezcla tres problemas famosos por lo difíciles que son: el viajante, cubrir una región con discos, y el problema de la galería de arte.",
    "c1_5": "Hasta este artículo, lo mejor que se sabía era una aproximación teórica, con un factor de unos tres coma cuatro seis. Y nadie sabía cuánto se alejaba una solución concreta del óptimo.",
    "c1_6": "Este artículo, de Fekete, Krupke, Perk, Rieck y Scheffer, da el primer método práctico que calcula, a la vez, una solución, y una garantía de qué tan cerca está del óptimo.",
    # 2. Los tours óptimos son rectos
    "c2_1": "Primer resultado teórico: un tour óptimo está hecho sólo de segmentos rectos. Nunca tiene curvas.",
    "c2_2": "La idea de la prueba: supongamos que el tour tiene un arco curvo. El disco, al recorrerlo, barre esta franja.",
    "c2_3": "La franja tiene un lado convexo, el de afuera de la curva.",
    "c2_4": "Si alguna parte de ese lado convexo ya la cubre otro tramo del tour, podemos cambiar el arco por una cuerda recta. El tour se acorta, y todo sigue cubierto.",
    "c2_5": "Los autores muestran que en un tour óptimo esa situación siempre ocurre. Por lo tanto, ningún arco curvo sobrevive. Basta buscar entre polígonos.",
    # 3. Coordenadas irracionales
    "c3_1": "Segundo resultado, la mala noticia. Tomemos un triángulo con vértices racionales, y un cortador de radio uno.",
    "c3_2": "Cualquier tour tiene que tocar los tres círculos de radio uno alrededor de los vértices.",
    "c3_3": "Los dos círculos de abajo se cortan en un único punto p dentro del triángulo. Los autores prueban que p tiene que estar en el tour óptimo.",
    "c3_4": "Y su altura es la raíz de uno menos alfa medios al cuadrado. Para alfa igual a uno, es raíz de tres entre dos: un número irracional.",
    "c3_5": "Así que incluso con datos enteros, el óptimo puede necesitar coordenadas irracionales. Igual que en la galería de arte. Los autores dejan abierta la pregunta de si el problema es tan difícil como ella.",
    # 4. Testigos y CETSP
    "c4_1": "Ahora, el método práctico. La idea clave son los testigos.",
    "c4_2": "En vez de cubrir todo el polígono, elegimos unos pocos puntos, los testigos, y sólo exigimos cubrir esos.",
    "c4_3": "Cubrir un testigo es lo mismo que pasar por el disco de radio r a su alrededor. Eso es un problema del viajante con vecindarios, el close-enough TSP.",
    "c4_4": "Y aquí está el truco. Cubrir unos pocos puntos es más fácil que cubrir todo el polígono. Así que el tour óptimo de los testigos nunca es más largo que el óptimo del problema. Es una cota inferior.",
    "c4_5": "Esa cota la resuelven de forma exacta, con ramificación y acotamiento, y programación cónica de segundo orden.",
    # 5. El esquema primal-dual
    "c5_1": "El algoritmo empieza con unos quince testigos en el borde del polígono.",
    "c5_2": "Calcula su tour óptimo. Lo verde queda cubierto. Lo rojo, no.",
    "c5_3": "Para obtener una solución válida, se repara el tour: en cada región roja se ponen testigos, se calcula un pequeño tour que la cubra, y se engancha al tour principal por su punto más cercano.",
    "c5_4": "Ahora todo está cubierto. Esa longitud es una cota superior.",
    "c5_5": "Y luego se repite. Se añaden diez testigos nuevos en las regiones rojas, y se vuelve a resolver.",
    "c5_6": "Con cada iteración, la cota inferior sube, y la parte cubierta crece.",
    "c5_7": "Entre la cota inferior y la mejor cota superior queda un hueco. El óptimo está garantizado dentro de él. Esa es la ventaja del método: cada iteración da una solución y una garantía.",
    "c5_8": "Y demuestran que converge: si los testigos llenan el polígono, el área sin cubrir tiende a cero.",
    # 6. Resultados
    "c6_1": "¿Qué tal funciona? Lo probaron con polígonos de hasta dos mil vértices, de la base de datos de Salzburgo.",
    "c6_2": "Lo que más pesa no es el número de vértices, sino el área relativa: cuántas veces cabe el área del cortador en el polígono.",
    "c6_3": "Hasta un área relativa de seis, suelen encontrar el óptimo, o quedarse a menos de un tres por ciento de la cota.",
    "c6_4": "Hasta treinta, quedan como mucho un cincuenta por ciento por encima de la cota inferior. El algoritmo de aproximación clásico se queda cerca del cien por ciento.",
    "c6_5": "En este ejemplo, su tour mide sesenta y cinco coma tres, y el de la aproximación, ochenta y ocho coma tres.",
    "c6_6": "Y sus cotas inferiores son más de un veinte por ciento mejores que las que salen del área o del diámetro del polígono.",
    # 7. Conexión con CG:SHOP y cierre
    "c7_1": "¿Y para nuestro concurso? Nuestra cota inferior actual sale del área. Justo la que este artículo muestra que es floja.",
    "c7_2": "En la versión discreta, cada celda es un testigo, y cubrirla es visitar una de las pocas posiciones del cortador que la tocan. Con unas pocas celdas bien separadas, se obtiene una cota más fuerte, y sabremos cuánto nos falta de verdad.",
    "c7_3": "Resumiendo: los tours óptimos son rectos, pero pueden tener coordenadas irracionales.",
    "c7_4": "Y con testigos se cierra el problema por los dos lados: por abajo, con una cota, y por arriba, con un tour.",
    "c7_5": "Un corte más cercano.",
}
