"""``note-md-to-wxr``: turn manuscripts back into a note-importable ZIP."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import unquote

from note_wxr_tools import manifest
from note_wxr_tools.frontmatter import parse
from note_wxr_tools.htmlmd import sha256
from note_wxr_tools.mdhtml import ImageSrc, block_to_html, split_blocks
from note_wxr_tools.to_md import ConversionError, sanitize_filename
from note_wxr_tools.validate import validate
from note_wxr_tools.wxr import ASSETS_PREFIX
from note_wxr_tools.wxrwriter import ITEM_LAYOUT, render

CHANNEL_NAME = ".note-channel.json"
ASSET_SRC = re.compile(r'\ssrc="(/assets/[^"]*)"')
ZIP_TIME = (2000, 1, 1, 0, 0, 0)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Report:
    zip_path: Path
    articles: int = 0
    images: int = 0
    regenerated_blocks: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Article:
    stem: str
    fields: dict[str, str]
    guid: str
    images: dict[str, bytes]
    inputs: dict[str, str]
    regenerated: int


def _read_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConversionError(f"{path.name}: file is missing") from None
    except (OSError, ValueError) as error:
        raise ConversionError(f"{path.name}: unreadable: {error}") from error
    if not isinstance(data, dict):
        raise ConversionError(f"{path.name}: unexpected structure")
    return data


def _wxr_dates(iso: str) -> tuple[str, str]:
    """Return the local and UTC ``YYYY-MM-DD HH:MM:SS`` forms of ``iso``."""
    moment = datetime.fromisoformat(iso)
    local = moment.replace(tzinfo=None).strftime(DATE_FORMAT)
    return local, moment.astimezone(UTC).strftime(DATE_FORMAT)


def _body_html(
    body: str, sidecar: dict[str, object], to_src: ImageSrc
) -> tuple[str, int]:
    """Return the body HTML and the number of regenerated blocks.

    Blocks whose Markdown hash matches the sidecar keep their original HTML;
    the others are regenerated from the Markdown.
    """
    blocks: list[dict[str, str]] = sidecar["blocks"]  # type: ignore[assignment]
    manuscript = split_blocks(body)
    matcher = SequenceMatcher(
        None,
        [b["markdown_sha256"] for b in blocks],
        [sha256(b) for b in manuscript],
        autojunk=False,
    )
    parts: list[str] = []
    regenerated = 0
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            parts.extend(blocks[i]["html"] for i in range(i1, i2))
        else:
            regenerated += j2 - j1
            parts.extend(block_to_html(manuscript[j], to_src) for j in range(j1, j2))
    return "".join(parts), regenerated


def _image_src(stem: str) -> ImageSrc:
    prefix = f"{stem}-img/"

    def to_src(dest: str) -> str:
        path = unquote(dest)
        return ASSETS_PREFIX + path[len(prefix) :] if path.startswith(prefix) else dest

    return to_src


def _collect_images(folder: Path, stem: str, content: str) -> dict[str, bytes]:
    images: dict[str, bytes] = {}
    for match in ASSET_SRC.finditer(content):
        name = html.unescape(match[1])[len(ASSETS_PREFIX) :]
        path = folder / f"{stem}-img" / name
        if not path.is_file():
            raise ConversionError(f"{stem}.md: missing image file {stem}-img/{name}")
        images[name] = path.read_bytes()
    return images


def _article(folder: Path, path: Path) -> _Article:
    props, body = parse(path.read_text(encoding="utf-8"))
    stem = path.stem
    sidecar = _read_json(folder / f"{stem}.note.json")
    item: dict[str, str] = sidecar["item"]  # type: ignore[assignment]
    content, regenerated = _body_html(body, sidecar, _image_src(stem))
    if not regenerated and sha256(content) != sidecar["body_sha256"]:
        raise ConversionError(f"{stem}.md: rebuilt body differs from the original")
    fields = {tag: item.get(tag, "") for tag, _ in ITEM_LAYOUT}
    original = item.get("title", "")
    fields["title"] = original if sanitize_filename(original) == stem else stem
    fields["link"] = props.get("publication_url") or item.get("link", "")
    fields["guid"] = props["platform_post_id"]
    fields["content:encoded"] = content
    fields["wp:post_date"], fields["wp:post_date_gmt"] = _wxr_dates(
        props["platform_created_at"]
    )
    fields["wp:post_modified"], fields["wp:post_modified_gmt"] = _wxr_dates(
        props["platform_updated_at"]
    )
    fields["wp:status"] = (
        "draft" if props["publication_status"] == "draft" else "publish"
    )
    images = _collect_images(folder, stem, content)
    inputs = {
        p.name: manifest.sha256_bytes(p.read_bytes())
        for p in (path, folder / f"{stem}.note.json")
    }
    for name, data in images.items():
        inputs[f"{stem}-img/{name}"] = manifest.sha256_bytes(data)
    return _Article(
        stem, fields, props["platform_post_id"], images, inputs, regenerated
    )


def _check_inputs(articles: Sequence[Path]) -> Path:
    if not articles:
        raise ConversionError("no article given")
    if len({p.resolve() for p in articles}) != len(articles):
        raise ConversionError("the same article was given more than once")
    for path in articles:
        if path.suffix != ".md" or not path.is_file():
            raise ConversionError(f"not a manuscript file: {path}")
    folders = {p.resolve().parent for p in articles}
    if len(folders) != 1:
        raise ConversionError("all articles must be in the same account folder")
    return folders.pop()


def _write_zip(path: Path, xml_name: str, xml: str, assets: dict[str, bytes]) -> None:
    def entry(name: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(name, ZIP_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        return info

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(entry(xml_name), xml.encode("utf-8"))
        for name in sorted(assets):
            archive.writestr(entry(f"assets/{name}"), assets[name])


def convert(articles: Sequence[Path], out: Path, *, force: bool = False) -> Report:
    """Write ``note-<account>-1.zip`` and ``manifest.json`` into ``out``."""
    folder = _check_inputs(articles)
    checked = validate(folder)
    if checked.errors:
        raise ConversionError("\n".join(checked.errors))
    channel_file = _read_json(folder / CHANNEL_NAME)
    channel, author, guids = (
        channel_file.get("channel"),
        channel_file.get("author"),
        channel_file.get("guids"),
    )
    if not (
        isinstance(channel, dict)
        and isinstance(author, dict)
        and isinstance(guids, list)
    ):
        raise ConversionError(f"{CHANNEL_NAME}: unexpected structure")
    built = [_article(folder, Path(p).resolve()) for p in articles]
    unknown = [a.guid for a in built if a.guid not in guids]
    if unknown:
        raise ConversionError(f"not in {CHANNEL_NAME}: {', '.join(unknown)}")
    built.sort(key=lambda a: guids.index(a.guid))
    account = author.get("wp:author_login", "")
    assets: dict[str, bytes] = {}
    for article in built:
        for name, data in article.images.items():
            if assets.setdefault(name, data) != data:
                raise ConversionError(f"image {name} differs between articles")
    xml = render(channel, author, [a.fields for a in built])
    zip_path = out / f"note-{account}-1.zip"
    manifest_path = out / manifest.MANIFEST_NAME
    existing = [str(p) for p in (zip_path, manifest_path) if p.exists()]
    if existing and not force:
        raise ConversionError(f"already exists (use --force): {', '.join(existing)}")
    out.mkdir(parents=True, exist_ok=True)
    _write_zip(zip_path, f"note-{account}-1.xml", xml, assets)
    inputs = {CHANNEL_NAME: manifest.sha256_bytes((folder / CHANNEL_NAME).read_bytes())}
    for article in built:
        inputs.update(article.inputs)
    document = manifest.build(
        command="note-md-to-wxr",
        allow_lossy=False,
        inputs=inputs,
        articles=[
            manifest.ArticleEntry(a.guid, a.stem, sha256(a.fields["content:encoded"]))
            for a in built
        ],
        image_count=len(assets),
        total_size=sum(len(d) for d in assets.values()),
        warnings=checked.warnings,
    )
    manifest_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return Report(
        zip_path,
        len(built),
        len(assets),
        sum(a.regenerated for a in built),
        checked.warnings,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="note-md-to-wxr",
        description="Turn manuscripts back into a note-importable ZIP.",
    )
    parser.add_argument("articles", nargs="+", type=Path, help="article .md files")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args(argv)
    try:
        report = convert(args.articles, args.out, force=args.force)
    except (ConversionError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"wrote {report.zip_path} ({report.articles} article(s), "
        f"{report.images} image(s), {report.regenerated_blocks} regenerated block(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
