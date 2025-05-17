import os
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# === Хранилище сессий пользователей ===
user_sessions = {}

# === Telegram Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"step": 1, "media": {}, "text": ""}
    await update.message.reply_text("👋 Привет! Отправь текст, фото или видео, чтобы создать пост.")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {"step": 1, "media": {}, "text": ""})

    message = update.message
    text = message.caption or message.text or ""
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None

    # Сохраняем полученные данные
    if text:
        session["text"] = text
    if photo:
        session["media"]["photo"] = photo
    if video:
        session["media"]["video"] = video

    session["step"] = 2
    user_sessions[user_id] = session

    await update.message.reply_text(
    "🗓 Теперь выбери дату и время публикации.\n\n"
    "📅 Календарь, кнопка 'Опубликовать сейчас' и поле ручного ввода скоро будут добавлены."
)

# === AIOHTTP ping-сервер для Render ===

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

# === Main ===

async def main():
    await start_ping_server()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_media))

    logging.info("🤖 Telegram-бот запущен через polling")
    await application.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error("❌ Ошибка запуска: " + str(e))
