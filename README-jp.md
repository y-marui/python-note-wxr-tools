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

### note-wxr-to-md

note のエクスポート（ZIP または展開済みディレクトリ）を Markdown 原稿に変換する。

```sh
uv run note-wxr-to-md <export.zip|dir> --out <dir>
```

- `--out` 配下の `<アカウント>/` に、記事 `.md`、サイドカー `.note.json`、画像 `<タイトル>-img/`、`.note-channel.json` を出力する。
- 既存ファイルは `--force` を付けない限り上書きしない。
- タイトルが空の記事は `無題 (YYYY-MM-DD <guid 先頭6文字>)`、重複する記事は末尾に ` (<guid 先頭6文字>)` を付けて自動的に命名する（手作業は不要）。`--rename "<guid>=<新タイトル>"` で個別に上書きできる。
- 情報が失われる変換は失敗する。警告に下げるには `--allow-lossy` を付ける。
- `--against <posts dir>` は書き出さずに差分だけを報告する（`--out` とは併用不可）。手で取り込んだ原稿と `platform_post_id` で照合し、プロパティと本文の差分を出す。posts 側には一切書き込まない。
- `--into <posts dir>` は既存の posts ディレクトリに新規記事を追加する（`--out`・`--against` とは併用不可）。`platform_post_id` で一致し変更のない記事はスキップし、差分のある記事は `--against` と同じ差分を報告して何も書かず終了コード 1 で終わる。`--force` を付けると `editorial_note` などの追加プロパティを残したまま上書きする。posts 側にしかないファイルは削除しない。`<アカウント>/.note-channel.json` は無ければ作成し、あれば新しい guid を追加する形で更新する（何も削除しない）ため、`note-md-to-wxr` で再エクスポートできる。
- 仕様は [docs/specification.md](docs/specification.md) を参照。

### note-wxr-validate

変換した原稿フォルダ（アカウントフォルダ）を仕様に照らして検査する。エラーがあれば終了コード 1 を返す。

```sh
uv run note-wxr-validate <dir>
```

- 必須プロパティ、画像の参照先、サイドカーのハッシュ、`manifest.json` とディスクの一致を確認する。
- `note-wxr-to-md` は同じフォルダに `manifest.json` を書き出す。

### note-md-to-wxr

原稿を note にインポートできる ZIP に戻す。原稿は同じアカウントフォルダのものを明示的に指定する。

```sh
uv run note-md-to-wxr <article.md>... --out <dir>
```

- 先に validator を実行し、失敗したら何も書かない。
- 編集していないブロックは元の HTML を再利用し、編集したブロックだけ Markdown から再生成する。
- `--out` に `note-<アカウント>-1.zip` と `manifest.json` を出力する。既存ファイルは `--force` なしでは上書きしない。
- `--image-map <map.json>` で `/assets/` の参照を公開 HTTPS URL に置き換える（`{"<ファイル名>": "https://..."}`）。未マップの画像があればエラー。この出力は元のエクスポートと byte 一致しない。
- `--allow-lossy` で、画像ファイル欠落・解決できない画像 URL・guid 重複を警告に下げる（manifest に記録）。

### Development commands

```sh
make all    # lint + type + test
```

| コマンド | 内容 |
|---|---|
| `make install` | `uv sync`（依存関係インストール） |
| `make lint` | `ruff check .`（linting） |
| `make type` | `mypy src`（型チェック） |
| `make test` | `pytest`（テスト実行） |
| `make test-realdata` | 実データの往復テスト（ローカル専用。`NOTE_WXR_REALDATA_ZIP` に実際のエクスポート ZIP を指定。CI では実行しない） |
| `make all` | lint + type + test |

## License

MIT License — [LICENSE](LICENSE) を参照

---
*この文書には英語版 [README.md](README.md) があります。編集時は同一コミットで更新してください。*
