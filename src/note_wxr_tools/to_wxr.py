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
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import unquote

from note_wxr_tools import manifest
from note_wxr_tools.frontmatter import article_guid, parse
from note_wxr_tools.htmlmd import sha256
from note_wxr_tools.mdhtml import ImageSrc, block_to_html, split_blocks
from note_wxr_tools.to_md import ConversionError, sanitize_filename
from note_wxr_tools.validate import validate
from note_wxr_tools.wxr import ASSETS_PREFIX
from note_wxr_tools.wxrwriter import ITEM_DEFAULTS, ITEM_LAYOUT, render

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
    replaced_images: int = 0


@dataclass
class _Options:
    """Settings shared by all articles of one run."""

    folder: Path
    channel: dict[str, str]
    allow_lossy: bool = False
    image_map: dict[str, str] | None = None
    warnings: list[str] = field(default_factory=list)
    replaced: int = 0


@dataclass
class _Article:
    stem: str
    fields: dict[str, str]
    guid: str
    body_sha256: str
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


def _collect_images(options: _Options, stem: str, content: str) -> dict[str, bytes]:
    images: dict[str, bytes] = {}
    for match in ASSET_SRC.finditer(content):
        name = html.unescape(match[1])[len(ASSETS_PREFIX) :]
        path = options.folder / f"{stem}-img" / name
        if path.is_file():
            images[name] = path.read_bytes()
        elif not options.allow_lossy:
            raise ConversionError(f"{stem}.md: missing image file {stem}-img/{name}")
        else:
            options.warnings.append(f"{stem}.md: missing image attachment {name}")
    return images


def _load_image_map(path: Path) -> dict[str, str]:
    """Read ``{"<file>": "https://..."}``; keys may carry ``/assets/``."""
    mapping = {}
    for key, url in _read_json(path).items():
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ConversionError(f"{path.name}: {key}: not an HTTPS URL")
        mapping[key.lstrip("/").removeprefix("assets/")] = url
    return mapping


def _apply_image_map(options: _Options, stem: str, content: str) -> str:
    """Replace ``/assets/<file>`` with public URLs; every image must be mapped."""
    mapping = options.image_map
    assert mapping is not None
    unmapped = []

    def replace(match: re.Match[str]) -> str:
        name = html.unescape(match[1])[len(ASSETS_PREFIX) :]
        url = mapping.get(name)
        if url is None:
            unmapped.append(name)
            return match[0]
        options.replaced += 1
        return f' src="{html.escape(url, quote=True)}"'

    replaced = ASSET_SRC.sub(replace, content)
    if unmapped:
        raise ConversionError(f"{stem}.md: not in the image map: {', '.join(unmapped)}")
    return replaced


def _sidecar_or_none(folder: Path, stem: str) -> dict[str, object] | None:
    path = folder / f"{stem}.note.json"
    return _read_json(path) if path.exists() else None


def _item_fields(
    options: _Options, props: dict[str, str], stem: str, guid: str
) -> dict[str, str]:
    """Return the item fields other than the body, dates and status."""
    fields = dict(ITEM_DEFAULTS)
    fields["title"] = props.get("note_title", stem)
    fields["dc:creator"] = options.channel.get("title", "")
    fields["link"] = props.get("publication_url") or (
        f"{options.channel.get('link', '').rstrip('/')}/n/{guid}"
    )
    created = datetime.fromisoformat(props["platform_created_at"])
    fields["pubDate"] = format_datetime(created)
    return fields


def _sidecar_fields(
    sidecar: dict[str, object], props: dict[str, str], stem: str
) -> dict[str, str]:
    item: dict[str, str] = sidecar["item"]  # type: ignore[assignment]
    fields = {tag: item.get(tag, "") for tag, _ in ITEM_LAYOUT}
    original = item.get("title", "")
    if "note_title" in props:
        fields["title"] = props["note_title"]
    else:
        fields["title"] = original if sanitize_filename(original) == stem else stem
    fields["link"] = props.get("publication_url") or item.get("link", "")
    return fields


def _article(options: _Options, path: Path) -> _Article:
    folder = options.folder
    props, body = parse(path.read_text(encoding="utf-8"))
    stem = path.stem
    guid = article_guid(props, stem)
    sidecar = _sidecar_or_none(folder, stem)
    if sidecar is None:
        blocks = split_blocks(body)
        content = "".join(block_to_html(b, _image_src(stem)) for b in blocks)
        regenerated = len(blocks)
        fields = _item_fields(options, props, stem, guid)
    else:
        content, regenerated = _body_html(body, sidecar, _image_src(stem))
        if not regenerated and sha256(content) != sidecar["body_sha256"]:
            raise ConversionError(f"{stem}.md: rebuilt body differs from the original")
        fields = _sidecar_fields(sidecar, props, stem)
    fields["guid"] = guid
    if options.image_map is not None:
        content = _apply_image_map(options, stem, content)
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
    images = (
        {} if options.image_map is not None else _collect_images(options, stem, content)
    )
    inputs = {path.name: manifest.sha256_bytes(path.read_bytes())}
    if sidecar is not None:
        sidecar_path = folder / f"{stem}.note.json"
        inputs[sidecar_path.name] = manifest.sha256_bytes(sidecar_path.read_bytes())
    for name, data in images.items():
        inputs[f"{stem}-img/{name}"] = manifest.sha256_bytes(data)
    return _Article(stem, fields, guid, sha256(body), images, inputs, regenerated)


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


