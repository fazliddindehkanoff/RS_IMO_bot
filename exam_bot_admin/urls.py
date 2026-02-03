"""
URL configuration for exam_bot_admin project.
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from admin_panel.views import webhook_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook/", webhook_view, name="webhook"),
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="home"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
