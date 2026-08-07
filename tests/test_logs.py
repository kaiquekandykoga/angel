import json
import logging
from datetime import UTC, datetime

import pytest

from nishikihebi.logs import configure_logging


@pytest.fixture(autouse=True)
def _reset_handlers():
    yield
    logger = logging.getLogger("nishikihebi")
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)


def test_configure_logging_creates_directory_and_returns_timestamped_path(tmp_path):
    directory = tmp_path / "log"
    timestamp = datetime(2026, 8, 7, 12, 30, 45, tzinfo=UTC)

    path = configure_logging(directory, timestamp=timestamp)

    assert directory.is_dir()
    assert path == directory / "nishikihebi-20260807T123045Z.jsonl"


def test_configure_logging_writes_json_lines_with_context(tmp_path):
    path = configure_logging(tmp_path)
    logger = logging.getLogger("nishikihebi")

    logger.info("hello", extra={"context": {"foo": "bar"}})

    line = path.read_text().strip()
    record = json.loads(line)
    assert record["level"] == "INFO"
    assert record["logger"] == "nishikihebi"
    assert record["message"] == "hello"
    assert record["foo"] == "bar"
    assert "time" in record


def test_configure_logging_sets_console_handler_to_info_and_file_handler_to_debug(
    tmp_path,
):
    configure_logging(tmp_path)
    logger = logging.getLogger("nishikihebi")

    file_handler = next(
        h for h in logger.handlers if isinstance(h, logging.FileHandler)
    )
    console_handler = next(
        h for h in logger.handlers if not isinstance(h, logging.FileHandler)
    )

    assert console_handler.level == logging.INFO
    assert file_handler.level == logging.DEBUG


def test_configure_logging_twice_does_not_duplicate_handlers(tmp_path):
    configure_logging(tmp_path)
    configure_logging(tmp_path)
    logger = logging.getLogger("nishikihebi")

    assert len(logger.handlers) == 2
