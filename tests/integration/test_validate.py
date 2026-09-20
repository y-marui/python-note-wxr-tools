import json
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.manifest import MANIFEST_NAME
from note_wxr_tools.to_md import convert
from note_wxr_tools.validate import image_refs, main, validate
from tests.factory import make_item

MakeExport = Callable[..., Path]
IMAGE_BODY = '<figure><img src="/assets/a.png"><figcaption></figcaption></figure>'


@pytest.fixture
def folder(make_export: MakeExport, tmp_path: Path) -> Path:
    export = make_export([make_item(body=IMAGE_BODY)], {"a.png": b"PNG"})
    convert(export, tmp_path / "out")
    return tmp_path / "out" / "acct-x"


def _edit_json(path: Path, change: Callable[[dict], None]) -> None:  # type: ignore[type-arg]
    data = json.loads(path.read_text("utf-8"))
    change(data)
    path.write_text(json.dumps(data), "utf-8")


def test_validate_converter_output_is_clean(folder: Path) -> None:
    result = validate(folder)
    assert (result.errors, result.warnings) == ([], [])


def test_validate_ignores_readme_and_hidden_markdown(folder: Path) -> None:
    (folder / "README.md").write_text("# Notes about this account\n", "utf-8")
    (folder / ".scratch.md").write_text("no front matter\n", "utf-8")
    result = validate(folder)
    assert (result.errors, result.warnings) == ([], [])


def test_validate_reports_missing_and_invalid_properties(folder: Path) -> None:
    md = folder / "Title.md"
    text = md.read_text("utf-8")
    text = text.replace('platform: "note"\n', "").replace(
        'publication_status: "published"', 'publication_status: "live"'
    )
    md.write_text(text.replace('title: "Title"', 'title: "Other"'), "utf-8")

    errors = "\n".join(validate(folder).errors)
    assert "missing property platform" in errors
    assert "invalid publication_status" in errors
    assert "does not match filename" in errors


def test_validate_accepts_unquoted_front_matter_values(folder: Path) -> None:
    md = folder / "Title.md"
    md.write_text(md.read_text("utf-8").replace('"Title"', "Title", 1), "utf-8")
    assert validate(folder).errors == []


def test_validate_requires_url_for_published_only(folder: Path) -> None:
    md = folder / "Title.md"
    lines = [
        line
        for line in md.read_text("utf-8").split("\n")
        if not line.startswith("publication_url")
    ]
    md.write_text("\n".join(lines), "utf-8")
    assert "needs publication_url" in "\n".join(validate(folder).errors)


def test_validate_reports_missing_image_and_wrong_folder(folder: Path) -> None:
    (folder / "Title-img" / "a.png").unlink()
    md = folder / "Title.md"
    md.write_text(md.read_text("utf-8") + "\n![](elsewhere/b.png)\n", "utf-8")

    errors = "\n".join(validate(folder).errors)
    assert "missing image file: Title-img/a.png" in errors
    assert "image outside Title-img/: elsewhere/b.png" in errors


def test_validate_downgrades_image_problems_when_manifest_allows_lossy(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export([make_item(body='<p><img src="https://e.com/x.png"></p>')])
    convert(export, tmp_path / "out", allow_lossy=True)

    result = validate(tmp_path / "out" / "acct-x")
    assert result.errors == []
    assert any("unresolved image URL" in w for w in result.warnings)


def test_validate_reports_sidecar_problems(folder: Path) -> None:
    _edit_json(folder / "Title.note.json", lambda d: d.update(body_sha256="0" * 64))
    assert "does not match body_sha256" in "\n".join(validate(folder).errors)

    (folder / "Title.note.json").write_text("{}", "utf-8")
    assert "unexpected structure" in "\n".join(validate(folder).errors)

    (folder / "Title.note.json").unlink()
    assert "Title.note.json: file is missing" in validate(folder).errors


def test_validate_reports_manifest_drift(folder: Path) -> None:
    def change(data: dict) -> None:  # type: ignore[type-arg]
        data["articles"][0]["body_sha256"] = "1" * 64
        data["articles"].append({"guid": "gone", "title": "G", "body_sha256": "2" * 64})

    _edit_json(folder / MANIFEST_NAME, change)
    errors = "\n".join(validate(folder).errors)
    assert "body hash of Title differs from sidecar" in errors
    assert "article G not found on disk" in errors
    assert "overall body_sha256" in errors


def test_validate_reports_missing_manifest(folder: Path) -> None:
    (folder / MANIFEST_NAME).unlink()
    assert "manifest.json: file is missing" in validate(folder).errors


def test_validate_warns_when_image_totals_are_stale(folder: Path) -> None:
    (folder / "Title-img" / "b.png").write_bytes(b"more")
    result = validate(folder)
    assert result.errors == []
    assert "manifest: image_count is stale" in result.warnings
    assert "manifest: total_size is stale" in result.warnings


def test_validate_rejects_duplicate_guid_and_empty_folder(
    folder: Path, tmp_path: Path
) -> None:
    text = (folder / "Title.md").read_text("utf-8")
    (folder / "Copy.md").write_text(text.replace('"Title"', '"Copy"', 1), "utf-8")
    (folder / "Copy.note.json").write_text(
        (folder / "Title.note.json").read_text("utf-8"), "utf-8"
    )
    assert "duplicate platform_post_id n1" in "\n".join(validate(folder).errors)

    empty = tmp_path / "empty"
    empty.mkdir()
    assert "no manuscripts" in "\n".join(validate(empty).errors)


def test_image_refs_handles_markdown_html_encoding_and_code() -> None:
    body = (
        "![a](x/a.png) ![b](<x/b c.png>) ![c](x/d%20e.png)\n"
        '<img src="x/f.png" alt="">\n'
        "```\n![no](x/no.png)\n```\n"
    )
    assert image_refs(body) == ["x/a.png", "x/b c.png", "x/d e.png", "x/f.png"]


def test_main_exit_codes(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(folder)]) == 0
    assert capsys.readouterr().out == "ok\n"

    (folder / MANIFEST_NAME).unlink()
    assert main([str(folder)]) == 1
    assert "error: manifest.json" in capsys.readouterr().err


def test_validate_downgrades_duplicate_guid_when_lossy_is_allowed(folder: Path) -> None:
    text = (folder / "Title.md").read_text("utf-8")
    (folder / "Copy.md").write_text(text.replace('"Title"', '"Copy"', 1), "utf-8")
    (folder / "Copy.note.json").write_text(
        (folder / "Title.note.json").read_text("utf-8"), "utf-8"
    )
    (folder / "Copy-img").mkdir()
    (folder / "Copy-img" / "a.png").write_bytes(b"PNG")
    md = folder / "Copy.md"
    md.write_text(md.read_text("utf-8").replace("Title-img/", "Copy-img/"), "utf-8")

    assert "duplicate platform_post_id" in "\n".join(validate(folder).errors)
    result = validate(folder, allow_lossy=True)
    assert not any("duplicate" in e for e in result.errors)
    assert any("duplicate platform_post_id n1" in w for w in result.warnings)
