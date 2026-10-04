# kicad-visor

Extract docs from KiCad projects: schematics, PCB layers and (eventually) history videos for social media.

## Requirements

- Python 3.9+
- KiCad 9+ (`kicad-cli`, auto-detected inside the macOS app bundle)
- `rsvg-convert` (librsvg) for png/jpg
- `ffmpeg` for jpg and video

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Usage

```bash
kicad-visor list   path/to/repo     # projects that would be processed
kicad-visor export path/to/repo     # export every project found
kicad-visor init   path/to/repo     # write an example kicad-visor-config.py
```

`export` flags: `-o/--output`, `-f/--formats svg,pdf,png,jpg`, `--dpi`, `--language es|en`, `--theme`, `-c/--config`, `-v/--verbose`.

Output goes to `<target>/docs/kicad-visor/<project>/esquematico/`. That folder is owned by kicad-visor and is wiped on each export.

## Configuration

Settings come from defaults, then `kicad-visor-config.py` in the target folder (plain Python), then command-line flags. Run `kicad-visor init` for a commented example.
