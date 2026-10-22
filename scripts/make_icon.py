"""Gera assets/macpronto.ico e assets/macpronto.png a partir do desenho do logo.

Uso: python scripts/make_icon.py  (precisa do Pillow, só para desenvolvimento)
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 1024  # desenha grande e reduz, para bordas suaves


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def draw() -> Image.Image:
    scale = SIZE / 64
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

    # Fundo em degradê diagonal, recortado num quadrado arredondado
    top, bottom = (59, 130, 246), (79, 70, 229)
    gradient = Image.new("RGBA", (SIZE, SIZE))
    pixels = gradient.load()
    for y in range(SIZE):
        for x in range(SIZE):
            pixels[x, y] = (*lerp(top, bottom, (x + y) / (2 * SIZE)), 255)
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([2 * scale, 2 * scale, 62 * scale, 62 * scale], radius=16 * scale, fill=255)
    image.paste(gradient, (0, 0), mask)

    canvas = ImageDraw.Draw(image)
    # Conector do pendrive
    canvas.rounded_rectangle(
        [22 * scale, 10 * scale, 42 * scale, 23 * scale], radius=2.5 * scale, fill=(255, 255, 255, 140)
    )
    canvas.rounded_rectangle(
        [27 * scale, 14 * scale, 30 * scale, 18 * scale], radius=0.8 * scale, fill=(70, 100, 235, 255)
    )
    canvas.rounded_rectangle(
        [34 * scale, 14 * scale, 37 * scale, 18 * scale], radius=0.8 * scale, fill=(70, 100, 235, 255)
    )
    # Corpo do pendrive
    canvas.rounded_rectangle(
        [16 * scale, 21 * scale, 48 * scale, 55 * scale], radius=7 * scale, fill=(255, 255, 255, 255)
    )
    # Marca de "pronto"
    points = [(24.5 * scale, 38.5 * scale), (30 * scale, 44 * scale), (40.5 * scale, 32.5 * scale)]
    canvas.line(points, fill=(62, 99, 235, 255), width=round(4.5 * scale), joint="curve")
    for x, y in (points[0], points[-1]):
        r = 2.25 * scale
        canvas.ellipse([x - r, y - r, x + r, y + r], fill=(62, 99, 235, 255))
    return image


def main() -> None:
    image = draw()
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    image.resize((512, 512), Image.LANCZOS).save(assets / "macpronto.png")
    image.save(
        assets / "macpronto.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("assets/macpronto.ico e assets/macpronto.png gerados")


if __name__ == "__main__":
    main()
