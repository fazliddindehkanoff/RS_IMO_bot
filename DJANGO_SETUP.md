# Django + Webhook Setup Guide

## Overview

The bot now supports both polling and webhook modes. Django is integrated for the admin panel using django-unfold, and the bot receives updates via webhook.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Add to your `.env` file:

```bash
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
CSRF_TRUSTED_ORIGINS=https://localhost,https://yourdomain.com

# Webhook Settings
WEBHOOK_URL=https://yourdomain.com/webhook
WEBHOOK_SECRET=your-secret-token-optional

# Existing bot settings
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
```

### 3. Django Migrations

Create Django's auth tables (for admin login):

```bash
python manage.py migrate
```

### 4. Create Django Superuser

```bash
python manage.py createsuperuser
```

### 5. Set Up Webhook

#### For Development (using ngrok or similar):

```bash
# Start ngrok
ngrok http 8000

# Set webhook (use the ngrok URL)
python manage.py setup_webhook --url https://your-ngrok-url.ngrok.io/webhook
```

#### For Production:

```bash
python manage.py setup_webhook --url https://yourdomain.com/webhook --secret-token your-secret-token
```

### 6. Run Django Server

```bash
python manage.py runserver
```

The bot will now receive updates via the `/webhook` endpoint.

## Switching Between Modes

### Switch to Webhook Mode

```bash
python manage.py setup_webhook --url https://yourdomain.com/webhook
```

### Switch Back to Polling Mode

```bash
python manage.py remove_webhook
# Then run: python -m src.main
```

## Admin Panel

Access the Django admin panel at:
- URL: `http://localhost:8000/admin/`
- Login with the superuser credentials you created

The admin panel uses django-unfold for a modern interface.

## Project Structure

```
exam_bot_admin/          # Django project
├── settings.py          # Django settings
├── urls.py              # URL routing (includes /webhook)
├── webhook.py           # Bot initialization for webhook mode
└── asgi.py              # ASGI config

admin_panel/             # Django app
├── views.py             # Webhook view handler
├── admin.py             # Django admin configuration
└── management/
    └── commands/
        ├── setup_webhook.py    # Command to set webhook
        └── remove_webhook.py   # Command to remove webhook
```

## Webhook Endpoint

The webhook endpoint is available at:
- **URL**: `/webhook/`
- **Method**: POST
- **Content-Type**: application/json
- **CSRF**: Exempt (required for Telegram)

Telegram will send updates to this endpoint in JSON format.

## Development vs Production

### Development
- Use `python manage.py runserver` for Django
- Use ngrok or similar for webhook testing
- Set `DEBUG=True` in `.env`

### Production
- Use a production WSGI server (gunicorn, uvicorn)
- Set up proper SSL certificate (required for webhooks)
- Set `DEBUG=False` in `.env`
- Configure proper `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`

## Troubleshooting

### Webhook not receiving updates
1. Check webhook info: The bot will log webhook info when you run `setup_webhook`
2. Verify URL is accessible: Test with `curl -X POST https://yourdomain.com/webhook/`
3. Check Django logs for errors
4. Ensure SSL certificate is valid (Telegram requires HTTPS)

### Bot not responding
1. Check if webhook is set: `python manage.py setup_webhook` will show current status
2. Check Django server logs
3. Verify `BOT_TOKEN` is correct
4. Check database connection

### Admin panel not loading
1. Run migrations: `python manage.py migrate`
2. Create superuser: `python manage.py createsuperuser`
3. Check `ALLOWED_HOSTS` in settings

## Next Steps

1. **Create Django Models**: Create Django models that mirror SQLAlchemy models for admin panel
2. **Admin Integration**: Configure django-unfold admin for managing bot data
3. **API Endpoints**: Add REST API endpoints for programmatic access
4. **Authentication**: Set up proper authentication for admin panel
