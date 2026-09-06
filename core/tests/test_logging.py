import json
import logging
import sys

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from config.logging import JsonFormatter, select_log_format
from core.middleware import RequestLoggingMiddleware


class LogFormatTests(SimpleTestCase):
    def test_default_format_is_text_in_development_and_json_in_production(self):
        self.assertEqual(select_log_format(debug=True, configured=None), 'text')
        self.assertEqual(select_log_format(debug=False, configured=None), 'json')

    def test_explicit_format_overrides_default(self):
        self.assertEqual(select_log_format(debug=True, configured='JSON'), 'json')
        self.assertEqual(select_log_format(debug=False, configured=' text '), 'text')

    def test_invalid_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'either text or json'):
            select_log_format(debug=True, configured='xml')

    def test_json_formatter_includes_context_and_exception(self):
        logger = logging.getLogger('trimly.test')
        try:
            raise ValueError('example failure')
        except ValueError:
            record = logger.makeRecord(
                logger.name,
                logging.ERROR,
                __file__,
                1,
                'Request failed.',
                (),
                sys.exc_info(),
                extra={
                    'event': 'request_failed',
                    'request_id': 'request-id',
                    'status': 500,
                },
            )

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload['level'], 'ERROR')
        self.assertEqual(payload['logger'], 'trimly.test')
        self.assertEqual(payload['message'], 'Request failed.')
        self.assertEqual(payload['event'], 'request_failed')
        self.assertEqual(payload['request_id'], 'request-id')
        self.assertEqual(payload['status'], 500)
        self.assertIn('ValueError: example failure', payload['exception'])
        self.assertIn('timestamp', payload)


class RequestLoggingMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_response_has_server_generated_request_id_and_safe_context(self):
        target_url = 'https://private.example/sensitive-path'
        request = self.factory.post(
            '/api/shorten?tracking=secret',
            data=json.dumps({'url': target_url}),
            content_type='application/json',
            HTTP_X_REQUEST_ID='client-controlled-id',
            HTTP_X_FORWARDED_FOR='203.0.113.10',
            REMOTE_ADDR='127.0.0.1',
        )
        middleware = RequestLoggingMiddleware(lambda request: HttpResponse(status=201))

        with self.assertLogs('trimly.request', level='INFO') as captured:
            response = middleware(request)

        record = captured.records[0]
        self.assertEqual(response['X-Request-ID'], record.request_id)
        self.assertNotEqual(record.request_id, 'client-controlled-id')
        self.assertEqual(record.method, 'POST')
        self.assertEqual(record.path, '/api/shorten')
        self.assertEqual(record.status, 201)
        self.assertEqual(record.remote_addr, '127.0.0.1')
        self.assertNotIn(target_url, JsonFormatter().format(record))
        self.assertNotIn('tracking=secret', JsonFormatter().format(record))
        self.assertNotIn('203.0.113.10', JsonFormatter().format(record))

    def test_response_status_controls_log_level(self):
        cases = (
            (200, logging.INFO),
            (404, logging.WARNING),
            (429, logging.WARNING),
            (500, logging.ERROR),
        )

        for status, expected_level in cases:
            with self.subTest(status=status):
                middleware = RequestLoggingMiddleware(
                    lambda request, response_status=status: HttpResponse(status=response_status)
                )
                request = self.factory.get('/example')
                with self.assertLogs('trimly.request', level='INFO') as captured:
                    response = middleware(request)

                self.assertEqual(response.status_code, status)
                self.assertEqual(captured.records[0].levelno, expected_level)
                self.assertIn('X-Request-ID', response)

    def test_health_check_is_logged_at_debug(self):
        request = self.factory.get('/api/health')
        middleware = RequestLoggingMiddleware(lambda request: HttpResponse(status=200))

        with self.assertLogs('trimly.request', level='DEBUG') as captured:
            middleware(request)

        self.assertEqual(captured.records[0].levelno, logging.DEBUG)

    def test_uncaught_exception_is_logged_with_exception_context(self):
        def fail(request):
            raise RuntimeError('failure')

        request = self.factory.get('/broken')
        middleware = RequestLoggingMiddleware(fail)

        with (
            self.assertLogs('trimly.request', level='ERROR') as captured,
            self.assertRaisesRegex(RuntimeError, 'failure'),
        ):
            middleware(request)

        record = captured.records[0]
        self.assertEqual(record.event, 'request_failed')
        self.assertEqual(record.status, 500)
        self.assertIsNotNone(record.exc_info)
