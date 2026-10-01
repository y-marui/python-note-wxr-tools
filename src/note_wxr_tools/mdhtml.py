"""Convert the Markdown subset written by ``note-wxr-to-md`` back to HTML.

This is the inverse of ``htmlmd``. It is only used for blocks a user edited;
untouched blocks keep their original HTML from the sidecar.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from note_wxr_tools.htmlmd import IMG_SRC

ImageSrc = Callable[[str], str]

PUNCTUATION = frozenset("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
FENCE = re.compile(r"^(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*$")
HR = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})[ \t]*$")
RAW_HTML = re.compile(r"^<(/?[A-Za-z][A-Za-z0-9-]*)(\s|/?>)")
LIST_ITEM = re.compile(r"^([-*+]|\d+[.)])( +)(.*)$")
LINK_TAIL = re.compile(r'\(\s*(<[^>]*>|[^)\s]*)\s*(?:"[^"]*")?\s*\)')
AUTOLINK = re.compile(r"<([A-Za-z][A-Za-z0-9+.-]*:[^\s<>]*)>")
ENTITY = re.compile(r"&(#\w+|\w+);")
IMAGE_ONLY = re.compile(r"^!\[.*\]\((?:<[^>]*>|[^)\s]*)\)$")
HARD_BREAK_SPACES = re.compile(r" {2,}\n")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr(text: str) -> str:
    return html.escape(text, quote=True)


def split_blocks(body: str) -> list[str]:
    """Split a manuscript body into blocks separated by blank lines.

    Blank lines inside a fenced code block do not separate blocks.
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    fence = ""
    for line in body.split("\n"):
        if fence:
            current.append(line)
            stripped = line.strip()
            if stripped.startswith(fence) and set(stripped) == {fence[0]}:
                fence = ""
        elif not line.strip():
            if current:
                blocks.append(current)
                current = []
        else:
            match = FENCE.match(line)
            fence = match[1] if match else ""
            current.append(line)
    if current:
        blocks.append(current)
    return ["\n".join(lines) for lines in blocks]


def block_to_html(block: str, image_src: ImageSrc) -> str:
    """Return the HTML for one manuscript block."""
    lines = block.split("\n")
    first = lines[0]
    if FENCE.match(first):
        return _code_block(lines)
    if RAW_HTML.match(first):
        return IMG_SRC.sub(
            lambda m: m[1] + _attr(image_src(html.unescape(m[2]))) + m[3], block
        )
    heading = HEADING.match(first) if len(lines) == 1 else None
    if heading:
        level = len(heading[1])
        return f"<h{level}>{_inline(heading[2], image_src)}</h{level}>"
    if len(lines) == 1 and HR.match(first):
        return "<hr>"
    if all(line.startswith(">") for line in lines):
        return _blockquote(lines, image_src)
    if LIST_ITEM.match(first):
        return _list(lines, image_src)
    if len(lines) == 1 and IMAGE_ONLY.match(first):
        return f"<figure>{_inline(first, image_src)}<figcaption></figcaption></figure>"
    return f"<p>{_inline(block, image_src)}</p>"


def _code_block(lines: list[str]) -> str:
    fence = FENCE.match(lines[0])
    assert fence is not None
    inner = lines[1:]
    if inner and inner[-1].strip().startswith(fence[1]):
        inner = inner[:-1]
    return f"<pre>{_escape(chr(10).join(inner))}</pre>"


def _blockquote(lines: list[str], image_src: ImageSrc) -> str:
    paragraphs: list[list[str]] = [[]]
    for line in lines:
        text = line[1:].removeprefix(" ")
        if text.strip():
            paragraphs[-1].append(text)
        elif paragraphs[-1]:
            paragraphs.append([])
    body = "".join(
        f"<p>{_inline(chr(10).join(p), image_src)}</p>" for p in paragraphs if p
    )
    return f"<blockquote>{body}</blockquote>"


def _list(lines: list[str], image_src: ImageSrc) -> str:
    first = LIST_ITEM.match(lines[0])
    assert first is not None
    tag = "ol" if first[1][0].isdigit() else "ul"
    items: list[tuple[int, list[str]]] = []
    for line in lines:
        match = LIST_ITEM.match(line)
        if match:
            width = len(match[1]) + len(match[2])
            items.append((width, [match[3]]))
        elif items:
            width = items[-1][0]
            items[-1][1].append(line[width:] if line[:width].strip() == "" else line)
    body = "".join(_list_item(item, image_src) for _, item in items)
    return f"<{tag}>{body}</{tag}>"


