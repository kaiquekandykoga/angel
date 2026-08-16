import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from nishikihebi.console import BOLD, CYAN, DIM, RED, YELLOW, color_enabled, style

_LEVEL_CODES: dict[str, tuple[str, ...]] = {
    "DEBUG": (DIM,),
    "INFO": (CYAN,),
    "WARNING": (YELLOW,),
    "ERROR": (RED,),
    "CRITICAL": (BOLD, RED),
}


class ColorFormatter(logging.Formatter):
    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self.stream = stream

    def format(self, record: logging.LogRecord) -> str:
        levelname = f"{record.levelname:<7}"
        codes = _LEVEL_CODES.get(record.levelname, ())
        if codes and color_enabled(self.stream):
            levelname = style(levelname, *codes, stream=self.stream)
        return f"{levelname} {record.getMessage()}"


class JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **getattr(record, "context", {}),
        }
        return json.dumps(payload)


def configure_logging(
    directory: Path = Path("log"), timestamp: datetime | None = None
) -> Path:
    timestamp = timestamp or datetime.now(UTC)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"nishikihebi-{timestamp:%Y%m%dT%H%M%SZ}.jsonl"

    logger = logging.getLogger("nishikihebi")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColorFormatter(console_handler.stream))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(file_handler)

    return path


class ContextLogger:
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def debug(self, message: str, **fields: object) -> None:
        self.logger.debug(message, extra={"context": fields}, stacklevel=2)

    def info(self, message: str, **fields: object) -> None:
        self.logger.info(message, extra={"context": fields}, stacklevel=2)

    def warning(self, message: str, **fields: object) -> None:
        self.logger.warning(message, extra={"context": fields}, stacklevel=2)

    def error(self, message: str, **fields: object) -> None:
        self.logger.error(message, extra={"context": fields}, stacklevel=2)


def get_logger(name: str) -> ContextLogger:
    return ContextLogger(logging.getLogger(name))
