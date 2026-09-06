from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.throttling import AnonRateThrottle

from core.exceptions import ShortCodeAllocationFailed
from core.models import ShortURL
from core.services import shorten


class ShortenViewTests(TestCase):
    def test_valid_url_returns_created_with_full_body(self):
        response = self.client.post(
            reverse('shorten'),
            data={'url': 'https://example.com/some/path'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(len(body['code']), 5)
        self.assertEqual(body['long_url'], 'https://example.com/some/path')
        self.assertTrue(body['short_url'].endswith(body['code']))
        self.assertTrue(ShortURL.objects.filter(code=body['code']).exists())

    def test_missing_url_returns_bad_request(self):
        response = self.client.post(reverse('shorten'), data={}, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('url', response.json())

    def test_disallowed_scheme_returns_bad_request(self):
        response = self.client.post(
            reverse('shorten'),
            data={'url': 'ftp://example.com/file'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('url', response.json())

    @mock.patch('core.views.shorten', side_effect=ShortCodeAllocationFailed)
    def test_allocation_failure_returns_service_unavailable(self, shorten):
        response = self.client.post(
            reverse('shorten'),
            data={'url': 'https://example.com/no-room-left'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 503)
        shorten.assert_called_once_with('https://example.com/no-room-left')

    @mock.patch('core.views.shorten', side_effect=RuntimeError('unexpected failure'))
    def test_unhandled_error_has_request_id_and_structured_exception_log(self, shorten):
        self.client.raise_request_exception = False

        with self.assertLogs('trimly.request', level='ERROR') as captured:
            response = self.client.post(
                reverse('shorten'),
                data={'url': 'https://example.com/private-target'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn('X-Request-ID', response)
        self.assertEqual(captured.records[0].event, 'request_failed')
        self.assertIsNotNone(captured.records[0].exc_info)
        self.assertNotIn('private-target', captured.output[0])


class ShortenViewThrottleTests(TestCase):
    def setUp(self):
        # LocMemCache (DRF's throttle store) persists process-wide across the
        # whole test run and Django's TestCase does not clear it between
        # tests - without this, request counts left over from another test
        # could make this test pass or fail for the wrong reason.
        cache.clear()

    def test_exceeding_write_rate_returns_too_many_requests(self):
        # AnonRateThrottle.THROTTLE_RATES is bound to the DRF settings dict at
        # class-body evaluation (import time), so overriding
        # settings.REST_FRAMEWORK at test time does not change it - the class
        # attribute has to be patched directly to take effect here.
        with mock.patch.object(AnonRateThrottle, 'THROTTLE_RATES', {'anon': '2/min'}):
            for _ in range(2):
                response = self.client.post(
                    reverse('shorten'),
                    data={'url': 'https://example.com/within-limit'},
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 201)

            response = self.client.post(
                reverse('shorten'),
                data={'url': 'https://example.com/over-limit'},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 429)


class RedirectViewTests(TestCase):
    def test_round_trip_shorten_then_follow_redirects_to_original_url(self):
        long_url = 'https://example.com/pair-programmed-feature'
        created = shorten(long_url)

        response = self.client.get(reverse('redirect', args=[created.code]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, long_url)

    def test_unknown_code_returns_not_found(self):
        response = self.client.get(reverse('redirect', args=['zzzzz']))

        self.assertEqual(response.status_code, 404)

    def test_malformed_code_returns_not_found_not_server_error(self):
        response = self.client.get(reverse('redirect', args=['toolongcode']))

        self.assertEqual(response.status_code, 404)
