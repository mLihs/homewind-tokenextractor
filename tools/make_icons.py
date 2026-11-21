"""Render the app icons from the Homewind wind mark (favicon.svg of homewind.io, 32 x 32 units).

macOS does not round app icons, so the Mac icon carries its own rounded shape inside
Apple's grid: an 824 px body centred on a transparent 1024 px canvas.
Windows and Linux get the full-size rounded square.

The mark is drawn with QPainterPath instead of QtSvg, whose large-arc rendering flattens the curls.

Run on macOS (needs iconutil):  .venv/bin/python tools/make_icons.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPen

ASSETS = Path(__file__).resolve().parent.parent / "src" / "homewind_tokenextractor" / "assets"
CANVAS = 1024
BODY = 824
NAVY = QColor("#132237")
PINK = QColor("#f00f66")


def wind_mark() -> QPainterPath:
    path = QPainterPath()
    # M6 11.5 h12.5 a3.5 3.5 0 1 0 -3.5 -3.5
    path.moveTo(6, 11.5)
    path.lineTo(18.5, 11.5)
    path.arcTo(QRectF(15, 4.5, 7, 7), 270, 270)
    # M6 17 h19 a4 4 0 1 1 -4 4
    path.moveTo(6, 17)
    path.lineTo(25, 17)
    path.arcTo(QRectF(21, 17, 8, 8), 90, -270)
    # M6 22.5 h8
    path.moveTo(6, 22.5)
    path.lineTo(14, 22.5)
    return path


def render(canvas: int, body: int) -> Image.Image:
    image = QImage(canvas, canvas, QImage.Format_RGBA8888)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    offset = (canvas - body) / 2
    painter.translate(offset, offset)
    painter.scale(body / 32, body / 32)
    painter.setPen(Qt.NoPen)
    painter.setBrush(NAVY)
    painter.drawRoundedRect(QRectF(0, 0, 32, 32), 7, 7)
    pen = QPen(PINK, 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(wind_mark())
    painter.end()
    data = bytes(image.constBits())
    return Image.frombuffer("RGBA", (canvas, canvas), data, "raw", "RGBA", image.bytesPerLine(), 1).copy()


def main() -> None:
    QGuiApplication(sys.argv)

    render(CANVAS, BODY).save(ASSETS / "icon.png")

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                render(px, round(px * BODY / CANVAS)).save(iconset / name)
        subprocess.run(["iconutil", "-c", "icns", "-o", str(ASSETS / "icon.icns"), str(iconset)], check=True)

    sizes = (16, 24, 32, 48, 64, 128, 256)
    frames = [render(s, s) for s in sizes]
    frames[-1].save(ASSETS / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[:-1])

    for name in ("icon.png", "icon.icns", "icon.ico"):
        print(name, (ASSETS / name).stat().st_size)


if __name__ == "__main__":
    if shutil.which("iconutil") is None:
        raise SystemExit("iconutil not found; run this on macOS")
    main()
