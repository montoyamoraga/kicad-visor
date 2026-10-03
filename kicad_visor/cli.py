"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from kicad_visor import __version__, schematic, tools
from kicad_visor.config import CONFIG_FILENAME, FORMATS, Config, ConfigError, load, validate
from kicad_visor.discover import find_projects

EXAMPLE_CONFIG = f'''\
# kicad-visor configuration. Plain Python: anything goes, as long as the
# settings below end up as top-level names. Delete what you don't change.

# Output folder, relative to this folder unless absolute.
output = "docs/kicad-visor"

# "es" or "en"; `labels` overrides individual words.
language = "es"
labels = {{}}  # e.g. {{"schematic": "esquemas"}}

# Any of {list(FORMATS)}.
formats = {list(FORMATS)}

# png/jpg resolution and background (None = transparent png).
dpi = 300
background = "#ffffff"
jpg_quality = 2  # 2 best .. 31 worst

# Schematic look. theme = None uses the project's own setting.
theme = None
black_and_white = False
exclude_drawing_sheet = False

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

    p_export = sub.add_parser("export", help="export schematics")
    common(p_export)
    p_export.add_argument("-o", "--output", help="output folder")
    p_export.add_argument("-f", "--formats",
                          help=f"comma-separated subset of {','.join(FORMATS)}")
    p_export.add_argument("--dpi", type=int, help="png/jpg resolution")
    p_export.add_argument("--language", help="label language (es, en)")
    p_export.add_argument("--theme", help="KiCad color theme name")

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
    for name in ("output", "dpi", "language", "theme"):
        value = getattr(args, name, None)
        if value is not None:
            setattr(config, name, value)
    if getattr(args, "formats", None):
        config.formats = [f.strip() for f in args.formats.split(",") if f.strip()]
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
        print(f"{project.name}")
        out = out_root / project.name / config.label("schematic")
        try:
            files = schematic.export(project, out, config, args.verbose)
        except tools.ToolError as error:
            failures += 1
            print(f"  error: {error}", file=sys.stderr)
            continue
        if not files:
            print("  no schematic, skipped")
        for path in files:
            print(f"  {path.relative_to(out_root)}")
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    commands = {"init": cmd_init, "list": cmd_list, "export": cmd_export}
    try:
        return commands[args.command](args)
    except (ConfigError, tools.ToolError) as error:
        print(f"kicad-visor: {error}", file=sys.stderr)
        return 2
