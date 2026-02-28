"""
URL configuration for exam_bot_admin project.
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from admin_panel.views import webhook_view, RegAppView, reg_app_submit_view, reg_app_user_info_view, TestAppView, test_app_questions_view, test_app_submit_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("webhook/", webhook_view, name="webhook"),
    path("reg-app/submit/", reg_app_submit_view, name="reg_app_submit"),
    path("reg-app/user-info/", reg_app_user_info_view, name="reg_app_user_info"),
    path("reg-app/", RegAppView.as_view(), name="reg_app"),
    path("test-app/", TestAppView.as_view(), name="test_app"),
    path("test-app/questions/", test_app_questions_view, name="test_app_questions"),
    path("test-app/submit/", test_app_submit_view, name="test_app_submit"),
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="home"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
