# Video corto (vertical, 1–2 min): estilo risografía

Versión para la convocatoria de video corto: 1080×1920, MP4, < 2 min.
Se basa sólo en el artículo de Fekete et al. (ESA 2023).

Estilo: impresión en risografía. Cada tinta (amarillo, verde, rosa `#e4007c`, azul)
es una capa aparte. Al final, cada capa se tiñe, pierde tinta con un grano de papel,
se desplaza unos píxeles (mal registro) y se imprime con *multiply* sobre papel crema.

```bash
python build.py                 # video completo -> lawn_mowing_riso_1080x1920.mp4
python build.py --stills 10 45  # imágenes fijas en build/stills/ (para revisar rápido)
python build.py --audio         # sólo la mezcla de audio, para la vista previa
```

Vista previa en vivo: corre `python build.py --audio` y abre `anim.html` en el navegador.

| Archivo | Qué hace |
|---|---|
| `guion.py` | El texto de cada frase, las pausas y la voz provisional. |
| `grabacion/` | Tu voz: un archivo por frase (`a1.m4a`, …). Ver `grabacion/LEEME.md`. |
| `voz.py` | Usa tu grabación o, si falta, la voz provisional (Piper, sin internet). Escribe la línea de tiempo. |
| `prep.py` | El campo: busca todos los tours y la cadena de ventanas que quita giros. |
| `anim.js`, `anim.html` | La animación en canvas. `render(t)` dibuja el segundo `t`. |
| `render.cjs` | Renderiza los cuadros con Chromium (Playwright) en paralelo. |
| `build.py` | Une todo: voz, cuadros, efectos, música y el MP4 final. |

Necesita Python con `numpy`, `scipy`, `imageio-ffmpeg`, y Node con `playwright`.
La música y los efectos se sintetizan con `../sfx.py` (sin bibliotecas externas).
