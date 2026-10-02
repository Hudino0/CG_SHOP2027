# Video: The Lawn Mowing Problem (Fekete et al., 2023)

Animación explicativa al estilo 3Blue1Brown, en español, con voz y sonido.

Herramientas (todas gratuitas): Manim Community, edge-tts (voz neural), NumPy/SciPy
(efectos y música sintetizados), FFmpeg (vía imageio-ffmpeg), LaTeX (MiKTeX).

```bash
python build.py          # 1080p30 -> lawn_mowing_fekete_1080p30.mp4
python build.py -q l     # borrador rápido 480p
python build.py S4Piezas # re-renderiza sólo una escena y vuelve a unir
```

- `narration.py` — guion (cambia el texto y se regenera sólo esa frase)
- `fekete.py` — las 7 escenas
- `sfx.py` — efectos de sonido y música de fondo
- Necesita Python ≤ 3.13 (Manim no tiene ruedas para 3.14).