def _read_channel(folder: Path) -> tuple[dict[str, str], dict[str, str]]:
    data = _read_json(folder / CHANNEL_NAME)
    channel, author = data.get("channel"), data.get("author")
    if not (isinstance(channel, dict) and isinstance(author, dict)):
        raise ConversionError(f"{CHANNEL_NAME}: unexpected structure")
    return channel, author


def _merge_assets(built: list[_Article]) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    for article in built:
        for name, data in article.images.items():
            if assets.setdefault(name, data) != data:
                raise ConversionError(f"image {name} differs between articles")
    return assets


def _manifest(
    options: _Options,
    built: list[_Article],
    assets: dict[str, bytes],
    image_map: Path | None,
) -> dict[str, object]:
    inputs = {
        CHANNEL_NAME: manifest.sha256_bytes(
            (options.folder / CHANNEL_NAME).read_bytes()
        )
    }
    for article in built:
        inputs.update(article.inputs)
    extra: dict[str, object] = {}
    if image_map is not None:
        inputs[f"image-map/{image_map.name}"] = manifest.sha256_bytes(
            image_map.read_bytes()
        )
        extra["image_map"] = {"replaced": options.replaced}
    return manifest.build(
        command="note-md-to-wxr",
        allow_lossy=options.allow_lossy,
        inputs=inputs,
        articles=[manifest.ArticleEntry(a.guid, a.stem, a.body_sha256) for a in built],
        image_count=len(assets),
        total_size=sum(len(d) for d in assets.values()),
        warnings=options.warnings,
        extra=extra,
    )


def convert(
    articles: Sequence[Path],
    out: Path,
    *,
    force: bool = False,
    allow_lossy: bool = False,
    image_map: Path | None = None,
) -> Report:
    """Write ``note-<account>-1.zip`` and ``manifest.json`` into ``out``.

    With ``image_map``, ``/assets/<file>`` references become the mapped public
    URLs and no images are packed; such output is not byte-identical to the
    original export.
    """
    folder = _check_inputs(articles)
    checked = validate(folder, allow_lossy=allow_lossy)
    if checked.errors:
        raise ConversionError("\n".join(checked.errors))
    channel, author = _read_channel(folder)
    options = _Options(
        folder,
        channel,
        allow_lossy,
        _load_image_map(image_map) if image_map else None,
        list(checked.warnings),
    )
    built = [_article(options, Path(p).resolve()) for p in articles]
    built.sort(key=lambda a: (a.fields["wp:post_date_gmt"], a.guid))
    for number, article in enumerate(built, 1):
        article.fields.setdefault("wp:post_id", str(number))
    assets = _merge_assets(built)
    account = author.get("wp:author_login", "")
    zip_path = out / f"note-{account}-1.zip"
    manifest_path = out / manifest.MANIFEST_NAME
    existing = [str(p) for p in (zip_path, manifest_path) if p.exists()]
    if existing and not force:
        raise ConversionError(f"already exists (use --force): {', '.join(existing)}")
    out.mkdir(parents=True, exist_ok=True)
    xml = render(channel, author, [a.fields for a in built])
    _write_zip(zip_path, f"note-{account}-1.xml", xml, assets)
    document = _manifest(options, built, assets, image_map)
    manifest_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    return Report(
        zip_path,
        len(built),
        len(assets),
        sum(a.regenerated for a in built),
        options.warnings,
        options.replaced,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="note-md-to-wxr",
        description="Turn manuscripts back into a note-importable ZIP.",
    )
    parser.add_argument("articles", nargs="+", type=Path, help="article .md files")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument(
        "--allow-lossy",
        action="store_true",
        help="downgrade lossy failures to warnings",
    )
    parser.add_argument(
        "--image-map",
        type=Path,
        metavar="MAP.json",
        help='JSON {"<file>": "https://..."}; replaces /assets/ references '
        "(output is not byte-identical to the export)",
    )
    args = parser.parse_args(argv)
    try:
        report = convert(
            args.articles,
            args.out,
            force=args.force,
            allow_lossy=args.allow_lossy,
            image_map=args.image_map,
        )
    except (ConversionError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"wrote {report.zip_path} ({report.articles} article(s), "
        f"{report.images} image(s), {report.regenerated_blocks} regenerated block(s), "
        f"{report.replaced_images} image URL(s) replaced)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
