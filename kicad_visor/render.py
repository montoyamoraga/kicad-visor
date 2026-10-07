"""3D renders of the board through `kicad-cli pcb render`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Sequence

from kicad_visor import raster, tools
from kicad_visor.config import Config
from kicad_visor.discover import Project
from kicad_visor.util import fresh_dir, slug


def _vector(values: Sequence[float]) -> str:
    # kicad-cli reads "-45,0,45" as a flag, so keep angles in [0, 360).
    return ",".join(f"{v % 360:g}" for v in values)


def _args(view: Dict[str, Any], config: Config) -> List[str]:
    width, height = view.get("size", config.render_size)
    args = ["--width", str(width), "--height", str(height),
            "--quality", view.get("quality", config.render_quality)]
    if "side" in view:
        args += ["--side", view["side"]]
    if "rotate" in view:
        args += ["--rotate", _vector(view["rotate"])]
    if "zoom" in view:
        args += ["--zoom", str(view["zoom"])]
    for key in ("pan", "pivot"):
        if key in view:
            # Offsets, not angles: negative values must survive, so pass
            # them with "=" glued on.
            args.append(f"--{key}=" + ",".join(f"{v:g}" for v in view[key]))
    if view.get("perspective"):
        args.append("--perspective")
    if view.get("floor"):
        args.append("--floor")
    return args


def render(board: Path, dest: Path, view: Dict[str, Any], config: Config,
           verbose: bool = False) -> Path:
    """Render one transparent png of `board` as described by `view`."""
    cli = tools.kicad_cli(config.kicad_cli)
    tools.run([cli, "pcb", "render", *_args(view, config),
               "--background", "transparent", "-o", str(dest), str(board)], verbose)
    return dest


def export(project: Project, out: Path, config: Config,
           verbose: bool = False) -> List[Path]:
    """Render every view in config.render_views into `out`, which is wiped first."""
    board = project.pcb
    if board is None:
        return []

    fresh_dir(out)
    written: List[Path] = []
    for view in config.render_views:
        png = render(board, out / f"{slug(config.label(view['name']))}.png",
                     view, config, verbose)
        if "jpg" in config.formats:
            written.append(raster.flatten_jpg(png, config, verbose))
        if "png" in config.formats:
            written.append(png)
        else:
            png.unlink()
    return written
