"""Build favicon raster assets for ruralhealth.xyz from a single geometric spec.

The 'rh' monogram is defined on a 32-unit grid (matching dashboard/favicon.svg).
This script renders the same geometry at every output size, so the SVG and
raster outputs stay visually identical.

Build-time-only dependency:
    pip install Pillow

Run from the repo root:
    python3 scripts/build_favicon.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

VIEW = 32
GLYPHS = [
    (4, 10, 4, 18),
    (4, 10, 10, 4),
    (18, 4, 4, 24),
    (18, 10, 10, 4),
    (24, 14, 4, 14),
]

OUT = Path(__file__).resolve().parent.parent / "dashboard"


def render(size: int, transparent: bool) -> Image.Image:
    supersample = 8
    s = size * supersample
    bg = (255, 255, 255, 0) if transparent else (255, 255, 255, 255)
    img = Image.new("RGBA", (s, s), bg)
    draw = ImageDraw.Draw(img)
    scale = s / VIEW
    for x, y, w, h in GLYPHS:
        draw.rectangle(
            [x * scale, y * scale, (x + w) * scale - 1, (y + h) * scale - 1],
            fill=(0, 0, 0, 255),
        )
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    ico_master = render(64, transparent=True)
    ico_master.save(
        OUT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )

    apple = render(180, transparent=False)
    apple.convert("RGB").save(OUT / "apple-touch-icon.png", format="PNG", optimize=True)

    render(192, transparent=True).save(OUT / "icon-192.png", format="PNG", optimize=True)
    render(512, transparent=True).save(OUT / "icon-512.png", format="PNG", optimize=True)

    print(f"Wrote favicon assets to {OUT}")


if __name__ == "__main__":
    main()
