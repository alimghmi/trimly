import logging
import sys
import time
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger('trimly.request')


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = str(uuid4())
        started = time.perf_counter()

        try:
            response = self.get_response(request)
        except Exception:
            self._log_request(
                request,
                request_id=request_id,
                status=500,
                started=started,
                exception_info=sys.exc_info(),
            )
            raise

        response['X-Request-ID'] = request_id
        exception_info = getattr(request, '_trimly_exception_info', None)
        self._log_request(
            request,
            request_id=request_id,
            status=response.status_code,
            started=started,
            exception_info=exception_info if response.status_code >= 500 else None,
        )
        return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> None:
        request._trimly_exception_info = sys.exc_info()

    @staticmethod
    def _log_request(
        request: HttpRequest,
        *,
        request_id: str,
        status: int,
        started: float,
        exception_info=None,
    ) -> None:
        if request.path == '/api/health':
            level = logging.DEBUG
        elif status >= 500:
            level = logging.ERROR
        elif status >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO

        extra = {
            'event': 'request_completed' if exception_info is None else 'request_failed',
            'request_id': request_id,
            'method': request.method,
            'path': request.path,
            'status': status,
            'duration_ms': round((time.perf_counter() - started) * 1000, 2),
            'remote_addr': request.META.get('REMOTE_ADDR'),
        }
        logger.log(
            level,
            'Request completed.' if exception_info is None else 'Request failed.',
            extra=extra,
            exc_info=exception_info,
        )
