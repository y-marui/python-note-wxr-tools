"""Parse the flat front matter of a manuscript (a small YAML subset)."""

from __future__ import annotations

import hashlib
import json


class FrontMatterError(ValueError):
    """The manuscript has no usable front matter."""


def parse(text: str) -> tuple[dict[str, str], str]:
    """Split ``text`` into flat string properties and the body.

    Values may be JSON-style double-quoted, single-quoted or bare. Nested
    values, lists and block scalars (such as a multi-line ``editorial_note``)
    are skipped because the tools do not use them.
    """
    if not text.startswith("---\n"):
        raise FrontMatterError("front matter must start with ---")
    end = text.find("\n---\n", 3)
    if end == -1:
        if not text.endswith("\n---"):
            raise FrontMatterError("front matter is not closed with ---")
        end = len(text) - 4
    props: dict[str, str] = {}
    for line in text[4:end].split("\n"):
        if not line or line[0] in " \t#-":
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise FrontMatterError(f"not a key: value line: {line!r}")
        props[key.strip()] = _scalar(value.strip())
    return props, text[end + 5 :].lstrip("\n")


def _scalar(value: str) -> str:
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value.strip('"')
        return parsed if isinstance(parsed, str) else value
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1].replace("''", "'")
    if value[:1] in ("|", ">"):
        return ""
    return value


def article_guid(props: dict[str, str], stem: str) -> str:
    """Return ``platform_post_id``, or a stable id for an Obsidian-made article."""
    if props.get("platform_post_id"):
        return props["platform_post_id"]
    seed = f"{props.get('account', '')}/{stem}".encode()
    return "n" + hashlib.sha256(seed).hexdigest()[:12]
