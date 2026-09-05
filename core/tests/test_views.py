from django.test import TestCase
from django.urls import reverse

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
