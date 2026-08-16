import json
import logging
from datetime import UTC, datetime

import pytest

from nishikihebi.logs import configure_logging, get_logger


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


def test_get_logger_debug_writes_json_lines_with_fields(tmp_path):
    path = configure_logging(tmp_path)
    log = get_logger("nishikihebi.foo")

    log.debug("evaluated pull request", foo="bar")

    record = json.loads(path.read_text().strip())
    assert record["level"] == "DEBUG"
    assert record["logger"] == "nishikihebi.foo"
    assert record["message"] == "evaluated pull request"
    assert record["foo"] == "bar"


@pytest.mark.parametrize(
    ("method", "level_name"),
    [
        ("debug", "DEBUG"),
        ("info", "INFO"),
        ("warning", "WARNING"),
        ("error", "ERROR"),
    ],
)
def test_get_logger_methods_map_to_correct_level(tmp_path, method, level_name):
    path = configure_logging(tmp_path)
    log = get_logger("nishikihebi")

    getattr(log, method)("message", key="value")

    record = json.loads(path.read_text().strip())
    assert record["level"] == level_name
    assert record["key"] == "value"


def test_get_logger_call_with_no_fields_produces_valid_record(tmp_path):
    path = configure_logging(tmp_path)
    log = get_logger("nishikihebi")

    log.info("no fields here")

    record = json.loads(path.read_text().strip())
    assert record["level"] == "INFO"
    assert record["logger"] == "nishikihebi"
    assert record["message"] == "no fields here"
    assert "time" in record


def test_get_logger_record_equivalent_to_raw_extra_call(tmp_path):
    path = configure_logging(tmp_path)
    log = get_logger("nishikihebi")

    log.info("hello", foo="bar")
    wrapped_record = json.loads(path.read_text().strip())

    path = configure_logging(tmp_path)
    raw_logger = logging.getLogger("nishikihebi")

    raw_logger.info("hello", extra={"context": {"foo": "bar"}})
    raw_record = json.loads(path.read_text().strip().splitlines()[-1])

    del wrapped_record["time"]
    del raw_record["time"]
    assert wrapped_record == raw_record
