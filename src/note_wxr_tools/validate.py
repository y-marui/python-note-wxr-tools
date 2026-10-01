"""``note-wxr-validate``: check manuscripts against the specification."""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

from note_wxr_tools import manifest
from note_wxr_tools.frontmatter import FrontMatterError, article_guid, parse
from note_wxr_tools.htmlmd import sha256

REQUIRED_PROPERTIES = (
    "title",
    "account",
    "platform_created_at",
    "platform_updated_at",
    "publication_status",
    "platform",
    "origin",
)
STATUSES = ("draft", "published", "needs_update")
ISO_DATETIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d")
FENCED_CODE = re.compile(r"^(```|~~~).*?^\1", re.M | re.S)
MARKDOWN_IMAGE = re.compile(r"!\[(?:[^\]\\]|\\.)*\]\(\s*(<[^>]*>|[^)\s]*)")
HTML_IMAGE = re.compile(r'<img\b[^>]*?\ssrc="([^"]*)"')
HEX64 = re.compile(r"[0-9a-f]{64}")


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Article:
    guid: str
    title: str
    body_sha256: str


def image_refs(body: str) -> list[str]:
    """Return the image destinations referenced by a manuscript body."""
    body = FENCED_CODE.sub("", body)
    refs = []
    for match in MARKDOWN_IMAGE.finditer(body):
        ref = match[1]
        refs.append(ref[1:-1] if ref.startswith("<") else ref)
    refs.extend(html.unescape(m[1]) for m in HTML_IMAGE.finditer(body))
    return [unquote(ref) for ref in refs]


def _load_json(path: Path, result: Result) -> object | None:
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        result.errors.append(f"{path.name}: file is missing")
        return None
    except (OSError, ValueError) as error:
        result.errors.append(f"{path.name}: unreadable: {error}")
        return None
    return data


def _valid_sidecar(data: object) -> bool:
    if not isinstance(data, dict):
        return False
    blocks = data.get("blocks")
    return (
        isinstance(data.get("item"), dict)
        and isinstance(data.get("body_sha256"), str)
        and isinstance(blocks, list)
        and all(
            isinstance(b, dict)
            and isinstance(b.get("html"), str)
            and HEX64.fullmatch(str(b.get("markdown_sha256"))) is not None
            for b in blocks
        )
    )


def _check_sidecar(path: Path, result: Result) -> None:
    """Validate a sidecar; it is optional, so a missing file is fine."""
    if not path.exists():
        return
    data = _load_json(path, result)
    if data is None:
        return
    if not _valid_sidecar(data):
        result.errors.append(f"{path.name}: unexpected structure")
        return
    assert isinstance(data, dict)
    if sha256("".join(b["html"] for b in data["blocks"])) != data["body_sha256"]:
        result.errors.append(f"{path.name}: block HTML does not match body_sha256")


def _check_images(
    folder: Path, title: str, body: str, allow_lossy: bool, result: Result
) -> None:
    prefix = f"{title}-img/"
    for ref in image_refs(body):
        problem = None
        if urlparse(ref).scheme:
            problem = "unresolved image URL"
        else:
            path = posixpath.normpath(ref)
            if not path.startswith(prefix):
                problem = f"image outside {prefix}"
            elif not (folder / path).is_file():
                problem = "missing image file"
        if problem:
            message = f"{title}.md: {problem}: {ref}"
            (result.warnings if allow_lossy else result.errors).append(message)


def _check_article(
    folder: Path, path: Path, allow_lossy: bool, result: Result
) -> _Article | None:
    name = path.name
    try:
        props, body = parse(path.read_text(encoding="utf-8"))
    except (FrontMatterError, OSError, UnicodeDecodeError) as error:
        result.errors.append(f"{name}: {error}")
        return None
    for key in REQUIRED_PROPERTIES:
        if not props.get(key):
            result.errors.append(f"{name}: missing property {key}")
    if props.get("title") and props["title"] != path.stem:
        result.errors.append(
            f"{name}: title {props['title']!r} does not match filename"
        )
    if props.get("platform") and props["platform"] != "note":
        result.errors.append(f"{name}: platform must be note")
    status = props.get("publication_status")
    if status and status not in STATUSES:
        result.errors.append(f"{name}: invalid publication_status {status!r}")
    if status == "published" and not props.get("publication_url"):
        result.errors.append(f"{name}: published article needs publication_url")
    for key in ("platform_created_at", "platform_updated_at"):
        if props.get(key) and not ISO_DATETIME.fullmatch(props[key]):
            result.errors.append(f"{name}: {key} is not ISO 8601 with an offset")
    _check_images(folder, path.stem, body, allow_lossy, result)
    _check_sidecar(folder / f"{path.stem}.note.json", result)
    return _Article(article_guid(props, path.stem), path.stem, sha256(body))


