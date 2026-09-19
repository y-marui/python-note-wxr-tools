.PHONY: install lint format type test test-realdata all update-charter

install:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run mypy src

test:
	uv run pytest

# Local only: needs NOTE_WXR_REALDATA_ZIP=/path/to/export.zip
test-realdata:
	uv run pytest -m realdata

all: lint type test

update-charter:
	curl -fsSL https://raw.githubusercontent.com/y-marui/dev-charter/main/scripts/install.sh | CHARTER_UPDATE_ONLY=1 bash
