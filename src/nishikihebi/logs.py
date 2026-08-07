import json
import logging
from datetime import UTC, datetime
from pathlib import Path


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
    console_handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(file_handler)

    return path
