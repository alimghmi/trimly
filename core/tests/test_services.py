from django.core.cache import cache
from django.test import TestCase, override_settings

from core.models import ShortURL
from core.services import resolve, shorten
from core.shortcodes import ShortCodeExhausted


class ShortenTests(TestCase):
    def test_creates_a_row_with_a_five_character_code(self):
        result = shorten('https://example.com')
        self.assertEqual(len(result.code), 5)
        self.assertEqual(result.long_url, 'https://example.com')
        self.assertTrue(ShortURL.objects.filter(code=result.code).exists())

    @override_settings(TRIMLY_CODE_LENGTH=1, TRIMLY_CODE_GEN_MAX_RETRIES=1000)
    def test_retries_on_collision_and_still_succeeds(self):
        for i in range(61):
            shorten(f'https://example.com/{i}')
        self.assertEqual(ShortURL.objects.count(), 61)

        result = shorten('https://example.com/one-more')

        self.assertEqual(ShortURL.objects.count(), 62)
        self.assertEqual(len(result.code), 1)

    @override_settings(TRIMLY_CODE_LENGTH=1, TRIMLY_CODE_GEN_MAX_RETRIES=1000)
    def test_raises_when_keyspace_is_completely_full(self):
        for i in range(62):
            shorten(f'https://example.com/{i}')
        self.assertEqual(ShortURL.objects.count(), 62)

        with self.assertRaises(ShortCodeExhausted):
            shorten('https://example.com/no-room-left')


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
