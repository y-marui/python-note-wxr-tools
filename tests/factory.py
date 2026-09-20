"""Builders for synthetic note WXR exports (no real article data)."""

import zipfile
from pathlib import Path

ITEM = """<item><title><![CDATA[{title}]]></title><link>https://note.com/acct_x/n/{guid}</link>\
<dc:creator><![CDATA[Synthetic]]></dc:creator><guid isPermaLink="false">{guid}</guid>\
<description></description><content:encoded><![CDATA[{body}]]></content:encoded>\
<excerpt:encoded></excerpt:encoded><wp:post_id>{post_id}</wp:post_id>\
<pubDate>Wed, 04 Sep 2019 17:39:39 +0900</pubDate>\
<wp:post_date><![CDATA[2019-09-04 17:39:39]]></wp:post_date>\
<wp:post_date_gmt><![CDATA[2019-09-04 08:39:39]]></wp:post_date_gmt>\
<wp:post_modified><![CDATA[2019-09-05 10:00:00]]></wp:post_modified>\
<wp:post_modified_gmt><![CDATA[2019-09-05 01:00:00]]></wp:post_modified_gmt>\
<wp:comment_status><![CDATA[open]]></wp:comment_status>\
<wp:ping_status><![CDATA[open]]></wp:ping_status>\
<wp:post_name><![CDATA[slug]]></wp:post_name><wp:status><![CDATA[{status}]]></wp:status>\
<wp:post_parent>0</wp:post_parent><wp:menu_order>0</wp:menu_order>\
<wp:post_type><![CDATA[post]]></wp:post_type>\
<wp:post_password><![CDATA[]]></wp:post_password><wp:is_sticky>0</wp:is_sticky>{extra}</item>"""

WXR = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" \
xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/" \
xmlns:content="http://purl.org/rss/1.0/modules/content/" \
xmlns:wfw="http://wellformedweb.org/CommentAPI/" \
xmlns:dc="http://purl.org/dc/elements/1.1/" \
xmlns:wp="http://wordpress.org/export/1.2/"><channel><title>Synthetic</title>\
<link>https://note.com/acct_x</link><description>desc</description>\
<pubDate>Sat, 19 Sep 2026 21:23:49 +0900</pubDate><language>ja</language>\
<wp:wxr_version>1.2</wp:wxr_version><wp:author><wp:author_id>1</wp:author_id>\
<wp:author_login><![CDATA[acct_x]]></wp:author_login></wp:author>\
<generator>note.com</generator>{items}</channel></rss>"""

DEFAULT_BODY = '<h2 name="a">Head</h2><p name="b">Hello <strong>world</strong></p>'


def make_item(
    guid: str = "n1",
    title: str = "Title",
    body: str = DEFAULT_BODY,
    status: str = "publish",
    post_id: int = 1,
    extra: str = "",
) -> str:
    return ITEM.format(
        guid=guid,
        title=title,
        body=body,
        status=status,
        post_id=post_id,
        extra=extra,
    )


def write_export(
    path: Path, items: list[str], assets: dict[str, bytes] | None = None
) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("note-acct_x-1.xml", WXR.format(items="".join(items)))
        for name, data in (assets or {}).items():
            archive.writestr(f"assets/{name}", data)
    return path


# A body that mimics the shapes seen in real note exports: block `name`
# attributes, newlines inside <b> in <h2>, figures (image, image with a link
# caption, quote card), nested lists, links, code and blocks that stay raw HTML.
REALISTIC_BODY = (
    '<h2 name="zGAft"><b>Section one</b></h2>'
    '<p name="Xcj05">　A paragraph with <strong>bold</strong> and '
    '<a href="https://example.com/a" target="_blank" rel="noopener noreferrer">'
    "a link</a>.<br></p>"
    '<p name="09abee84-fa03-4f3f-aed7-51fdb4c4dcbb"><a href="https://example.com/b">'
    "https://example.com/b</a></p>"
    '<h2 name="9FK5D">\n<b>Section two</b><br>\n</h2>'
    '<figure name="cc016517-709a-4c6d-b18b-dbe5853b3693"><img src="/assets/n1_a.png">'
    "<figcaption></figcaption></figure>"
    '<figure name="a1" id="a1"><img src="/assets/n1_b.png" alt="alt text" width="620" '
    'height="413"><figcaption><a href="https://example.com/c" target="_blank" '
    'rel="noopener noreferrer">caption</a></figcaption></figure>'
    '<figure name="q1" id="q1"><blockquote><p name="q2" id="q2"><strong>quoted</strong>'
    "<br></p></blockquote><figcaption></figcaption></figure>"
    '<ul name="u1"><li>first<ul><li>nested</li></ul></li>'
    "<li>second &amp; more</li></ul>"
    '<ol name="o1"><li>one</li><li>two</li></ol>'
    '<blockquote name="b1"><p name="b2">quote line one<br>quote line two</p>'
    "</blockquote>"
    '<p name="e1"></p>'
    '<hr name="r1">'
    "\n"
    '<p name="last">Trailing paragraph 1. not a list &lt;tag&gt;</p>'
)
REALISTIC_ASSETS = {"n1_a.png": b"A" * 10, "n1_b.png": b"B" * 20}


def realistic_items() -> list[str]:
    """One published article with every shape above and one draft."""
    return [
        make_item(guid="n1", title="Published", body=REALISTIC_BODY, post_id=1),
        make_item(
            guid="n2",
            title="Draft",
            body='<p name="d">Draft text</p>',
            status="draft",
            post_id=2,
        ),
    ]