def _check_manifest(folder: Path, articles: list[_Article], result: Result) -> None:
    """Check the manifest, if there is one, against the files on disk.

    Manuscripts may be edited or added after the manifest was written, so
    differences per article are warnings; only a manifest that contradicts
    itself is an error.
    """
    if not (folder / manifest.MANIFEST_NAME).exists():
        return
    data = _load_json(folder / manifest.MANIFEST_NAME, result)
    if not isinstance(data, dict):
        return
    warn = result.warnings.append
    entries = [a for a in data.get("articles", []) if isinstance(a, dict)]
    listed = {str(a.get("title")): a for a in entries}
    disk = {a.title: a for a in articles}
    for title in sorted(listed.keys() - disk.keys()):
        warn(f"manifest: article {title} not found on disk")
    for title in sorted(disk.keys() - listed.keys()):
        warn(f"manifest: article {title} is not listed")
    for title in sorted(listed.keys() & disk.keys()):
        entry, article = listed[title], disk[title]
        if entry.get("guid") != article.guid:
            warn(f"manifest: guid of {title} differs from the manuscript")
        if entry.get("body_sha256") != article.body_sha256:
            warn(f"manifest: body hash of {title} differs from the manuscript")
    if data.get("article_count") != len(entries):
        warn("manifest: article_count does not match articles")
    pairs = [(str(a.get("guid")), str(a.get("body_sha256"))) for a in entries]
    if data.get("body_sha256") != manifest.overall_body_hash(pairs):
        result.errors.append("manifest: overall body_sha256 does not match articles")
    _check_image_totals(folder, data, result)


def _check_image_totals(folder: Path, data: dict[str, object], result: Result) -> None:
    files = [
        f
        for d in folder.glob("*-img")
        if d.is_dir()
        for f in d.rglob("*")
        if f.is_file()
    ]
    if data.get("image_count") != len(files):
        result.warnings.append("manifest: image_count is stale")
    if data.get("total_size") != sum(f.stat().st_size for f in files):
        result.warnings.append("manifest: total_size is stale")


def validate(folder: Path, *, allow_lossy: bool = False) -> Result:
    """Validate an account folder written by ``note-wxr-to-md``.

    ``README.md`` and hidden files are documentation, not manuscripts.
    With ``allow_lossy`` (or when the manifest records it) image problems and
    guid collisions are warnings instead of errors.
    """
    result = Result()
    if not folder.is_dir():
        result.errors.append(f"not a directory: {folder}")
        return result
    manifest_data = _load_json_quiet(folder / manifest.MANIFEST_NAME)
    allow_lossy = allow_lossy or bool(
        manifest_data and manifest_data.get("allow_lossy") is True
    )
    paths = sorted(
        p
        for p in folder.glob("*.md")
        if p.name != "README.md" and not p.name.startswith(".")
    )
    if not paths:
        result.errors.append("no manuscripts (*.md) found")
    articles = [
        a for p in paths if (a := _check_article(folder, p, allow_lossy, result))
    ]
    seen: dict[str, str] = {}
    for article in articles:
        if article.guid in seen:
            (result.warnings if allow_lossy else result.errors).append(
                f"duplicate platform_post_id {article.guid}: "
                f"{seen[article.guid]} and {article.title}"
            )
        seen[article.guid] = article.title
    if len(articles) == len(paths):
        _check_manifest(folder, articles, result)
    return result


def _load_json_quiet(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="note-wxr-validate",
        description="Check manuscripts against the note WXR specification.",
    )
    parser.add_argument("dir", type=Path, help="account folder with manuscripts")
    args = parser.parse_args(argv)
    result = validate(args.dir)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    if result.errors:
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
