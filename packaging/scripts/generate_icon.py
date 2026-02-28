#!/usr/bin/env python3
"""Generate a placeholder macOS app icon for Tax PDF Redactor."""

from __future__ import annotations

import sys
from pathlib import Path
import shutil

from PIL import Image, ImageDraw


ICON_SIZES = [
    (16, 16),
    (32, 32),
    (64, 64),
    (128, 128),
    (256, 256),
    (512, 512),
    (1024, 1024),
]


def draw_master_icon(size: int = 1024) -> Image.Image:
    """Create the master icon image."""

    image = Image.new('RGBA', (size, size), '#f5f1e8')
    draw = ImageDraw.Draw(image)

    shadow_bounds = (
        int(size * 0.17),
        int(size * 0.13),
        int(size * 0.81),
        int(size * 0.89),
    )
    draw.rounded_rectangle(
        shadow_bounds,
        radius=int(size * 0.08),
        fill='#d9c6a5',
    )

    page_bounds = (
        int(size * 0.14),
        int(size * 0.10),
        int(size * 0.78),
        int(size * 0.86),
    )
    page_radius = int(size * 0.08)
    draw.rounded_rectangle(page_bounds, radius=page_radius, fill='#fffdf8')

    fold = [
        (int(size * 0.62), int(size * 0.10)),
        (int(size * 0.78), int(size * 0.10)),
        (int(size * 0.78), int(size * 0.26)),
    ]
    draw.polygon(fold, fill='#f4d58d')
    draw.line(
        [(int(size * 0.62), int(size * 0.10)), (int(size * 0.78), int(size * 0.26))],
        fill='#d9c6a5',
        width=max(4, int(size * 0.006)),
    )

    accent_bounds = (
        int(size * 0.26),
        int(size * 0.16),
        int(size * 0.92),
        int(size * 0.82),
    )
    draw.rounded_rectangle(
        accent_bounds,
        radius=int(size * 0.16),
        fill='#f4d58d',
    )

    bar_specs = [
        (0.29, 0.36, 0.80, 0.43),
        (0.29, 0.50, 0.76, 0.57),
        (0.29, 0.64, 0.72, 0.71),
    ]
    for left, top, right, bottom in bar_specs:
        draw.rounded_rectangle(
            (
                int(size * left),
                int(size * top),
                int(size * right),
                int(size * bottom),
            ),
            radius=int(size * 0.03),
            fill='#111111',
        )

    return image


def generate_icns(output_path: Path) -> int:
    """Generate an icns file and return a process exit code."""

    if sys.platform != 'darwin':
        print('This icon generator only supports macOS.', file=sys.stderr)
        return 1

    output_path = output_path.resolve()
    legacy_iconset_dir = output_path.parent / 'TaxPDFRedactor.iconset'
    master_png = output_path.parent / 'TaxPDFRedactor.png'

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(legacy_iconset_dir, ignore_errors=True)

    master_image = draw_master_icon()
    master_image.save(master_png)
    master_image.save(
        output_path,
        sizes=ICON_SIZES,
    )

    print(f'Generated app icon: {output_path}')
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""

    args = argv if argv is not None else sys.argv[1:]
    output_path = (
        Path(args[0])
        if args
        else Path('build/macos/TaxPDFRedactor.icns')
    )
    return generate_icns(output_path)


if __name__ == '__main__':
    raise SystemExit(main())
