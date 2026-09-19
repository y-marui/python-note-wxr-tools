import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.to_md import ConversionError, convert, iso_datetime, main
from tests.factory import make_item

MakeExport = Callable[..., Path]


def _folder(out: Path) -> Path:
    return out / "acct-x"


def test_convert_writes_manuscript_sidecar_and_channel(
    make_export: MakeExport, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    report = convert(make_export([make_item()]), out)

    assert (report.articles, report.images) == (1, 0)
    text = (_folder(out) / "Title.md").read_text(encoding="utf-8")
    assert text == (
        "---\n"
        'title: "Title"\n'
        'account: "acct_x"\n'
        'platform_post_id: "n1"\n'
        'publication_url: "https://note.com/acct_x/n/n1"\n'
        'platform_created_at: "2019-09-04T17:39:39+09:00"\n'
        'platform_updated_at: "2019-09-05T10:00:00+09:00"\n'
        'publication_status: "published"\n'
        'platform: "note"\n'
        'origin: "note.com export"\n'
        "---\n\n## Head\n\nHello **world**\n"
    )
    channel = json.loads((_folder(out) / ".note-channel.json").read_text("utf-8"))
    assert channel["guids"] == ["n1"]
    assert channel["channel"]["language"] == "ja"
    assert channel["author"]["wp:author_login"] == "acct_x"


def test_convert_sidecar_reassembles_original_body(
    make_export: MakeExport, tmp_path: Path
) -> None:
    body = '<h2 name="a">Head</h2>\n<p name="b">x<br></p><figure><a></a></figure>'
    out = tmp_path / "out"
    convert(make_export([make_item(body=body)]), out)

    sidecar = json.loads((_folder(out) / "Title.note.json").read_text("utf-8"))
    assert "".join(b["html"] for b in sidecar["blocks"]) == body
    assert sidecar["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    assert sidecar["item"]["wp:post_id"] == "1"
    assert sidecar["item"]["title"] == "Title"
    assert sidecar["item"]["wp:post_modified_gmt"] == "2019-09-05 01:00:00"


def test_convert_copies_images_and_rewrites_references(
    make_export: MakeExport, tmp_path: Path
) -> None:
    body = '<figure><img src="/assets/a.png"><figcaption></figcaption></figure>'
    out = tmp_path / "out"
    report = convert(make_export([make_item(body=body)], {"a.png": b"PNG"}), out)

    assert report.images == 1
    assert (_folder(out) / "Title-img" / "a.png").read_bytes() == b"PNG"
    assert "![](Title-img/a.png)" in (_folder(out) / "Title.md").read_text("utf-8")


def test_convert_draft_omits_publication_url(
    make_export: MakeExport, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    convert(make_export([make_item(status="draft")]), out)

    text = (_folder(out) / "Title.md").read_text("utf-8")
    assert 'publication_status: "draft"' in text
    assert "publication_url" not in text


def test_convert_maps_unusable_filename_characters_to_full_width(
    make_export: MakeExport, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    convert(make_export([make_item(title="a/b: c")]), out)

    assert (_folder(out) / "a／b： c.md").exists()


def test_convert_never_overwrites_without_force(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item()])
    out = tmp_path / "out"
    convert(export, out)

    with pytest.raises(ConversionError, match="already exist"):
        convert(export, out)
    convert(export, out, force=True)


def test_convert_rejects_empty_and_duplicate_titles_unless_renamed(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export(
        [
            make_item(guid="n1", title=""),
            make_item(guid="n2", title="Same"),
            make_item(guid="n3", title="Same"),
        ]
    )
    with pytest.raises(ConversionError) as error:
        convert(export, tmp_path / "bad")
    assert "n1" in str(error.value) and "duplicate" in str(error.value)

    convert(export, tmp_path / "ok", renames={"n1": "One", "n3": "Three"})
    assert (_folder(tmp_path / "ok") / "Three.md").exists()
    assert 'title: "Three"' in (_folder(tmp_path / "ok") / "Three.md").read_text(
        "utf-8"
    )


def test_convert_rejects_rename_for_unknown_guid(
    make_export: MakeExport, tmp_path: Path
) -> None:
    with pytest.raises(ConversionError, match="no article with guid zzz"):
        convert(make_export([make_item()]), tmp_path / "o", renames={"zzz": "x"})


def test_convert_rejects_unsupported_status(
    make_export: MakeExport, tmp_path: Path
) -> None:
    with pytest.raises(ConversionError, match="unsupported wp:status"):
        convert(make_export([make_item(status="private")]), tmp_path / "o")


@pytest.mark.parametrize(
    "body, message",
    [
        ('<p><img src="/assets/missing.png"></p>', "missing image attachment"),
        ('<p><img src="https://e.com/x.png"></p>', "unresolved image URL"),
    ],
)
def test_convert_image_problems_fail_unless_lossy_allowed(
    make_export: MakeExport, tmp_path: Path, body: str, message: str
) -> None:
    export = make_export([make_item(body=body)])
    with pytest.raises(ConversionError, match=message):
        convert(export, tmp_path / "bad")

    report = convert(export, tmp_path / "ok", allow_lossy=True)
    assert any(message in w for w in report.warnings)


def test_convert_unrepresentable_item_field_is_lossy(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(extra="<wp:extra>1</wp:extra>")])
    with pytest.raises(ConversionError, match="cannot be represented"):
        convert(export, tmp_path / "bad")
    convert(export, tmp_path / "ok", allow_lossy=True)


def test_convert_guid_collision_is_lossy(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(title="A"), make_item(title="B")])
    with pytest.raises(ConversionError, match="guid collision"):
        convert(export, tmp_path / "bad")
    assert convert(export, tmp_path / "ok", allow_lossy=True).articles == 2

    from note_wxr_tools.validate import validate

    result = validate(_folder(tmp_path / "ok"))
    assert result.errors == []
    assert any("duplicate platform_post_id" in w for w in result.warnings)


def test_convert_reads_extracted_directory(
    make_export: MakeExport, tmp_path: Path
) -> None:
    import zipfile

    src = tmp_path / "src"
    with zipfile.ZipFile(make_export([make_item()])) as archive:
        archive.extractall(src)
    assert convert(src, tmp_path / "out").articles == 1


def test_iso_datetime_negative_offset() -> None:
    assert iso_datetime("2020-01-01 00:00:00", "2020-01-01 05:30:00") == (
        "2020-01-01T00:00:00-05:30"
    )


def test_main_reports_errors_with_exit_code_1(
    make_export: MakeExport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    export = str(make_export([make_item(title="")]))
    assert main([export, "--out", str(tmp_path / "o")]) == 1
    assert "--rename" in capsys.readouterr().err

    args = [export, "--out", str(tmp_path / "o"), "--rename", "n1=Named"]
    assert main(args) == 0
    assert "wrote 1 article(s)" in capsys.readouterr().out


def test_convert_writes_manifest(make_export: MakeExport, tmp_path: Path) -> None:
    body = '<figure><img src="/assets/a.png"><figcaption></figcaption></figure>'
    export = make_export(
        [make_item(body=body), make_item(guid="n2", title="Two", status="draft")],
        {"a.png": b"PNG"},
    )
    out = tmp_path / "out"
    convert(export, out, allow_lossy=True)

    data = json.loads((_folder(out) / "manifest.json").read_text("utf-8"))
    assert data["command"] == "note-wxr-to-md"
    assert data["allow_lossy"] is True
    assert (data["article_count"], data["image_count"], data["total_size"]) == (2, 1, 3)
    assert [a["guid"] for a in data["articles"]] == ["n1", "n2"]
    assert (
        data["articles"][0]["body_sha256"] == hashlib.sha256(body.encode()).hexdigest()
    )
    paths = {i["path"] for i in data["inputs"]}
    assert paths == {"note-acct_x-1.xml", "assets/a.png"}
