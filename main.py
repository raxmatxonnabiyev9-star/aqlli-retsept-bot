"""Aqlli Retsept bot — ishga tushirish nuqtasi (Render.com / webhook rejimi).

Render bepul tier'da bot polling emas, WEBHOOK rejimida ishlaydi. Flask web
server HTTP portni tinglaydi (Render shuni talab qiladi) va Telegram'dan
kelgan yangilanishlarni python-telegram-bot Application'iga uzatadi.

Endpointlar:
  - "/"                     → health check, {"status": "ok"} qaytaradi
  - "/webhook/<BOT_TOKEN>"  → Telegram yangilanishlarini qabul qiladi

Agar WEBHOOK_URL bo'sh bo'lsa (lokal ishlab chiqish), bot oddiy polling
rejimiga tushadi — bu mahalliy sinov uchun qulay.
"""

import asyncio
import logging
import os
import threading

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_file
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot import handlers
from services import recipe_store
from services.channel_service import ChannelService
from services.ai_service import AIService
from services.unsplash_service import UnsplashService

# Mini App (web sahifa) joylashgan papka
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")

# Logging sozlamasi
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def env_oqi(nom: str, majburiy: bool = True) -> str:
    """Environment variable'ni o'qiydi; majburiy bo'lsa va bo'sh bo'lsa xato beradi."""
    qiymat = os.getenv(nom, "")
    if majburiy and not qiymat:
        raise RuntimeError(f"{nom} environment variable o'rnatilmagan! .env faylni tekshiring.")
    return qiymat


def application_yarat() -> Application:
    """python-telegram-bot Application'ini yaratadi va handlerlarni ro'yxatdan o'tkazadi."""
    gemini_key = env_oqi("GEMINI_API_KEY")
    unsplash_key = env_oqi("UNSPLASH_ACCESS_KEY", majburiy=False)
    channel_id = env_oqi("CHANNEL_ID", majburiy=False)

    app = Application.builder().token(env_oqi("BOT_TOKEN")).build()

    # Servislarni bot_data ga joylaymiz (kanal servisi initialize'dan keyin qo'shiladi)
    # Izoh: bot_data kaliti "claude" tarixiy sabablarga ko'ra saqlangan (handlerlar
    # shu kalitdan o'qiydi); endi uning ortida Gemini AIService turadi.
    app.bot_data["claude"] = AIService(api_key=gemini_key)
    app.bot_data["unsplash"] = UnsplashService(access_key=unsplash_key)
    app.bot_data["channel_id"] = channel_id

    # Handlerlar
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.rasm_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.matn_handler))
    app.add_handler(CallbackQueryHandler(handlers.tugma_handler))

    return app


# ──────────────────────────────────────────────
# Flask web server (webhook rejimi)
# ──────────────────────────────────────────────

flask_app = Flask(__name__)

# Quyidagilar webhook rejimida ishga tushganda to'ldiriladi
_application: Application | None = None
_loop: asyncio.AbstractEventLoop | None = None
_bot_token: str = ""


@flask_app.get("/")
def health():
    """Render uchun health check — bot tirikligini bildiradi."""
    return jsonify({"status": "ok"})


@flask_app.get("/app")
def miniapp():
    """Telegram Mini App sahifasini (retsept kartasi) qaytaradi."""
    return send_file(os.path.join(WEB_DIR, "miniapp.html"))


@flask_app.get("/api/recipe/<rid>")
def api_recipe(rid: str):
    """Mini App so'ragan retsept JSON'ini ID bo'yicha qaytaradi."""
    retsept = recipe_store.ol(rid)
    if not retsept:
        abort(404)
    return jsonify(retsept)


@flask_app.post("/webhook/<token>")
def webhook(token: str):
    """Telegram yuborgan yangilanishni qabul qilib, botning event loop'iga uzatadi.

    Xavfsizlik uchun URL'dagi token BOT_TOKEN bilan mos kelishi shart.
    """
    if token != _bot_token:
        abort(403)
    if _application is None or _loop is None:
        abort(503)

    update = Update.de_json(request.get_json(force=True), _application.bot)
    # Flask (sync) dan asinxron event loop'ga xavfsiz uzatish
    asyncio.run_coroutine_threadsafe(_application.process_update(update), _loop)
    return "ok"


def _loopni_ishga_tushir(loop: asyncio.AbstractEventLoop) -> None:
    """Berilgan event loop'ni alohida thread'da abadiy ishlatadi."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


async def _webhook_sozla(app: Application, webhook_url: str, bot_token: str) -> None:
    """Application'ni ishga tushiradi, kanal servisini ulaydi va webhook'ni ro'yxatdan o'tkazadi."""
    await app.initialize()
    app.bot_data["channel"] = ChannelService(bot=app.bot, channel_id=app.bot_data["channel_id"])
    await app.start()
    toliq_url = f"{webhook_url.rstrip('/')}/webhook/{bot_token}"
    await app.bot.set_webhook(url=toliq_url, allowed_updates=["message", "callback_query"])
    logger.info("Webhook o'rnatildi: %s", toliq_url)


def webhook_rejimida_ishga_tushir(app: Application, webhook_url: str, bot_token: str) -> None:
    """Webhook + Flask rejimida botni ishga tushiradi (Render uchun)."""
    global _application, _loop, _bot_token
    _application = app
    _bot_token = bot_token

    # Asinxron event loop'ni fon thread'ida ishga tushiramiz
    _loop = asyncio.new_event_loop()
    thread = threading.Thread(target=_loopni_ishga_tushir, args=(_loop,), daemon=True)
    thread.start()

    # Application initialize + webhook sozlashni shu loop'da bajaramiz
    future = asyncio.run_coroutine_threadsafe(
        _webhook_sozla(app, webhook_url, bot_token), _loop
    )
    future.result()  # tugashini kutamiz

    # Render bergan PORT'ni tinglaymiz
    port = int(os.getenv("PORT", "10000"))
    logger.info("Flask server ishga tushmoqda: 0.0.0.0:%d", port)
    flask_app.run(host="0.0.0.0", port=port, threaded=True)


def polling_rejimida_ishga_tushir(app: Application) -> None:
    """Lokal sinov uchun oddiy polling rejimi (WEBHOOK_URL bo'sh bo'lsa)."""

    async def _post_init(application: Application) -> None:
        """Polling boshlanishidan oldin kanal servisini ulaydi."""
        application.bot_data["channel"] = ChannelService(
            bot=application.bot, channel_id=application.bot_data["channel_id"]
        )

    app.post_init = _post_init

    # Mini App lokalda ham ochilishi uchun Flask'ni fon thread'ida ishga tushiramiz
    port = int(os.getenv("PORT", "8080"))
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(
            host="0.0.0.0", port=port, use_reloader=False, debug=False, threaded=True
        ),
        daemon=True,
    )
    flask_thread.start()
    logger.info("Mini App lokal manzili: http://localhost:%d/app", port)

    logger.info("WEBHOOK_URL topilmadi — lokal POLLING rejimida ishga tushyapman...")
    app.run_polling(allowed_updates=["message", "callback_query"])


def main() -> None:
    """Konfiguratsiyaga qarab webhook yoki polling rejimida botni ishga tushiradi."""
    load_dotenv()

    bot_token = env_oqi("BOT_TOKEN")
    webhook_url = env_oqi("WEBHOOK_URL", majburiy=False)

    app = application_yarat()

    if webhook_url:
        webhook_rejimida_ishga_tushir(app, webhook_url, bot_token)
    else:
        polling_rejimida_ishga_tushir(app)


if __name__ == "__main__":
    main()
