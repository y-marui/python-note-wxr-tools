"""``manifest.json``: what a tool run produced, for later verification."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import metadata

MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
PACKAGE = "python-note-wxr-tools"


@dataclass
class ArticleEntry:
    guid: str
    title: str
    body_sha256: str


def tool_version() -> str:
    try:
        return metadata.version(PACKAGE)
    except metadata.PackageNotFoundError:
        return "unknown"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def overall_body_hash(articles: Iterable[tuple[str, str]]) -> str:
    """Hash of the per-article body hashes, ordered by ``(guid, hash)``."""
    joined = "\n".join(body_hash for _, body_hash in sorted(articles))
    return sha256_bytes(joined.encode("utf-8"))


def build(
    *,
    command: str,
    allow_lossy: bool,
    inputs: dict[str, str],
    articles: list[ArticleEntry],
    image_count: int,
    total_size: int,
    warnings: list[str],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Return the manifest; ``total_size`` is the size of all image files."""
    document: dict[str, object] = {
        "manifest_version": MANIFEST_VERSION,
        "tool": {"name": PACKAGE, "version": tool_version()},
        "command": command,
        "allow_lossy": allow_lossy,
        "inputs": [{"path": p, "sha256": h} for p, h in sorted(inputs.items())],
        "article_count": len(articles),
        "image_count": image_count,
        "total_size": total_size,
        "body_sha256": overall_body_hash((a.guid, a.body_sha256) for a in articles),
        "articles": [
            {"guid": a.guid, "title": a.title, "body_sha256": a.body_sha256}
            for a in articles
        ],
        "warnings": warnings,
    }
    return document | (extra or {})
