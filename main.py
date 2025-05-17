import os
import logging
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Этапы сценария
STEP_CONTENT, STEP_DATE, STEP_PLATFORM = range(3)

user_data = {}

# === Handlers ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_chat.id] = {"media": {}}
    await update.message.reply_text("📥 Отправь текст, фото и/или видео поста:")
    return STEP_CONTENT

async def receive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    message = update.message

    text = message.caption or message.text or ""
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None

    user_data[uid]["media"] = {"text": text, "photo": photo, "video": video}

    await update.message.reply_text("📅 Теперь выбери дату и время публикации (в формате ГГГГ-ММ-ДД ЧЧ:ММ):")
    return STEP_DATE

async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_chat.id
    user_data[uid]["datetime"] = update.message.text.strip()

    keyboard = [
        [InlineKeyboardButton("Telegram ✅", callback_data="tg"),
         InlineKeyboardButton("VK", callback_data="vk")],
        [InlineKeyboardButton("Tilda", callback_data="tilda")],
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")]
    ]

    await update.message.reply_text("🌐 Выбери платформы для публикации:", reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_PLATFORM

async def platform_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.message.chat.id

    if query.data == "confirm":
        media = user_data[uid]["media"]
        dt = user_data[uid]["datetime"]
        platforms = user_data[uid].get("platforms", ["Telegram ✅"])

        result = f"🎉 Пост сохранён!

📝 Текст: {media['text']}
📅 Дата: {dt}
📡 Платформы: {', '.join(platforms)}"
        await query.edit_message_text(result)

        keyboard = [[InlineKeyboardButton("➕ Новый пост", callback_data="newpost")]]
        await query.message.reply_text("Готово ✅", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    # Добавление/удаление платформ
    platforms = user_data[uid].get("platforms", [])
    if query.data in platforms:
        platforms.remove(query.data)
    else:
        platforms.append(query.data)
    user_data[uid]["platforms"] = platforms

    # Обновить клавиатуру
    def btn(label): return f"{label}{' ✅' if label in platforms else ''}"
    keyboard = [
        [InlineKeyboardButton(btn("Telegram"), callback_data="tg"),
         InlineKeyboardButton(btn("VK"), callback_data="vk")],
        [InlineKeyboardButton(btn("Tilda"), callback_data="tilda")],
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")]
    ]
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    return STEP_PLATFORM

async def new_post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await start(query, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Отменено.")
    return ConversationHandler.END

# === Ping server ===

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

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STEP_CONTENT: [MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, receive_content)],
            STEP_DATE: [MessageHandler(filters.TEXT, receive_date)],
            STEP_PLATFORM: [CallbackQueryHandler(platform_select)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(new_post_callback, pattern="^newpost$"))

    logging.info("🤖 Telegram-бот запущен через polling")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")
