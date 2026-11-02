"""Convert the WAV files made by make_sounds.py into OGG for the browser.

make_sounds.py uses only the standard library.  Browsers/pygbag prefer OGG,
so this small build tool uses soundfile (pip install soundfile) once.
"""
from pathlib import Path
import soundfile as sf

ROOT = Path(__file__).resolve().parent
SOUNDS = ROOT / "sounds"


def main():
    for wav in sorted(SOUNDS.glob("*.wav")):
        data, rate = sf.read(wav, always_2d=False)
        target = wav.with_suffix(".ogg")
        sf.write(target, data, rate, format="OGG", subtype="VORBIS")
        wav.unlink()
        print("wrote", target.name)


if __name__ == "__main__":
    main()
