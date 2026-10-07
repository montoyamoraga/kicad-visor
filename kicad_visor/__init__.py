"""Docs out of KiCad projects: schematics, PCB layers, 3D renders and
looping turntable videos.

    import kicad_visor

    # One video: the board turns around its vertical axis over pink.
    kicad_visor.turntable_video("board.kicad_pcb", "flip.mp4", axis="y",
                                direction="left", background="#ff9ecf")

    # Everything, for every project under a folder.
    kicad_visor.export("path/to/repo")
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from kicad_visor import pcb, render, schematic, turntable
from kicad_visor.config import Config, ConfigError, validate
from kicad_visor.discover import find_projects
from kicad_visor.motion import AXES
from kicad_visor.tools import ToolError
from kicad_visor.turntable import video as turntable_video
from kicad_visor.util import slug

__version__ = "0.0.1"

__all__ = ["AXES", "Config", "ConfigError", "ToolError", "export", "turntable_video"]


def export(target: Union[str, Path], config: Optional[Config] = None, *,
           verbose: bool = False) -> List[Path]:
    """Export every KiCad project under `target` (a folder or a .kicad_pro).

    config: what to export and how; defaults to Config(). Its output folder
        is relative to `target` unless absolute.
    verbose: print every external command.

    Returns the files written. Raises ToolError when an external program
    (kicad-cli, rsvg-convert, ffmpeg) is missing or fails.
    """
    exporters = {"schematic": schematic, "pcb": pcb, "render": render,
                 "turntable": turntable}
    config = config or Config()
    validate(config)
    target = Path(target).resolve()
    out_root = config.output_dir(target if target.is_dir() else target.parent)
    written: List[Path] = []
    for project in find_projects(target, config.exclude):
        for output in config.outputs:
            out = out_root / slug(project.name) / slug(config.label(output))
            written += exporters[output].export(project, out, config, verbose)
    return written
