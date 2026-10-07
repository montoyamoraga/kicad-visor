"""Locating and running the external programs kicad-visor relies on."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Sequence

# Places KiCad installs kicad-cli without putting it on PATH.
KICAD_CLI_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "/Applications/KiCad.app/Contents/MacOS/kicad-cli",
    r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
]


class ToolError(Exception):
    pass


def find(name: str, explicit: Optional[str] = None, env: Optional[str] = None,
         candidates: Sequence[str] = ()) -> str:
    """Resolve a program: explicit path, then env var, then PATH, then candidates."""
    for option in (explicit, os.environ.get(env) if env else None):
        if option:
            if Path(option).is_file():
                return option
            raise ToolError(f"{name} not found at {option}")
    on_path = shutil.which(name)
    if on_path:
        return on_path
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise ToolError(f"{name} not found; install it or set its path in the config")


def kicad_cli(explicit: Optional[str] = None) -> str:
    return find("kicad-cli", explicit, "KICAD_CLI", KICAD_CLI_CANDIDATES)


def rsvg_convert(explicit: Optional[str] = None) -> str:
    return find("rsvg-convert", explicit, "RSVG_CONVERT")


def ffmpeg(explicit: Optional[str] = None) -> str:
    return find("ffmpeg", explicit, "FFMPEG")


def run(args: List[str], verbose: bool = False) -> str:
    if verbose:
        print("  $", " ".join(args))
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise ToolError(
            f"{Path(args[0]).name} failed ({result.returncode}):\n"
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def run_stderr(args: List[str]) -> str:
    """Run a command for what it reports on stderr (ffmpeg's analysis filters)."""
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise ToolError(f"{Path(args[0]).name} failed ({result.returncode}):\n"
                        f"{result.stderr.strip()}")
    return result.stderr
