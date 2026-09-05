from django.contrib import admin

from core.models import ShortURL


@admin.register(ShortURL)
class ShortURLAdmin(admin.ModelAdmin):
    list_display = ("code", "long_url", "created_at")
    search_fields = ("code", "long_url")
