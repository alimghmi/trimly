from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.exceptions import ShortCodeAllocationFailed
from core.models import ShortURL
from core.services import resolve, shorten
from core.shortcodes import ALPHABET


class ShortenTests(TestCase):
    def test_creates_a_row_with_a_five_character_code(self):
        result = shorten('https://example.com')
        self.assertEqual(len(result.code), 5)
        self.assertEqual(result.long_url, 'https://example.com')
        self.assertTrue(ShortURL.objects.filter(code=result.code).exists())

    @override_settings(TRIMLY_CODE_LENGTH=1, TRIMLY_CODE_GEN_MAX_RETRIES=2)
    @mock.patch('core.services.generate', side_effect=['0', 'Z'])
    def test_retries_on_collision_and_still_succeeds(self, generate):
        ShortURL.objects.bulk_create(
            ShortURL(code=code, long_url=f'https://example.com/{code}') for code in ALPHABET[:-1]
        )
        self.assertEqual(ShortURL.objects.count(), 61)

        result = shorten('https://example.com/one-more')

        self.assertEqual(ShortURL.objects.count(), 62)
        self.assertEqual(result.code, 'Z')
        self.assertEqual(generate.call_count, 2)

    @override_settings(TRIMLY_CODE_LENGTH=1, TRIMLY_CODE_GEN_MAX_RETRIES=3)
    @mock.patch('core.services.generate', return_value='0')
    def test_raises_after_retry_budget_when_keyspace_is_full(self, generate):
        ShortURL.objects.bulk_create(
            ShortURL(code=code, long_url=f'https://example.com/{code}') for code in ALPHABET
        )
        self.assertEqual(ShortURL.objects.count(), 62)

        with (
            self.assertLogs('core.services', level='ERROR') as captured,
            self.assertRaises(ShortCodeAllocationFailed),
        ):
            shorten('https://example.com/no-room-left')
        self.assertEqual(generate.call_count, 3)
        self.assertEqual(captured.records[0].event, 'short_code_allocation_exhausted')
        self.assertEqual(captured.records[0].attempts, 3)
        self.assertEqual(captured.records[0].code_length, 1)


class ResolveTests(TestCase):
    def test_resolve_return_correct_url(self):
        url = 'https://example.com'
        code = shorten(url).code
        self.assertEqual(resolve(code), url)

    def test_resolve_nonexistent_url_raise(self):
        with self.assertRaises(ShortURL.DoesNotExist):
            resolve('zzZzz')


class CacheBehaviorTests(TestCase):
    def setUp(self):
        # LocMemCache persists process-wide across the whole test run, and
        # Django's TestCase does not clear it between tests - without this,
        # a stale entry from an earlier test could mask a real bug here.
        cache.clear()

    def test_second_resolve_of_same_code_is_served_from_cache(self):
        code = shorten('https://example.com/cache-me').code

        with self.assertNumQueries(1):
            resolve(code)

        with self.assertNumQueries(0):
            resolve(code)

    def test_second_resolve_of_missing_code_is_served_from_negative_cache(self):
        with self.assertNumQueries(1), self.assertRaises(ShortURL.DoesNotExist):
            resolve('qqqqq')

        with self.assertNumQueries(0), self.assertRaises(ShortURL.DoesNotExist):
            resolve('qqqqq')

    def test_cache_failure_falls_back_to_database(self):
        url = 'https://example.com/cache-unavailable'
        code = shorten(url).code

        with (
            mock.patch('core.services.cache.get', side_effect=ConnectionError),
            mock.patch('core.services.cache.set', side_effect=ConnectionError),
            self.assertLogs('core.services', level='WARNING') as captured,
        ):
            self.assertEqual(resolve(code), url)
        self.assertEqual(len(captured.records), 2)
        self.assertEqual(captured.records[0].event, 'cache_operation_failed')
        self.assertEqual(captured.records[0].cache_operation, 'read')
        self.assertEqual(captured.records[0].fallback, 'database')
        self.assertEqual(captured.records[0].exception_type, 'ConnectionError')
        self.assertEqual(captured.records[1].cache_operation, 'write')

    def test_cache_write_failure_does_not_mask_missing_code(self):
        with (
            mock.patch('core.services.cache.set', side_effect=ConnectionError),
            self.assertLogs('core.services', level='WARNING'),
            self.assertRaises(ShortURL.DoesNotExist),
        ):
            resolve('qqqqq')
