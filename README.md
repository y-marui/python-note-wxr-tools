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
- Resolve empty or duplicate titles with `--rename "<guid>=<new title>"`.
- Lossy conversions fail; `--allow-lossy` downgrades them to warnings.
- See [docs/specification.md](docs/specification.md) for the specification.

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
| `make all` | lint + type + test |

## License

MIT License — see [LICENSE](LICENSE)

---
*This document has a Japanese canonical version [README-jp.md](README-jp.md). Update both in the same commit when editing.*
