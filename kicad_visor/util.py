"""Small helpers shared by the exporters."""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path


def slug(text: str) -> str:
    """'Fuente de alimentación' -> 'fuente-de-alimentacion'."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower() or "sin-nombre"


def fresh_dir(path: Path) -> Path:
    """Empty `path` (creating it if needed). Output folders belong to kicad-visor:
    clearing them drops files for sheets/views that no longer exist."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path
