from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import ShortURL


class ShortURLAdminAddTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='password123'
        )
        self.client.force_login(self.admin_user)

    def test_add_generates_a_five_character_code(self):
        response = self.client.post(
            reverse('admin:core_shorturl_add'),
            {'long_url': 'https://example.com/via-admin', '_save': 'Save'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ShortURL.objects.count(), 1)
        created = ShortURL.objects.get()
        self.assertEqual(len(created.code), 5)
        self.assertEqual(created.long_url, 'https://example.com/via-admin')

    def test_two_sequential_adds_do_not_collide(self):
        self.client.post(
            reverse('admin:core_shorturl_add'),
            {'long_url': 'https://example.com/first', '_save': 'Save'},
        )
        self.client.post(
            reverse('admin:core_shorturl_add'),
            {'long_url': 'https://example.com/second', '_save': 'Save'},
        )

        self.assertEqual(ShortURL.objects.count(), 2)
        codes = set(ShortURL.objects.values_list('code', flat=True))
        self.assertEqual(len(codes), 2)
