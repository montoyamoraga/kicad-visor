"""Turning SVGs into PNG, JPG and PDF."""

from __future__ import annotations

from pathlib import Path
from typing import List

from kicad_visor import tools
from kicad_visor.config import Config


def _rsvg(svg: Path, dest: Path, config: Config, verbose: bool, *extra: str) -> Path:
    tools.run([tools.rsvg_convert(config.rsvg_convert), *extra,
               "-o", str(dest), str(svg)], verbose)
    return dest


def to_pdf(svg: Path, config: Config, verbose: bool = False) -> Path:
    """Vector pdf with the same page as the svg."""
    return _rsvg(svg, svg.with_suffix(".pdf"), config, verbose, "-f", "pdf")


def flatten_jpg(png: Path, config: Config, verbose: bool = False) -> Path:
    """jpg of `png` laid over the configured background (white if none)."""
    color = config.background or "#ffffff"
    jpg = png.with_suffix(".jpg")
    tools.run([tools.ffmpeg(config.ffmpeg), "-y", "-loglevel", "error", "-i", str(png),
               "-filter_complex",
               f"[0]format=rgba,split[a][b];[a]drawbox=c={color}@1:t=fill[bg];"
               "[bg][b]overlay=format=auto",
               "-q:v", str(config.jpg_quality), str(jpg)], verbose)
    return jpg


def rasterize(svg: Path, config: Config, verbose: bool = False) -> List[Path]:
    """Write png and/or jpg next to `svg`, as requested by config.formats."""
    wants_png = "png" in config.formats
    wants_jpg = "jpg" in config.formats
    if not (wants_png or wants_jpg):
        return []

    args = ["-d", str(config.dpi), "-p", str(config.dpi)]
    if config.background:
        args += ["-b", config.background]
    png = _rsvg(svg, svg.with_suffix(".png"), config, verbose, *args)

    written = []
    if wants_jpg:
        written.append(flatten_jpg(png, config, verbose))
    if wants_png:
        written.append(png)
    else:
        png.unlink()
    return written
