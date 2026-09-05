import logging

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from core.exceptions import ShortCodeAllocationFailed
from core.models import ShortURL
from core.shortcodes import generate, is_valid

_NOT_FOUND = '__trimly_not_found__'
logger = logging.getLogger(__name__)


def _cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:
        logger.warning('Cache read failed. Falling back to the database.', exc_info=True)
        return None


def _cache_set(key: str, value: str, timeout: int) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        logger.warning('Cache write failed. Continuing without caching.', exc_info=True)


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
        raise ShortCodeAllocationFailed

    return short_url


def resolve(code: str) -> str:
    if not is_valid(code, settings.TRIMLY_CODE_LENGTH):
        raise ValueError('Provided code is not valid.')

    cached = _cache_get(code)
    if cached == _NOT_FOUND:
        raise ShortURL.DoesNotExist
    elif cached is not None:
        return cached

    try:
        long_url = ShortURL.objects.values_list('long_url', flat=True).get(code=code)
    except ShortURL.DoesNotExist:
        _cache_set(code, _NOT_FOUND, timeout=settings.TRIMLY_NOT_FOUND_CACHE_TTL)
        raise

    _cache_set(code, long_url, timeout=settings.TRIMLY_CACHE_TTL)
    return long_url
