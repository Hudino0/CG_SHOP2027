"""Prepara la voz de cada frase y la línea de tiempo: build/voz/*.wav y build/timeline.json.

Si existe grabacion/<clave>.<ext> (wav, m4a, mp3, ogg...), usa tu grabación.
Si no, sintetiza una voz provisional con Piper (se descarga la primera vez).
"""
import json
import subprocess
import tarfile
import urllib.request
import wave
from pathlib import Path

import imageio_ffmpeg

import guion

ROOT = Path(__file__).parent
BUILD = ROOT / "build"
VOZ = BUILD / "voz"
REC = ROOT / "grabacion"
PIPER = BUILD / "piper"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
REL = "https://github.com/rhasspy/piper/releases/download"
# recorta silencio al inicio y al final, y deja todo en 48 kHz estéreo
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB,areverse")


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("descargando", url)
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        f.write(r.read())
    with tarfile.open(dest) as t:
        t.extractall(dest.parent, filter="data")
    dest.unlink()


def piper_ready() -> tuple[Path, Path]:
    exe = PIPER / "piper" / "piper"
    if not exe.exists():
        fetch(f"{REL}/v1.2.0/piper_amd64.tar.gz", PIPER / "piper.tgz")
    model = PIPER / f"{guion.VOZ_PIPER}.onnx"
    if not model.exists():
        fetch(f"{REL}/v0.0.2/voice-{guion.VOZ_PIPER}.tar.gz", PIPER / "voice.tgz")
    return exe, model


def recording(key: str) -> Path | None:
    found = sorted(p for p in REC.glob(f"{key}.*") if p.suffix.lower() != ".md")
    return found[0] if found else None


def make(key: str, text: str) -> str:
    wav = VOZ / f"{key}.wav"
    stamp = VOZ / f"{key}.txt"
    src = recording(key)
    sig = f"rec:{src.name}:{src.stat().st_mtime_ns}" if src else f"piper:{guion.VOZ_PIPER}:{guion.VELOCIDAD}:{text}"
    if wav.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == sig:
        return "grabación" if src else "piper"
    if src is None:
        exe, model = piper_ready()
        src = VOZ / f"{key}.raw.wav"
        subprocess.run([exe, "-m", model, "-f", src, "--length_scale", str(guion.VELOCIDAD),
                        "--sentence_silence", "0.15"],
                       input=text.encode(), check=True, capture_output=True)
        kind = "piper"
    else:
        kind = "grabación"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-af", TRIM, "-ar", "48000", "-ac", "2", wav],
                   check=True)
    if kind == "piper":
        src.unlink()
    stamp.write_text(sig, encoding="utf-8")
    print(kind, key)
    return kind


def duration(wav: Path) -> float:
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def main() -> dict:
    VOZ.mkdir(parents=True, exist_ok=True)
    REC.mkdir(exist_ok=True)
    lines, scenes, kinds = [], {}, {}
    t = guion.INICIO
    for i, (scene, frases) in enumerate(guion.ESCENAS):
        if i:
            t += guion.PAUSA_ESCENA
        s0 = t
        for j, (key, text) in enumerate(frases):
            if j:
                t += guion.PAUSA_FRASE
            kinds[key] = make(key, text)
            d = duration(VOZ / f"{key}.wav")
            lines.append({"key": key, "text": text, "scene": scene, "start": round(t, 3), "end": round(t + d, 3)})
            t += d + guion.EXTRA.get(key, 0)
        scenes[scene] = {"start": round(s0, 3), "end": round(t, 3)}
    total = t + guion.FINAL
    scenes["cierre"]["end"] = round(total, 3)
    tl = {"lines": lines, "scenes": scenes, "total": round(total, 3)}
    (BUILD / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(k == "grabación" for k in kinds.values())
    print(f"voz: {n} grabadas, {len(kinds) - n} provisionales · duración total {total:.1f} s")
    return tl


if __name__ == "__main__":
    main()
