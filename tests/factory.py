"""Builders for synthetic note WXR exports (no real article data)."""

import zipfile
from pathlib import Path

ITEM = """<item><title><![CDATA[{title}]]></title><link>https://note.com/acct_x/n/{guid}</link>\
<dc:creator><![CDATA[Display]]></dc:creator><guid isPermaLink="false">{guid}</guid>\
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
