# python-note-wxr-tools

> **This is the reference (English) version.**
> The canonical (Japanese) version is [README-jp.md](README-jp.md).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/ci.yml)
[![Charter Check](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/dev-charter-check.yml/badge.svg)](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/dev-charter-check.yml)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/y-marui?style=social)](https://github.com/sponsors/y-marui)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-yellow.svg)](https://www.buymeacoffee.com/y.marui)

Convert note.com WXR exports to Markdown and back, verified by manifests. Personal article and image data live in the user's own repository, never here.

## Setup

```sh
git clone https://github.com/y-marui/python-note-wxr-tools.git
cd python-note-wxr-tools
make install
```

## Usage

### note-wxr-to-md

Convert a note export (ZIP or extracted directory) into Markdown manuscripts.

```sh
uv run note-wxr-to-md <export.zip|dir> --out <dir>
```

- Writes articles (`.md`), sidecars (`.note.json`), images (`<title>-img/`) and `.note-channel.json` under `<account>/` in `--out`.
- Existing files are never overwritten unless `--force` is given.
- Empty titles become `無題 (YYYY-MM-DD <guid prefix>)` and duplicate titles get ` (<guid prefix>)` appended, so no manual step is needed. Override any title with `--rename "<guid>=<new title>"`.
- Lossy conversions fail; `--allow-lossy` downgrades them to warnings.
- `--against <posts dir>` only reports differences and writes nothing (not combinable with `--out`). It matches manuscripts you imported by hand by `platform_post_id` and lists property and body differences; the posts directory is never written.
- See [docs/specification.md](docs/specification.md) for the specification.

### note-wxr-validate

Check a converted account folder against the specification. Exits 1 on any error.

```sh
uv run note-wxr-validate <dir>
```

- Checks required properties, image references, sidecar hashes and that `manifest.json` matches the files on disk.
- `note-wxr-to-md` writes `manifest.json` into the same folder.

### note-md-to-wxr

Turn manuscripts back into a note-importable ZIP. Give explicit article paths from one account folder.

```sh
uv run note-md-to-wxr <article.md>... --out <dir>
```

- Runs the validator first and writes nothing if it fails.
- Unedited blocks reuse their original HTML; only edited blocks are regenerated from Markdown.
- Writes `note-<account>-1.zip` and `manifest.json` into `--out`. Existing files are not overwritten without `--force`.
- `--image-map <map.json>` replaces `/assets/` references with public HTTPS URLs (`{"<file>": "https://..."}`). Any unmapped image is an error, and the output is not byte-identical to the export.
- `--allow-lossy` downgrades a missing image file, an unresolved image URL and a duplicate guid to warnings (recorded in the manifest).

### Development commands

```sh
make all    # lint + type + test
```

| Command | Description |
|---|---|
| `make install` | `uv sync` |
| `make lint` | `ruff check .` |
| `make type` | `mypy src` |
| `make test` | `pytest` |
| `make test-realdata` | Round-trip test on a real export (local only; set `NOTE_WXR_REALDATA_ZIP` to an export ZIP; not run in CI) |
| `make all` | lint + type + test |

## License

MIT License — see [LICENSE](LICENSE)

---
*This document has a Japanese canonical version [README-jp.md](README-jp.md). Update both in the same commit when editing.*
