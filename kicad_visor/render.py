"""3D renders of the board through `kicad-cli pcb render`.

Views without a zoom of their own get a fitted one: small probe renders
measure where the board lands, and the camera moves as close as it can
with the whole board, tall parts included, inside the frame.
"""

from __future__ import annotations

import math
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from kicad_visor import raster, tools
from kicad_visor.config import Config
from kicad_visor.discover import Project
from kicad_visor.util import fresh_dir, slug

BBOX = re.compile(r"x1:(-?\d+) x2:(-?\d+) y1:(-?\d+) y2:(-?\d+)")

# Fitting: the board may reach this fraction of the way from the center to
# the frame edge. Probes are rendered this many pixels on their long side.
MARGIN = 0.9
PROBE_SIZE = 360


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


def _reach(png: Path, config: Config) -> float:
    """How far the board reaches toward the frame edge: 1.0 touches it."""
    result = tools.run_stderr([tools.ffmpeg(config.ffmpeg), "-hide_banner",
                               "-i", str(png), "-vf", "alphaextract,bbox=min_val=16",
                               "-f", "null", "-"])
    found = BBOX.findall(result)
    if not found:
        return 0.0
    x1, x2, y1, y2 = (int(v) for v in found[-1])
    width, height = _png_size(png)
    reach_x = max(width / 2 - x1, x2 + 1 - width / 2) / (width / 2)
    reach_y = max(height / 2 - y1, y2 + 1 - height / 2) / (height / 2)
    return max(reach_x, reach_y)


def _png_size(png: Path) -> Tuple[int, int]:
    header = png.read_bytes()[16:24]
    return int.from_bytes(header[:4], "big"), int.from_bytes(header[4:], "big")


def fit(board: Path, views: List[Dict[str, Any]], config: Config,
        verbose: bool = False) -> float:
    """Largest zoom at which the board stays inside the frame in every view."""

    def reach_at(zoom: float) -> float:
        with tempfile.TemporaryDirectory(prefix="kicad-visor-") as tmp:
            def one(i: int) -> float:
                width, height = views[i].get("size", config.render_size)
                scale = PROBE_SIZE / max(width, height)
                # Small, fast and without the floor, which would fill the
                # frame and hide where the board ends.
                probe = dict(views[i], zoom=zoom, quality="basic", floor=False,
                             size=(round(width * scale), round(height * scale)))
                png = Path(tmp) / f"{i}.png"
                render(board, png, probe, config, verbose)
                return _reach(png, config)
            with ThreadPoolExecutor(max_workers=max(1, config.render_jobs)) as pool:
                return max(pool.map(one, range(len(views))))

    # Reach grows with zoom, but not proportionally: perspective makes parts
    # swinging toward the camera grow faster, and which angle is worst can
    # change with zoom. So every guess is checked on the whole loop, and the
    # answer is bracketed between the largest zoom that fits (`fits`) and the
    # smallest that doesn't (`too_big`).
    fits, too_big = 0.0, math.inf
    zoom = 0.4
    for _ in range(7):
        reach = reach_at(zoom)
        if reach <= 0:
            return 1.0
        if reach <= MARGIN:
            fits = max(fits, zoom)
            if reach >= MARGIN - 0.04:
                break
        else:
            too_big = min(too_big, zoom)
        # A clipped probe (reach 1) says little about how far over it is.
        guess = zoom * (0.8 if reach >= 1 else MARGIN / reach)
        if not fits < guess < too_big:
            guess = (fits + too_big) / 2 if too_big < math.inf else zoom * 1.5
        zoom = guess
    return fits or zoom * 0.5


def export(project: Project, out: Path, config: Config,
           verbose: bool = False) -> List[Path]:
    """Render every view in config.render_views into `out`, which is wiped first."""
    board = project.pcb
    if board is None:
        return []

    fresh_dir(out)
    written: List[Path] = []
    for view in config.render_views:
        if "zoom" not in view:
            view = dict(view, zoom=fit(board, [view], config, verbose))
        png = render(board, out / f"{slug(config.label(view['name']))}.png",
                     view, config, verbose)
        if "jpg" in config.formats:
            written.append(raster.flatten_jpg(png, config, verbose))
        if "png" in config.formats:
            written.append(png)
        else:
            png.unlink()
    return written
