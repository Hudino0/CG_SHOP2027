"""Construye el video completo: voz -> efectos -> escenas -> unión -> música.

    python build.py            # 1080p30
    python build.py -q l       # borrador 480p15, rápido
    python build.py S3Pixeles  # renderiza sólo esas escenas (y vuelve a unir)
    python build.py -v closer  # el video de "A Closer Cut" (arXiv:2211.05891)
"""
import argparse
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).parent
BUILD = ROOT / "build"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
QUALITY = {"l": ("480p15", ["-ql"]), "h": ("1080p30", ["-r", "1920,1080", "--frame_rate", "30"])}
# video -> (módulo del guion, módulo de las escenas, nombre del archivo final)
VIDEOS = {
    "fekete": ("narration", "fekete", "lawn_mowing_fekete"),
    "closer": ("narration_closer", "closer", "closer_cut"),
}


def run(cmd):
    print(">", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenes", nargs="*")
    ap.add_argument("-q", default="h", choices=QUALITY)
    ap.add_argument("-v", "--video", default="fekete", choices=VIDEOS)
    args = ap.parse_args()
    script, scenes_mod, name = VIDEOS[args.video]

    run([sys.executable, "tts.py", script])
    run([sys.executable, "sfx.py"])
    sys.path.insert(0, str(ROOT))
    SCENES = __import__(scenes_mod).SCENES

    folder, flags = QUALITY[args.q]
    media = BUILD / "media"
    for sc in args.scenes or SCENES:
        run([sys.executable, "-m", "manim", *flags, "--disable_caching", "--media_dir", str(media),
             f"{scenes_mod}.py", sc])

    clips = [media / "videos" / scenes_mod / folder / f"{sc}.mp4" for sc in SCENES]
    missing = [c for c in clips if not c.exists()]
    if missing:
        print("faltan escenas:", *missing)
        return
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips))
    joined = BUILD / f"joined_{args.video}_{folder}.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])

    # música de fondo con la duración exacta
    out = subprocess.run([FFMPEG, "-i", joined], capture_output=True, text=True).stderr
    hms = out.split("Duration: ")[1].split(",")[0].split(":")
    dur = int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])
    import sfx
    music = sfx.music(dur, BUILD / f"music_{args.video}.wav")

    final = ROOT / f"{name}_{folder}.mp4"
    run([FFMPEG, "-y", "-loglevel", "error", "-i", joined, "-i", music, "-filter_complex",
         "[1:a]volume=0.11[m];[0:a][m]amix=inputs=2:duration=first:normalize=0,"
         "loudnorm=I=-16:TP=-1.5:LRA=11[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", final])
    print(f"\nlisto: {final}  ({dur / 60:.1f} min)")


if __name__ == "__main__":
    main()
