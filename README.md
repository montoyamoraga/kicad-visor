# kicad-visor

Docs out of KiCad projects: schematics, PCB layers, 3D renders and seamlessly looping turntable videos of the board.

Made by [piruetas](https://piruetas.xyz), an art studio from Chile.

## Requirements

- Python 3.9+
- KiCad 9+ (`kicad-cli`, auto-detected inside the macOS app bundle)
- `rsvg-convert` (librsvg) for png/jpg
- `ffmpeg` for jpg and video

## Install

```bash
pip install git+https://github.com/piruetasxyz/kicad-visor
```

Or, from a clone, `pip install -e .`

## Quick start

```bash
# One turntable video of a board.
kicad-visor turntable board.kicad_pcb --axis y --direction left --background "#ff9ecf"

# Everything, for every KiCad project under a folder.
kicad-visor export path/to/repo
```

```python
import kicad_visor

kicad_visor.turntable_video("board.kicad_pcb", "flip.mp4", axis="y", direction="left",
                            background="#ff9ecf", size=(1080, 1920))

kicad_visor.export("path/to/repo")
```

## Turntable videos

Picture the board on a turntable: you pick the axis it turns around and which way it goes, and the camera stays still. Every video is one full turn, so the last frame flows into the first and it loops seamlessly.

| axis | turns around | like | direction (the face toward the camera moves…) |
|------|--------------|------|-----------------------------------------------|
| `x`  | the horizontal screen axis | a rolling drum | `down` (default) or `up` |
| `y`  | the vertical screen axis | a revolving door | `right` (default) or `left` |
| `z`  | the board's own normal | a record | `ccw` (default) or `cw`, as seen from the camera |

A `z` spin is seen from above at an angle; `x` and `y` are seen straight on. Before rendering, kicad-visor fits the camera: it renders small probe frames around the whole loop, measures where the board lands, and picks the closest zoom that keeps it in frame, whatever the board's shape or how tall its parts are.

### From Python

```python
kicad_visor.turntable_video(board, out, axis="z", direction=None, *,
                            background="#ffffff", size=(1080, 1080),
                            seconds=6)
```

| parameter | default | |
|-----------|---------|---|
| `board` | | the `.kicad_pcb` file (or its `.kicad_pro`) |
| `out` | | the video to write; the format comes from the suffix (see below) |
| `axis` | `"z"` | `"x"`, `"y"` or `"z"` |
| `direction` | first option for the axis | see the table above |
| `background` | `"#ffffff"` | any [ffmpeg color](https://ffmpeg.org/ffmpeg-utils.html#Color): `"#ff9ecf"`, `"pink"`. `None` for transparent |
| `size` | `(1080, 1080)` | `(width, height)` in pixels |
| `seconds` | `6` | loop length |

| suffix | codec | transparent background |
|--------|-------|------------------------|
| `.mp4` | H.264 | no: needs a color |
| `.mov` | ProRes 4444 when transparent, H.264 otherwise | yes, opens in any video editor |

### From the command line

```bash
kicad-visor turntable BOARD [-o OUT] [--axis x|y|z] [--direction ...] [--seconds S]
                            [--background COLOR|none] [--size WxH]
```

The output defaults to `<board>-<axis>-<direction>.mp4` in the current folder (`.mov` with `--background none`). Examples:

```bash
# A record spinning clockwise, vertical for phones.
kicad-visor turntable board.kicad_pcb --axis z --direction cw --size 1080x1920

# Tumbling forward over a transparent background, for a video editor.
kicad-visor turntable board.kicad_pcb --axis x --direction up --background none
```

### Cache

Rendered frames are cached in `~/.cache/kicad-visor/frames/`, keyed by the board file, the motion, the size and the length. Re-running, or changing the background, only re-encodes; editing the board or the motion renders again. Delete that folder to reclaim space.

## Exporting whole projects

```bash
kicad-visor list   path/to/repo     # projects that would be processed
kicad-visor export path/to/repo     # export every project found
kicad-visor init   path/to/repo     # write an example kicad-visor-config.py
```

`export` flags: `-o/--output`, `--only schematic,pcb,render,turntable`, `-f/--formats svg,pdf,png,jpg`, `--dpi`, `--quality basic|high` (3D stills), `--background COLOR|none`, `--language es|en`, `--theme`, `-c/--config`, `-v/--verbose`.

Output, per project (folder names follow `language`; these are the Spanish defaults):

```
docs/kicad-visor/
  index.html        every project, with a picture of each
  <project>/
    index.html      the project's page: everything below, ready to browse
    esquematico/    one svg/png/jpg per sheet, one multi-page pdf
    placa/          2D views: frente, reverso, cobre, todo, and each layer alone
                    (f-cu, b-cu, f-mask, b-mask, f-silks, b-silks, edge-cuts)
    3d/             renders: arriba, abajo, iso-frente, iso-reverso, perspectiva
    video/          turntables: <axis>-<direction>-<aspect>-<background>.mp4
                    e.g. z-ccw-vertical-rosado.mp4, y-right-cuadrado-durazno.mp4
```

The `index.html` pages make the output a website: open them locally, or publish the folder (see below). They show whatever is in the output folder, so exporting only some outputs still gives complete pages.

These folders are owned by kicad-visor and wiped on each export. Back-side 2D views are mirrored, as seen from behind the board. Silkscreen and board-outline views get a dark background in every format, since KiCad draws them in pale colors. 3D png files are transparent; jpg files get `background`.

Turntables are not part of the default export, because they take tens of minutes per board: add `--only turntable`. The defaults are two turntables, `z`/`ccw` and `y`/`right`, each rendered for every aspect (horizontal 1920×1080, vertical 1080×1920, square 1080×1080) and laid over every background (white, green, pink, peach): 24 videos per board.

## Publishing to GitHub Pages

[examples/github-pages.yml](examples/github-pages.yml) is a GitHub Actions workflow that exports every KiCad project in a repository and publishes the result as a website, on every push to `main`. Nothing gets committed: the renders go straight to GitHub Pages.

1. Copy it to `.github/workflows/kicad-visor.yml` in the repository with your boards.
2. In the repository's Settings > Pages, set the source to "GitHub Actions".

It runs inside the official `kicad/kicad:10.0-full` image (KiCad 10 with 3D models); change the version to match the KiCad your boards were saved with. A `kicad-visor-config.py` at the root of the repository is used, as locally. Turntable videos are off by default; add `turntable` to `ONLY` in the workflow to enable them. The first run renders frames for tens of minutes per board; they are cached between runs and only rendered again when a board changes.

## Configuration

Settings come from defaults, then `kicad-visor-config.py` in the target folder (plain Python), then command-line flags. Run `kicad-visor init` for a commented example. Turntables, backgrounds and aspects, for instance:

```python
turntables = [("z", "cw"), ("x", "up"), "y"]  # a bare axis takes its default direction
backgrounds = {"white": "#ffffff", "pink": "#ff9ecf", "clear": None}  # None: transparent .mov
aspects = {"square": (1080, 1080), "vertical": (1080, 1920)}
turntable_seconds = 6
```

From Python, pass the same settings as a `Config`:

```python
from kicad_visor import Config, export

export("path/to/repo", Config(outputs=["turntable"], turntables=[("y", "left")],
                              backgrounds={"black": "#000000"}))
```

Errors from missing or failing tools (`kicad-cli`, `rsvg-convert`, `ffmpeg`) raise `kicad_visor.ToolError`; bad settings raise `ConfigError` or `ValueError`.

## About piruetas

[piruetas](https://piruetas.xyz) is a Chilean art studio founded in 2022 by [montoyamoraga](https://montoyamoraga.io), based in Santiago de Chile, developing its first projects and products. kicad-visor started as the tool piruetas uses to document its own boards.

- web: [piruetas.xyz](https://piruetas.xyz)
- github: [github.com/piruetasxyz](https://github.com/piruetasxyz)
- instagram: [@piruetas.xyz](https://instagram.com/piruetas.xyz)

## License

MIT, see [LICENSE](LICENSE).
