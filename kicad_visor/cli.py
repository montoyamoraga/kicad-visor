"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from kicad_visor import __version__, pcb, render, schematic, site, tools, turntable
from kicad_visor.config import (ASPECTS, BACKGROUNDS, CONFIG_FILENAME, DEFAULT_OUTPUTS, FORMATS, OUTPUTS,
                                TURNTABLES, Config, ConfigError, load, validate)
from kicad_visor.discover import find_projects
from kicad_visor.motion import AXES, check
from kicad_visor.util import slug

EXPORTERS = {
    "schematic": schematic,
    "pcb": pcb,
    "render": render,
    "turntable": turntable,
}

EXAMPLE_CONFIG = f'''\
# kicad-visor configuration. Plain Python: anything goes, as long as the
# settings below end up as top-level names. Delete what you don't change.

# Output folder, relative to this folder unless absolute.
output = "docs/kicad-visor"

# "es" or "en"; `labels` overrides individual words.
language = "es"
labels = {{}}  # e.g. {{"schematic": "esquemas"}}

# What to export, any of {list(OUTPUTS)}.
# turntable is slow (minutes per board), so it is off by default.
outputs = {list(DEFAULT_OUTPUTS)}

# Any of {list(FORMATS)}. 3D renders only make png/jpg.
formats = {list(FORMATS)}

# png/jpg resolution and background (None = transparent png).
dpi = 300
background = "#ffffff"
jpg_quality = 2  # 2 best .. 31 worst

# Schematic look. theme = None uses the project's own setting.
theme = None
black_and_white = False
exclude_drawing_sheet = False

# 2D PCB views: name, layers, mirror. Start from the defaults to extend them:
#   from kicad_visor.config import PCB_VIEWS
#   pcb_views = PCB_VIEWS + [{{"name": "mask", "layers": ["F.Mask", "Edge.Cuts"]}}]
# pcb_views = [...]

# 3D stills: name plus any of side, rotate (x, y, z), zoom, pan, pivot,
# perspective, floor, quality, size. Without a zoom, the camera is fitted so
# the whole board stays in frame. Defaults in kicad_visor.config.RENDER_VIEWS.
# render_views = [...]
render_size = (2000, 2000)
render_quality = "basic"  # or "high": shadows and floor, ~5x slower (stills only)

# Turntable videos: seamless loops, one per turntable x aspect x background.
# Each turntable is (axis, direction), the face toward the camera moving:
#   "x": the horizontal screen axis, "down" or "up"
#   "y": the vertical screen axis, "right" or "left"
#   "z": the board's own normal, like a record, "ccw" or "cw"
turntables = {TURNTABLES!r}
# Background colors, name -> any ffmpeg color; None is transparent (.mov).
backgrounds = {BACKGROUNDS!r}
aspects = {ASPECTS!r}
turntable_seconds = 6
# Rarely needed: frame rate, H.264 quality (lower is better, bigger files)
# and frames rendered in parallel.
fps = 30
video_crf = 18
render_jobs = 2

# Projects to skip, as globs relative to this folder.
exclude = [
    "**/*-backups/**",
    "**/.venv/**",
    "**/env/**",
    "**/node_modules/**",
]
'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kicad-visor",
        description="Extract docs from KiCad projects.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("target", nargs="?", default=".", type=Path,
                       help="folder to search for projects, or a .kicad_pro (default: .)")
        p.add_argument("-c", "--config", type=Path,
                       help=f"config file (default: <target>/{CONFIG_FILENAME} if present)")
        p.add_argument("-v", "--verbose", action="store_true",
                       help="print every external command")

    p_list = sub.add_parser("list", help="show the projects that would be processed")
    common(p_list)

    p_export = sub.add_parser("export", help="export schematics, PCB layers and 3D renders")
    common(p_export)
    p_export.add_argument("-o", "--output", help="output folder")
    p_export.add_argument("-f", "--formats",
                          help=f"comma-separated subset of {','.join(FORMATS)}")
    p_export.add_argument("--only",
                          help=f"comma-separated subset of {','.join(OUTPUTS)}")
    p_export.add_argument("--quality", dest="render_quality", choices=("basic", "high"),
                          help="3D still render quality")
    p_export.add_argument("--dpi", type=int, help="png/jpg resolution")
    p_export.add_argument("--language", help="label language (es, en)")
    p_export.add_argument("--theme", help="KiCad color theme name")
    p_export.add_argument("--background",
                          help="png/jpg background color, or 'none' for transparent png")

    p_turn = sub.add_parser(
        "turntable", help="render one looping turntable video of a board",
        description="Render one looping video of the board turning on a turntable. "
                    "Pick the axis it turns around and the direction: "
                    + "; ".join(f"{axis}: {' or '.join(ways)}" for axis, ways in AXES.items())
                    + " (the face toward the camera moves that way; z is seen from the camera).")
    p_turn.add_argument("board", type=Path, help=".kicad_pcb (or .kicad_pro) file")
    p_turn.add_argument("-o", "--output", type=Path,
                        help="video file, .mp4 or .mov (default: <board>-<axis>-<direction>.mp4, .mov when transparent)")
    p_turn.add_argument("--axis", choices=list(AXES), default="z",
                        help="axis the board turns around (default: z)")
    p_turn.add_argument("--direction",
                        help="which way it turns (default: the axis' first option)")
    p_turn.add_argument("--seconds", type=float, default=6, help="loop length (default: 6)")
    p_turn.add_argument("--background", default="#ffffff",
                        help="any ffmpeg color, or 'none' for transparent .mov (default: #ffffff)")
    p_turn.add_argument("--size", default="1080x1080", help="WIDTHxHEIGHT (default: 1080x1080)")
    p_turn.add_argument("-v", "--verbose", action="store_true", help="print every external command")

    p_init = sub.add_parser("init", help=f"write an example {CONFIG_FILENAME}")
    p_init.add_argument("target", nargs="?", default=".", type=Path)

    return parser


def _config_for(args: argparse.Namespace) -> Config:
    path = args.config
    if path is None:
        folder = args.target if args.target.is_dir() else args.target.parent
        default = folder / CONFIG_FILENAME
        path = default if default.is_file() else None
    config = load(path)
    for name in ("output", "dpi", "language", "theme", "render_quality", "background"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(config, name, value)
    if config.background in ("none", "transparent"):
        config.background = None
    if getattr(args, "formats", None):
        config.formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    if getattr(args, "only", None):
        config.outputs = [o.strip() for o in args.only.split(",") if o.strip()]
    validate(config)
    return config


def cmd_init(args: argparse.Namespace) -> int:
    path = args.target / CONFIG_FILENAME
    if path.exists():
        print(f"{path} already exists, not overwriting", file=sys.stderr)
        return 1
    path.write_text(EXAMPLE_CONFIG)
    print(f"wrote {path}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    config = _config_for(args)
    target = args.target.resolve()
    projects = find_projects(target, config.exclude)
    base = target if target.is_dir() else target.parent
    for project in projects:
        parts = [p for p, f in (("sch", project.schematic), ("pcb", project.pcb)) if f]
        print(f"{project.pro.relative_to(base)}  [{', '.join(parts)}]")
    print(f"{len(projects)} project(s)")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    config = _config_for(args)
    target = args.target.resolve()
    base = target if target.is_dir() else target.parent
    out_root = config.output_dir(base)
    projects = find_projects(target, config.exclude)
    if not projects:
        print("no KiCad projects found", file=sys.stderr)
        return 1

    failures = 0
    for project in projects:
        print(project.name)
        for output in config.outputs:
            out = out_root / slug(project.name) / slug(config.label(output))
            try:
                files = EXPORTERS[output].export(project, out, config, args.verbose)
            except tools.ToolError as error:
                failures += 1
                print(f"  {output} error: {error}", file=sys.stderr)
                continue
            if not files:
                print(f"  {output}: nothing to export")
            for path in files:
                print(f"  {path.relative_to(out_root)}")
    site.write(out_root, config, base.name)
    print(f"web pages: {out_root / 'index.html'}")
    return 1 if failures else 0


def cmd_turntable(args: argparse.Namespace) -> int:
    try:
        width, height = (int(n) for n in args.size.lower().split("x"))
    except ValueError:
        raise ConfigError(f"--size takes WIDTHxHEIGHT, not {args.size!r}") from None
    direction = check(args.axis, args.direction)
    background = None if args.background.lower() in ("none", "transparent") else args.background
    suffix = ".mov" if background is None else ".mp4"
    out = args.output or Path(f"{args.board.stem}-{args.axis}-{direction}{suffix}")
    turntable.video(args.board, out, args.axis, direction, background=background,
                    size=(width, height), seconds=args.seconds, verbose=args.verbose)
    print(out)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    commands = {"init": cmd_init, "list": cmd_list, "export": cmd_export,
                "turntable": cmd_turntable}
    try:
        return commands[args.command](args)
    except (ConfigError, ValueError, FileNotFoundError, tools.ToolError) as error:
        print(f"kicad-visor: {error}", file=sys.stderr)
        return 2
