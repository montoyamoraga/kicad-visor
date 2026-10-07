"""A browsable website out of the exported files: an index of projects, and
one page per project with its schematic, board views, renders and videos.

Pages are built from what is in the output folder, not from one run, so an
export of only some outputs still gets a complete page. Static hosts such as
GitHub Pages don't list folders, so without these pages the files would only
be reachable by their exact paths.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from kicad_visor.config import OUTPUTS, Config
from kicad_visor.util import slug

# What to show for a group of files with the same name, best first. The other
# formats are offered as links.
SHOWN = (".mp4", ".svg", ".png", ".jpg")
VIDEOS = (".mp4",)

STYLE = """
:root {
  --bg: #ffffff; --fg: #1d1d1b; --muted: #6b6b66; --card: #f3f2ee;
  --line: #e2e0da; --link: #1d1d1b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --fg: #ecebe6; --muted: #9a9993; --card: #222220;
    --line: #333331; --link: #ecebe6;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 1200px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 2rem; margin: 8px 0 24px; overflow-wrap: anywhere; }
h2 {
  font-size: 1.1rem; text-transform: lowercase; letter-spacing: .04em;
  color: var(--muted); border-top: 1px solid var(--line);
  padding-top: 16px; margin: 40px 0 16px;
}
a { color: var(--link); }
.back { color: var(--muted); text-decoration: none; }
.grid {
  display: grid; gap: 16px; align-items: start;
  grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
}
figure {
  margin: 0; min-width: 0; background: var(--card); border-radius: 8px; overflow: hidden;
}
.media {
  display: flex; align-items: center; justify-content: center;
  aspect-ratio: 4 / 3; background: #ffffff;
}
.media img, .media video { width: 100%; height: 100%; object-fit: contain; display: block; }
figcaption {
  padding: 8px 12px; font-size: .875rem; display: flex; gap: 8px;
  flex-wrap: wrap; justify-content: space-between; overflow-wrap: anywhere;
}
figcaption span { color: var(--muted); }
footer { margin-top: 64px; color: var(--muted); font-size: .875rem; }
"""

# Videos play only while on screen: a page can hold dozens of them.
SCRIPT = """
const seen = new IntersectionObserver((entries) => {
  for (const e of entries) e.isIntersecting ? e.target.play() : e.target.pause();
}, { threshold: 0.25 });
document.querySelectorAll("video").forEach((v) => seen.observe(v));
"""


def _page(title: str, body: str, config: Config) -> str:
    lang = "es" if config.language == "es" else "en"
    return (f'<!doctype html>\n<html lang="{lang}">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(title)}</title>\n<style>{STYLE}</style>\n</head>\n"
            f"<body>\n<main>\n{body}\n"
            f'<footer>{html.escape(config.label("made-with"))} '
            '<a href="https://github.com/piruetasxyz/kicad-visor">kicad-visor</a></footer>\n'
            f"</main>\n<script>{SCRIPT}</script>\n</body>\n</html>\n")


def _href(path: Path, base: Path) -> str:
    return quote(path.relative_to(base).as_posix())


def _groups(folder: Path) -> List[List[Path]]:
    """Files of `folder` grouped by name, in the order they were written."""
    groups: Dict[str, List[Path]] = {}
    for path in folder.iterdir():
        if path.is_file() and not path.name.startswith(".") and path.suffix != ".html":
            groups.setdefault(path.stem, []).append(path)
    # Exporters write views in their configured order (front before back),
    # which modification times keep and names don't.
    return sorted(groups.values(), key=lambda files: (min(f.stat().st_mtime for f in files),
                                                       files[0].stem))


def _shown(files: List[Path]) -> Optional[Path]:
    for suffix in SHOWN:
        for path in files:
            if path.suffix == suffix:
                return path
    return None


def _figure(files: List[Path], base: Path) -> str:
    shown = _shown(files)
    name = html.escape(files[0].stem)
    links = " · ".join(f'<a href="{_href(f, base)}">{f.suffix[1:]}</a>'
                       for f in sorted(files, key=lambda f: f.suffix))
    if shown is None:
        media = ""
    elif shown.suffix in VIDEOS:
        media = (f'<div class="media"><video src="{_href(shown, base)}" muted loop '
                 'playsinline preload="metadata"></video></div>')
    else:
        media = (f'<a class="media" href="{_href(shown, base)}"><img src="{_href(shown, base)}" '
                 f'alt="{name}" loading="lazy"></a>')
    return f"<figure>{media}<figcaption>{name}<span>{links}</span></figcaption></figure>"


def _sections(project: Path, config: Config) -> List[Path]:
    """The project's output folders, in export order, then any others."""
    known = [slug(config.label(output)) for output in OUTPUTS]
    folders = [p for p in project.iterdir() if p.is_dir() and not p.name.startswith(".")]
    return sorted(folders, key=lambda p: (known.index(p.name) if p.name in known
                                          else len(known), p.name))


def _thumbnail(project: Path, config: Config) -> Optional[Path]:
    """A picture for the project: a 3D render if there is one, else a board view."""
    order = ["render", "pcb", "schematic"]
    for output in order:
        folder = project / slug(config.label(output))
        if folder.is_dir():
            for files in _groups(folder):
                shown = _shown(files)
                if shown is not None and shown.suffix not in VIDEOS:
                    return shown
    return None


def write(out_root: Path, config: Config, title: str) -> List[Path]:
    """Write index.html for `out_root` and for each project folder in it."""
    projects = sorted(p for p in out_root.iterdir()
                      if p.is_dir() and not p.name.startswith(".") and _sections(p, config))
    written: List[Path] = []

    cards = []
    for project in projects:
        body = [f'<a class="back" href="../index.html">← {html.escape(config.label("projects"))}</a>',
                f"<h1>{html.escape(project.name)}</h1>"]
        for folder in _sections(project, config):
            figures = "\n".join(_figure(files, project) for files in _groups(folder))
            if figures:
                body.append(f"<h2>{html.escape(folder.name)}</h2>\n"
                            f'<div class="grid">\n{figures}\n</div>')
        page = project / "index.html"
        page.write_text(_page(project.name, "\n".join(body), config), encoding="utf-8")
        written.append(page)

        thumb = _thumbnail(project, config)
        media = (f'<div class="media"><img src="{_href(thumb, out_root)}" alt="" loading="lazy"></div>'
                 if thumb else "")
        cards.append(f'<figure><a href="{quote(project.name)}/index.html">{media}</a>'
                     f'<figcaption><a href="{quote(project.name)}/index.html">'
                     f"{html.escape(project.name)}</a></figcaption></figure>")

    body = (f"<h1>{html.escape(title)}</h1>\n<h2>{html.escape(config.label('projects'))}</h2>\n"
            f'<div class="grid">\n' + "\n".join(cards) + "\n</div>")
    index = out_root / "index.html"
    index.write_text(_page(title, body, config), encoding="utf-8")
    written.append(index)
    return written
