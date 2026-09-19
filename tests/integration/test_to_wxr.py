import json
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.to_md import ConversionError, convert
from note_wxr_tools.to_wxr import convert as to_wxr
from note_wxr_tools.to_wxr import main
from tests.factory import WXR, make_item

MakeExport = Callable[..., Path]
BODY = (
    '<h2 name="h1">Head</h2><p name="p1">First <strong>bold</strong></p>'
    '<figure name="f1"><img src="/assets/a.png"><figcaption></figcaption></figure>'
    '<p name="p2">Last</p>'
)


def _xml(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        return archive.read("note-acct_x-1.xml").decode("utf-8")


@pytest.fixture
def workspace(make_export: MakeExport, tmp_path: Path) -> tuple[Path, str]:
    """A converted account folder and the original WXR text."""
    items = [
        make_item(guid="n1", title="One", body=BODY, post_id=1),
        make_item(guid="n2", title="Two", body="<p>Two</p>", status="draft", post_id=2),
    ]
    export = make_export(items, {"a.png": b"PNG"})
    convert(export, tmp_path / "md")
    return tmp_path / "md" / "acct-x", WXR.format(items="".join(items))


def _run(folder: Path, tmp_path: Path, names: list[str] | None = None) -> Path:
    names = names or ["One", "Two"]
    return to_wxr([folder / f"{n}.md" for n in names], tmp_path / "wxr").zip_path


def test_convert_unedited_manuscripts_reproduce_the_original_xml(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, original = workspace
    report = to_wxr([folder / "One.md", folder / "Two.md"], tmp_path / "wxr")

    assert _xml(report.zip_path) == original
    assert (report.articles, report.images, report.regenerated_blocks) == (2, 1, 0)
    with zipfile.ZipFile(report.zip_path) as archive:
        assert archive.read("assets/a.png") == b"PNG"


def test_convert_orders_items_by_channel_and_accepts_a_subset(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    reordered = to_wxr([folder / "Two.md", folder / "One.md"], tmp_path / "a")
    assert _xml(reordered.zip_path).index('<guid isPermaLink="false">n1<') < _xml(
        reordered.zip_path
    ).index('<guid isPermaLink="false">n2<')

    subset = to_wxr([folder / "Two.md"], tmp_path / "b")
    xml = _xml(subset.zip_path)
    assert "n2<" in xml and "n1<" not in xml


def test_convert_regenerates_only_edited_blocks(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, original = workspace
    md = folder / "One.md"
    md.write_text(md.read_text("utf-8").replace("Last", "Changed *text*"), "utf-8")

    report = to_wxr([md], tmp_path / "wxr")
    xml = _xml(report.zip_path)
    assert report.regenerated_blocks == 1
    assert "<p>Changed <em>text</em></p>" in xml
    assert '<h2 name="h1">Head</h2><p name="p1">First <strong>bold</strong></p>' in xml
    assert '<p name="p2">Last</p>' not in xml


def test_convert_handles_inserted_and_deleted_blocks(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    md = folder / "One.md"
    text = md.read_text("utf-8")
    text = text.replace("## Head\n\n", "").replace(
        "Last", "Last\n\nNew ![](One-img/a.png) image"
    )
    md.write_text(text, "utf-8")

    xml = _xml(to_wxr([md], tmp_path / "wxr").zip_path)
    assert "<h2" not in xml
    assert '<p>New <img src="/assets/a.png"> image</p>' in xml


def test_convert_maps_front_matter_edits_back_to_wxr_fields(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    md = folder / "One.md"
    text = md.read_text("utf-8")
    text = text.replace(
        'platform_updated_at: "2019-09-05T10:00:00+09:00"',
        'platform_updated_at: "2020-01-01T00:30:00-05:00"',
    ).replace('publication_status: "published"', 'publication_status: "needs_update"')
    md.write_text(text, "utf-8")

    xml = _xml(to_wxr([md], tmp_path / "wxr").zip_path)
    assert "<wp:post_modified><![CDATA[2020-01-01 00:30:00]]>" in xml
    assert "<wp:post_modified_gmt><![CDATA[2020-01-01 05:30:00]]>" in xml
    assert "<wp:status><![CDATA[publish]]>" in xml


def test_convert_uses_the_renamed_title(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(title="")])
    convert(export, tmp_path / "md", renames={"n1": "Named"})

    zip_path = _run(tmp_path / "md" / "acct-x", tmp_path, ["Named"])
    assert "<title><![CDATA[Named]]></title>" in _xml(zip_path)


def test_convert_refuses_when_validation_fails(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    (folder / "One-img" / "a.png").unlink()

    with pytest.raises(ConversionError, match="missing image file"):
        _run(folder, tmp_path)
    assert not (tmp_path / "wxr").exists()


def test_convert_requires_the_channel_file(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    (folder / ".note-channel.json").unlink()
    with pytest.raises(ConversionError, match=r"\.note-channel\.json: file is missing"):
        _run(folder, tmp_path)


def test_convert_rejects_articles_missing_from_the_channel(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    channel = folder / ".note-channel.json"
    data = json.loads(channel.read_text("utf-8"))
    data["guids"] = ["n2"]
    channel.write_text(json.dumps(data), "utf-8")
    with pytest.raises(ConversionError, match="not in .note-channel.json: n1"):
        _run(folder, tmp_path, ["One"])


def test_convert_rejects_bad_article_arguments(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    with pytest.raises(ConversionError, match="no article"):
        to_wxr([], tmp_path / "o")
    with pytest.raises(ConversionError, match="more than once"):
        to_wxr([folder / "One.md", folder / "One.md"], tmp_path / "o")
    with pytest.raises(ConversionError, match="not a manuscript"):
        to_wxr([folder / "missing.md"], tmp_path / "o")
    other = tmp_path / "other"
    other.mkdir()
    (other / "x.md").write_text("x", "utf-8")
    with pytest.raises(ConversionError, match="same account folder"):
        to_wxr([folder / "One.md", other / "x.md"], tmp_path / "o")


def test_convert_never_overwrites_without_force(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    _run(folder, tmp_path)
    with pytest.raises(ConversionError, match="already exists"):
        _run(folder, tmp_path)
    to_wxr([folder / "One.md"], tmp_path / "wxr", force=True)


def test_convert_writes_manifest_for_the_output(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    _run(folder, tmp_path)

    data = json.loads((tmp_path / "wxr" / "manifest.json").read_text("utf-8"))
    assert data["command"] == "note-md-to-wxr"
    assert (data["article_count"], data["image_count"], data["total_size"]) == (2, 1, 3)
    assert {i["path"] for i in data["inputs"]} >= {"One.md", "One-img/a.png"}


def test_main_exit_codes(
    workspace: tuple[Path, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, _ = workspace
    args = [str(folder / "One.md"), "--out", str(tmp_path / "wxr")]
    assert main(args) == 0
    assert "wrote" in capsys.readouterr().out
    assert main(args) == 1
    assert "already exists" in capsys.readouterr().err


def _write_map(path: Path, mapping: dict[str, str]) -> Path:
    path.write_text(json.dumps(mapping), "utf-8")
    return path


def test_convert_image_map_replaces_references_and_records_the_count(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    md = folder / "One.md"
    md.write_text(
        md.read_text("utf-8").replace("Last", "Last ![](One-img/a.png)"), "utf-8"
    )
    mapping = _write_map(
        tmp_path / "map.json", {"/assets/a.png": "https://cdn.example/a.png?x=1&y=2"}
    )

    report = to_wxr([md], tmp_path / "wxr", image_map=mapping)

    xml = _xml(report.zip_path)
    assert "/assets/" not in xml
    assert xml.count('src="https://cdn.example/a.png?x=1&amp;y=2"') == 2
    assert (report.images, report.replaced_images) == (0, 2)
    with zipfile.ZipFile(report.zip_path) as archive:
        assert archive.namelist() == ["note-acct_x-1.xml"]
    data = json.loads((tmp_path / "wxr" / "manifest.json").read_text("utf-8"))
    assert data["image_map"] == {"replaced": 2}
    assert "image-map/map.json" in {i["path"] for i in data["inputs"]}


def test_convert_image_map_accepts_bare_file_names(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    mapping = _write_map(tmp_path / "map.json", {"a.png": "https://cdn.example/a.png"})
    report = to_wxr([folder / "One.md"], tmp_path / "wxr", image_map=mapping)
    assert report.replaced_images == 1


def test_convert_image_map_rejects_unmapped_images_and_non_https_urls(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    empty = _write_map(tmp_path / "empty.json", {})
    with pytest.raises(ConversionError, match="not in the image map: a.png"):
        to_wxr([folder / "One.md"], tmp_path / "wxr", image_map=empty)
    assert not (tmp_path / "wxr").exists()

    insecure = _write_map(tmp_path / "http.json", {"a.png": "http://cdn.example/a.png"})
    with pytest.raises(ConversionError, match="not an HTTPS URL"):
        to_wxr([folder / "One.md"], tmp_path / "wxr", image_map=insecure)


def test_convert_allow_lossy_downgrades_missing_images_and_records_it(
    workspace: tuple[Path, str], tmp_path: Path
) -> None:
    folder, _ = workspace
    (folder / "One-img" / "a.png").unlink()
    with pytest.raises(ConversionError, match="missing image file"):
        to_wxr([folder / "One.md"], tmp_path / "strict")

    report = to_wxr([folder / "One.md"], tmp_path / "lossy", allow_lossy=True)

    assert report.images == 0
    assert any("missing image file" in w for w in report.warnings)
    data = json.loads((tmp_path / "lossy" / "manifest.json").read_text("utf-8"))
    assert data["allow_lossy"] is True
    assert data["warnings"] == report.warnings


def test_main_supports_allow_lossy_and_image_map(
    workspace: tuple[Path, str],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder, _ = workspace
    mapping = _write_map(tmp_path / "map.json", {"a.png": "https://cdn.example/a.png"})
    args = [str(folder / "One.md"), "--out", str(tmp_path / "wxr")]
    assert main([*args, "--image-map", str(mapping), "--allow-lossy"]) == 0
    assert "1 image URL(s) replaced" in capsys.readouterr().out
