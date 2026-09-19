# Architecture

`note-wxr-to-md` (#2) is built from three modules:

| Module | Role |
|---|---|
| `wxr.py` | Reads an export (ZIP or directory) and parses the WXR into plain dicts |
| `htmlmd.py` | Splits `content:encoded` into top-level blocks and converts each to Markdown, falling back to raw HTML per block |
| `to_md.py` | Plans the output (filenames, front matter, sidecar, channel file, images), reports lossy problems, then writes; also the CLI |

All output is planned in memory first; nothing is written when any error
remains or when an existing file would be overwritten without `--force`.

`note-md-to-wxr`, `note-wxr-validate` and the manifest are added with #3-#4.
