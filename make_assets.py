"""Build the game's pictures from raw_art/ with Pillow.

Run:  python make_assets.py
raw_art/ is never changed.  assets/ can be deleted and rebuilt at any time.
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw_art"
OUT = ROOT / "assets"
SCALE = 3


def scale_nearest(image):
    return image.resize(
        (image.width * SCALE, image.height * SCALE), Image.Resampling.NEAREST
    )


def tint_gem(source, dark, light):
    """Turn grey pixels into a coloured crystal, keeping the alpha."""
    image = source.convert("RGBA")
    pixels = image.load()
    values = []
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if a:
                values.append(0.299 * r + 0.587 * g + 0.114 * b)
    low = min(values) if values else 0.0
    high = max(values) if values else 255.0
    span = max(1.0, high - low)
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, a = pixels[x, y]
            if not a:
                continue
            brightness = 0.299 * r + 0.587 * g + 0.114 * b
            shade = (brightness - low) / span
            pixels[x, y] = (
                int(dark[0] + (light[0] - dark[0]) * shade),
                int(dark[1] + (light[1] - dark[1]) * shade),
                int(dark[2] + (light[2] - dark[2]) * shade),
                a,
            )
    return image


def main():
    OUT.mkdir(exist_ok=True)
    gem = Image.open(RAW / "gem.png")

    for path in sorted(RAW.glob("*.png")):
        if path.name == "gem.png":
            continue
        image = Image.open(path)
        scale_nearest(image).save(OUT / path.name)

    blue = tint_gem(gem, (40, 130, 255), (190, 245, 255))
    pink = tint_gem(gem, (220, 60, 140), (255, 205, 230))
    scale_nearest(blue).save(OUT / "gem_blue.png")
    scale_nearest(pink).save(OUT / "gem_pink.png")

    print("Wrote", len(list(OUT.glob("*.png"))), "pictures to", OUT)


if __name__ == "__main__":
    main()
