"""Render a note-style WXR file (the inverse of ``wxr.parse``)."""

from __future__ import annotations

XML_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
    'xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/" '
    'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
    'xmlns:wfw="http://wellformedweb.org/CommentAPI/" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" '
    'xmlns:wp="http://wordpress.org/export/1.2/"><channel>'
)
XML_TAIL = "</channel></rss>"
# Element order of an <item> and whether note wraps its text in CDATA.
ITEM_LAYOUT = (
    ("title", True),
    ("link", False),
    ("dc:creator", True),
    ("guid", False),
    ("description", False),
    ("content:encoded", True),
    ("excerpt:encoded", False),
    ("wp:post_id", False),
    ("pubDate", False),
    ("wp:post_date", True),
    ("wp:post_date_gmt", True),
    ("wp:post_modified", True),
    ("wp:post_modified_gmt", True),
    ("wp:comment_status", True),
    ("wp:ping_status", True),
    ("wp:post_name", True),
    ("wp:status", True),
    ("wp:post_parent", False),
    ("wp:menu_order", False),
    ("wp:post_type", True),
    ("wp:post_password", True),
    ("wp:is_sticky", False),
)
# Item fields that had the same value in every real export; used when there
# is no sidecar to say otherwise (``wp:post_name`` is not constant; it is left empty).
ITEM_DEFAULTS = {
    "wp:post_type": "post",
    "wp:post_parent": "0",
    "wp:menu_order": "0",
    "wp:is_sticky": "0",
    "wp:comment_status": "open",
    "wp:ping_status": "open",
    "wp:post_password": "",
    "wp:post_name": "",
    "excerpt:encoded": "",
    "description": "",
}
PLAIN_AUTHOR_FIELDS = frozenset({"wp:author_id"})
GUID_OPEN = '<guid isPermaLink="false">'


def _cdata(text: str) -> str:
    return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _plain(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _element(tag: str, text: str, cdata: bool) -> str:
    open_tag = GUID_OPEN if tag == "guid" else f"<{tag}>"
    return f"{open_tag}{_cdata(text) if cdata else _plain(text)}</{tag}>"


def render_item(fields: dict[str, str]) -> str:
    parts = [_element(tag, fields[tag], cdata) for tag, cdata in ITEM_LAYOUT]
    return "<item>" + "".join(parts) + "</item>"


def render_author(author: dict[str, str]) -> str:
    parts = [
        _element(tag, text, tag not in PLAIN_AUTHOR_FIELDS)
        for tag, text in author.items()
    ]
    return "<wp:author>" + "".join(parts) + "</wp:author>"


def render(
    channel: dict[str, str], author: dict[str, str], items: list[dict[str, str]]
) -> str:
    """Return the WXR document; ``items`` hold every tag of ``ITEM_LAYOUT``."""
    head = [_element(tag, text, False) for tag, text in channel.items()]
    # note writes the author block before <generator>.
    position = next(
        (i for i, tag in enumerate(channel) if tag == "generator"), len(head)
    )
    head.insert(position, render_author(author))
    return XML_HEAD + "".join(head) + "".join(map(render_item, items)) + XML_TAIL
