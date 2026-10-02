"""Sintetiza la narración con edge-tts y guarda WAV + duraciones.

    python tts.py                     # narration.py         -> build/audio
    python tts.py narration_closer    # narration_closer.py  -> build/audio_closer
"""
import asyncio
import importlib
import json
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio_ffmpeg

MODULE = sys.argv[1] if len(sys.argv) > 1 else "narration"
_n = importlib.import_module(MODULE)
RATE, SCRIPT, VOICE = _n.RATE, _n.SCRIPT, _n.VOICE

SUFFIX = MODULE.removeprefix("narration").removeprefix("_")
OUT = Path(__file__).parent / "build" / ("audio_" + SUFFIX if SUFFIX else "audio")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def duration(wav: Path) -> float:
    import wave
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


async def synth(key: str, text: str) -> None:
    mp3 = OUT / f"{key}.mp3"
    wav = OUT / f"{key}.wav"
    stamp = OUT / f"{key}.txt"
    if wav.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == text:
        return
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(mp3))
    # recorta silencio inicial/final y pasa a WAV 48 kHz
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                    "silenceremove=start_periods=1:start_threshold=-50dB,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse",
                    "-ar", "48000", "-ac", "2", str(wav)], check=True)
    mp3.unlink()
    stamp.write_text(text, encoding="utf-8")
    print("tts", key)


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for key, text in SCRIPT.items():
        await synth(key, text)
    durs = {k: round(duration(OUT / f"{k}.wav"), 3) for k in SCRIPT}
    (OUT / "durations.json").write_text(json.dumps(durs, indent=1))
    print(f"total narración: {sum(durs.values()):.1f} s")


if __name__ == "__main__":
    asyncio.run(main())
