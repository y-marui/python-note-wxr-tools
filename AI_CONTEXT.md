# AI_CONTEXT.md

> このファイルは Claude Code・GitHub Copilot など AI ツールが唯一参照するコンテキストファイルです。
> セッション開始時に必ず読み込んでください。

---

## AI Reference Order

AI はタスク開始時に以下の順で参照する:

1. `README.md`（概要・セットアップ）
2. `CONTRIBUTING.md`（PR・Issue ルール・開発フロー）

必要に応じて以下を参照する（順不同）:

- `docs/architecture.md`（モジュール・コンポーネント構造）
- `docs/file-map.md`（ファイルレベルの依存関係 ※情報が足りない・古い場合は適宜探索し、追記・更新する）
- `docs/specification.md`（機能仕様・データフロー）
- `docs/ui-design.md`（UI 設計・コンポーネント仕様）

---

## Project Overview

**目的:** note の WXR エクスポートと Markdown 原稿を相互変換する Python ツール（`note-wxr-to-md` / `md-to-note-wxr`）。
uv + Claude Code + GitHub Copilot 前提の OSS。

**チーム規模:** 個人〜3人（小規模チーム）。アジャイルで迅速な意思決定を重視。

**技術スタック:**

バージョン管理・パッケージ管理・Lint/Format・型チェックの一般方針は
[docs/dev-charter/topics/python/PYTHON_DEV_ENV.md](docs/dev-charter/topics/python/PYTHON_DEV_ENV.md)
を参照（CLI を実装する場合は
[docs/dev-charter/topics/python/PYTHON_CLI.md](docs/dev-charter/topics/python/PYTHON_CLI.md) も参照）。

**主要ディレクトリ:**

```
src/note_wxr_tools/   # パッケージ本体
tests/unit/         # 単体テスト
tests/integration/  # 統合テスト
docs/               # 仕様書・ナレッジベース（人間・AI 共用。仕様変更は依頼・承認を経て記述）
docs/dev-charter/   # 開発憲章（git subtree で取り込み）

```

