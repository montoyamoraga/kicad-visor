"""Turning SVGs into PNG and JPG."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from kicad_visor import tools
from kicad_visor.config import Config


def _png(svg: Path, dest: Path, background: Optional[str], config: Config,
         verbose: bool) -> None:
    args = [tools.rsvg_convert(config.rsvg_convert),
            "-d", str(config.dpi), "-p", str(config.dpi), "-o", str(dest)]
    if background:
        args += ["-b", background]
    tools.run(args + [str(svg)], verbose)


def rasterize(svg: Path, config: Config, verbose: bool = False) -> List[Path]:
    """Write png and/or jpg next to `svg`, as requested by config.formats."""
    written = []
    png = svg.with_suffix(".png")

    if "png" in config.formats:
        _png(svg, png, config.background, config, verbose)
        written.append(png)

    if "jpg" in config.formats:
        # JPG has no alpha: reuse the png only if it was rendered opaque.
        source = png
        if not (png in written and config.background):
            source = svg.with_suffix(".tmp.png")
            _png(svg, source, config.background or "#ffffff", config, verbose)
        jpg = svg.with_suffix(".jpg")
        tools.run([tools.ffmpeg(config.ffmpeg), "-y", "-loglevel", "error",
                   "-i", str(source), "-q:v", str(config.jpg_quality), str(jpg)],
                  verbose)
        if source != png:
            source.unlink()
        written.append(jpg)

    return written
