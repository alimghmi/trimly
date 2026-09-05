from urllib.parse import urlparse

from django.conf import settings
from rest_framework import serializers


class ShortenRequestSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)

    def validate_url(self, value: str):
        parsed_url = urlparse(value)
        if parsed_url.scheme.lower() not in settings.TRIMLY_ALLOWED_SCHEMES:
            raise serializers.ValidationError(
                f'URL scheme must be {", ".join(s for s in settings.TRIMLY_ALLOWED_SCHEMES)}'
            )

        return value
