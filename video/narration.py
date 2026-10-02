"""Guion del video. Cada clave es una frase que se sintetiza en build/audio/<clave>.wav."""

VOICE = "es-MX-JorgeNeural"
RATE = "+0%"

SCRIPT = {
    # 1. El problema
    "n1_1": "Imagina que tienes que cortar el césped de un jardín con esta forma.",
    "n1_2": "Tu cortadora es un disco de diámetro uno. Todo lo que toca el disco, queda cortado.",
    "n1_3": "La pregunta es muy simple: ¿cuál es el recorrido cerrado más corto que corta todo el jardín?",
    "n1_4": "Dicho de otra forma: buscamos el tour más corto que pase a distancia, como mucho, un medio, de cada punto de la región.",
    "n1_5": "Se parece al problema del viajante, donde hay que visitar unas cuantas ciudades.",
    "n1_6": "Pero aquí, cada punto del jardín es una ciudad. Hay infinitas. Y el camino puede ir por donde quiera.",
    "n1_7": "Por eso es NP-difícil, y durante treinta años nadie ha sabido calcular soluciones exactas.",
    "n1_8": "Este artículo de Fekete y sus coautores, de dos mil veintitrés, explica por qué. Y a partir de esa explicación, construye un algoritmo.",
    # 2. La mala noticia: álgebra
    "n2_1": "Empecemos por la mala noticia, con el caso más sencillo posible: un cuadrado de dos por dos.",
    "n2_2": "Para cortar cada esquina, el centro del disco tiene que tocar este círculo de radio un medio.",
    "n2_3": "Y para cortar el centro del cuadrado, tiene que volver a pasar cerca del medio.",
    "n2_4": "Por simetría, basta con estudiar un cuarto. El camino entra por abajo, sube una pequeña distancia, delta...",
    "n2_5": "...se desvía para tocar el círculo de la esquina, y sale por la derecha.",
    "n2_6": "¿Cuánto debe valer delta? Si lo movemos, la longitud cambia. El mejor punto de contacto es donde una elipse, con focos en los dos extremos, apenas roza el círculo.",
    "n2_7": "El mínimo está en delta, aproximadamente cero coma uno seis ocho. Cada cuarto mide uno coma tres cero nueve, y el tour completo, unos cinco coma dos tres cinco.",
    "n2_8": "Pero aquí viene la sorpresa. Delta no es un número bonito. Es la raíz de este polinomio de grado dieciséis.",
    "n2_9": "Los autores reducen el polinomio módulo tres números primos, y los grados de los factores demuestran que su grupo de Galois es el grupo simétrico, S dieciséis.",
    "n2_10": "Y S dieciséis no es resoluble. Igual que con la ecuación de quinto grado, eso significa que no existe ninguna fórmula, con sumas, productos y raíces, que dé el valor de delta.",
    "n2_11": "Conclusión: incluso para un simple cuadrado, el tour óptimo no se puede escribir de forma exacta. El problema es algebraicamente difícil.",
    # 3. Píxeles y giros
    "n3_1": "Ahora, la buena idea. Muchas regiones reales se pueden aproximar con cuadraditos de lado uno. Esto se llama un poliominó, y cada cuadradito es un píxel.",
    "n3_2": "Si la cortadora fuera un cuadrado, todo sería fácil: basta con visitar el centro de cada píxel. Es el problema del viajante sobre la cuadrícula.",
    "n3_3": "Con un disco, en línea recta, tampoco hay problema: al cruzar un píxel por el medio, lo corta entero.",
    "n3_4": "El problema son los giros. Si el disco gira justo en el centro, la esquina de afuera queda sin cortar.",
    "n3_5": "Es la misma lección que el cuadrado de dos por dos: los giros cuestan.",
    # 4. Piezas de rompecabezas
    "n4_1": "La solución son piezas de rompecabezas. Cada píxel se entra y se sale por el punto medio de un lado. Y solo hay tres formas de atravesarlo.",
    "n4_2": "Recto, con longitud uno.",
    "n4_3": "Un giro de noventa grados. El camino se desvía para tocar el círculo de la esquina. Longitud: uno coma tres dos seis.",
    "n4_4": "Y una vuelta en U, con longitud uno coma seis uno uno.",
    "n4_5": "Así, cada giro cuesta un extra, tau, de más o menos cero coma tres tres. El costo de un tour es su longitud, más tau por el número de giros.",
    "n4_6": "Con esto demuestran que, a partir de cualquier tour en la cuadrícula de longitud L, se obtiene un tour válido de longitud a lo sumo L por uno más tau. Para poliominós simples, eso da una aproximación de uno coma cinco nueve, mejor que las conocidas.",
    # 5. El algoritmo
    "n5_1": "El algoritmo práctico tiene tres pasos.",
    "n5_2": "Paso A: calcular un buen tour del viajante por los centros de los píxeles. Por ejemplo, con Concorde.",
    "n5_3": "Si lo recorremos con el disco, en cada giro queda una esquina sin cortar.",
    "n5_4": "Paso B: cambiar cada visita por su pieza de rompecabezas. Las esquinas sin cortar desaparecen, y el tour ya es válido.",
    "n5_5": "Paso C: reducir los giros. Se elige una ventana pequeña del tour, se resuelve un programa entero solo ahí dentro, y se repite muchas veces. Esto se llama búsqueda en vecindarios grandes.",
    "n5_6": "Menos giros, tour más corto.",
    # 6. Resultados
    "n6_1": "¿Y funciona? El método clásico usa una cuadrícula más fina, con píxeles que caben dentro del disco. Así nunca hay que preocuparse por los giros... pero se puede desperdiciar hasta un cuarenta y uno por ciento.",
    "n6_2": "Solo con las piezas de rompecabezas, los tours son un veintisiete por ciento más cortos en poliominós. Y optimizando los giros, se gana otro cinco por ciento.",
    "n6_3": "Además, superan los mejores resultados anteriores, en instancias hasta veinte veces más grandes.",
    # 7. Cierre
    "n7_1": "Resumiendo. El tour óptimo es imposible de escribir, incluso para un cuadrado.",
    "n7_2": "Pero entender por qué, es decir, entender que los giros cuestan, lleva directamente a un algoritmo sencillo y muy bueno.",
    "n7_3": "Del álgebra, a los algoritmos.",
}
