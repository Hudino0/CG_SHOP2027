"""Construye el video corto vertical: voz -> datos -> cuadros -> mezcla de audio -> mp4.

    python build.py                 # video completo, 1080x1920 a 30 fps
    python build.py --stills 3 20   # sólo unas imágenes fijas (segundos) en build/stills/
    python build.py --audio         # sólo la voz y la mezcla (para la vista previa en anim.html)
"""
import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

ROOT = Path(__file__).parent
BUILD = ROOT / "build"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SR = 48000
NAME = "lawn_mowing_riso_1080x1920"
sys.path.insert(0, str(ROOT.parent))  # sfx.py del video largo
import sfx  # noqa: E402

import prep  # noqa: E402
import voz  # noqa: E402


def run(cmd, **kw):
    print(">", " ".join(map(str, cmd))[:160])
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def node_env():
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    return {**os.environ, "NODE_PATH": root}


def read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getframerate() == SR and w.getnchannels() == 2, path
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, 2)
    return x.astype(float) / 32768


def add(out: np.ndarray, x: np.ndarray, t: float, vol: float) -> None:
    s = int(t * SR)
    e = min(len(out), s + len(x))
    if s < e:
        out[s:e] += x[:e - s] * vol


def mix(tl: dict, cues: list) -> Path:
    n = int(tl["total"] * SR)
    voice = np.zeros((n, 2))
    for line in tl["lines"]:
        add(voice, read(BUILD / "voz" / f"{line['key']}.wav"), line["start"], 1.0)
    fx = np.zeros((n, 2))
    sfx.make_all()
    for c in cues:
        name = c["name"]
        path = sfx.mower(float(name.split(":")[1])) if name.startswith("hum:") else sfx.OUT / f"{name}.wav"
        add(fx, read(path), c["t"], c["vol"])
    music = read(sfx.music(tl["total"], BUILD / "musica.wav"))
    out = voice + .45 * fx + .10 * music[:n]
    out /= max(1, np.abs(out).max() / .95)
    path = BUILD / "mezcla.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())
    return path


def data(tl: dict) -> None:
    campo = (BUILD / "campo.json").read_text()
    (BUILD / "data.js").write_text(f"window.TL = {json.dumps(tl, ensure_ascii=False)};\nwindow.CAMPO = {campo};\n",
                                   encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", nargs="*", type=float)
    ap.add_argument("--audio", action="store_true")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("-j", type=int, default=os.cpu_count() or 4)
    args = ap.parse_args()

    if not (BUILD / "campo.json").exists():
        prep.main()
    tl = voz.main()
    data(tl)
    if args.stills is not None:
        run(["node", "render.cjs", "stills", *map(str, args.stills)], env=node_env())
        return
    if args.audio:
        # sólo la lista de efectos, sin renderizar cuadros
        run(["node", "-e", SFX_ONLY], env=node_env())
    else:
        run(["node", "render.cjs", "video", FFMPEG, str(args.fps), str(args.j)], env=node_env())
    audio = mix(tl, json.loads((BUILD / "sfx.json").read_text()))
    if args.audio:
        print("listo:", audio)
        return
    joined = BUILD / "video.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", BUILD / "segs.txt", "-c", "copy", joined])
    final = ROOT / f"{NAME}.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-i", joined, "-i", audio, "-af", "loudnorm=I=-15:TP=-1.5:LRA=11",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-b:a", "192k",
         "-movflags", "+faststart", "-shortest", final])
    print(f"\nlisto: {final}  ({tl['total']:.1f} s)")


SFX_ONLY = """
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => { const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.resolve('anim.html') + '?render'); await p.evaluate(() => window.READY);
  fs.writeFileSync('build/sfx.json', JSON.stringify(await p.evaluate(() => window.sfxCues()))); await b.close(); })();
"""

if __name__ == "__main__":
    main()
