from django.db import models


class ShortURL(models.Model):
    code = models.CharField(primary_key=True, max_length=5, editable=False)
    long_url = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Short URL'
        verbose_name_plural = 'Short URLs'
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f'{self.code} -> {self.long_url}'
