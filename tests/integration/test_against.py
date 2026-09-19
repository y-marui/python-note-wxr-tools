import re
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.to_md import ConversionError, convert, main
from tests.factory import REALISTIC_ASSETS, make_item, realistic_items

MakeExport = Callable[..., Path]


@pytest.fixture
def export(make_export: MakeExport) -> Path:
    return make_export(realistic_items(), REALISTIC_ASSETS)


@pytest.fixture
def posts(export: Path, tmp_path: Path) -> Path:
    """A hand-imported copy: block name/id attributes dropped, a note added."""
    convert(export, tmp_path / "generated")
    posts = tmp_path / "posts" / "note" / "acct-x"
    posts.mkdir(parents=True)
    for md in (tmp_path / "generated" / "acct-x").glob("*.md"):
        text = re.sub(r' (?:name|id)="[^"]*"', "", md.read_text("utf-8"))
        text = text.replace("---\n\n", 'editorial_note: "hand written"\n---\n\n', 1)
        (posts / md.name).write_text(text, "utf-8")
    shutil_images = tmp_path / "generated" / "acct-x"
    for img in shutil_images.glob("*-img"):
        (posts / img.name).mkdir()
        for f in img.iterdir():
            (posts / img.name / f.name).write_bytes(f.read_bytes())
    return tmp_path / "posts"


def _snapshot(directory: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()}


def test_against_reports_no_difference_for_hand_imported_copies(
    export: Path, posts: Path
) -> None:
    before = _snapshot(posts)
    report = convert(export, against_dir=posts)

    comparison = report.comparison
    assert comparison is not None
    assert comparison.matched == 2
    assert comparison.differences == []
    assert (comparison.new_in_export, comparison.only_in_posts) == ([], [])
    assert _snapshot(posts) == before


def test_against_reports_body_and_property_differences(
    export: Path, posts: Path
) -> None:
    md = posts / "note" / "acct-x" / "Draft.md"
    text = md.read_text("utf-8")
    text = text.replace("Draft text", "Edited by hand").replace(
        'publication_status: "draft"', 'publication_status: "needs_update"'
    )
    md.write_text(text.replace('origin: "note.com export"\n', ""), "utf-8")
    before = _snapshot(posts)

    comparison = convert(export, against_dir=posts).comparison

    assert comparison is not None
    (difference,) = comparison.differences
    assert difference.title == "Draft"
    assert "publication_status: posts 'needs_update' / export 'draft'" in (
        difference.properties
    )
    assert any(
        line.startswith("origin: missing in posts") for line in difference.properties
    )
    assert "-Edited by hand" in "\n".join(difference.body)
    assert "+Draft text" in "\n".join(difference.body)
    assert _snapshot(posts) == before


def test_against_lists_new_and_only_in_posts_articles(
    make_export: MakeExport, posts: Path
) -> None:
    export = make_export(
        [*realistic_items(), make_item(guid="n3", title="Fresh")], REALISTIC_ASSETS
    )
    extra = posts / "note" / "acct-x" / "Old.md"
    extra.write_text(
        '---\ntitle: "Old"\nplatform_post_id: "gone"\n---\n\nbody\n', "utf-8"
    )

    comparison = convert(export, against_dir=posts).comparison

    assert comparison is not None
    assert comparison.new_in_export == ["Fresh (n3)"]
    assert len(comparison.only_in_posts) == 1
    assert comparison.only_in_posts[0].endswith("Old.md (gone)")

    other = posts / "note" / "other"
    other.mkdir()
    (other / "X.md").write_text(
        '---\ntitle: "X"\naccount: "someone-else"\nplatform_post_id: "x1"\n---\n\nb\n',
        "utf-8",
    )
    again = convert(export, against_dir=posts).comparison
    assert again is not None
    assert len(again.only_in_posts) == 1


def test_against_warns_about_duplicate_ids_and_skips_unrelated_files(
    export: Path, posts: Path
) -> None:
    folder = posts / "note" / "acct-x"
    (folder / "Copy.md").write_text((folder / "Draft.md").read_text("utf-8"), "utf-8")
    (folder / "README.md").write_text("# no front matter\n", "utf-8")

    comparison = convert(export, against_dir=posts).comparison

    assert comparison is not None
    assert any("duplicate platform_post_id n2" in w for w in comparison.warnings)


def test_against_tolerates_untitled_articles_and_rejects_bad_directories(
    make_export: MakeExport, tmp_path: Path
) -> None:
    export = make_export(
        [make_item(guid="n1", title=""), make_item(guid="n2", title="")]
    )
    empty = tmp_path / "posts"
    empty.mkdir()

    comparison = convert(export, against_dir=empty).comparison
    assert comparison is not None
    assert comparison.new_in_export == ["untitled-n1 (n1)", "untitled-n2 (n2)"]

    with pytest.raises(ConversionError, match="not a directory"):
        convert(export, against_dir=tmp_path / "missing")


def test_main_against_prints_report_and_writes_nothing(
    export: Path,
    posts: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    assert main([str(export), "--against", str(posts)]) == 0

    out = capsys.readouterr().out
    assert "matched 2 article(s): 2 identical, 0 with differences" in out
    assert list(workdir.iterdir()) == []


def test_main_requires_exactly_one_of_out_and_against(
    export: Path, posts: Path, tmp_path: Path
) -> None:
    for extra in ([], ["--out", str(tmp_path / "o"), "--against", str(posts)]):
        with pytest.raises(SystemExit) as error:
            main([str(export), *extra])
        assert error.value.code == 2
