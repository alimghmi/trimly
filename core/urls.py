from django.urls import path

from core import views

urlpatterns = [
    path('api/health', views.HealthCheck.as_view(), name='health-check'),
    path('api/shorten', views.ShortenView.as_view(), name='shorten'),
    path('<str:code>', views.redirect_view, name='redirect'),
]
