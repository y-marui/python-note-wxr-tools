import re
from collections.abc import Callable
from pathlib import Path

import pytest

from note_wxr_tools.into import merge_front_matter
from note_wxr_tools.to_md import ConversionError, convert, main
from tests.factory import REALISTIC_ASSETS, realistic_items

MakeExport = Callable[..., Path]


@pytest.fixture
def export(make_export: MakeExport) -> Path:
    return make_export(realistic_items(), REALISTIC_ASSETS)


def _snapshot(directory: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(directory.rglob("*")) if p.is_file()}


def _hand_imported(export: Path, tmp_path: Path) -> Path:
    """A posts directory like a hand import: no block attributes, a note added."""
    convert(export, tmp_path / "generated")
    posts = tmp_path / "posts"
    folder = posts / "acct-x"
    folder.mkdir(parents=True)
    generated = tmp_path / "generated" / "acct-x"
    for md in generated.glob("*.md"):
        text = re.sub(r' (?:name|id)="[^"]*"', "", md.read_text("utf-8"))
        text = text.replace("---\n\n", 'editorial_note: "by hand"\n---\n\n', 1)
        (folder / md.name).write_text(text, "utf-8")
    for source in [*generated.glob("*.note.json"), *generated.glob("*-img")]:
        if source.is_dir():
            (folder / source.name).mkdir()
            for image in source.iterdir():
                (folder / source.name / image.name).write_bytes(image.read_bytes())
        else:
            (folder / source.name).write_bytes(source.read_bytes())
    return posts


def test_into_writes_new_articles_without_manifest_or_channel(
    export: Path, tmp_path: Path
) -> None:
    posts = tmp_path / "posts"
    posts.mkdir()
    summary = convert(export, into_dir=posts).into

    assert summary is not None
    assert sorted(summary.created) == ["Draft", "Published"]
    folder = posts / "acct-x"
    assert (folder / "Published.md").exists()
    assert (folder / "Published.note.json").exists()
    assert any(folder.glob("*-img/*"))
    assert not (folder / "manifest.json").exists()
    assert not (folder / ".note-channel.json").exists()


def test_into_is_idempotent(export: Path, tmp_path: Path) -> None:
    posts = tmp_path / "posts"
    posts.mkdir()
    convert(export, into_dir=posts)
    before = _snapshot(posts)

    summary = convert(export, into_dir=posts).into
    assert summary is not None
    assert (summary.created, summary.overwritten, summary.unchanged) == ([], [], 2)
    assert summary.pending == []
    assert _snapshot(posts) == before


def test_into_skips_hand_imported_copies(export: Path, tmp_path: Path) -> None:
    posts = _hand_imported(export, tmp_path)
    before = _snapshot(posts)

    summary = convert(export, into_dir=posts).into
    assert summary is not None
    assert (summary.created, summary.unchanged, summary.pending) == ([], 2, [])
    assert _snapshot(posts) == before


def test_into_reports_differences_and_writes_nothing_without_force(
    export: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    posts = _hand_imported(export, tmp_path)
    draft = posts / "acct-x" / "Draft.md"
    draft.write_text(draft.read_text("utf-8").replace("Draft text", "Edited"), "utf-8")
    before = _snapshot(posts)

    assert main([str(export), "--into", str(posts)]) == 1
    out = capsys.readouterr().out
    assert "Draft" in out and "Edited" in out and "--force" in out
    assert _snapshot(posts) == before


def test_into_force_overwrites_and_keeps_extra_properties(
    export: Path, tmp_path: Path
) -> None:
    posts = _hand_imported(export, tmp_path)
    draft = posts / "acct-x" / "Draft.md"
    text = draft.read_text("utf-8").replace("Draft text", "Edited")
    text = text.replace(
        'editorial_note: "by hand"', "editorial_note: |\n  line 1\n  line 2"
    )
    draft.write_text(text, "utf-8")

    summary = convert(export, into_dir=posts, force=True).into
    assert summary is not None
    assert summary.overwritten == ["Draft"]
    result = draft.read_text("utf-8")
    assert "Edited" not in result and "Draft text" in result
    assert "editorial_note: |\n  line 1\n  line 2\n---" in result
    assert 'origin: "note.com export"' in result


def test_into_never_deletes_files_only_in_posts(export: Path, tmp_path: Path) -> None:
    posts = _hand_imported(export, tmp_path)
    keep = posts / "acct-x" / "Mine.md"
    keep.write_text('---\ntitle: "Mine"\n---\n\nbody\n', "utf-8")
    convert(export, into_dir=posts, force=True)
    assert keep.exists()


def test_into_rejects_new_article_that_would_overwrite_another_file(
    export: Path, tmp_path: Path
) -> None:
    posts = tmp_path / "posts"
    (posts / "acct-x").mkdir(parents=True)
    (posts / "acct-x" / "Draft.md").write_text("unrelated\n", "utf-8")
    with pytest.raises(ConversionError, match="not the manuscript for"):
        convert(export, into_dir=posts, force=True)
    assert (posts / "acct-x" / "Draft.md").read_text("utf-8") == "unrelated\n"
    assert not (posts / "acct-x" / "Published.md").exists()


def test_into_needs_a_directory_and_excludes_other_modes(
    export: Path, tmp_path: Path
) -> None:
    with pytest.raises(ConversionError, match="not a directory"):
        convert(export, into_dir=tmp_path / "missing")
    with pytest.raises(SystemExit):
        main([str(export), "--into", str(tmp_path), "--out", str(tmp_path / "o")])
    with pytest.raises(SystemExit):
        main([str(export), "--into", str(tmp_path), "--against", str(tmp_path)])


def test_merge_front_matter_keeps_unknown_entries_verbatim() -> None:
    existing = (
        '---\ntitle: "Old"\neditorial_note: |\n  a\n  b\ntags:\n  - x\n'
        'platform: "note"\n---\n\nold body\n'
    )
    generated = '---\ntitle: "New"\nplatform: "note"\n---\n\nnew body\n'
    assert merge_front_matter(existing, generated) == (
        '---\ntitle: "New"\nplatform: "note"\neditorial_note: |\n  a\n  b\n'
        "tags:\n  - x\n---\n\nnew body\n"
    )
