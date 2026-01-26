"""
ASGI config for exam_bot_admin project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""
import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "exam_bot_admin.settings")
django.setup()

# Import bot setup after Django is initialized
from exam_bot_admin.webhook import bot, dp

application = get_asgi_application()
