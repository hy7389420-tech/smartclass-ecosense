import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        error_type = getattr(record, "error_type", None)
        if error_type:
            payload["error_type"] = error_type
        return json.dumps(payload)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        handlers=[logging.StreamHandler()],
        force=True,
    )
    logging.getLogger().handlers[0].setFormatter(JsonFormatter())
