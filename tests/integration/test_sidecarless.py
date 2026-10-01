"""Building WXR from front matter and Markdown alone (no sidecar)."""

import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.frontmatter import parse as parse_front_matter
from note_wxr_tools.to_md import ConversionError, convert, main
from note_wxr_tools.to_wxr import convert as to_wxr
from note_wxr_tools.validate import validate
from note_wxr_tools.wxr import parse
from tests.factory import REALISTIC_ASSETS, make_item, realistic_items

MakeExport = Callable[..., Path]


def _items(zip_path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        xml = archive.read("note-acct_x-1.xml")
    return [item.fields for item in parse(xml).items]


def _rebuild(export: Path, tmp_path: Path, names: list[str]) -> list[dict[str, str]]:
    convert(export, tmp_path / "md")
    folder = tmp_path / "md" / "acct-x"
    assert not list(folder.glob("*.note.json"))
    assert validate(folder).errors == []
    report = to_wxr([folder / f"{n}.md" for n in names], tmp_path / "wxr")
    return _items(report.zip_path)


def test_to_wxr_builds_items_from_front_matter_and_channel(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export(realistic_items(), REALISTIC_ASSETS)
    original = {
        i.fields["guid"]: i.fields
        for i in parse(zipfile.ZipFile(export).read("note-acct_x-1.xml")).items
    }
    rebuilt = _rebuild(export, tmp_path, ["Published", "Draft"])

    assert [f["wp:post_id"] for f in rebuilt] == ["1", "2"]
    for fields in rebuilt:
        before = original[fields["guid"]]
        for tag in (
            "title",
            "link",
            "pubDate",
            "wp:post_date",
            "wp:post_date_gmt",
            "wp:post_modified",
            "wp:post_modified_gmt",
            "wp:status",
            "wp:post_type",
            "wp:post_parent",
            "wp:menu_order",
            "wp:is_sticky",
            "wp:comment_status",
            "wp:ping_status",
            "wp:post_password",
            "excerpt:encoded",
            "description",
        ):
            assert fields[tag] == before[tag], tag
        assert fields["dc:creator"] == "Synthetic"


def test_to_wxr_keeps_the_original_title_from_note_title(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(title="a/b: c")])
    convert(export, tmp_path / "md")
    md = tmp_path / "md" / "acct-x" / "a／b： c.md"
    props, _ = parse_front_matter(md.read_text("utf-8"))
    assert props["note_title"] == "a/b: c"

    [item] = _items(to_wxr([md], tmp_path / "wxr").zip_path)
    assert item["title"] == "a/b: c"


def test_note_title_is_omitted_when_the_title_is_filename_safe(
    make_export: MakeExport, tmp_path: Path
) -> None:
    convert(make_export([make_item()]), tmp_path / "md")
    props, _ = parse_front_matter(
        (tmp_path / "md" / "acct-x" / "Title.md").read_text("utf-8")
    )
    assert "note_title" not in props


def test_to_wxr_generates_a_stable_guid_for_articles_made_in_obsidian(
    make_export: MakeExport, tmp_path: Path
) -> None:
    convert(make_export([make_item(status="draft")]), tmp_path / "md")
    folder = tmp_path / "md" / "acct-x"
    text = (folder / "Title.md").read_text("utf-8")
    (folder / "Made.md").write_text(
        "\n".join(
            line
            for line in text.replace('"Title"', '"Made"', 1).split("\n")
            if not line.startswith("platform_post_id")
        ),
        "utf-8",
    )
    assert validate(folder).errors == []

    first = _items(to_wxr([folder / "Made.md"], tmp_path / "a").zip_path)[0]
    second = _items(to_wxr([folder / "Made.md"], tmp_path / "b").zip_path)[0]
    assert first["guid"] == second["guid"] != "n1"
    assert first["link"] == f"https://note.com/acct_x/n/{first['guid']}"


def test_to_wxr_orders_items_by_creation_date(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export(
        [make_item(guid="n1", title="One"), make_item(guid="n2", title="Two")]
    )
    convert(export, tmp_path / "md")
    folder = tmp_path / "md" / "acct-x"
    two = folder / "Two.md"
    two.write_text(
        two.read_text("utf-8").replace("2019-09-04T17:39:39", "2019-01-01T00:00:00"),
        "utf-8",
    )

    items = _items(to_wxr([folder / "One.md", two], tmp_path / "wxr").zip_path)
    assert [i["guid"] for i in items] == ["n2", "n1"]


def test_to_md_with_sidecar_flag_writes_sidecars(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item()])
    assert main([str(export), "--out", str(tmp_path / "md"), "--with-sidecar"]) == 0
    assert (tmp_path / "md" / "acct-x" / "Title.note.json").exists()


def test_to_md_rejects_item_fields_it_cannot_restore_without_a_sidecar(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export(
        [
            make_item(extra="").replace(
                "<wp:comment_status><![CDATA[open]]>",
                "<wp:comment_status><![CDATA[closed]]>",
            )
        ]
    )
    with pytest.raises(ConversionError, match="wp:comment_status differs"):
        convert(export, tmp_path / "bad")
    convert(export, tmp_path / "with", with_sidecar=True)
    convert(export, tmp_path / "lossy", allow_lossy=True)
