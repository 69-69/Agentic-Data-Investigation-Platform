import contextvars
import json
import logging
from datetime import datetime, timezone

correlation_id = contextvars.ContextVar("correlation_id", default="")
execution_deadline = contextvars.ContextVar("execution_deadline", default=float("inf"))
logger = logging.getLogger("investigation.agent")


def event(name: str, **fields):
    # Callers supply bounded safe metadata, never credentials or exception bodies.
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "agent-service",
                "level": "INFO",
                "event": name,
                "correlationId": correlation_id.get(),
                **fields,
            },
            default=str,
        )
    )


def configure():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
