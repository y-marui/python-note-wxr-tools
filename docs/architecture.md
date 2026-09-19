# Architecture

`note-wxr-to-md` (#2) and `note-wxr-validate` (#4) share these modules:

| Module | Role |
|---|---|
| `wxr.py` | Reads an export (ZIP or directory) and parses the WXR into plain dicts |
| `htmlmd.py` | Splits `content:encoded` into top-level blocks and converts each to Markdown, falling back to raw HTML per block |
| `to_md.py` | Plans the output (filenames, front matter, sidecar, channel file, manifest, images), reports lossy problems, then writes; also the CLI |
| `manifest.py` | Builds `manifest.json` and the overall body hash |
| `frontmatter.py` | Parses the flat front matter of a manuscript |
| `validate.py` | Checks an account folder against the specification; also the CLI. `note-md-to-wxr` calls `validate()` first |

All output is planned in memory first; nothing is written when any error
remains or when an existing file would be overwritten without `--force`.

`note-md-to-wxr` is added with #3.
