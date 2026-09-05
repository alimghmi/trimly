from django.test import SimpleTestCase

from core.shortcodes import ALPHABET, generate, is_valid


class GenerateTests(SimpleTestCase):
    def test_generate_returns_requested_length(self):
        code = generate(5)
        self.assertEqual(len(code), 5)

    def test_generate_uses_only_alphabet_symbols(self):
        code = generate(5)
        self.assertTrue(all(c in ALPHABET for c in code))


class IsValidTests(SimpleTestCase):
    def test_accepts_code_of_correct_length_and_alphabet(self):
        self.assertTrue(is_valid(generate(5), length=5))

    def test_rejects_wrong_length(self):
        self.assertFalse(is_valid('abc', length=5))
        self.assertFalse(is_valid('abcdef', length=5))

    def test_rejects_symbols_outside_alphabet(self):
        self.assertFalse(is_valid('ab-de', length=5))
        self.assertFalse(is_valid('ab.de', length=5))

    def test_rejects_empty_string(self):
        self.assertFalse(is_valid('', length=5))
