import os
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Telegram Bot Handler ===

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.caption or message.text or ""
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None

    logging.info(f"📝 Пост получен:\nТекст: {text}\nФото: {photo}\nВидео: {video}")
    await message.reply_text("Пост получен и обработан ✅")

# === AIOHTTP ping server for Render ===

async def handle_ping(request):
    return web.Response(text="pong")

async def start_ping_server():
    app = web.Application()
    app.add_routes([web.get("/", handle_ping), web.get("/ping", handle_ping)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logging.info("🚀 AIOHTTP ping-сервер запущен на порту 8080")

# === Main entrypoint ===

async def main():
    await start_ping_server()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_media))

    logging.info("🤖 Telegram-бот запущен через polling")
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")
