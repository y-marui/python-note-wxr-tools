# Changelog

## [Unreleased]

### Added

- Initial project setup from the Python package template (`note_wxr_tools` package).
- `note-wxr-to-md`: convert a note WXR export (ZIP or directory) into Markdown manuscripts, `<title>.note.json` sidecars, `<title>-img/` images, `.note-channel.json` and `manifest.json`. Blocks outside the supported Markdown subset stay as raw HTML. Existing files are never overwritten without `--force`; empty titles become `無題 (YYYY-MM-DD <guid prefix>)` and duplicate titles get ` (<guid prefix>)` appended automatically; `--rename "<guid>=<title>"` overrides a title.
- `note-wxr-to-md --against <posts dir>`: report-only comparison with manuscripts already imported by hand, matched by `platform_post_id`. Nothing is written to the posts directory.
- `note-md-to-wxr`: turn manuscripts back into a note-importable ZIP. Unedited blocks reuse their original HTML, so an unedited export is reproduced byte for byte; edited blocks are regenerated from Markdown.
- `note-md-to-wxr --image-map <map.json>`: replace `/assets/` references with public HTTPS URLs (output is outside the byte-exact guarantee).
- `--allow-lossy` on both converters: downgrade a missing image, an unresolved image URL, a guid collision or an unrepresentable item field to warnings recorded in the manifest.
- `note-wxr-validate <dir>`: check required properties, image references, sidecar hashes and that `manifest.json` matches the files on disk.
- Round-trip tests on synthetic fixtures, and a local-only `make test-realdata` that round-trips a real export named by `NOTE_WXR_REALDATA_ZIP`.
