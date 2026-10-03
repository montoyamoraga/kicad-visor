"""Configuration: defaults, overridden by a Python config file, overridden by CLI flags.

A config file is plain Python. Every top-level name that matches a field of
`Config` is picked up; unknown names that don't start with an underscore are
an error, so typos don't silently do nothing.
"""

from __future__ import annotations

import runpy
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Dict, List, Optional

CONFIG_FILENAME = "kicad-visor-config.py"

FORMATS = ("svg", "pdf", "png", "jpg")

LABELS = {
    "es": {
        "schematic": "esquematico",
        "pcb": "placa",
    },
    "en": {
        "schematic": "schematic",
        "pcb": "pcb",
    },
}


@dataclass
class Config:
    # Output folder, relative to the target folder unless absolute.
    output: str = "docs/kicad-visor"
    # Language for folder names, captions and video text.
    language: str = "es"
    # Per-key overrides of the built-in labels for `language`.
    labels: Dict[str, str] = field(default_factory=dict)
    # Which formats to produce.
    formats: List[str] = field(default_factory=lambda: list(FORMATS))
    # Resolution for png/jpg.
    dpi: int = 300
    # Background for png/jpg; None keeps png transparent (jpg always gets white).
    background: Optional[str] = "#ffffff"
    # JPG quality, 2 (best) to 31 (worst), as ffmpeg's -q:v.
    jpg_quality: int = 2
    # KiCad color theme name; None uses the project's own setting.
    theme: Optional[str] = None
    black_and_white: bool = False
    exclude_drawing_sheet: bool = False
    # Glob patterns (relative to the target) of projects to skip.
    exclude: List[str] = field(
        default_factory=lambda: [
            "**/*-backups/**",
            "**/.venv/**",
            "**/env/**",
            "**/node_modules/**",
        ]
    )
    # Explicit tool paths; None means auto-detect.
    kicad_cli: Optional[str] = None
    rsvg_convert: Optional[str] = None
    ffmpeg: Optional[str] = None

    def label(self, key: str) -> str:
        if key in self.labels:
            return self.labels[key]
        return LABELS.get(self.language, LABELS["en"]).get(key, key)

    def output_dir(self, target: Path) -> Path:
        out = Path(self.output).expanduser()
        return out if out.is_absolute() else target / out


class ConfigError(Exception):
    pass


def load(path: Optional[Path]) -> Config:
    config = Config()
    if path is None:
        return config
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    namespace = runpy.run_path(str(path))
    known = {f.name for f in fields(Config)}
    for name, value in namespace.items():
        if name.startswith("_") or name in ("annotations",):
            continue
        if callable(value) or type(value).__name__ == "module":
            continue
        if name not in known:
            raise ConfigError(
                f"{path}: unknown setting '{name}' (known: {', '.join(sorted(known))})"
            )
        setattr(config, name, value)
    validate(config)
    return config


def validate(config: Config) -> None:
    bad = [f for f in config.formats if f not in FORMATS]
    if bad:
        raise ConfigError(f"unknown format(s) {bad}; choose from {list(FORMATS)}")
    if not 2 <= config.jpg_quality <= 31:
        raise ConfigError("jpg_quality must be between 2 and 31")
