from typing import ClassVar

from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ShortCodeExhausted
from core.models import ShortURL
from core.serializers import ShortenRequestSerializer
from core.services import resolve, shorten


class HealthCheck(APIView):
    throttle_classes: ClassVar = []

    def get(self, request):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class ShortenView(APIView):
    serializer_class = ShortenRequestSerializer

    def get_serializer(self, *args, **kwargs):
        return self.serializer_class(*args, **kwargs)

    def post(self, request):
        req_serializer = self.get_serializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        url = req_serializer.validated_data['url']  # type: ignore[index]

        try:
            short_url = shorten(url)
        except ShortCodeExhausted:
            return Response(
                {'detail': 'No short codes are available right now. Please try again shortly.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        short_url_dict = {
            'code': short_url.code,
            'long_url': short_url.long_url,
            'short_url': f'{settings.TRIMLY_BASE_URL}/{short_url.code}',
        }
        return Response(data=short_url_dict, status=status.HTTP_201_CREATED)


def redirect_view(request, code):
    try:
        long_url = resolve(code=code)
    except (ShortURL.DoesNotExist, ValueError):
        raise Http404 from None

    return redirect(long_url, permanent=False)
