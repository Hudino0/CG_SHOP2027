"""Efectos de sonido y música de fondo, sintetizados con numpy (sin descargas)."""
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
OUT = Path(__file__).parent / "build" / "sfx"
rng = np.random.default_rng(7)


def write(name: str, x: np.ndarray, peak: float = 0.8) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    x = x / (np.abs(x).max() + 1e-9) * peak
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


def t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def env(n: int, a: float = 0.005, r: float = 0.05) -> np.ndarray:
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def bell(freq: float, sec: float, decay: float = 3.0) -> np.ndarray:
    tt = t(sec)
    x = sum(a * np.sin(2 * np.pi * freq * m * tt) * np.exp(-decay * m ** 0.7 * tt)
            for m, a in [(1, 1), (2, .45), (3, .2), (4.2, .1)])
    return x * env(len(tt), .003, .05)


def pluck(freq: float, sec: float) -> np.ndarray:
    """Nota tipo piano suave."""
    tt = t(sec)
    x = sum(a * np.sin(2 * np.pi * freq * m * tt + 0.3 * m) * np.exp(-(1.2 + 1.5 * m) * tt)
            for m, a in [(1, 1), (2, .5), (3, .25), (4, .12), (5, .06)])
    return x * env(len(tt), .004, .2)


def noise_band(sec, lo, hi):
    sos = butter(2, [lo, hi], btype="band", fs=SR, output="sos")
    return sosfilt(sos, rng.standard_normal(int(sec * SR)))


def make_all() -> None:
    # pop: aparece algo
    tt = t(.14)
    f = 500 + 700 * np.exp(-tt * 40)
    write("pop", np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 30) * env(len(tt)), .6)
    # click suave
    tt = t(.04)
    write("click", np.sin(2 * np.pi * 2200 * tt) * np.exp(-tt * 180), .35)
    # whoosh: transición
    sec = .7
    tt = t(sec)
    x = np.zeros(len(tt))
    for k, c in enumerate(np.linspace(300, 3000, 12)):
        seg = noise_band(sec, c * .8, c * 1.25)
        x += seg * np.exp(-((tt - sec * (k + 1) / 13) ** 2) / (2 * .06 ** 2))
    write("whoosh", x * np.sin(np.pi * tt / sec), .45)
    # ding: resultado
    write("ding", bell(1318.5, 1.6) + .6 * bell(1975.5, 1.6, 3.5), .5)
    # éxito: arpegio mayor
    notes = [1046.5, 1318.5, 1568.0, 2093.0]
    x = np.zeros(int(1.8 * SR))
    for i, fq in enumerate(notes):
        s = bell(fq, 1.8 - i * .09, 3.2)
        x[int(i * .09 * SR):int(i * .09 * SR) + len(s)] += s
    write("success", x, .5)
    # error: zumbido grave
    tt = t(.35)
    x = np.sign(np.sin(2 * np.pi * 110 * tt)) + np.sign(np.sin(2 * np.pi * 116.5 * tt))
    sos = butter(2, 900, fs=SR, output="sos")
    write("error", sosfilt(sos, x) * env(len(tt), .01, .12), .35)
    # tic tac de reloj/contador
    tt = t(.05)
    write("tick", np.sin(2 * np.pi * 1500 * tt) * np.exp(-tt * 120), .25)
    # golpe grave (revelación)
    tt = t(1.2)
    f = 90 * np.exp(-tt * 1.5) + 40
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.5) + .15 * noise_band(1.2, 60, 400) * np.exp(-tt * 8)
    write("boom", x * env(len(tt), .002, .2), .7)


def mower(sec: float) -> Path:
    """Zumbido suave de motor, de la duración pedida."""
    name = f"mower_{int(round(sec * 100))}"
    path = OUT / f"{name}.wav"
    if path.exists():
        return path
    tt = t(sec)
    wob = 1 + .02 * np.sin(2 * np.pi * 5.3 * tt)
    ph = 2 * np.pi * np.cumsum(62 * wob) / SR
    x = sum(np.sin(m * ph) / m for m in range(1, 9))
    x += .4 * noise_band(sec, 200, 1200)
    sos = butter(2, 700, fs=SR, output="sos")
    x = sosfilt(sos, x) * env(len(tt), .25, .35)
    return write(name, x, .5)


def music(sec: float, path: Path) -> Path:
    """Música ambiental tranquila: acordes + arpegio de piano suave."""
    n = int(sec * SR)
    out = np.zeros((n, 2))
    # la menor – fa – do – sol (en Hz, octava media)
    prog = [[220.0, 261.6, 329.6], [174.6, 220.0, 261.6], [196.0, 261.6, 329.6], [196.0, 246.9, 293.7]]
    bar = 4.0
    k = 0
    while k * bar < sec:
        chord = prog[k % 4]
        s0 = int(k * bar * SR)
        tt = t(bar + 2)
        pad = sum(np.sin(2 * np.pi * f * tt) + .5 * np.sin(2 * np.pi * f * 1.003 * tt) + .3 * np.sin(2 * np.pi * f * 2 * tt)
                  for f in chord)
        pad *= np.minimum(1, tt / 1.5) * np.minimum(1, np.maximum(0, (bar + 2 - tt) / 2))
        pad = pad * .05
        # bajo
        pad += .08 * np.sin(2 * np.pi * chord[0] / 2 * tt) * np.minimum(1, tt / .3) * np.exp(-tt * .4)
        e = min(n, s0 + len(tt))
        out[s0:e, 0] += pad[:e - s0]
        out[s0:e, 1] += pad[:e - s0]
        # arpegio (una nota cada medio segundo, paneo alterno)
        arp = [chord[0] * 2, chord[1] * 2, chord[2] * 2, chord[1] * 2 * 2, chord[2] * 2, chord[1] * 2, chord[0] * 4, chord[2] * 2]
        for j, f in enumerate(arp):
            st = s0 + int(j * .5 * SR)
            if st >= n or rng.random() < .25:
                continue
            p = pluck(f, 2.5) * .09
            e = min(n, st + len(p))
            pan = .3 if j % 2 else .7
            out[st:e, 0] += p[:e - st] * (1 - pan)
            out[st:e, 1] += p[:e - st] * pan
        k += 1
    # reverberación barata: ecos atenuados
    for d, g in [(.113, .35), (.217, .25), (.331, .18), (.47, .12)]:
        s = int(d * SR)
        out[s:, 0] += g * out[:-s, 1]
        out[s:, 1] += g * out[:-s, 0]
    fade = np.minimum(1, np.minimum(np.arange(n) / (3 * SR), (n - np.arange(n)) / (4 * SR)))
    out *= fade[:, None]
    out = out / np.abs(out).max() * .8
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype("<i2").tobytes())
    return path


if __name__ == "__main__":
    make_all()
    print("sfx listos en", OUT)
