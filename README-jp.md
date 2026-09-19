# python-note-wxr-tools

> **このファイルは正本（日本語版）です。**
> 英語版（参照）は [README.md](README.md) を参照してください。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/ci.yml)
[![Charter Check](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/dev-charter-check.yml/badge.svg)](https://github.com/y-marui/python-note-wxr-tools/actions/workflows/dev-charter-check.yml)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/y-marui?style=social)](https://github.com/sponsors/y-marui)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-yellow.svg)](https://www.buymeacoffee.com/y.marui)

一行概要：note のWXRエクスポートとMarkdown原稿を相互変換し、マニフェストで検証するツール。個別の記事・画像データは扱わず、利用者のリポジトリで管理する。

## Setup

```sh
git clone https://github.com/y-marui/python-note-wxr-tools.git
cd python-note-wxr-tools
make install
```

## Usage

```sh
make all    # lint + type + test
```

| コマンド | 内容 |
|---|---|
| `make install` | `uv sync`（依存関係インストール） |
| `make lint` | `ruff check .`（linting） |
| `make type` | `mypy src`（型チェック） |
| `make test` | `pytest`（テスト実行） |
| `make all` | lint + type + test |

## License

MIT License — [LICENSE](LICENSE) を参照

---
*この文書には英語版 [README.md](README.md) があります。編集時は同一コミットで更新してください。*
