from django.test import SimpleTestCase

from core.serializers import ShortenRequestSerializer


class ShortenRequestSerializerTests(SimpleTestCase):
    def test_accepts_http_and_https(self):
        for url in ['http://example.com', 'https://example.com/path?q=1']:
            serializer = ShortenRequestSerializer(data={'url': url})
            self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_rejects_missing_url(self):
        serializer = ShortenRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)

    def test_rejects_disallowed_scheme(self):
        serializer = ShortenRequestSerializer(data={'url': 'ftp://example.com/file'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)

    def test_rejects_malformed_url(self):
        serializer = ShortenRequestSerializer(data={'url': 'not a url'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('url', serializer.errors)
