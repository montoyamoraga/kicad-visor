"""Configuration: defaults, overridden by a Python config file, overridden by CLI flags.

A config file is plain Python. Every top-level name that matches a field of
`Config` is picked up; unknown names that don't start with an underscore are
an error, so typos don't silently do nothing.
"""

from __future__ import annotations

import runpy
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kicad_visor.motion import check

CONFIG_FILENAME = "kicad-visor-config.py"

FORMATS = ("svg", "pdf", "png", "jpg")
OUTPUTS = ("schematic", "pcb", "render", "turntable")
# Turntables take minutes per board, so they only run when asked for.
DEFAULT_OUTPUTS = ("schematic", "pcb", "render")

# Words used in folder and file names. View names are looked up here too, so
# a view called "front" lands in "frente.png" when language = "es".
LABELS = {
    "es": {
        "schematic": "esquematico",
        "pcb": "placa",
        "render": "3d",
        "front": "frente",
        "back": "reverso",
        "copper": "cobre",
        "all": "todo",
        "top": "arriba",
        "bottom": "abajo",
        "iso-front": "iso-frente",
        "iso-back": "iso-reverso",
        "perspective": "perspectiva",
        "turntable": "video",
        "horizontal": "horizontal",
        "vertical": "vertical",
        "square": "cuadrado",
        "white": "blanco",
        "black": "negro",
        "green": "verde",
        "pink": "rosado",
        "peach": "durazno",
        # Words on the generated web pages.
        "projects": "proyectos",
        "made-with": "hecho con",
    },
    "en": {
        "schematic": "schematic",
        "pcb": "pcb",
        "render": "3d",
        "turntable": "video",
        "made-with": "made with",
    },
}

EDGE = "Edge.Cuts"
LAYERS = ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", EDGE]

# Behind layers KiCad draws in pale colors (silkscreen, board outline),
# which vanish on white.
DARK = "#2b3530"

# 2D PCB views. Each is one image made of `layers`; back views are mirrored
# so they read as seen from behind the board. "background" paints behind the
# view in every format; without it, png/jpg get `background` and svg/pdf
# stay transparent.
PCB_VIEWS: List[Dict[str, Any]] = [
    {"name": "front", "layers": ["F.Cu", "F.Mask", "F.SilkS", EDGE]},
    {"name": "back", "layers": ["B.Cu", "B.Mask", "B.SilkS", EDGE], "mirror": True},
    {"name": "copper", "layers": ["F.Cu", "B.Cu", EDGE]},
    {"name": "all", "layers": LAYERS},
] + [
    # Every layer alone, with the board outline for context.
    {"name": layer, "layers": [layer] if layer == EDGE else [layer, EDGE],
     "mirror": layer.startswith("B."),
     **({"background": DARK} if layer in ("F.SilkS", "B.SilkS", EDGE) else {})}
    for layer in LAYERS
]

# 3D stills. Keys: side, rotate (x, y, z degrees), zoom, pan, pivot,
# perspective, floor, quality.
RENDER_VIEWS: List[Dict[str, Any]] = [
    {"name": "top", "side": "top", "zoom": 0.9},
    {"name": "bottom", "side": "bottom", "zoom": 0.9},
    {"name": "iso-front", "rotate": (-45, 0, 45)},
    {"name": "iso-back", "rotate": (-135, 0, 135)},
    {"name": "perspective", "rotate": (-60, 0, 30), "perspective": True, "floor": True},
]

# Turntable videos, one per (axis, direction); see kicad_visor.motion.AXES.
TURNTABLES: List[Tuple[str, str]] = [
    ("z", "ccw"),    # spins like a record, seen from above at an angle
    ("y", "right"),  # turns around the vertical axis, showing front then back
]

# Video backgrounds, name -> color. Names go in file names; colors are
# anything ffmpeg understands. None is transparent (written as .mov).
BACKGROUNDS: Dict[str, Optional[str]] = {
    "white": "#ffffff",
    "green": "#7ed957",
    "pink": "#ff9ecf",
    "peach": "#ffcba4",
}

# Social media frames; each is rendered and framed separately.
ASPECTS: Dict[str, Tuple[int, int]] = {
    "horizontal": (1920, 1080),
    "vertical": (1080, 1920),
    "square": (1080, 1080),
}


@dataclass
class Config:
    # Output folder, relative to the target folder unless absolute.
    output: str = "docs/kicad-visor"
    # Language for folder names, captions and video text.
    language: str = "es"
    # Per-key overrides of the built-in labels for `language`.
    labels: Dict[str, str] = field(default_factory=dict)
    # What to export.
    outputs: List[str] = field(default_factory=lambda: list(DEFAULT_OUTPUTS))
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
    # 2D PCB views, see PCB_VIEWS above.
    pcb_views: List[Dict[str, Any]] = field(default_factory=lambda: list(PCB_VIEWS))
    # 3D renders, see RENDER_VIEWS above. Always png (transparent) and jpg.
    render_views: List[Dict[str, Any]] = field(default_factory=lambda: list(RENDER_VIEWS))
    render_size: Tuple[int, int] = (2000, 2000)
    # basic (fast) or high (shadows, ~5x slower).
    render_quality: str = "basic"
    # Turntable videos, see TURNTABLES, BACKGROUNDS and ASPECTS above. A bare
    # axis ("x") takes its default direction.
    turntables: List[Tuple[str, str]] = field(default_factory=lambda: list(TURNTABLES))
    backgrounds: Dict[str, Optional[str]] = field(default_factory=lambda: dict(BACKGROUNDS))
    aspects: Dict[str, Tuple[int, int]] = field(default_factory=lambda: dict(ASPECTS))
    # Length of each loop.
    turntable_seconds: float = 6
    fps: int = 30
    # H.264 quality, lower is better (18 is visually lossless).
    video_crf: int = 18
    # Frames rendered in parallel; kicad-cli spends part of each frame
    # starting up on one core.
    render_jobs: int = 2
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
        # _private and ALL_CAPS names are the config file's own helpers,
        # e.g. `from kicad_visor.config import PCB_VIEWS`.
        if name.startswith("_") or name.isupper() or name == "annotations":
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
    bad = [o for o in config.outputs if o not in OUTPUTS]
    if bad:
        raise ConfigError(f"unknown output(s) {bad}; choose from {list(OUTPUTS)}")
    for view in config.pcb_views + config.render_views:
        if "name" not in view:
            raise ConfigError(f"view without a name: {view}")
    if config.render_quality not in ("basic", "high"):
        raise ConfigError("render_quality must be 'basic' or 'high'")
    turntables = []
    for motion in config.turntables:
        axis, direction = (motion, None) if isinstance(motion, str) else motion
        try:
            turntables.append((axis, check(axis, direction)))
        except ValueError as error:
            raise ConfigError(str(error)) from None
    config.turntables = turntables
    if config.turntable_seconds <= 0:
        raise ConfigError("turntable_seconds must be positive")
    if not 2 <= config.jpg_quality <= 31:
        raise ConfigError("jpg_quality must be between 2 and 31")
