"""Finding KiCad projects under a folder."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional


@dataclass
class Project:
    pro: Path

    @property
    def name(self) -> str:
        return self.pro.stem

    @property
    def folder(self) -> Path:
        return self.pro.parent

    @property
    def schematic(self) -> Optional[Path]:
        path = self.pro.with_suffix(".kicad_sch")
        return path if path.is_file() else None

    @property
    def pcb(self) -> Optional[Path]:
        """The board file, or None if missing or not laid out yet (no
        footprints), so PCB, 3D and video exports skip it."""
        path = self.pro.with_suffix(".kicad_pcb")
        if not path.is_file() or "(footprint " not in path.read_text(encoding="utf-8"):
            return None
        return path


def _excluded(relative: Path, patterns: List[str]) -> bool:
    # fnmatch's "*" also matches "/", and the "./" prefix lets "**/env/**"
    # catch an env folder sitting right at the top of the target.
    candidate = "./" + relative.as_posix()
    return any(fnmatch(candidate, pattern) for pattern in patterns)


def find_projects(target: Path, exclude: List[str]) -> List[Project]:
    target = target.resolve()
    if target.is_file():
        if target.suffix != ".kicad_pro":
            target = target.with_suffix(".kicad_pro")
        return [Project(target)]
    return [
        Project(pro)
        for pro in sorted(target.rglob("*.kicad_pro"))
        if not _excluded(pro.relative_to(target), exclude)
    ]
