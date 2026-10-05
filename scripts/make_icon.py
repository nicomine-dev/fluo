"""Genera fluo/resources/fluo.ico (y un PNG) con Pillow. Solo desarrollo.

    python scripts/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "fluo" / "resources"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line = max(1, round(s / 40))

    # hoja
    m = s * 0.12
    d.rounded_rectangle(
        [m, s * 0.06, s - m, s * 0.94],
        radius=s * 0.07,
        fill=(255, 255, 255, 255),
        outline=(58, 62, 70, 255),
        width=line,
    )
    # renglones
    for y in (0.24, 0.36, 0.48, 0.60, 0.72):
        x1 = 0.74 if y != 0.72 else 0.56
        d.rounded_rectangle(
            [s * 0.24, s * y, s * x1, s * (y + 0.045)],
            radius=s * 0.02,
            fill=(176, 180, 188, 255),
        )
    # resaltado amarillo encima de dos renglones (translúcido, como marcador)
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.rounded_rectangle(
        [s * 0.20, s * 0.335, s * 0.80, s * 0.545],
        radius=s * 0.035,
        fill=(255, 226, 64, 215),
    )
    img = Image.alpha_composite(img, hl)
    # trazo rojo a mano alzada
    d = ImageDraw.Draw(img)
    pts = [(s * 0.22, s * 0.86), (s * 0.40, s * 0.78), (s * 0.58, s * 0.88), (s * 0.80, s * 0.76)]
    d.line(pts, fill=(222, 56, 56, 255), width=max(2, round(s / 14)), joint="curve")
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    big = draw(256)
    big.save(OUT_DIR / "fluo.png")
    big.save(OUT_DIR / "fluo.ico", format="ICO", sizes=[(n, n) for n in SIZES])
    print("ok:", OUT_DIR / "fluo.ico")


if __name__ == "__main__":
    main()