def _list_item(lines: list[str], image_src: ImageSrc) -> str:
    split = next(
        (i for i, line in enumerate(lines) if i and LIST_ITEM.match(line)), len(lines)
    )
    text = _inline("\n".join(lines[:split]), image_src)
    nested = _list(lines[split:], image_src) if split < len(lines) else ""
    return f"<li>{text}{nested}</li>"


def _inline(text: str, image_src: ImageSrc) -> str:
    text = HARD_BREAK_SPACES.sub("\\\n", text.strip())
    out: list[str] = []
    i = 0
    while i < len(text):
        piece, i = _token(text, i, image_src)
        out.append(piece)
    return "".join(out)


def _token(text: str, i: int, image_src: ImageSrc) -> tuple[str, int]:
    char = text[i]
    if char == "\\":
        following = text[i + 1 : i + 2]
        if following == "\n":
            return "<br>", i + 2
        if following in PUNCTUATION and following:
            return _escape(following), i + 2
        return "\\", i + 1
    if char == "\n":
        return " ", i + 1
    handler = {"!": _image, "[": _link, "<": _autolink, "`": _code}.get(char)
    if handler and (found := handler(text, i, image_src)):
        return found
    if char in "*_" and (found := _emphasis(text, i, image_src)):
        return found
    if char == "&" and (match := ENTITY.match(text, i)):
        return _escape(html.unescape(match[0])), match.end()
    return _escape(char), i + 1


def _bracket_end(text: str, start: int) -> int:
    """Return the index of the ``]`` matching the ``[`` at ``start`` or -1."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        depth += text[i] == "["
        depth -= text[i] == "]"
        if depth == 0:
            return i
        i += 1
    return -1


def _dest(raw: str) -> str:
    return raw[1:-1] if raw.startswith("<") else raw


def _image(text: str, i: int, image_src: ImageSrc) -> tuple[str, int] | None:
    if not text.startswith("![", i):
        return None
    end = _bracket_end(text, i + 1)
    tail = LINK_TAIL.match(text, end + 1) if end != -1 else None
    if not tail:
        return None
    alt = re.sub(r"\\(.)", r"\1", text[i + 2 : end])
    src = _attr(image_src(_dest(tail[1])))
    alt_attr = f' alt="{_attr(alt)}"' if alt else ""
    return f'<img src="{src}"{alt_attr}>', tail.end()


def _link(text: str, i: int, image_src: ImageSrc) -> tuple[str, int] | None:
    end = _bracket_end(text, i)
    tail = LINK_TAIL.match(text, end + 1) if end != -1 else None
    if not tail:
        return None
    inner = _inline(text[i + 1 : end], image_src)
    return f'<a href="{_attr(_dest(tail[1]))}">{inner}</a>', tail.end()


def _autolink(text: str, i: int, image_src: ImageSrc) -> tuple[str, int] | None:
    match = AUTOLINK.match(text, i)
    if not match:
        return None
    return f'<a href="{_attr(match[1])}">{_escape(match[1])}</a>', match.end()


def _code(text: str, i: int, image_src: ImageSrc) -> tuple[str, int] | None:
    ticks = len(text[i:]) - len(text[i:].lstrip("`"))
    close = re.compile(rf"(?<!`)`{{{ticks}}}(?!`)").search(text, i + ticks)
    if not close:
        return None
    code = text[i + ticks : close.start()].replace("\n", " ")
    if len(code) > 2 and code.startswith(" ") and code.endswith(" "):
        code = code[1:-1]
    return f"<code>{_escape(code)}</code>", close.end()


def _emphasis(text: str, i: int, image_src: ImageSrc) -> tuple[str, int] | None:
    mark = text[i]
    strong = text.startswith(mark * 2, i)
    delimiter = mark * (2 if strong else 1)
    if mark == "_" and i and text[i - 1].isalnum():
        return None
    start = i + len(delimiter)
    close = _find_close(text, start, delimiter)
    if close == -1 or not text[start:close].strip() or text[start].isspace():
        return None
    if (
        mark == "_"
        and text[close + len(delimiter) : close + len(delimiter) + 1].isalnum()
    ):
        return None
    inner = _inline(text[start:close], image_src)
    tag = "strong" if strong else "em"
    return f"<{tag}>{inner}</{tag}>", close + len(delimiter)


def _find_close(text: str, start: int, delimiter: str) -> int:
    mark = delimiter[0]
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == mark:
            run = len(text[i:]) - len(text[i:].lstrip(mark))
            if run == len(delimiter) or (len(delimiter) == 2 and run >= 2):
                return i
            i += run
            continue
        i += 1
    return -1
