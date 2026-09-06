import json
import logging
from datetime import UTC, datetime

STRUCTURED_FIELDS = (
    'event',
    'request_id',
    'method',
    'path',
    'status',
    'duration_ms',
    'remote_addr',
    'cache_operation',
    'fallback',
    'exception_type',
    'attempts',
    'code_length',
)


def select_log_format(*, debug: bool, configured: str | None) -> str:
    log_format = configured.strip().lower() if configured else ('text' if debug else 'json')
    if log_format not in {'json', 'text'}:
        raise ValueError('DJANGO_LOG_FORMAT must be either text or json.')
    return log_format


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.fromtimestamp(record.created, tz=UTC).isoformat(
                timespec='milliseconds'
            ),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for field in STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        context = ' '.join(
            f'{field}={getattr(record, field)!r}'
            for field in STRUCTURED_FIELDS
            if hasattr(record, field)
        )
        return f'{message} {context}' if context else message
