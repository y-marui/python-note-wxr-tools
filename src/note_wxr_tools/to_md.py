"""``note-wxr-to-md``: convert a note WXR export into Markdown manuscripts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from note_wxr_tools import against, into, manifest
from note_wxr_tools.frontmatter import parse as parse_front_matter
from note_wxr_tools.htmlmd import Block, convert_body, sha256
from note_wxr_tools.wxr import ASSETS_PREFIX, Export, ExportError, Item, Source, parse

PLATFORM = "note"
ORIGIN = "note.com export"
UNTITLED = "無題"
GUID_PREFIX = 6
STATUSES = {"publish": "published", "draft": "draft"}
FILENAME_MAP = str.maketrans(
    {c: chr(ord(c) + 0xFEE0) for c in '/:*?"<>|'} | {"\\": "＼"}
)
REQUIRED = (
    "title",
    "guid",
    "link",
    "content:encoded",
    "wp:post_date",
    "wp:post_date_gmt",
    "wp:post_modified",
    "wp:post_modified_gmt",
    "wp:status",
)
# Item fields the Markdown cannot hold; stored verbatim in the sidecar.
SIDECAR_FIELDS = (
    "title",
    "link",
    "wp:post_id",
    "wp:post_name",
    "wp:post_type",
    "wp:post_parent",
    "wp:menu_order",
    "wp:is_sticky",
    "wp:comment_status",
    "wp:ping_status",
    "wp:post_password",
    "excerpt:encoded",
    "description",
    "dc:creator",
    "pubDate",
    "wp:post_date_gmt",
    "wp:post_modified_gmt",
)
KNOWN_FIELDS = frozenset(SIDECAR_FIELDS) | {
    "guid",
    "content:encoded",
    "wp:post_date",
    "wp:post_modified",
    "wp:status",
}


CHANNEL_NAME = ".note-channel.json"


class ConversionError(Exception):
    """One or more problems prevent a faithful conversion."""


@dataclass
class Report:
    articles: int = 0
    images: int = 0
    warnings: list[str] = field(default_factory=list)
    comparison: against.Comparison | None = None
    into: into.IntoSummary | None = None


@dataclass
class _Plan:
    files: dict[Path, bytes] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    report: Report = field(default_factory=Report)
    article_files: dict[str, list[Path]] = field(default_factory=dict)
    folder: Path = Path(".")


def sanitize_filename(title: str) -> str:
    return title.translate(FILENAME_MAP).strip()


def iso_datetime(local: str, gmt: str) -> str:
    """Return ``local`` as ISO 8601 with the offset implied by ``gmt``."""
    fmt = "%Y-%m-%d %H:%M:%S"
    local_time = datetime.strptime(local, fmt)
    offset = (local_time - datetime.strptime(gmt, fmt)).total_seconds()
    if offset % 60:
        raise ValueError(f"non-minute UTC offset between {local} and {gmt}")
    minutes = int(abs(offset) // 60)
    sign = "+" if offset >= 0 else "-"
    stamp = local_time.isoformat()
    return f"{stamp}{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def _json(data: object) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _front_matter(props: dict[str, str]) -> str:
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in props.items()]
    return "\n".join(["---", *lines, "---"])


class _Converter:
    def __init__(
        self,
        source: Source,
        export: Export,
        out: Path,
        allow_lossy: bool,
        renames: dict[str, str],
        placements: dict[str, Path] | None = None,
    ) -> None:
        self.placements = placements or {}
        self.source = source
        self.export = export
        self.allow_lossy = allow_lossy
        self.renames = renames
        self.plan = _Plan()
        self.inputs: dict[str, str] = {}
        self.entries: list[manifest.ArticleEntry] = []
        self.image_size = 0
        self.account = export.author.get("wp:author_login", "")
        self.folder = out / self.account.replace("_", "-")
        self.plan.folder = self.folder

    def lossy(self, message: str) -> None:
        if self.allow_lossy:
            self.plan.report.warnings.append(message)
        else:
            self.plan.errors.append(f"{message} (use --allow-lossy to downgrade)")

    def run(self) -> _Plan:
        if not self.account:
            self.plan.errors.append("wp:author_login is empty")
            return self.plan
        guids = [item.fields.get("guid", "") for item in self.export.items]
        self._check_renames(guids)
        for guid in sorted({g for g in guids if guids.count(g) > 1}):
            self.lossy(f"guid collision: {guid}")
        stems = self._stems()
        for item, stem in zip(self.export.items, stems, strict=True):
            if stem is not None:
                self._article(item, stem)
        self._channel(guids)
        self._manifest()
        return self.plan

    def _check_renames(self, guids: list[str]) -> None:
        for guid in self.renames:
            if guid not in guids:
                self.plan.errors.append(f"--rename: no article with guid {guid}")

    def _stems(self) -> list[str | None]:
        """Filename stem per item (None when it cannot be determined)."""
        titles = [self._title(item) for item in self.export.items]
        counts = Counter(t for t, explicit in titles if not explicit)
        stems: list[str | None] = []
        seen: dict[str, str] = {}
        for item, (title, explicit) in zip(self.export.items, titles, strict=True):
            guid = item.fields.get("guid", "")
            if guid in self.placements:
                title, explicit = self.placements[guid].stem, True
            if not explicit and counts[title] > 1:
                title = f"{title} ({guid[:GUID_PREFIX]})"
            stem = sanitize_filename(title)
            if not stem or stem in (".", ".."):
                self.plan.errors.append(
                    f"empty or unusable title for {guid}"
                    f' (use --rename "{guid}=<new title>")'
                )
                stems.append(None)
                continue
            if stem in seen:
                self.plan.errors.append(
                    f'duplicate title "{stem}" for {seen[stem]} and {guid}'
                    f' (use --rename "{guid}=<new title>")'
                )
                stems.append(None)
                continue
            seen[stem] = guid
            stems.append(stem)
        return stems

    def _title(self, item: Item) -> tuple[str, bool]:
        """Return the title and whether ``--rename`` set it explicitly.

        Empty titles get a placeholder derived from the creation date and guid,
        so re-running the import gives the same filename.
        """
        guid = item.fields.get("guid", "")
        if guid in self.renames:
            return self.renames[guid], True
        title = sanitize_filename(item.fields.get("title", ""))
        if title:
            return title, False
        date = item.fields.get("wp:post_date", "")[:10]
        label = f"{date} {guid[:GUID_PREFIX]}".strip()
        return f"{UNTITLED} ({label})", True

    def _article(self, item: Item, stem: str) -> None:
        fields = item.fields
        guid = fields.get("guid", "")
        missing = [tag for tag in REQUIRED if tag not in fields]
        if missing:
            self.plan.errors.append(f"{guid}: missing {', '.join(missing)}")
            return
        for tag in sorted(set(fields) - KNOWN_FIELDS):
            self.lossy(f"{guid}: item field {tag} cannot be represented")
        if item.guid_attrs != {"isPermaLink": "false"}:
            self.lossy(f"{guid}: unexpected guid attributes {item.guid_attrs}")
        status = fields["wp:status"]
        if status not in STATUSES:
            self.plan.errors.append(f"{guid}: unsupported wp:status {status!r}")
            return
        try:
            created = iso_datetime(fields["wp:post_date"], fields["wp:post_date_gmt"])
            updated = iso_datetime(
                fields["wp:post_modified"], fields["wp:post_modified_gmt"]
            )
        except ValueError as error:
            self.plan.errors.append(f"{guid}: {error}")
            return
        images: dict[str, bytes] = {}
        blocks = convert_body(
            fields["content:encoded"], self._image_resolver(guid, stem, images)
        )
        raw = sum(block.raw for block in blocks)
        if raw:
            self.plan.report.warnings.append(f"{stem}: {raw} block(s) kept as raw HTML")
        props = {
            "title": stem,
            "account": self.account,
            "platform_post_id": guid,
        }
        if status == "publish":
            props["publication_url"] = fields["link"]
        props |= {
            "platform_created_at": created,
            "platform_updated_at": updated,
            "publication_status": STATUSES[status],
            "platform": PLATFORM,
            "origin": ORIGIN,
        }
        body = "\n\n".join(block.markdown for block in blocks)
        text = f"{_front_matter(props)}\n\n{body}\n"
        folder = (
            self.placements[guid].parent if guid in self.placements else self.folder
        )
        files = {
            folder / f"{stem}.md": text.encode("utf-8"),
            folder / f"{stem}.note.json": _json(self._sidecar(item, blocks)),
        }
        for name, data in images.items():
            files[folder / f"{stem}-img" / name] = data
        self.plan.files |= files
        self.plan.article_files[guid] = list(files)
        self.plan.report.articles += 1
        self.plan.report.images += len(images)
        self.image_size += sum(len(data) for data in images.values())
        for name, data in images.items():
            self.inputs[f"assets/{name}"] = manifest.sha256_bytes(data)
        self.entries.append(
            manifest.ArticleEntry(guid, stem, sha256(fields["content:encoded"]))
        )

    def _image_resolver(self, guid: str, stem: str, images: dict[str, bytes]):  # type: ignore[no-untyped-def]
        def resolve(src: str) -> str:
            if not src.startswith(ASSETS_PREFIX):
                self.lossy(f"{guid}: unresolved image URL {src}")
                return src
            name = src[len(ASSETS_PREFIX) :]
            data = images.get(name) or self.source.read_asset(name)
            if data is None:
                self.lossy(f"{guid}: missing image attachment {src}")
                return src
            images[name] = data
            return f"{stem}-img/{name}"

        return resolve

    @staticmethod
    def _sidecar(item: Item, blocks: list[Block]) -> dict[str, object]:
        body = item.fields["content:encoded"]
        return {
            "item": {
                tag: item.fields[tag] for tag in SIDECAR_FIELDS if tag in item.fields
            },
            "body_sha256": sha256(body),
            "blocks": [
                {"html": b.html, "markdown_sha256": b.markdown_sha256} for b in blocks
            ],
        }

    def _manifest(self) -> None:
        self.inputs[self.source.xml_name()] = manifest.sha256_bytes(
            self.source.read_xml()
        )
        report = self.plan.report
        document = manifest.build(
            command="note-wxr-to-md",
            allow_lossy=self.allow_lossy,
            inputs=self.inputs,
            articles=self.entries,
            image_count=report.images,
            total_size=self.image_size,
            warnings=report.warnings,
        )
        self.plan.files[self.folder / manifest.MANIFEST_NAME] = _json(document)

    def _channel(self, guids: list[str]) -> None:
        self.plan.files[self.folder / CHANNEL_NAME] = _json(
            {
                "channel": self.export.channel,
                "author": self.export.author,
                "guids": guids,
            }
        )


def _compare_against(plan: _Plan, posts: Path) -> against.Comparison:
    generated = {}
    for path, data in plan.files.items():
        if path.suffix != ".md":
            continue
        props, body = parse_front_matter(data.decode("utf-8"))
        generated[props["platform_post_id"]] = against.Generated(
            props["title"], props, body
        )
    return against.compare(generated, posts)


def convert(
    source: Path,
    out: Path | None = None,
    *,
    force: bool = False,
    allow_lossy: bool = False,
    renames: dict[str, str] | None = None,
    against_dir: Path | None = None,
    into_dir: Path | None = None,
) -> Report:
    """Convert ``source`` into ``out`` and return a summary.

    With ``against_dir`` nothing is written: the articles are only compared
    with the manuscripts already in that directory. With ``into_dir`` new
    articles are added to that directory (see ``_convert_into``).
    """
    reader = Source(source)
    export = parse(reader.read_xml())
    placements: dict[str, Path] = {}
    if into_dir is not None:
        if not into_dir.is_dir():
            raise ConversionError(f"not a directory: {into_dir}")
        found = against.scan_posts(into_dir, against.Comparison())
        placements = {guid: path for guid, (path, _) in found.items()}
    plan = _Converter(
        reader,
        export,
        into_dir or out or Path("."),
        allow_lossy,
        renames or {},
        placements,
    ).run()
    if into_dir is not None:
        return _convert_into(plan, into_dir, set(placements), force)
    if against_dir is not None:
        if plan.errors:
            raise ConversionError("\n".join(plan.errors))
        if not against_dir.is_dir():
            raise ConversionError(f"not a directory: {against_dir}")
        plan.report.comparison = _compare_against(plan, against_dir)
        return plan.report
    if not force:
        existing = sorted(str(p) for p in plan.files if p.exists())
        if existing:
            shown = ", ".join(existing[:5])
            plan.errors.append(
                f"{len(existing)} file(s) already exist (use --force): {shown}"
            )
    if plan.errors:
        raise ConversionError("\n".join(plan.errors))
    for path, data in plan.files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return plan.report


def _convert_into(plan: _Plan, posts: Path, matched: set[str], force: bool) -> Report:
    """Add new articles to ``posts``; overwrite differing ones only with ``force``.

    The manifest describes a whole export, so it is not written into an
    existing posts directory. ``.note-channel.json`` is created or updated.
    """
    plan.errors.extend(into.find_conflicts(plan.article_files, matched))
    if plan.errors:
        raise ConversionError("\n".join(plan.errors))
    comparison = _compare_against(plan, posts)
    plan.report.warnings.extend(comparison.warnings)
    channel_path = plan.folder / CHANNEL_NAME
    try:
        state, channel = into.prepare_channel(
            channel_path, plan.files.pop(channel_path)
        )
    except ValueError as error:
        raise ConversionError(str(error)) from error
    plan.report.into = into.apply(
        plan.files, plan.article_files, comparison, matched, force
    )
    plan.report.into.channel = state
    if channel is not None:
        channel_path.parent.mkdir(parents=True, exist_ok=True)
        channel_path.write_bytes(channel)
    return plan.report


def _rename(value: str) -> tuple[str, str]:
    guid, sep, title = value.partition("=")
    if not sep or not guid:
        raise argparse.ArgumentTypeError('expected "<guid>=<new title>"')
    return guid, title


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="note-wxr-to-md",
        description="Convert a note WXR export into Markdown manuscripts.",
    )
    parser.add_argument("source", type=Path, help="export ZIP or extracted directory")
    parser.add_argument("--out", type=Path, help="output directory")
    parser.add_argument(
        "--against",
        type=Path,
        metavar="POSTS_DIR",
        help="only report differences from the manuscripts in POSTS_DIR "
        "(matched by platform_post_id); writes nothing",
    )
    parser.add_argument(
        "--into",
        type=Path,
        metavar="POSTS_DIR",
        help="add new articles to POSTS_DIR (matched by platform_post_id); "
        "articles that differ are reported and, with --force, overwritten "
        "while keeping extra properties; nothing is deleted",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing files (with --into: differing manuscripts)",
    )
    parser.add_argument(
        "--allow-lossy",
        action="store_true",
        help="downgrade lossy failures to warnings",
    )
    parser.add_argument(
        "--rename",
        action="append",
        default=[],
        type=_rename,
        metavar="GUID=TITLE",
        help="use TITLE for the article with GUID (repeatable)",
    )
    args = parser.parse_args(argv)
    if sum(x is not None for x in (args.out, args.against, args.into)) != 1:
        parser.error("give exactly one of --out, --against and --into")
    try:
        report = convert(
            args.source,
            args.out,
            against_dir=args.against,
            into_dir=args.into,
            force=args.force,
            allow_lossy=args.allow_lossy,
            renames=dict(args.rename),
        )
    except (ExportError, ConversionError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if report.comparison is not None:
        for warning in report.comparison.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(against.format_report(report.comparison))
        return 0
    if report.into is not None:
        return _print_into(report.into)
    print(f"wrote {report.articles} article(s), {report.images} image(s)")
    return 0


def _print_into(summary: into.IntoSummary) -> int:
    print(
        f"created {len(summary.created)}, overwritten {len(summary.overwritten)}, "
        f"unchanged {summary.unchanged}, differing {len(summary.pending)}, "
        f"channel {summary.channel}"
    )
    if not summary.pending:
        return 0
    print("\n".join(against.format_differences(summary.pending)))
    print("\nnot written: use --force to overwrite the differing manuscripts")
    return 1


if __name__ == "__main__":
    sys.exit(main())
