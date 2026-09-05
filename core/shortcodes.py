import secrets

ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
ALPHABET_SET = set(ALPHABET)


class ShortCodeExhausted(RuntimeError):
    """Raised when no free code was found within the retry budget."""


def generate(length: int) -> str:
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid(code: str, length: int) -> bool:
    return len(code) == length and all(c in ALPHABET_SET for c in code)
