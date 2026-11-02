"""Make the game's short sounds with only the Python standard library.

Run:  python make_sounds.py
The browser build loads the finished .wav files; it never runs this script.
"""
from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "sounds"
RATE = 22050


def envelope(i, n, attack=0.006, release=0.06):
    a = max(1, int(attack * RATE))
    r = max(1, int(release * RATE))
    if i < a:
        return i / a
    if i > n - r:
        return max(0.0, (n - i) / r)
    return 1.0


def tone(freq, duration, volume=0.4, freq_end=None, wave_kind="sine"):
    n = max(1, int(duration * RATE))
    out = []
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = freq if freq_end is None else freq + (freq_end - freq) * (i / n)
        phase += 2.0 * math.pi * f / RATE
        if wave_kind == "sine":
            value = math.sin(phase)
        elif wave_kind == "square":
            value = 1.0 if math.sin(phase) >= 0 else -1.0
        else:
            value = 2.0 * ((phase / (2.0 * math.pi)) % 1.0) - 1.0
        out.append(value * volume * envelope(i, n))
    return out


def noise(duration, volume=0.3, seed=1):
    n = max(1, int(duration * RATE))
    rng = random.Random(seed)
    return [
        rng.uniform(-1.0, 1.0) * volume * envelope(i, n, 0.002, 0.04)
        for i in range(n)
    ]


def mix(*tracks):
    length = max(len(t) for t in tracks)
    out = [0.0] * length
    for track in tracks:
        for i, value in enumerate(track):
            out[i] += value
    return out


def sequence(notes, volume=0.35, gap=0.0):
    out = []
    for freq, duration in notes:
        out.extend(tone(freq, duration, volume))
        if gap:
            out.extend([0.0] * int(gap * RATE))
    return out


def write_wav(name, samples):
    OUT.mkdir(exist_ok=True)
    peak = max(1.0, max(abs(s) for s in samples))
    scale = 0.92 / peak
    data = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s * scale)) * 32767))
        for s in samples
    )
    with wave.open(str(OUT / name), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(data)


def main():
    write_wav("hit.wav", mix(noise(0.055, 0.30, 2), tone(190, 0.06, 0.22, 90)))
    write_wav("shoot.wav", tone(980, 0.045, 0.14, 620))
    write_wav(
        "gem.wav",
        mix(sequence([(1046.5, 0.045), (1568.0, 0.07)], 0.24), noise(0.03, 0.04, 7)),
    )
    write_wav(
        "levelup.wav",
        sequence([(523.25, 0.08), (659.25, 0.08), (783.99, 0.08), (1046.5, 0.16)], 0.30),
    )
    write_wav(
        "hurt.wav",
        mix(
            tone(240, 0.22, 0.32, 90, "saw"),
            noise(0.16, 0.18, 4),
            tone(120, 0.22, 0.20, 70),
        ),
    )
    write_wav(
        "victory.wav",
        sequence(
            [(523.25, 0.10), (659.25, 0.10), (783.99, 0.10), (1046.5, 0.12), (1318.5, 0.28)],
            0.32,
        ),
    )
    write_wav(
        "gameover.wav",
        sequence([(392.0, 0.16), (329.63, 0.16), (261.63, 0.18), (196.0, 0.34)], 0.32),
    )
    print("Wrote", len(list(OUT.glob("*.wav"))), "sounds to", OUT)


if __name__ == "__main__":
    main()
