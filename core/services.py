from django.conf import settings
from django.db import IntegrityError, transaction

from core.models import ShortURL
from core.shortcodes import ShortCodeExhausted, generate, is_valid


def shorten(url: str) -> ShortURL:
    for _ in range(settings.TRIMLY_CODE_GEN_MAX_RETRIES):
        code = generate(settings.TRIMLY_CODE_LENGTH)
        try:
            with transaction.atomic():
                short_url = ShortURL.objects.create(code=code, long_url=url)
        except IntegrityError:
            continue
        else:
            break
    else:
        raise ShortCodeExhausted

    return short_url


def resolve(code: str) -> str:
    if not is_valid(code, settings.TRIMLY_CODE_LENGTH):
        raise ValueError('Provided code is not valid.')

    return ShortURL.objects.get(code=code).long_url
