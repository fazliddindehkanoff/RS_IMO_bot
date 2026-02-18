"""
Django settings for exam_bot_admin project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-change-this-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = ["*",]
CSRF_COOKIE_SECURE = False
# Application definition
INSTALLED_APPS = [
    "unfold",  # django-unfold must be before django.contrib.admin
    "unfold.contrib.filters",  # Optional: filters
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "admin_panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "exam_bot_admin.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "exam_bot_admin.wsgi.application"

# Database - using the same SQLite database as the bot
# Ensure data directory exists
import dj_database_url

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{DATA_DIR}/exam_bot.db",
        conn_max_age=600,
    )
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django Unfold settings
UNFOLD = {
    "SITE_TITLE": "RS IMO Bot Admin",
    "SITE_HEADER": "RS IMO Bot Administration",
    "SITE_URL": "/",
    "SITE_ICON": None,
    "SITE_LOGO": None,
    "SITE_SYMBOL": "smart_toy",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "ENVIRONMENT": "exam_bot_admin.settings.environment_callback",
    "DASHBOARD_CALLBACK": "admin_panel.dashboard.dashboard_callback",
    "LOGIN": {
        "image": None,
        "redirect_after": None,
    },
    "STYLES": [],
    "SCRIPTS": [],
    "COLORS": {
        "primary": {
            "50": "239 246 255",
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "147 197 253",
            "400": "96 165 250",
            "500": "59 130 246",
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
            "950": "23 37 84",
        },
    },
    "SIDEBAR": {
        "show_search": False,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Grant Exam Bot",
                "separator": False,
                "items": [
                    {"title": "Bosh sahifa", "icon": "dashboard", "link": "/admin/"},
                    {"title": "Reyting", "icon": "leaderboard", "link": "/admin/admin_panel/studentrating/"},
                    {"title": "O'quvchilar", "icon": "school", "link": "/admin/admin_panel/student/"},
                    {"title": "O'qituvchilar", "icon": "badge", "link": "/admin/admin_panel/teacher/"},
                    {"title": "Ota-onalar", "icon": "family_restroom", "link": "/admin/admin_panel/parent/"},
                    {"title": "Testlar", "icon": "assignment", "link": "/admin/admin_panel/test/"},
                    {"title": "Savollar", "icon": "quiz", "link": "/admin/admin_panel/testquestion/"},
                    {"title": "Test topshirishlar", "icon": "assignment_turned_in", "link": "/admin/admin_panel/testattempt/"},
                    {"title": "Test javoblari", "icon": "fact_check", "link": "/admin/admin_panel/testanswer/"},
                    {"title": "Taklif Va Shikoyatlar", "icon": "feedback", "link": "/admin/admin_panel/feedback/"},
                    {"title": "Xabarnomalar", "icon": "send", "link": "/admin/admin_panel/broadcastmessage/"},
                    {"title": "Hamkorlar", "icon": "handshake", "link": "/admin/admin_panel/partner/"},
                    {"title": "Majburiy kanallar", "icon": "campaign", "link": "/admin/admin_panel/mandatorychannel/"},
                ],
            },
        ],
    },
}

def environment_callback(request):
    """Return environment name for django-unfold."""
    return ["Development"] if DEBUG else ["Production"]

# CSRF settings for webhook
# CSRF_TRUSTED_ORIGINS must include protocol (http:// or https://)
csrf_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "https://rs.nomean.uz")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins.split(",") if origin.strip()]

# Telegram Bot Settings
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://yourdomain.com/webhook")
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Registration Web App (Mini App) – must be HTTPS for Telegram. Set in .env as REG_WEBAPP_URL.
REG_WEBAPP_URL = os.getenv("REG_WEBAPP_URL", "").strip()
