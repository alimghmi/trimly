from django.contrib import admin

from core.models import ShortURL
from core.services import shorten


@admin.register(ShortURL)
class ShortURLAdmin(admin.ModelAdmin):
    list_display = ('code', 'long_url', 'created_at')
    search_fields = ('code', 'long_url')

    def save_model(self, request, obj, form, change) -> None:
        if change:
            return super().save_model(request, obj, form, change)
        else:
            created = shorten(obj.long_url)
            obj.code = created.code
            obj.created_at = created.created_at
