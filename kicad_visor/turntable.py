"""Seamlessly looping turntable videos of the 3D board.

Picture the board on a turntable: you choose the axis it turns around and
which way it goes, and the camera stays still. `video` renders one such
loop to a file.

Each loop is one full turn, so the last frame flows into the first. Before
rendering, the camera zoom is fitted by rendering small probe frames around
the whole loop and measuring where the board lands, so it never leaves the
frame whatever its shape, perspective or tall parts.

Frames are cached outside the project, keyed by the board file, the motion
and the frame size, so re-running (or changing backgrounds) only re-encodes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from kicad_visor import render, tools
from kicad_visor.config import Config, validate
from kicad_visor.discover import Project
from kicad_visor.motion import check, rotation
from kicad_visor.util import fresh_dir, slug

CACHE = Path.home() / ".cache" / "kicad-visor" / "frames"
BBOX = re.compile(r"x1:(-?\d+) x2:(-?\d+) y1:(-?\d+) y2:(-?\d+)")

# Fitting: the board may reach this fraction of the way from the center to
# the frame edge. Probes are rendered this many pixels on their long side,
# at this many points around the loop.
MARGIN = 0.9
PROBE_SIZE = 360
PROBE_STEPS = 16

# A color for ffmpeg ("#ff9ecf", "pink", "0xff9ecf"), or None for transparent.
Background = Optional[str]


def _view(rotate: Tuple[float, float, float], zoom: float,
          size: Tuple[int, int]) -> Dict[str, object]:
    # Always basic quality: "high" adds shadows at ~5x the render time.
    return {"rotate": rotate, "zoom": round(zoom, 4), "perspective": True,
            "quality": "basic", "size": size}


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


def _fit(board: Path, axis: str, direction: str, size: Tuple[int, int],
         config: Config, verbose: bool) -> float:
    """Largest zoom at which the whole loop stays inside a `size` frame."""
    scale = PROBE_SIZE / max(size)
    probe = (round(size[0] * scale), round(size[1] * scale))
    rotations = [rotation(axis, direction, i / PROBE_STEPS) for i in range(PROBE_STEPS)]

    def reach_at(zoom: float) -> float:
        with tempfile.TemporaryDirectory(prefix="kicad-visor-") as tmp:
            def one(i: int) -> float:
                png = Path(tmp) / f"{i}.png"
                view = _view(rotations[i], zoom, probe)
                render.render(board, png, view, config, verbose)
                return _reach(png, config)
            with ThreadPoolExecutor(max_workers=max(1, config.render_jobs)) as pool:
                return max(pool.map(one, range(PROBE_STEPS)))

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


def frames(board: Path, axis: str, direction: str, size: Tuple[int, int],
           config: Config, verbose: bool = False) -> List[Path]:
    """Render (or reuse from the cache) one transparent png per frame of the loop."""
    count = max(1, round(config.turntable_seconds * config.fps))
    width, height = size
    label = f"{axis}-{direction} {width}x{height}"

    key = hashlib.sha1(board.read_bytes())
    key.update(json.dumps([axis, direction, size, count]).encode())
    prefix = f"{axis}-{direction}-{width}x{height}-"
    folder = CACHE / slug(board.stem) / f"{prefix}{key.hexdigest()[:12]}"
    paths = [folder / f"{i:04d}.png" for i in range(count)]
    todo = [i for i, frame in enumerate(paths) if not frame.is_file()]
    if not todo:
        print(f"  {label}: {count} frames cached")
        return paths

    # Frames of an older version of this board/motion are dead weight.
    for stale in folder.parent.glob(f"{prefix}*"):
        if stale != folder:
            shutil.rmtree(stale)
    folder.mkdir(parents=True, exist_ok=True)

    fit_file = folder / "fit.json"
    if fit_file.is_file():
        fit = json.loads(fit_file.read_text())["zoom"]
    else:
        print(f"  {label}: fitting camera", flush=True)
        fit = _fit(board, axis, direction, size, config, verbose)
        fit_file.write_text(json.dumps({"zoom": fit}))

    views = [_view(rotation(axis, direction, i / count), fit, size)
             for i in range(count)]

    def one(i: int) -> None:
        # Render under a temporary name so an interrupted run never leaves
        # a half-written frame that looks cached.
        partial = paths[i].with_suffix(".partial.png")
        render.render(board, partial, views[i], config, verbose)
        partial.rename(paths[i])

    done = count - len(todo)
    with ThreadPoolExecutor(max_workers=max(1, config.render_jobs)) as pool:
        for _ in pool.map(one, todo):
            done += 1
            print(f"\r  {label}: frame {done}/{count}", end="", flush=True)
    print()
    return paths


def _codec(path: Path, transparent: bool, config: Config) -> List[str]:
    """Encoder arguments for `path`, picked by its suffix."""
    if path.suffix.lower() not in (".mp4", ".mov"):
        raise ValueError(f"{path.name}: videos are .mp4 or .mov")
    if path.suffix.lower() == ".mov" and transparent:
        # ProRes 4444 keeps the alpha channel and opens in every video editor.
        return ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    if transparent:
        raise ValueError(f"{path.name}: a transparent background needs a .mov file; "
                         ".mp4 has no alpha channel")
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(config.video_crf),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart"]


def encode(paths: Sequence[Path], outputs: Sequence[Tuple[Path, Background]],
           size: Tuple[int, int], config: Config, verbose: bool = False) -> None:
    """Lay the frames over each background and write one video per output.

    One ffmpeg run decodes the frames once and writes every output.
    """
    codecs = [_codec(path, color is None, config) for path, color in outputs]
    width, height = size
    args = [tools.ffmpeg(config.ffmpeg), "-y", "-loglevel", "error",
            "-framerate", str(config.fps), "-i", str(paths[0].parent / "%04d.png")]
    graph = [f"[0]split={len(outputs)}" + "".join(f"[f{i}]" for i in range(len(outputs)))]
    # kicad-cli renders a few pixels short of the size it is asked for
    # (1920x1080 comes out 1904x1064), so frames are centered on the canvas.
    inputs = 1
    for i, (_, color) in enumerate(outputs):
        if color is None:
            graph.append(f"[f{i}]format=rgba,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:"
                         f"color=black@0[o{i}]")
            continue
        args += ["-f", "lavfi", "-i", f"color=c={color}:s={width}x{height}:r={config.fps}"]
        graph.append(f"[{inputs}][f{i}]overlay=(W-w)/2:(H-h)/2:shortest=1[o{i}]")
        inputs += 1
    args += ["-filter_complex", ";".join(graph)]
    for i, ((path, _), codec) in enumerate(zip(outputs, codecs)):
        path.parent.mkdir(parents=True, exist_ok=True)
        args += ["-map", f"[o{i}]", *codec, str(path)]
    tools.run(args, verbose)


def video(board: Union[str, Path], out: Union[str, Path],
          axis: str = "z", direction: Optional[str] = None, *,
          background: Background = "#ffffff",
          size: Tuple[int, int] = (1080, 1080),
          seconds: float = 6,
          verbose: bool = False) -> Path:
    """Render a looping turntable video of a KiCad board.

    board: the .kicad_pcb file (or its .kicad_pro).
    out: the video to write, .mp4 (H.264) or .mov. A transparent background
        needs .mov, written as ProRes 4444.
    axis: what the board turns around: "x", "y" or "z", see motion.AXES.
    direction: which way, see motion.AXES; None takes the axis default.
    background: any ffmpeg color ("#ff9ecf", "pink"), or None for transparent.
    size: (width, height) in pixels.
    seconds: length of the loop.
    verbose: print every external command.

    Returns the path of the video.
    """
    board = Path(board).resolve()
    if board.suffix != ".kicad_pcb":
        board = board.with_suffix(".kicad_pcb")
    if not board.is_file():
        raise FileNotFoundError(f"board not found: {board}")
    out = Path(out)
    direction = check(axis, direction)
    config = Config(turntable_seconds=seconds)
    validate(config)
    _codec(out, background is None, config)  # fail before rendering, not after
    encode(frames(board, axis, direction, size, config, verbose), [(out, background)],
           size, config, verbose)
    return out


def export(project: Project, out: Path, config: Config,
           verbose: bool = False) -> List[Path]:
    """Write one video per turntable x aspect x background into `out` (wiped first).

    Videos over a color are .mp4; a None (transparent) background gives .mov.
    """
    board = project.pcb
    if board is None:
        return []

    tools.ffmpeg(config.ffmpeg)
    fresh_dir(out)
    written: List[Path] = []

    for axis, direction in config.turntables:
        for aspect_name, size in config.aspects.items():
            paths = frames(board, axis, direction, size, config, verbose)
            outputs = []
            for background, color in config.backgrounds.items():
                suffix = ".mov" if color is None else ".mp4"
                outputs.append((out / (f"{axis}-{direction}-{slug(config.label(aspect_name))}"
                                       f"-{slug(config.label(background))}{suffix}"), color))
            encode(paths, outputs, size, config, verbose)
            written += [path for path, _ in outputs]

    return written
