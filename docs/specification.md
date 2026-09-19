# Specification

Conversion between a note.com WXR export and Markdown manuscripts.
Tracking issue: [#1](https://github.com/y-marui/python-note-wxr-tools/issues/1).
Origin: [y-marui/obsidian-vault#7](https://github.com/y-marui/obsidian-vault/issues/7).

Implementation is split across #2 (`note-wxr-to-md`), #3 (`note-md-to-wxr`),
#4 (`note-wxr-validate`, manifest), #5 (tests), #6 (`--image-map`,
`--allow-lossy`) and #7 (`--against`).

## Goal

An unedited note WXR export goes through `note-wxr-to-md` and then
`note-md-to-wxr` and comes back **byte-identical**: both every
`content:encoded` value and the whole XML file.

Output that uses `--image-map` (#6) is outside this guarantee.

## Commands

All commands share the `note-` prefix.

| Command | Purpose |
|---|---|
| `note-wxr-to-md <export.zip\|dir> --out <dir>` | WXR export to Markdown manuscripts, sidecars and images |
| `note-md-to-wxr <article.md>... --out <dir>` | Manuscripts back to a note-importable ZIP |
| `note-wxr-validate <dir>` | Check manuscripts against this specification |

Common rules:

- Existing files are never overwritten unless `--force` is given.
- Output is never written into the consuming repository directly; `--out`
  is always explicit.
- `note-md-to-wxr` takes explicit article paths only (no batch input file).
- `note-md-to-wxr` runs the validator first and refuses to write on failure.
- Every command writes a `manifest.json` next to its output (see Manifest).

## Property mapping

Each article's front matter is derived from the WXR `<item>`:

| Front matter property | WXR source | Notes |
|---|---|---|
| `title` | `title` | Equals the filename stem (see Filenames) |
| `account` | `wp:author_login` | |
| `platform_post_id` | `guid` | Unique per article |
| `publication_url` | `link` | Omitted for drafts |
| `platform_created_at` | `wp:post_date` | ISO 8601 with `+09:00` |
| `platform_updated_at` | `wp:post_modified` | ISO 8601 with `+09:00` |
| `publication_status` | `wp:status` | `publish` becomes `published`, `draft` stays `draft`; any other value fails |
| `platform` | fixed | `note` |
| `origin` | fixed | `note.com export` |

`account` is the `wp:author_login` of the channel's single `wp:author`
(an export with several authors fails). An export ZIP or directory must
contain exactly one XML file.

The remaining item fields live in the sidecar.

## Output layout

~~~text
<out>/<account-folder>/
  .note-channel.json
  <title>.md
  <title>.note.json
  <title>-img/<image files>
  manifest.json
~~~

- `<account-folder>` is the account name with `_` replaced by `-`.
- Images referenced as `/assets/<file>` in the export are copied into
  `<title>-img/` and referenced from the Markdown by relative path.
- `note-md-to-wxr` writes a ZIP with the same layout as a note export
  (`note-<account>-N.xml` and `assets/`). Image references stay
  `/assets/...` by default.

## Sidecar `<title>.note.json`

Stored next to each article. It holds everything the Markdown cannot:

- **Blocks**: for each top-level HTML block of `content:encoded`, in order,
  the original HTML (including attributes such as `name`) and the hash of
  the Markdown generated from it.
- **Item fields**: the original `title` and `link` (the front matter holds
  the filename-safe title and omits the URL for drafts), `wp:post_id`, `post_name`, `post_type`, `post_parent`,
  `menu_order`, `is_sticky`, `comment_status`, `ping_status`,
  `post_password`, `excerpt:encoded`, `description`, `dc:creator`,
  `pubDate`, `wp:post_date_gmt`, `wp:post_modified_gmt`.
- **Body hash**: hash of the whole original `content:encoded`.

Hashes are SHA-256, hex encoded, over UTF-8 bytes.

The file is JSON: `{"item": {<tag>: <text>}, "body_sha256": ..., "blocks":
[{"html": ..., "markdown_sha256": ...}]}`. Item keys are the WXR tag names
(`wp:post_id`, `excerpt:encoded`, ...). Whitespace between top-level blocks
belongs to the following block's `html`, so the `html` values concatenate to
the original body.

### Regeneration rule

On `note-md-to-wxr`, each block of the manuscript is compared with the
sidecar:

- Markdown hash unchanged: the original HTML is reused verbatim.
- Markdown edited: the block is regenerated from the Markdown.

If no block was edited, the reassembled body equals the original
`content:encoded` (checked against the body hash).

## Markdown body

The body is the blocks' Markdown joined by one blank line; a block never
contains a blank line, so `note-md-to-wxr` can split the body back into
blocks. Only these elements become Markdown: `h1`-`h6`, `p`, `ul`/`ol`
(nested), `blockquote` of paragraphs, `hr`, `pre`, `img` and a `figure` that
holds only an image with an empty caption, plus inline `strong`/`b`,
`em`/`i`, `code`, `a` and `br`. Any other block, or an empty one, is kept as
raw HTML (blank lines inside it are removed) and reported as a warning.
Attributes such as `name` are not kept in Markdown; the sidecar keeps them.

## Account-level `.note-channel.json`

Data shared by all articles of an account:

- Channel fields (`title`, `link`, `description`, `pubDate`, `language`,
  `wp:wxr_version`, ...), keyed by WXR tag name under `channel`.
- The `wp:author` block, under `author`.
- Article order: `guids`, a list of `guid`, used to order `<item>` elements.

`note-md-to-wxr` fails if this file is missing.

## Filenames

- Characters unusable in filenames become their full-width forms
  (`/` to `／`, `:` to `：`, and so on).
- Two articles with the same resulting title fail, unless resolved with
  `--rename "<guid>=<new title>"`. The renamed title is written to the
  front matter `title`.
- The account folder name replaces `_` with `-`.

## Lossy policy

| Situation | Default | With `--allow-lossy` |
|---|---|---|
| Dropped metadata (an item field not representable) | failure | warning |
| Missing image attachment | failure | warning |
| Unresolved image URL | failure | warning |
| `guid` collision | failure | warning |
| Unknown HTML element | warning (kept as raw HTML) | warning |

With `--allow-lossy`, downgraded failures are recorded in the manifest.
Anything not expressible in Markdown stays as raw HTML so the body is not
lost.

## Manifest `manifest.json`

Written next to every tool output. Schema is finalised with the validator
(#4); it contains:

- Target articles (`guid`, `title`).
- Article count, image count and total size.
- Per-article body hashes and an overall body hash.
- Warnings.
- Whether `--allow-lossy` was used.
- Tool version.
- Hashes of the input files.

`note-wxr-validate` checks that the manifest matches the files on disk.

## Validation

`note-wxr-validate <dir>` checks:

- Required properties are present and consistent (`title` matches the
  filename, valid `publication_status`, `platform_post_id`, ...).
- `<title>-img/` exists and every `<img>` resolves.
- Sidecar hashes match.
- The manifest matches the files on disk.

## Dependencies

No third-party runtime dependency at first (standard library only). Any
later dependency must be permissively licensed and actively maintained, so
that the project can be made closed later.
