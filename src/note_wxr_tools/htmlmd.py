"""Split a note ``content:encoded`` body into top-level blocks and convert them.

Only a small set of elements is converted to Markdown. A block that contains
anything else stays as raw HTML so the body is never lost.
"""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser

VOID_TAGS = frozenset({"br", "hr", "img", "input", "meta", "link", "wbr"})
INLINE_ESCAPE = re.compile(r"([\\`*_\[\]<])|&(?=#?\w+;)")
LINE_START_ESCAPE = re.compile(r"^(?:([#>+-])|(\d+)([.)]))(?=\s|$)", re.M)
IMG_SRC = re.compile(r'(<img\b[^>]*?\ssrc=")([^"]*)(")')
HARD_BREAK = "\\\n"


class Unsupported(Exception):
    """The block cannot be expressed in the supported Markdown subset."""


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node | str]


@dataclass
class Block:
    html: str
    markdown: str
    raw: bool

    @property
    def markdown_sha256(self) -> str:
        return sha256(self.markdown)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _TreeBuilder(HTMLParser):
    """Build a tolerant DOM and record the source span of each top-level tag."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self._offsets = [0]
        for line in source.split("\n"):
            self._offsets.append(self._offsets[-1] + len(line) + 1)
        self._source = source
        self.root = Node("#root", {}, [])
        self.spans: list[tuple[int, int, Node]] = []
        self._stack = [self.root]
        self._start = 0

    def _here(self) -> int:
        line, col = self.getpos()
        return self._offsets[line - 1] + col

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs}, [])
        self._stack[-1].children.append(node)
        if len(self._stack) == 1:
            self._start = self._here()
        if tag in VOID_TAGS:
            if len(self._stack) == 1:
                end = self._start + len(self.get_starttag_text() or "")
                self.spans.append((self._start, end, node))
            return
        self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self._stack) - 1, 0, -1):
            if self._stack[depth].tag == tag:
                node = self._stack[depth]
                del self._stack[depth:]
                if depth == 1:
                    begin = self._here()
                    end = self._source.index(">", begin) + 1
                    self.spans.append((self._start, end, node))
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def split_blocks(body: str) -> list[tuple[str, Node | str]]:
    """Return ``(original html, node)`` per top-level block, in order.

    Whitespace between blocks is attached to the following block and
    trailing whitespace to the last one, so the parts concatenate to ``body``.
    Loose text between elements becomes its own block (as a plain string).
    """
    builder = _TreeBuilder(body)
    builder.feed(body)
    builder.close()
    blocks: list[tuple[str, Node | str]] = []
    pending = ""
    cursor = 0
    for start, end, node in builder.spans:
        gap = body[cursor:start]
        if gap.strip():
            blocks.append((pending + gap, gap.strip()))
            pending = ""
        else:
            pending += gap
        blocks.append((pending + body[start:end], node))
        pending = ""
        cursor = end
    tail = body[cursor:]
    if tail.strip():
        blocks.append((tail, tail.strip()))
    elif tail and blocks:
        blocks[-1] = (blocks[-1][0] + tail, blocks[-1][1])
    return blocks


ImageResolver = Callable[[str], str]


def convert_body(body: str, resolve_image: ImageResolver) -> list[Block]:
    """Convert a whole body into blocks, falling back to raw HTML per block."""
    blocks = []
    for source, node in split_blocks(body):
        try:
            markdown = _block(node, resolve_image)
            raw = False
        except Unsupported:
            markdown = _rewrite_images(source.strip(), resolve_image)
            markdown = re.sub(r"\n[ \t]*\n(?:\s*\n)*", "\n", markdown)
            raw = True
        blocks.append(Block(source, markdown, raw))
    return blocks


def _rewrite_images(fragment: str, resolve_image: ImageResolver) -> str:
    def replace(match: re.Match[str]) -> str:
        src = resolve_image(html.unescape(match[2]))
        return match[1] + html.escape(src, quote=True) + match[3]

    return IMG_SRC.sub(replace, fragment)


def _block(node: Node | str, resolve_image: ImageResolver) -> str:
    if isinstance(node, str):
        return _inline([node], resolve_image, strip=True)
    tag = node.tag
    if re.fullmatch(r"h[1-6]", tag):
        return "#" * int(tag[1]) + " " + _text(node, resolve_image)
    if tag == "p":
        return _text(node, resolve_image)
    if tag in ("ul", "ol"):
        return "\n".join(_list(node, resolve_image))
    if tag == "blockquote":
        return _blockquote(node, resolve_image)
    if tag == "hr":
        return "---"
    if tag == "img":
        return _image(node, resolve_image)
    if tag == "pre":
        return _pre(node)
    if tag == "figure":
        return _figure(node, resolve_image)
    raise Unsupported(tag)


def _text(node: Node, resolve_image: ImageResolver) -> str:
    text = _inline(node.children, resolve_image, strip=True)
    if not text:
        raise Unsupported("empty " + node.tag)
    return text


def _blockquote(node: Node, resolve_image: ImageResolver) -> str:
    paragraphs = []
    for child in node.children:
        if isinstance(child, str):
            if child.strip():
                raise Unsupported("blockquote text")
        elif child.tag == "p":
            paragraphs.append(_text(child, resolve_image))
        else:
            raise Unsupported("blockquote " + child.tag)
    if not paragraphs:
        raise Unsupported("empty blockquote")
    quoted = []
    for paragraph in paragraphs:
        quoted.append("\n".join("> " + line for line in paragraph.split("\n")))
    return "\n>\n".join(quoted)


def _figure(node: Node, resolve_image: ImageResolver) -> str:
    """Convert only a bare image with an empty caption."""
    parts = [c for c in node.children if not (isinstance(c, str) and not c.strip())]
    if len(parts) == 2 and all(isinstance(p, Node) for p in parts):
        image, caption = parts
        assert isinstance(image, Node) and isinstance(caption, Node)
        if (
            image.tag == "img"
            and caption.tag == "figcaption"
            and not any(
                (c.strip() if isinstance(c, str) else True) for c in caption.children
            )
        ):
            return _image(image, resolve_image)
    raise Unsupported("figure")


def _image(node: Node, resolve_image: ImageResolver) -> str:
    src = node.attrs.get("src")
    if not src:
        raise Unsupported("img without src")
    destination = resolve_image(src)
    alt = INLINE_ESCAPE.sub(
        lambda m: "\\" + m[1] if m[1] else "&", node.attrs.get("alt", "")
    )
    return f"![{alt}]({_destination(destination)})"


def _destination(url: str) -> str:
    if re.search(r"[\s()<>]", url) or not url:
        return "<" + url.replace("<", "%3C").replace(">", "%3E") + ">"
    return url


def _pre(node: Node) -> str:
    code = "".join(_plain(node))
    longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}\n{code.strip(chr(10))}\n{fence}"


def _plain(node: Node) -> list[str]:
    parts = []
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag == "br":
            parts.append("\n")
        else:
            parts.extend(_plain(child))
    return parts


def _list(node: Node, resolve_image: ImageResolver) -> list[str]:
    lines: list[str] = []
    ordered = node.tag == "ol"
    number = 0
    for child in node.children:
        if isinstance(child, str):
            if child.strip():
                raise Unsupported("list text")
            continue
        if child.tag != "li":
            raise Unsupported("list " + child.tag)
        number += 1
        marker = f"{number}. " if ordered else "- "
        indent = " " * len(marker)
        inline = _item_inline(child)
        nested = [c for c in child.children if _is_list(c)]
        text = _inline(inline, resolve_image, strip=True)
        if not text:
            raise Unsupported("empty list item")
        lines.append(marker + text.replace("\n", "\n" + indent))
        for sub in nested:
            assert isinstance(sub, Node)
            lines.extend(indent + line for line in _list(sub, resolve_image))
    return lines


def _item_inline(item: Node) -> list[Node | str]:
    """Return the inline content of ``item``, unwrapping a single ``<p>``."""
    rest = [c for c in item.children if not _is_list(c)]
    paragraphs = [c for c in rest if isinstance(c, Node) and c.tag == "p"]
    if not paragraphs:
        return rest
    others = [c for c in rest if c is not paragraphs[0]]
    if len(paragraphs) > 1 or any(not isinstance(c, str) or c.strip() for c in others):
        raise Unsupported("list item paragraphs")
    return paragraphs[0].children


def _is_list(child: Node | str) -> bool:
    return isinstance(child, Node) and child.tag in ("ul", "ol")


def _inline(
    children: list[Node | str], resolve_image: ImageResolver, strip: bool
) -> str:
    if strip:
        children = _trim(children)
    out = "".join(_inline_part(child, resolve_image) for child in children)
    if strip:
        out = re.sub(r"\n[ \t]+", "\n", out.strip())
    return LINE_START_ESCAPE.sub(_escape_line_start, out)


def _escape_line_start(match: re.Match[str]) -> str:
    if match[1]:
        return "\\" + match[1]
    return f"{match[2]}\\{match[3]}"


def _trim(children: list[Node | str]) -> list[Node | str]:
    """Drop leading and trailing line breaks and blank text."""

    def blank(child: Node | str) -> bool:
        return child.strip() == "" if isinstance(child, str) else child.tag == "br"

    start, end = 0, len(children)
    while start < end and blank(children[start]):
        start += 1
    while end > start and blank(children[end - 1]):
        end -= 1
    return children[start:end]


def _inline_part(child: Node | str, resolve_image: ImageResolver) -> str:
    if isinstance(child, str):
        collapsed = re.sub(r"[ \t\r\n\f]+", " ", child)
        return INLINE_ESCAPE.sub(lambda m: "\\" + m[1] if m[1] else "\\&", collapsed)
    tag = child.tag
    if tag == "br":
        return HARD_BREAK
    if tag == "img":
        return _image(child, resolve_image)
    inner = _inline(child.children, resolve_image, strip=False)
    if tag in ("strong", "b"):
        return _wrap(inner, "**")
    if tag in ("em", "i"):
        return _wrap(inner, "*")
    if tag == "code":
        return _code_span("".join(_plain(child)))
    if tag == "a":
        return _link(child, inner)
    raise Unsupported(tag)


EDGE_SPACE = re.compile(r"(?:\s|\\\n)+")


def _wrap(inner: str, mark: str) -> str:
    """Wrap ``inner`` in ``mark`` keeping spaces and breaks outside the marks.

    A break inside the emphasis would leave the marker next to a bare ``\\``.
    """
    lead = EDGE_SPACE.match(inner)
    trail = re.search(EDGE_SPACE.pattern + "$", inner)
    start = lead.end() if lead else 0
    end = trail.start() if trail else len(inner)
    if start >= end:
        return inner
    return f"{inner[:start]}{mark}{inner[start:end]}{mark}{inner[end:]}"


def _code_span(code: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", code)), default=0)
    fence = "`" * (longest + 1)
    pad = " " if code.startswith("`") or code.endswith("`") else ""
    return f"{fence}{pad}{code}{pad}{fence}"


def _link(node: Node, inner: str) -> str:
    href = node.attrs.get("href")
    if not href or not inner.strip():
        raise Unsupported("link")
    plain = "".join(_plain(node)).strip()
    if plain == href and not re.search(r"[\s<>]", href):
        return f"<{href}>"
    return f"[{inner.strip()}]({_destination(href)})"
