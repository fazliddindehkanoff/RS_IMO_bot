"""Webhook view for Telegram bot."""
import json
import asyncio
import logging
import threading
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from exam_bot_admin.webhook import bot, dp

logger = logging.getLogger(__name__)

# Global event loop running in background thread
_background_loop = None
_background_thread = None


def get_background_loop():
    """Get or create background event loop for processing updates."""
    global _background_loop, _background_thread
    
    if _background_loop is None or _background_loop.is_closed():
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        _background_loop = asyncio.new_event_loop()
        _background_thread = threading.Thread(
            target=run_loop,
            args=(_background_loop,),
            daemon=True
        )
        _background_thread.start()
        logger.info("Started background event loop for webhook processing")
    
    return _background_loop


@csrf_exempt
@require_http_methods(["POST"])
def webhook_view(request):
    """Handle Telegram webhook updates."""
    try:
        # Parse update from request body
        update_json = json.loads(request.body)
        update_id = update_json.get('update_id', 'unknown')
        logger.debug(f"Received update: {update_id}")

        # Get background loop and schedule update processing
        loop = get_background_loop()
        asyncio.run_coroutine_threadsafe(
            process_update(update_json),
            loop
        )

        # Return 200 OK immediately (Telegram expects quick response)
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook request")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)


async def process_update(update_json):
    """Process a Telegram update."""
    try:
        from aiogram.types import Update

        update = Update(**update_json)
        await dp.feed_update(bot, update)
        logger.debug(f"Processed update {update.update_id}")
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
