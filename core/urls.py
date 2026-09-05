from django.urls import path

from core import views

urlpatterns = [
    path('api/health', views.health_check, name='health-check'),
]
