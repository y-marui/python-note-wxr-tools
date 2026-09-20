from urllib.parse import unquote

import pytest

from note_wxr_tools.htmlmd import convert_body
from note_wxr_tools.mdhtml import block_to_html, split_blocks


def _html(markdown: str) -> str:
    return block_to_html(
        markdown, lambda dest: "/assets/" + unquote(dest).split("/")[-1]
    )


def test_split_blocks_separates_on_blank_lines_and_keeps_fences_whole() -> None:
    body = "a\nb\n\n\n```\nx\n\ny\n```\n\nc"
    assert split_blocks(body) == ["a\nb", "```\nx\n\ny\n```", "c"]


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("## Head", "<h2>Head</h2>"),
        (
            "a **b** *c* _d_ `e`",
            "<p>a <strong>b</strong> <em>c</em> <em>d</em> <code>e</code></p>",
        ),
        ("a\\\nb", "<p>a<br>b</p>"),
        (
            "1\\. a \\* b \\&amp; &amp; x < y",
            "<p>1. a * b &amp;amp; &amp; x &lt; y</p>",
        ),
        ("snake_case_word", "<p>snake_case_word</p>"),
        (
            "[site](https://e.com/a) <https://e.com/b>",
            '<p><a href="https://e.com/a">site</a> '
            '<a href="https://e.com/b">https://e.com/b</a></p>',
        ),
        ("- a\n  - b\n- c", "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>"),
        ("1. x\n2. y", "<ol><li>x</li><li>y</li></ol>"),
        ("> a\n>\n> b", "<blockquote><p>a</p><p>b</p></blockquote>"),
        ("---", "<hr>"),
        ("```\na < b\n```", "<pre>a &lt; b</pre>"),
        (
            "![pic](x/a%20b.png)",
            '<figure><img src="/assets/a b.png" alt="pic">'
            "<figcaption></figcaption></figure>",
        ),
        (
            '<div><img src="Title-img/a.png"></div>',
            '<div><img src="/assets/a.png"></div>',
        ),
        ("a *not closed", "<p>a *not closed</p>"),
    ],
)
def test_block_to_html_converts_supported_markdown(
    markdown: str, expected: str
) -> None:
    assert _html(markdown) == expected


@pytest.mark.parametrize(
    "source",
    [
        '<h3 name="x">T <b>bold</b></h3>',
        "<p>a <strong>b</strong> <em>c</em> <b>d</b><br>e<br></p>",
        '<p><a href="https://e.com/a">site</a> <a href="https://e.com/b">https://e.com/b</a></p>',
        "<p>1. a * b _c_ [d] &amp;amp; &lt;tag&gt; `x`</p>",
        "<ul><li>a<ul><li>b</li><li>c</li></ul></li><li>d</li></ul><ol><li>x</li></ol>",
        "<ul><li><p>a <strong>b</strong></p><ul><li><p>c</p></li></ul></li></ul>",
        '<ol><li><p>x <a href="https://e.com">e</a></p></li></ol>',
        "<blockquote><p>a</p><p>b<br>c</p></blockquote><hr>",
        "<pre>a\n\nb</pre>",
        '<figure><img src="/assets/a.png" alt="x [y]">'
        "<figcaption></figcaption></figure>",
        "<p>- not a list</p><p># not a heading</p><p>2) nor this</p>",
    ],
)
def test_html_to_markdown_to_html_to_markdown_is_stable(source: str) -> None:
    """Regenerating an unedited block yields the same Markdown again."""

    def identity(src: str) -> str:
        return src

    def to_markdown(html: str) -> list[str]:
        return [b.markdown for b in convert_body(html, identity)]

    first = to_markdown(source)
    regenerated = "".join(block_to_html(m, identity) for m in first)
    assert to_markdown(regenerated) == first
