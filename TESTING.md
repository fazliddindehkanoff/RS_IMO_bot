# Testing Guide

## Quick Start Testing

### Option 1: Polling Mode (Easiest for Local Testing)

This is the simplest way to test the bot locally without setting up webhooks.

1. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```bash
   BOT_TOKEN=your_telegram_bot_token_here
   DJANGO_SECRET_KEY=your-secret-key
   DEBUG=True
   ```

2. **Run migrations** (if not done already):
   ```bash
   python manage.py migrate
   ```

3. **Run the bot in polling mode**:
   ```bash
   python bot/polling.py
   ```

4. **Test the bot**:
   - Open Telegram and find your bot
   - Send `/start` command
   - Follow the registration flow

### Option 2: Webhook Mode with ngrok (For Production-like Testing)

1. **Install ngrok** (if not installed):
   - Download from https://ngrok.com/
   - Or use: `choco install ngrok` (Windows) or `brew install ngrok` (Mac)

2. **Start Django server**:
   ```bash
   python manage.py runserver
   ```

3. **In a new terminal, start ngrok**:
   ```bash
   ngrok http 8000
   ```
   Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

4. **Set up webhook**:
   ```bash
   python manage.py setup_webhook --url https://abc123.ngrok.io/webhook
   ```

5. **Test the bot**:
   - Open Telegram and find your bot
   - Send `/start` command
   - Follow the registration flow

## Testing the Registration Flow

### Step-by-Step Test

1. **Start the bot** (using polling or webhook mode)

2. **Send `/start` command**:
   - Bot should respond with welcome message in Uzbek
   - Should ask for first name

3. **Enter first name**:
   - Type your first name
   - Bot should confirm and ask for last name

4. **Enter last name** (or skip):
   - Type last name or use skip button
   - Bot should ask for phone number

5. **Share phone number**:
   - Click "Telefon raqamini yuborish" button
   - Or type phone number manually
   - Bot should ask for grade

6. **Select grade**:
   - Choose from inline keyboard (5-8)
   - Bot should ask for date of birth

7. **Enter date of birth**:
   - Format: YYYY-MM-DD (e.g., 2010-05-15)
   - Bot should ask for region

8. **Select region**:
   - Choose from inline keyboard (12 regions)
   - Bot should ask for district

9. **Enter district**:
   - Type your district/city name
   - Bot should ask for language

10. **Select language**:
    - Choose from inline keyboard
    - Bot should ask for photo

11. **Send photo**:
    - Send a photo from your gallery
    - Bot should ask for document number

12. **Enter document number** (or skip):
    - Type document number or skip
    - Bot should ask for school name

13. **Enter school name**:
    - Type your school name
    - Bot should ask for parent name

14. **Enter parent information**:
    - Parent name
    - Parent phone
    - Relationship type

15. **Enter teacher information**:
    - Teacher name
    - Teacher phone
    - Subject

16. **Select registration source**:
    - Choose from inline keyboard
    - If "Boshqa", enter details

17. **Complete registration**:
    - Bot should show success message
    - Main menu should appear

## Checking Data in Django Admin

1. **Access admin panel**:
   ```
   http://localhost:8000/admin/
   ```

2. **Login** with superuser credentials

3. **Check registered students**:
   - Go to "O'quvchilar" (Students)
   - Verify all entered data is saved

4. **Check related data**:
   - "Ota-onalar" (Parents)
   - "O'qituvchilar" (Teachers)
   - "Ro'yxatdan o'tish manbalari" (Registration Sources)

## Troubleshooting

### Bot not responding
- Check if `BOT_TOKEN` is set correctly in `.env`
- Check if bot is running (polling mode) or webhook is set
- Check console logs for errors

### Database errors
- Run migrations: `python manage.py migrate`
- Check if database file exists in `data/exam_bot.db`

### Import errors
- Make sure you're in the project root directory
- Activate virtual environment if using one
- Check that all dependencies are installed: `pip install -r requirements.txt`

### Photo not saving
- Check if `media/students/` directory exists
- Check file permissions
- Check Django `MEDIA_ROOT` setting

### State not persisting
- Check `BotState` model in admin panel
- Verify state is being saved after each step

## Testing Checklist

- [ ] Bot responds to `/start` command
- [ ] First name is saved correctly
- [ ] Last name can be skipped
- [ ] Phone number can be shared via button or typed
- [ ] Grade selection works (inline keyboard)
- [ ] Date of birth accepts correct format
- [ ] Region selection works (all 12 regions)
- [ ] District text input works
- [ ] Language selection works
- [ ] Photo upload works
- [ ] Document number can be skipped
- [ ] School name is saved
- [ ] Parent information is saved
- [ ] Teacher information is saved
- [ ] Registration source selection works
- [ ] All data appears in Django admin
- [ ] Main menu appears after completion
- [ ] Re-registration shows "already registered" message

## Next Steps After Testing

Once registration is working:
1. Test exam functionality (when implemented)
2. Test certificate generation (when implemented)
3. Test feedback functionality (when implemented)
4. Test admin panel features
