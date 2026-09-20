# Specification

Conversion between a note.com WXR export and Markdown manuscripts.
Tracking issue: [#1](https://github.com/y-marui/python-note-wxr-tools/issues/1).
Origin: [y-marui/obsidian-vault#7](https://github.com/y-marui/obsidian-vault/issues/7).

Implementation is split across #2 (`note-wxr-to-md`), #3 (`note-md-to-wxr`),
#4 (`note-wxr-validate`, manifest), #5 (tests), #6 (`--image-map`,
`--allow-lossy`), #7 (`--against`) and #21 (`--into`).

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
| `note-wxr-to-md <export.zip\|dir> --into <posts dir>` | Add new articles to an existing posts directory |
| `note-md-to-wxr <article.md>... --out <dir>` | Manuscripts back to a note-importable ZIP |
| `note-wxr-validate <dir>` | Check manuscripts against this specification |

Common rules:

- Existing files are never overwritten unless `--force` is given.
- Output is never written into the consuming repository unless the target is
  named explicitly with `--out` or `--into`.
- `note-md-to-wxr` takes explicit article paths only (no batch input file).
- `note-md-to-wxr` runs the validator first and refuses to write on failure.
- Every command writes a `manifest.json` next to its output (see Manifest).

## Difference report `--against`

`note-wxr-to-md <export> --against <posts dir>` is a report-only mode for
migrating manuscripts that were imported by hand. It cannot be combined with
`--out` and writes nothing; the posts directory is only ever read, so
hand-written properties such as `editorial_note` are safe.

- Manuscripts under the posts directory (searched recursively) are matched to
  export articles by `platform_post_id`. Files without front matter or
  without that property are ignored; a duplicate id is a warning.
- For each matched article it lists property differences (a generated
  property that is missing or has another value; extra properties in the posts
  file are ignored) and a unified diff of the body. Block `name` and `id`
  attributes in HTML are ignored, since hand imports dropped them. A long diff
  is cut after 40 lines.
- It also lists articles that are new in the export and manuscripts that are
  only in the posts directory, limited to those without an `account` or with
  the export's account (`_` and `-` are treated alike).
- Empty and duplicate titles are named automatically (see Filenames), so the
  report can still be produced. Other problems, such as a missing image, still
  fail unless `--allow-lossy` is given.
- The exit code is 0 whether or not differences are found; it is a report.

## Import into a posts directory `--into`

`note-wxr-to-md <export> --into <posts dir>` applies the export to an existing
posts directory without manual merging. Articles are matched to manuscripts
(searched recursively) by `platform_post_id`, as in `--against`.

- New article (no manuscript with that id): the manuscript, sidecar and images
  are written under `<posts dir>/<account>/` (the account folder name replaces
  `_` with `-`).
- Matched and unchanged (no difference as defined for `--against`): skipped.
- Matched and different: nothing is written. The difference report is printed
  as for `--against` and the exit code is 1. With `--force` the manuscript,
  its sidecar and images are overwritten in place; the existing file name is
  kept, and front matter properties the export does not define (such as
  `editorial_note`, including multi-line values) are copied back.
- Files that exist only in the posts directory are never deleted.
- A new article whose file name is already taken by another file fails, and
  nothing is written (use `--rename`).
- `manifest.json` describes a whole export, so it is not written into an
  existing posts directory.
- `<account>/.note-channel.json` is created when missing, so an imported
  account can be re-exported with `note-md-to-wxr`. When it exists, the
  `channel` and `author` fields are replaced by the export's and `guids`
  keeps its order with new guids appended; nothing is removed, and other keys
  are kept. An unreadable file fails before anything is written. The summary
  line ends with `channel created`, `channel updated` or `channel unchanged`.
- Not combinable with `--out` or `--against`. Filenames follow the Filenames
  rules; the exit code is 0 when nothing differs.

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

## `note-md-to-wxr` output

`note-md-to-wxr <article.md>... --out <dir>` takes articles from one account
folder and writes, into `<dir>`:

- `note-<account>-1.zip` holding `note-<account>-1.xml` and `assets/<file>`.
  Only images still referenced by the rebuilt bodies are included; each is
  read from `<title>-img/<file>`. The ZIP entries have a fixed timestamp.
- `manifest.json` describing that output (`command` is `note-md-to-wxr`).
  `articles[].body_sha256` is the hash of the rebuilt `content:encoded`.

`--image-map <map.json>` replaces the `/assets/<file>` references of the
rebuilt bodies with public HTTPS URLs, for re-importing into note. The map is
a JSON object of `{"<file>": "https://..."}` (a `/assets/` prefix on the key
is accepted). Every image referenced must be mapped and every URL must be
`https://`, otherwise nothing is written. No images are packed into the ZIP,
and the manifest records `image_map.replaced` (the number of references
replaced) and the map file's hash. Output made with this option is outside
the byte-exact guarantee. Local files are never published automatically.

It runs the validator on the whole account folder first and refuses to write
on any error. `<item>` elements follow the `guids` order of
`.note-channel.json`, and only the given articles are included; a guid missing
from that list is an error.

WXR fields are rebuilt from the front matter and the sidecar:

| WXR field | Source |
|---|---|
| `title` | Sidecar `title`, unless the manuscript was renamed (then the front matter `title`) |
| `link` | Front matter `publication_url`, else sidecar `link` |
| `guid` | `platform_post_id` |
| `wp:post_date`, `wp:post_modified` | `platform_created_at`, `platform_updated_at` (local part) |
| `wp:post_date_gmt`, `wp:post_modified_gmt` | The same values converted to UTC |
| `wp:status` | `draft` for `draft`; `publish` for `published` and `needs_update` |
| everything else | Sidecar item fields |

`pubDate` is taken from the sidecar and is not updated when the dates are
edited. Element order and CDATA use follow note's export format, so an
unedited export is reproduced byte for byte.

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

Manuscript blocks and sidecar blocks are aligned by their Markdown hashes
(a longest-matching-subsequence diff), so edited, inserted and deleted blocks
are all handled; deleted blocks drop out with their original HTML.

If no block was edited, the reassembled body equals the original
`content:encoded` (checked against the body hash).

Regenerated blocks use the inverse of the Markdown subset (see Markdown
body): `h1`-`h6`, `p` with inline `strong`, `em`, `code`, `a` and `br`,
lists, `blockquote`, `hr`, `pre`, and an image-only block as
`<figure><img ...><figcaption></figcaption></figure>`. A block that starts
with an HTML tag is passed through as raw HTML. Regenerated blocks carry no
`name` attributes.

## Markdown body

The body is the blocks' Markdown joined by one blank line; a block never
contains a blank line, so `note-md-to-wxr` can split the body back into
blocks. Only these elements become Markdown: `h1`-`h6`, `p`, `ul`/`ol`
(nested), `blockquote` of paragraphs, `hr`, `pre`, `img` and a `figure` that
holds only an image with an empty caption, plus inline `strong`/`b`,
`em`/`i`, `code`, `a` and `br`. A list item holds inline text, or exactly one
`p` (as note writes it) with optional nested lists; an item with several
paragraphs, other block elements or no text keeps the whole list as raw HTML.
Any other block, or an empty one, is kept as
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
- An empty title becomes `無題 (YYYY-MM-DD <guid first 6 chars>)`, with the
  date from `platform_created_at` (for example `無題 (2026-03-18 n8bd10)`).
- Every article that shares its title with another gets
  ` (<guid first 6 chars>)` appended, so the names do not depend on article
  order and re-running gives the same filenames. Other titles are unchanged.
- The generated title is written to the front matter `title`.
  `--rename "<guid>=<new title>"` overrides it explicitly.
- A name that still collides (for example with a renamed title) fails.
- The account folder name replaces `_` with `-`.

## Lossy policy

| Situation | Default | With `--allow-lossy` |
|---|---|---|
| Dropped metadata (an item field not representable) | failure | warning |
| Missing image attachment | failure | warning |
| Unresolved image URL | failure | warning |
| `guid` collision | failure | warning |
| Unknown HTML element | warning (kept as raw HTML) | warning |

Both `note-wxr-to-md` and `note-md-to-wxr` accept `--allow-lossy`. In
`note-md-to-wxr` it downgrades a missing image file, an unresolved image
URL and a duplicate `platform_post_id` (a `guid` collision) to warnings; a
missing image is then left out of the ZIP. The validator applies the same
downgrade to a folder whose manifest records `allow_lossy`.

With `--allow-lossy`, downgraded failures are recorded in the manifest.
Anything not expressible in Markdown stays as raw HTML so the body is not
lost.

## Manifest `manifest.json`

Written next to every tool output (`note-wxr-to-md` writes it into the
account folder). JSON with these keys:

| Key | Content |
|---|---|
| `manifest_version` | `1` |
| `tool` | `name` and `version` of this package |
| `command` | The command that wrote it |
| `allow_lossy` | Whether `--allow-lossy` was used (downgraded failures are in `warnings`) |
| `inputs` | `path` and `sha256` of each input file: the export XML and every copied `assets/<file>` |
| `article_count`, `image_count` | Counts of articles and image files written |
| `total_size` | Total bytes of the image files written |
| `articles` | Per article: `guid`, `title` (filename stem) and `body_sha256` (hash of the original `content:encoded`) |
| `body_sha256` | Overall body hash: SHA-256 of the per-article body hashes, ordered by `guid` and joined by newlines |
| `warnings` | Warnings raised by the run |

`note-wxr-validate` checks that the manifest matches the files on disk.
Manuscripts may be edited after conversion, so the manifest describes the
original bodies (the sidecar hashes), not the Markdown text.

## Validation

`note-wxr-validate <dir>` takes the account folder and reports every problem
at once. It exits 1 if there is any error. Only `*.md` files other than
`README.md` and hidden files are manuscripts; `README.md` is account
documentation and is ignored. It checks:

- Required properties are present and consistent: `title` (equal to the
  filename stem), `account`, `platform_post_id`, `platform_created_at` and
  `platform_updated_at` (ISO 8601 with an offset), `publication_status` (one
  of `draft`, `published`, `needs_update`), `platform` (`note`) and `origin`.
  A `published` article also needs `publication_url`. `platform_post_id` is
  unique.
- Every image reference (Markdown and `<img>`) points to an existing file
  under `<title>-img/`. A remote URL, a path elsewhere or a missing file is an
  error, or a warning when the manifest says `allow_lossy`.
- The sidecar exists, has the expected structure, and its block HTML
  concatenates to its `body_sha256`. Block Markdown hashes are not compared:
  they differ from the manuscript once a block is edited, which is what the
  regeneration rule relies on.
- The manifest exists and matches the disk: the same articles (`guid`,
  `title`), the per-article and overall body hashes and `article_count` are
  errors. A stale `image_count` or `total_size` is only a warning, since
  images may be added to a manuscript later.

## Dependencies

No third-party runtime dependency at first (standard library only). Any
later dependency must be permissively licensed and actively maintained, so
that the project can be made closed later.
