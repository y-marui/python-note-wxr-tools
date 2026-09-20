"""The exact round trip (WXR -> Markdown -> WXR) on realistic synthetic data."""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.htmlmd import convert_body, split_blocks
from note_wxr_tools.mdhtml import split_blocks as split_markdown
from note_wxr_tools.to_md import convert as to_md
from note_wxr_tools.to_wxr import convert as to_wxr
from note_wxr_tools.validate import validate
from tests.factory import (
    REALISTIC_ASSETS,
    REALISTIC_BODY,
    WXR,
    make_item,
    realistic_items,
)

MakeExport = Callable[..., Path]
XML_NAME = "note-acct_x-1.xml"


def _content(zip_path: Path) -> str:
    """Return the ``content:encoded`` of the first item in the ZIP."""
    xml = zipfile.ZipFile(zip_path).read(XML_NAME).decode("utf-8")
    start = xml.index("<content:encoded><![CDATA[") + len("<content:encoded><![CDATA[")
    return xml[start : xml.index("]]></content:encoded>", start)]


@pytest.fixture
def account_folder(make_export: MakeExport, tmp_path: Path) -> Path:
    to_md(
        make_export(realistic_items(), REALISTIC_ASSETS),
        tmp_path / "md",
        with_sidecar=True,
    )
    return tmp_path / "md" / "acct-x"


def test_round_trip_is_byte_identical(account_folder: Path, tmp_path: Path) -> None:
    articles = [account_folder / "Published.md", account_folder / "Draft.md"]
    report = to_wxr(articles, tmp_path / "wxr")

    with zipfile.ZipFile(report.zip_path) as archive:
        assert archive.read(XML_NAME).decode("utf-8") == WXR.format(
            items="".join(realistic_items())
        )
        assert {n: archive.read(n) for n in archive.namelist()} == {
            XML_NAME: archive.read(XML_NAME),
            **{f"assets/{n}": d for n, d in REALISTIC_ASSETS.items()},
        }
    assert report.regenerated_blocks == 0


def test_converted_output_validates_and_keeps_unconvertible_blocks_raw(
    account_folder: Path,
) -> None:
    result = validate(account_folder)
    assert (result.errors, result.warnings) == ([], [])

    text = (account_folder / "Published.md").read_text("utf-8")
    assert "![](Published-img/n1_a.png)" in text
    assert '<img src="Published-img/n1_b.png"' in text
    assert "<figure" in text and '<p name="e1"></p>' in text


def _editable_indexes() -> list[int]:
    """Indexes of blocks whose Markdown can take a trailing text edit."""
    blocks = convert_body(REALISTIC_BODY, lambda src: src)
    return [
        i
        for i, block in enumerate(blocks)
        if not block.raw and not block.markdown.startswith(("![", "---"))
    ]


@pytest.mark.parametrize("index", _editable_indexes())
def test_editing_one_block_regenerates_only_that_block(
    account_folder: Path, tmp_path: Path, index: int
) -> None:
    md = account_folder / "Published.md"
    head, body = md.read_text("utf-8").split("\n---\n\n", 1)
    blocks = split_markdown(body)
    blocks[index] += " edited"
    md.write_text(f"{head}\n---\n\n" + "\n\n".join(blocks) + "\n", "utf-8")

    report = to_wxr([md], tmp_path / "wxr")
    original = [html for html, _ in split_blocks(REALISTIC_BODY)]
    before = "".join(original[:index])
    after = "".join(original[index + 1 :])
    content = _content(report.zip_path)

    assert report.regenerated_blocks == 1
    assert content.startswith(before) and content.endswith(after)
    assert "edited" in content[len(before) : len(content) - len(after)]


LIST_BODY = (
    "<p>intro</p>\n"
    "<ul><li><p>a <strong>b</strong></p><ul><li><p>nested</p></li></ul></li>"
    '<li><p><a href="https://e.com">link</a></p></li></ul>\n'
    "<ol><li><p>x</p></li><li><p>y</p></li></ol>"
)


def test_paragraph_lists_become_markdown_and_round_trip(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(body=LIST_BODY)])
    to_md(export, tmp_path / "md", with_sidecar=True)
    md = tmp_path / "md" / "acct-x" / "Title.md"
    text = md.read_text("utf-8")
    assert "- a **b**\n  - nested\n- [link](https://e.com)" in text
    assert "<ul>" not in text

    report = to_wxr([md], tmp_path / "wxr")
    assert report.regenerated_blocks == 0
    assert _content(report.zip_path) == LIST_BODY

    md.write_text(text.replace("- [link]", "- edited [link]"), "utf-8")
    edited = to_wxr([md], tmp_path / "wxr2")
    assert edited.regenerated_blocks == 1
    content = _content(edited.zip_path)
    assert content.startswith("<p>intro</p><ul>") and content.endswith(
        "\n<ol>" + LIST_BODY.split("<ol>")[1]
    )
    assert "edited" in content
