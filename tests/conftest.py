from collections.abc import Callable
from pathlib import Path

import pytest

from tests.factory import write_export


@pytest.fixture
def make_export(tmp_path: Path) -> Callable[..., Path]:
    """Build a synthetic export ZIP from item XML strings and asset files."""

    def build(items: list[str], assets: dict[str, bytes] | None = None) -> Path:
        return write_export(tmp_path / "export.zip", items, assets)

    return build
