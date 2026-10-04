"""Schematic export: one SVG/PNG/JPG per sheet, one multi-page PDF."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from kicad_visor import raster, tools
from kicad_visor.config import Config
from kicad_visor.discover import Project


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

    # The folder belongs to kicad-visor: clearing it drops sheets that no
    # longer exist instead of leaving stale images behind.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    cli = tools.kicad_cli(config.kicad_cli)
    style = _style_args(config)
    written: List[Path] = []

    if "pdf" in config.formats:
        pdf = out / f"{project.name}.pdf"
        tools.run([cli, "sch", "export", "pdf", *style, "-o", str(pdf), str(sch)],
                  verbose)
        written.append(pdf)

    if any(f in config.formats for f in ("svg", "png", "jpg")):
        tools.run([cli, "sch", "export", "svg", *style, "-o", str(out), str(sch)],
                  verbose)
        for svg in sorted(out.glob("*.svg")):
            written += raster.rasterize(svg, config, verbose)
            if "svg" in config.formats:
                written.append(svg)
            else:
                svg.unlink()

    return written
