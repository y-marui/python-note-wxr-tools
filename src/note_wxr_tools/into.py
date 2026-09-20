"""Apply generated manuscripts to an existing posts directory (``--into``).

Nothing is ever deleted. Only new articles are written, and differing ones are
overwritten only on request, keeping properties the export does not know.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from note_wxr_tools import against
from note_wxr_tools.frontmatter import FrontMatterError, parse


@dataclass
class IntoSummary:
    """What ``--into`` did with each article."""

    created: list[str] = field(default_factory=list)
    overwritten: list[str] = field(default_factory=list)
    unchanged: int = 0
    pending: list[against.Difference] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    channel: str = "unchanged"


def find_conflicts(
    article_files: dict[str, list[Path]], matched: set[str]
) -> list[str]:
    """Files of new articles that would land on a file that already exists."""
    return [
        f"{path} already exists but is not the manuscript for {guid}"
        f' (use --rename "{guid}=<new title>")'
        for guid, paths in article_files.items()
        if guid not in matched
        for path in paths
        if path.exists()
    ]


def merge_channel(existing: object, generated: dict[str, object]) -> dict[str, object]:
    """Return ``existing`` with the export's channel data applied.

    Channel and author fields are taken from the export. ``guids`` keeps the
    existing order and appends new guids; none is ever removed.
    """
    if not isinstance(existing, dict):
        raise ValueError("unexpected structure")
    merged = {
        **existing,
        "channel": generated["channel"],
        "author": generated["author"],
    }
    old = existing.get("guids", [])
    if not isinstance(old, list):
        raise ValueError("guids is not a list")
    new = generated["guids"]
    assert isinstance(new, list)
    merged["guids"] = [*old, *(g for g in dict.fromkeys(new) if g not in old)]
    return merged


def prepare_channel(path: Path, generated: bytes) -> tuple[str, bytes | None]:
    """Decide what to do with ``.note-channel.json`` without writing it.

    Returns ``created``, ``updated`` or ``unchanged`` and the bytes to write
    (``None`` when unchanged). Raises ``ValueError`` for an unusable file.
    """
    if not path.exists():
        return "created", generated
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
        merged = merge_channel(current, json.loads(generated))
    except (OSError, ValueError) as error:
        raise ValueError(f"{path.name}: {error}") from error
    if merged == current:
        return "unchanged", None
    text = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    return "updated", text.encode("utf-8")


def merge_front_matter(existing: str, generated: str) -> str:
    """Return ``generated`` plus the ``existing`` properties it does not define.

    Extra properties (such as a multi-line ``editorial_note``) are copied
    verbatim, so hand-written notes survive an overwrite.
    """
    head, body = _split(generated)
    known = {line.partition(":")[0] for line in head if line[:1] not in " \t#-"}
    extra: list[str] = []
    keep = False
    for line in _split(existing)[0]:
        if line[:1] not in (" ", "\t", "#", "-", ""):
            keep = line.partition(":")[0] not in known
        if keep:
            extra.append(line)
    return "\n".join(["---", *head, *extra, "---", body])


def _split(text: str) -> tuple[list[str], str]:
    end = text.index("\n---\n", 3)
    return text[4:end].split("\n"), text[end + 5 :]


def apply(
    files: dict[Path, bytes],
    article_files: dict[str, list[Path]],
    comparison: against.Comparison,
    matched: set[str],
    force: bool,
    overwrite_needs_update: bool = False,
) -> IntoSummary:
    """Write new articles, and differing ones only with ``force``.

    A differing manuscript with ``publication_status: needs_update`` holds
    edits that are not on note yet, so it is kept as is (even with ``force``)
    unless ``overwrite_needs_update`` is set.
    """
    differing = {d.guid: d for d in comparison.differences}
    summary = IntoSummary()
    for guid, paths in article_files.items():
        manuscript = paths[0]
        if guid not in matched:
            _write(files, paths)
            summary.created.append(manuscript.stem)
        elif guid not in differing:
            summary.unchanged += 1
        elif not overwrite_needs_update and _needs_update(manuscript):
            summary.kept.append(manuscript.stem)
        elif force:
            existing = manuscript.read_text(encoding="utf-8")
            generated = files[manuscript].decode("utf-8")
            files[manuscript] = merge_front_matter(existing, generated).encode("utf-8")
            _write(files, paths)
            summary.overwritten.append(manuscript.stem)
        else:
            summary.pending.append(differing[guid])
    return summary


def _needs_update(manuscript: Path) -> bool:
    try:
        props, _ = parse(manuscript.read_text(encoding="utf-8"))
    except (FrontMatterError, OSError, UnicodeDecodeError):
        return False
    return props.get("publication_status") == "needs_update"


def _write(files: dict[Path, bytes], paths: list[Path]) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[path])
