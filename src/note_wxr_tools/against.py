"""Compare generated manuscripts with ones already in a posts directory.

Read-only: nothing under the posts directory is ever written, so hand-written
properties such as ``editorial_note`` are safe.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

from note_wxr_tools.frontmatter import FrontMatterError, parse

HTML_TAG = re.compile(r"<[A-Za-z][^<>]*>")
BLOCK_ATTRIBUTE = re.compile(r'\s(?:name|id)="[^"]*"')
MAX_DIFF_LINES = 40


@dataclass
class Generated:
    """One article as ``note-wxr-to-md`` would write it."""

    title: str
    props: dict[str, str]
    body: str


@dataclass
class Difference:
    guid: str
    title: str
    path: Path
    properties: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)


@dataclass
class Comparison:
    matched: int = 0
    differences: list[Difference] = field(default_factory=list)
    new_in_export: list[str] = field(default_factory=list)
    only_in_posts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _account(props: dict[str, str]) -> str:
    """Account name with ``_`` and ``-`` treated alike (folders use ``-``)."""
    return props.get("account", "").replace("_", "-")


def normalize_body(body: str) -> list[str]:
    """Lines of ``body`` without block ``name``/``id`` attributes or trailing space.

    Hand-imported manuscripts dropped those attributes, so they are not a
    difference worth reporting.
    """
    text = HTML_TAG.sub(lambda m: BLOCK_ATTRIBUTE.sub("", m[0]), body)
    return [line.rstrip() for line in text.replace("\r\n", "\n").strip().split("\n")]


def scan_posts(
    posts: Path, comparison: Comparison
) -> dict[str, tuple[Path, dict[str, str]]]:
    """Map ``platform_post_id`` to the manuscript path and properties."""
    found: dict[str, tuple[Path, dict[str, str]]] = {}
    for path in sorted(posts.rglob("*.md")):
        try:
            props, _ = parse(path.read_text(encoding="utf-8"))
        except (FrontMatterError, OSError, UnicodeDecodeError):
            continue
        guid = props.get("platform_post_id")
        if not guid:
            continue
        if guid in found:
            comparison.warnings.append(
                f"duplicate platform_post_id {guid}: {found[guid][0]} and {path}"
            )
            continue
        found[guid] = (path, props)
    return found


def _property_differences(generated: Generated, existing: dict[str, str]) -> list[str]:
    lines = []
    for key, value in generated.props.items():
        if key not in existing:
            lines.append(f"{key}: missing in posts (export: {value!r})")
        elif existing[key] != value:
            lines.append(f"{key}: posts {existing[key]!r} / export {value!r}")
    return lines


def _body_differences(generated: Generated, existing_body: str) -> list[str]:
    diff = difflib.unified_diff(
        normalize_body(existing_body),
        normalize_body(generated.body),
        fromfile="posts",
        tofile="export",
        lineterm="",
        n=1,
    )
    lines = list(diff)
    if len(lines) > MAX_DIFF_LINES:
        omitted = len(lines) - MAX_DIFF_LINES
        lines = [*lines[:MAX_DIFF_LINES], f"... ({omitted} more diff line(s))"]
    return lines


def compare(generated: dict[str, Generated], posts: Path) -> Comparison:
    """Compare articles (keyed by ``platform_post_id``) with those in ``posts``."""
    result = Comparison()
    existing = scan_posts(posts, result)
    accounts = {_account(a.props) for a in generated.values()}
    for guid, article in generated.items():
        found = existing.get(guid)
        if found is None:
            result.new_in_export.append(f"{article.title} ({guid})")
            continue
        path = found[0]
        result.matched += 1
        props, body = parse(path.read_text(encoding="utf-8"))
        difference = Difference(
            guid,
            article.title,
            path,
            _property_differences(article, props),
            _body_differences(article, body),
        )
        if difference.properties or difference.body:
            result.differences.append(difference)
    # Manuscripts of other accounts are not part of this export.
    result.only_in_posts = [
        f"{path} ({guid})"
        for guid, (path, props) in existing.items()
        if guid not in generated
        and (not props.get("account") or _account(props) in accounts)
    ]
    return result


def format_report(result: Comparison) -> str:
    """Render the comparison as text for a terminal."""
    lines = [
        f"matched {result.matched} article(s): "
        f"{result.matched - len(result.differences)} identical, "
        f"{len(result.differences)} with differences",
        f"new in export: {len(result.new_in_export)}; "
        f"only in posts: {len(result.only_in_posts)}",
    ]
    for difference in result.differences:
        lines.append(f"\n{difference.title} ({difference.guid}): {difference.path}")
        lines.extend(f"  property {line}" for line in difference.properties)
        if difference.body:
            lines.append("  body differs:")
            lines.extend(f"    {line}" for line in difference.body)
    for label, items in (
        ("new in export", result.new_in_export),
        ("only in posts", result.only_in_posts),
    ):
        if items:
            lines.append(f"\n{label}:")
            lines.extend(f"  {item}" for item in items)
    return "\n".join(lines)
