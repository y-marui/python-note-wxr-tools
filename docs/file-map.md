# File Map

ファイルレベルの依存関係を記録するドキュメント。初回コード探索後に追記していく。

## How to Record

各ファイルについて、主要な import 元・呼び出し元・呼び出し先を記録する。

```
src/note_wxr_tools/
  __init__.py
    - exports: (公開シンボル)

  module_a.py
    - imports: module_b, module_c
    - used by: module_x
```

## File Dependency Map

<!-- 初回探索後にここへ追記する -->

```
src/note_wxr_tools/
  wxr.py
    - imports: (標準ライブラリのみ)
    - used by: to_md
  htmlmd.py
    - imports: (標準ライブラリのみ)
    - used by: to_md
  manifest.py
    - imports: (標準ライブラリのみ)
    - used by: to_md, validate
  frontmatter.py
    - imports: (標準ライブラリのみ)
    - used by: validate
  to_md.py
    - imports: wxr, htmlmd, manifest
    - used by: CLI エントリポイント `note-wxr-to-md`
  validate.py
    - imports: manifest, frontmatter, htmlmd
    - used by: CLI エントリポイント `note-wxr-validate`
```