**モジュール構成:** 変換ロジックは `src/note_wxr_tools/` に置く。コマンドは `note-wxr-to-md` / `note-md-to-wxr` / `note-wxr-validate`。詳細な仕様は [docs/specification.md](docs/specification.md) と [#1](https://github.com/y-marui/python-note-wxr-tools/issues/1) を参照。

**AI コンテキスト優先順位:**
1. タスクコンテキスト（Issue / Pull Request）
2. プロジェクトコンテキスト（`AI_CONTEXT.md`・プロジェクトドキュメント）
3. 開発憲章（`docs/dev-charter/`）
4. グローバルコンテキスト

---

## Applied Charter Principles

### Pre-Coding Checklist

不明・未定の項目があれば**作業前に1回でまとめて**質問する。推測で進めない。

**確認必須:**
- ゴール（完了条件）
- 言語・FW・バージョン制約
- 新規 or 既存コード修正
- テストの要否
- 影響範囲

**確認不要（既存コードに合わせて進める）:**
- コードスタイル / ファイル配置 / 軽微な実装詳細

### Development Philosophy（`docs/dev-charter/topics/SOFTWARE_DESIGN_PRINCIPLES.md`）

- まず小さなツールを構築する（段階的に拡張する）
- ローカルファーストのデザインを優先する（外部サービス依存を避ける）
- インフラストラクチャを最小限に保つ
- **最小限の依存関係**: 新規依存追加前に既存の依存で解決できないか必ず検討する
- オフライン機能を優先する（外部サービスなしで動作することを基本とする）

### Code Design Principles（`docs/dev-charter/PRINCIPLES.md`）

- **変更範囲は必要最小限**（Over-engineering しない）
- **YAGNI**: 今必要ない機能は実装しない
- **DRY の判断**: 2回の重複では抽象化しない、3回目で検討
- **既存コードの再利用**: 新規実装前に類似機能がないか確認
- **TODO/FIXME を残さない**: 実装するか、issue として記録する
- **既存コードのパターンに従う**: 命名規則・アーキテクチャ・ディレクトリ構造

### Coding Rules

- 可読性優先
- 関数は **50行以内**
- 単一責務
- コメントは「なぜそうするか」のみ。コードから自明な処理には書かない

### Git Workflow

- **Conventional Commits** 形式（`feat` / `fix` / `refactor` / `docs` / `chore`）
- **WIP 禁止**: 動作しないコードはコミットしない
- ブランチ戦略・PR フローなど開発者向け詳細は [CONTRIBUTING.md](CONTRIBUTING.md) を参照

### Work Stance

- **スコープ厳守**: 会話の主題・タスク・ゴールを AI が勝手に変更しない。話題変更はユーザーが明示するか、AI の提案をユーザーが許可した場合のみ
- **不明点の扱い**: 重要な情報不足や曖昧さは質問する。軽微な不足は合理的な仮定で補い、仮定を明示する。推測で断定しない
- 大きな変更前に方針を説明してから着手する
- 不要な依存追加禁止: 既存の依存で解決できないか先に検討する

### Document Sync Rule

仕様・ルール・構成に変更が生じたとき、変更と同じ作業内で関連ドキュメントを更新する。
対象は `docs/` 内のファイルに限らず、`AI_CONTEXT.md`・`README.md` 等のルートファイルも含む。

### dev-charter Modification Rules

`docs/dev-charter/` 配下のファイルを**直接編集しない**。

- 変更が必要な場合は dev-charter リポジトリ本体に Issue を立て、`git subtree pull` でアップデートを取り込む
- `git subtree pull` によるアップデートのみ許可する
- このプロジェクト固有のルールは、`AI_CONTEXT.md` または専用ファイルに記載する

### Charter Lookup

憲章参照: `docs/dev-charter/CHARTER_INDEX.md` でトピックを特定してから該当ファイルのみ読む

不明点が憲章に関係する場合は全ファイルを検索せず、以下の手順で参照する:

1. `docs/dev-charter/CHARTER_INDEX.md` を読み、該当トピックのファイルを特定する
2. 特定したファイル（原則 1〜2 件）のみを読む
3. 参照後にユーザーへ提案・確認を行う

### Error & Debug Handling

- エラー発生時は **原因分析 → 修正方針説明 → 実装** の順で進める
- エラーログ・スタックトレースは必ず**全文確認**してから対応（推測で修正しない）
- デバッグ用の `print` 文は本番コードに残さない

### Task Workflows

**バグ修正:**
1. 再現確認
2. 原因特定
3. 最小修正
4. テスト追加

**機能実装:**
1. `docs/specification.md` で仕様確認
2. `docs/architecture.md` でアーキテクチャ確認
3. 最小変更で実装
4. テスト追加

**テスト作成:**
1. テスト対象の仕様を `docs/specification.md` で確認
2. 正常系・異常系・境界値を洗い出す
3. fixture は `tests/conftest.py` に定義
4. モックは Protocol ベースで注入する
5. テスト名は `test_<対象>_<条件>_<期待結果>` の形式

### Review Checklist

- 仕様準拠
- テスト存在
- 可読性
- 依存関係問題なし

---

## Project-Specific Rules

### Data Separation Policy

このリポジトリは公開（OSS）であり、ツールのコードだけを置く。

- 実際の note 記事・画像・WXR・マニフェスト・公開 URL は置かない（原稿の正本は個人 vault `y-marui/obsidian-vault` の `posts/`）
- テストのフィクスチャは合成データだけを使う
- 出力先の規則（`posts/README.md` の原稿本文・プロパティ・画像命名）は vault 側が定義し、本ツールは検証機能として実装する
- 経緯: [obsidian-vault#7](https://github.com/y-marui/obsidian-vault/issues/7)

### Monetization Policy

- 独自の課金システムは**原則禁止**（メンテナンスコスト・セキュリティリスクのため）
- OSS の場合: **Buy Me a Coffee + GitHub Sponsors** を使用する
- マネタイズを本格検討する場合は `MONETIZATION.md` をリポジトリに作成し、この `AI_CONTEXT.md` に概要を追記する

### Language Policy

このプロジェクトは **OSS** のため、ドキュメント・コード・コメントは**英語**を基本とする。

| ファイル | 言語 |
|---|---|
| `README.md` | 英語（国際的な参照用） |
| `README-jp.md` | 日本語（正本）※ 必要に応じて作成 |
| ソースコード・コメント | 英語 |
| `AI_CONTEXT.md` | 日本語（開発チーム内部ツール、ユーザー判断による） |

日英両方のドキュメントが存在する場合は**日本語版を正本**として編集し、英語版をそれに合わせて更新する（英語版を独立して編集しない）。

### docs/ Role

| ディレクトリ | 役割 | AI の編集 |
|---|---|---|
| `docs/` | 人間・AI 共用の詳細仕様書 | 更新可。ただし仕様・設計判断の変更は、ユーザーの依頼または提案への承認を経て記述する |
| `docs/dev-charter/` | 開発憲章（git subtree） | **禁止**（直接編集しない。変更は dev-charter 本体に Issue を立て、`git subtree pull` で取り込む） |

### CI / Local Development Commands

```sh
make install        # uv sync
make lint           # ruff check .
make format         # ruff format .
make type           # mypy src
make test           # pytest
make all            # lint + type + test
make update-charter # git subtree pull で dev-charter を最新化
```

CI（GitHub Actions）は push / PR のたびに `security` → `lint`（ruff check / format / mypy）→ `test`（pytest）→ `build` の順で実行。

### Pre-commit Hooks (.pre-commit-config.yaml)

セキュリティ・品質チェックが自動で走る。セットアップ手順は [CONTRIBUTING.md](CONTRIBUTING.md) を参照。以下が有効:

| フック | 内容 |
|---|---|
| gitleaks | シークレット検出（`.gitleaks.toml` 設定） |
| detect-private-key | SSH 秘密鍵検出 |
| detect-dotenv | `.env` ファイルのコミットをブロック |
| no-hardcoded-local-paths | ローカル絶対パスのハードコードをブロック |
| check-added-large-files | 500 KB 超ファイルをブロック |
| trailing-whitespace / end-of-file-fixer | 空白・改行の正規化 |
| check-yaml / check-json / check-merge-conflict | 構文・競合チェック |
| shellcheck | シェルスクリプト静的解析 |

**コードレビュー要件:**
- `main` に到達するコミットは必ず他の開発者がレビューする
- 認証・認可・暗号化・データアクセスに関わる変更はセキュリティレビューを必須とする

---

## AI Tool Assignments

- **使用ツール**：Claude Code、GitHub Copilot、Gemini CLI
- **標準担当の正本**：`docs/dev-charter/AI_COLLABORATION_RULES.md` の「AI Tool Responsibilities」と「Rules for Multi-AI Usage」
- **このリポジトリ固有の上書き**：なし

---

## Prohibited Actions

### Security Constraints

- シークレット・API キー・パスワード・トークンを**絶対にコードに書かない**（環境変数または Secret Manager を使う）
- `.env` ファイルをコミットしない（ダミー値のみの `.env.example` をコミットする）
- SSH 秘密鍵・クラウドトークンをコミットしない
- ローカル絶対パス（`/Users/...`、`/home/...`、`C:\Users\...`）をコードにハードコードしない
- 500 KB を超えるファイルをコミットしない
- AI との会話ログをリポジトリにコミットしない
- **シークレットを含むファイルやコードを AI に渡さない**（プロンプト・コンテキスト・スクリーンショット含む）
- **AI が生成したコードは必ずレビューしてからコミットする**

### Prohibited Out-of-Scope Changes

- **API 仕様変更禁止**: API レスポンス変更・エンドポイント削除（破壊的変更で他サービスに影響）
- **設計変更禁止**: ディレクトリ構造変更・モジュール移動（アーキテクチャの一貫性を保つため）
- **大規模リファクタ禁止**: 意図しない挙動変化を防ぐため（明示的に依頼された場合を除く）
- **依存追加禁止**: ライセンス・セキュリティリスクを人間がレビューするため。必要な場合は Issue を作成する
- **WIP コミット禁止**: 動作しないコードはコミットしない
- `docs/dev-charter/` 配下を AI が直接編集しない（`docs/` のそれ以外は編集可。仕様変更は依頼・承認を経る）
