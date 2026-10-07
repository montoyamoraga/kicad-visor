"""2D PCB export: one image per view (a layer, or a combination of layers)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from kicad_visor import raster, tools
from kicad_visor.config import Config
from kicad_visor.discover import Project
from kicad_visor.util import fresh_dir, slug


def _paint_background(svg: Path, color: str) -> None:
    """Fill the svg's whole page with `color`, under everything else."""
    text = svg.read_text(encoding="utf-8")
    root = re.search(r"<svg\b[^>]*>", text)
    box = re.search(r'viewBox="([^"]+)"', root.group(0)) if root else None
    if box is None:
        return
    x, y, width, height = box.group(1).split()
    rect = f'\n<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{color}"/>'
    svg.write_text(text[:root.end()] + rect + text[root.end():], encoding="utf-8")


def export(project: Project, out: Path, config: Config,
           verbose: bool = False) -> List[Path]:
    """Export every view in config.pcb_views into `out`, which is wiped first."""
    board = project.pcb
    if board is None:
        return []

    fresh_dir(out)
    cli = tools.kicad_cli(config.kicad_cli)
    written: List[Path] = []

    for view in config.pcb_views:
        svg = out / f"{slug(config.label(view['name']))}.svg"
        # Board area only, no frame: these are pictures of the board, not
        # fabrication sheets.
        args = [cli, "pcb", "export", "svg", "--mode-single",
                "--layers", ",".join(view["layers"]),
                "--page-size-mode", "2", "--exclude-drawing-sheet"]
        if view.get("mirror"):
            args.append("--mirror")
        if config.theme:
            args += ["--theme", config.theme]
        if config.black_and_white:
            args.append("--black-and-white")
        tools.run(args + ["-o", str(svg), str(board)], verbose)
        if view.get("background"):
            _paint_background(svg, view["background"])

        # The pdf comes from the svg so it is cropped to the board the same way.
        if "pdf" in config.formats:
            written.append(raster.to_pdf(svg, config, verbose))
        written += raster.rasterize(svg, config, verbose)
        if "svg" in config.formats:
            written.append(svg)
        else:
            svg.unlink()

    return written
