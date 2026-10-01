import pytest

from note_wxr_tools.htmlmd import convert_body, sha256, split_blocks


def _md(body: str) -> list[str]:
    return [b.markdown for b in convert_body(body, lambda src: "img/" + src[8:])]


def test_split_blocks_concatenation_equals_body() -> None:
    body = "<p>a</p>\n<h2>b</h2> loose <hr>\n<ul><li>x</li></ul>\n"
    assert "".join(html for html, _ in split_blocks(body)) == body


def test_split_blocks_empty_body_yields_no_blocks() -> None:
    assert split_blocks("") == []


def test_convert_body_heading_paragraph_and_inline() -> None:
    body = '<h3 name="x">T</h3><p>a <strong>b</strong> <em>c</em> <b>d</b></p>'
    assert _md(body) == ["### T", "a **b** *c* **d**"]


def test_convert_body_link_and_autolink() -> None:
    body = '<p><a href="https://e.com/a">site</a> <a href="https://e.com/b">https://e.com/b</a></p>'
    assert _md(body) == ["[site](https://e.com/a) <https://e.com/b>"]


def test_convert_body_line_breaks_drop_trailing_and_keep_inner() -> None:
    assert _md("<p>a<br>b<br></p>") == ["a\\\nb"]


def test_convert_body_escapes_markdown_syntax_in_text() -> None:
    assert _md("<p>1. a * b _c_ [d] &amp;amp;</p>") == [
        "1\\. a \\* b \\_c\\_ \\[d\\] \\&amp;"
    ]


def test_convert_body_nested_lists() -> None:
    body = "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul><ol><li>x</li></ol>"
    assert _md(body) == ["- a\n  - b\n- c", "1. x"]


def test_convert_body_lists_with_paragraph_items() -> None:
    body = (
        '<ul name="u"><li name="i"><p name="p">a <strong>b</strong></p></li>'
        '<li><p>see <a href="https://e.com">e</a></p>'
        "<ul><li><p>nested</p></li></ul></li></ul>"
        "<ol><li><p>x</p></li><li><p>y</p></li></ol>"
    )
    blocks = convert_body(body, lambda src: src)
    assert [b.markdown for b in blocks] == [
        "- a **b**\n- see [e](https://e.com)\n  - nested",
        "1. x\n2. y",
    ]
    assert not any(b.raw for b in blocks)


@pytest.mark.parametrize(
    "body",
    [
        "<ul><li><p>a</p><p>b</p></li></ul>",
        "<ul><li><p>a</p>loose</li></ul>",
        "<ul><li><p></p></li></ul>",
        "<ul><li><blockquote>a</blockquote></li></ul>",
    ],
)
def test_convert_body_keeps_complex_lists_raw(body: str) -> None:
    blocks = convert_body(body, lambda src: src)
    assert [b.raw for b in blocks] == [True]
    assert blocks[0].html == body


def test_convert_body_blockquote_and_hr() -> None:
    body = "<blockquote><p>a</p><p>b<br>c</p></blockquote><hr>"
    assert _md(body) == ["> a\n>\n> b\\\n> c", "---"]


def test_convert_body_figure_with_bare_image_becomes_markdown_image() -> None:
    body = (
        '<figure name="f"><img src="/assets/a b.png" alt="pic">'
        "<figcaption></figcaption></figure>"
    )
    assert _md(body) == ["![pic](<img/a b.png>)"]


def test_convert_body_figure_with_caption_stays_raw_and_rewrites_src() -> None:
    body = '<figure><img src="/assets/a.png"><figcaption>cap</figcaption></figure>'
    (block,) = convert_body(body, lambda src: "img/" + src[8:])
    assert block.raw
    assert (
        block.markdown
        == '<figure><img src="img/a.png"><figcaption>cap</figcaption></figure>'
    )


def test_convert_body_raw_block_has_no_blank_lines() -> None:
    (block,) = convert_body("<div>a\n\n\nb</div>", lambda src: src)
    assert block.raw
    assert "\n\n" not in block.markdown


def test_convert_body_empty_paragraph_stays_raw() -> None:
    (block,) = convert_body("<p></p>", lambda src: src)
    assert block.raw


def test_convert_body_pre_becomes_fenced_code() -> None:
    assert _md("<pre>a\nb</pre>") == ["```\na\nb\n```"]


def test_convert_body_records_original_html_and_hash() -> None:
    (block,) = convert_body('<p name="x">a</p>', lambda src: src)
    assert block.html == '<p name="x">a</p>'
    assert block.markdown_sha256 == sha256("a")


@pytest.mark.parametrize("text", ["loose text"])
def test_convert_body_loose_text_becomes_block(text: str) -> None:
    assert _md(f"<p>a</p>{text}") == ["a", text]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("<p><b>a<br></b>&nbsp;b</p>", "**a**\\\n\xa0b"),
        ("<p>x<b><br>a</b></p>", "x\\\n**a**"),
        ("<p>x <b>a<br>b</b></p>", "x **a\\\nb**"),
        ("<p>x<i>a<br></i>y</p>", "x*a*\\\ny"),
        ("<p>x<b><i>a<br></i></b>y</p>", "x***a***\\\ny"),
        ("<p>x<b><br></b>y</p>", "x\\\ny"),
        ("<ul><li><p><b>a<br></b> b</p></li></ul>", "- **a**\\\n  b"),
    ],
)
def test_convert_body_emphasis_with_break_keeps_markers_balanced(
    body: str, expected: str
) -> None:
    assert _md(body) == [expected]
