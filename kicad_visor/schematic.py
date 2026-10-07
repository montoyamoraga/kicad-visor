"""Schematic export: one SVG/PNG/JPG per sheet, one multi-page PDF."""

from __future__ import annotations

from pathlib import Path
from typing import List

from kicad_visor import raster, tools
from kicad_visor.config import Config
from kicad_visor.discover import Project
from kicad_visor.util import fresh_dir, slug


def _style_args(config: Config) -> List[str]:
    args = []
    if config.theme:
        args += ["--theme", config.theme]
    if config.black_and_white:
        args.append("--black-and-white")
    if config.exclude_drawing_sheet:
        args.append("--exclude-drawing-sheet")
    return args


def export(project: Project, out: Path, config: Config,
           verbose: bool = False) -> List[Path]:
    """Export the project's schematic into `out`, which is wiped first."""
    sch = project.schematic
    if sch is None:
        return []

    fresh_dir(out)

    cli = tools.kicad_cli(config.kicad_cli)
    style = _style_args(config)
    written: List[Path] = []

    if "pdf" in config.formats:
        pdf = out / f"{slug(project.name)}.pdf"
        tools.run([cli, "sch", "export", "pdf", *style, "-o", str(pdf), str(sch)],
                  verbose)
        written.append(pdf)

    if any(f in config.formats for f in ("svg", "png", "jpg")):
        tools.run([cli, "sch", "export", "svg", *style, "-o", str(out), str(sch)],
                  verbose)
        # kicad-cli names sheets "<project>-<sheet name>.svg", spaces and all.
        for plotted in sorted(out.glob("*.svg")):
            svg = plotted.rename(out / f"{slug(plotted.stem)}.svg")
            written += raster.rasterize(svg, config, verbose)
            if "svg" in config.formats:
                written.append(svg)
            else:
                svg.unlink()

    return written
