# Grant Exam Telegram Bot

Production-ready Telegram bot for conducting online grant exams for school students (grades 5–8) with automatic testing, monitoring, and certificate generation.

## Features

- **Student Registration**: Multi-step FSM registration with student, parent, teacher, and source information
- **Grade-Based Tests**: Tests for grades 5-8 with timed exam flow
- **Admin Panel**: Complete test management, assignment, and monitoring
- **Certificate Generation**: Automatic personalized PDF/JPG certificate generation
- **Monitoring & Analytics**: Status tracking, segmentation, and export capabilities
- **Duplicate Protection**: Prevents duplicate test assignments and certificates
- **Webhook Support**: Bot works with Django webhook endpoint
- **Django Admin**: Modern admin panel using django-unfold

## Tech Stack

- Python 3.10+
- Aiogram 3 (Telegram Bot Framework)
- SQLAlchemy Async ORM (SQLite for dev, ready for PostgreSQL/MongoDB)
- Pillow + ReportLab (Certificate generation)
- Django 5.0 (Admin panel)
- django-unfold (Modern admin interface)

## Architecture

Clean Architecture with clear separation:
- **Routers**: Telegram handlers organized by feature
- **Services**: Business logic layer
- **Repositories**: Database access layer
- **Models**: ORM models and Pydantic schemas
- **Utils**: Certificate rendering, scoring, timers
- **Django Admin**: Web-based admin panel

## Setup

### Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   - Copy `.env.example` to `.env` (or create it)
   - Set `BOT_TOKEN`, `ADMIN_IDS`, and other settings

3. **Initialize Django**:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Set up webhook** (for production):
   ```bash
   python manage.py setup_webhook --url https://yourdomain.com/webhook
   ```

5. **Run Django server**:
   ```bash
   python manage.py runserver
   ```

### Development Mode (Polling)

If you want to use polling instead of webhook:

```bash
python manage.py remove_webhook
python -m src.main
```

## Project Structure

```
src/
├── main.py                 # Bot entry point (polling mode)
├── config.py              # Configuration management
├── database/
│   ├── base.py            # Base repository and session
│   ├── models.py          # SQLAlchemy models
│   └── migrations/        # Database migrations
├── routers/               # Telegram bot handlers
├── services/              # Business logic
├── repositories/          # Database access
├── schemas/               # Pydantic schemas
├── utils/                 # Utilities
└── keyboards/             # Keyboard builders

exam_bot_admin/            # Django project
├── settings.py            # Django settings
├── urls.py                # URL routing
├── webhook.py             # Bot setup for webhook
└── asgi.py                # ASGI config

admin_panel/               # Django app
├── views.py               # Webhook view
├── admin.py               # Admin configuration
└── management/commands/    # Management commands
```

## Webhook Endpoint

The bot receives updates via:
- **URL**: `/webhook/`
- **Method**: POST
- **Content-Type**: application/json

Telegram sends updates to this endpoint when webhook is configured.

## Admin Panel

Access the Django admin at:
- **URL**: `http://localhost:8000/admin/`
- **Login**: Use superuser credentials

## Documentation

- `SETUP.md` - Detailed setup instructions
- `DJANGO_SETUP.md` - Django and webhook setup guide
- `QUICK_REFERENCE.md` - Common operations and patterns

## License

MIT
