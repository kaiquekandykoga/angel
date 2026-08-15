import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

HERE = Path(__file__).parent
FIXTURES = HERE.parent / "fixtures"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.path is not None and item.path.is_relative_to(HERE):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def load_fixture() -> Callable[[str], Any]:
    def load(name: str) -> Any:
        path = FIXTURES / name
        if not path.is_file():
            raise FileNotFoundError(f"no recorded fixture at {path}")
        if path.suffix == ".json":
            return json.loads(path.read_text())
        return path.read_text()

    return load
