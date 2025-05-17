import os
import logging
from datetime import datetime
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")

user_states = {}
user_posts = {}
PLATFORMS = ["Telegram", "Instagram", "VK", "YouTube"]

# === STEP 1: RECEIVE CONTENT ===
async def handle_content(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    message = update.message
    
    if user_states.get(user_id) != "awaiting_content":
        user_states[user_id] = "awaiting_content"
        user_posts[user_id] = {}

    text = message.caption or message.text or ""
    photo = message.photo[-1].file_id if message.photo else None
    video = message.video.file_id if message.video else None

    user_posts[user_id].update({"text": text, "photo": photo, "video": video})
    user_states[user_id] = "awaiting_date"

    await message.reply_text("📅 Выберите дату и время публикации:", reply_markup=calendar_keyboard())

# === STEP 2: SELECT DATE ===
def calendar_keyboard():
    now = datetime.now()
    buttons = [
        [InlineKeyboardButton((now.replace(day=now.day+i).strftime("%d.%m")), callback_data=f"date_{now.replace(day=now.day+i).strftime('%Y-%m-%d')}")]
        for i in range(3)
    ]
    return InlineKeyboardMarkup(buttons)

# === STEP 3: SELECT PLATFORMS ===
def platforms_keyboard(selected=None):
    if selected is None:
        selected = []
    rows = []
    for platform in PLATFORMS:
        prefix = "✅ " if platform in selected else "➕ "
        rows.append([InlineKeyboardButton(f"{prefix}{platform}", callback_data=f"platform_{platform}")])
    rows.append([InlineKeyboardButton("Подтвердить ✅", callback_data="confirm")])
    return InlineKeyboardMarkup(rows)

# === CALLBACK HANDLER ===
async def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.effective_user.id
    data = query.data

    await query.answer()

    if data.startswith("date_"):
        date_str = data.split("_")[1]
        user_posts[user_id]["date"] = date_str
        user_states[user_id] = "awaiting_platforms"
        user_posts[user_id]["platforms"] = []
        await query.edit_message_text("📤 Выберите платформы для публикации:", reply_markup=platforms_keyboard())

    elif data.startswith("platform_"):
        platform = data.split("_")[1]
        selected = user_posts[user_id].get("platforms", [])
        if platform in selected:
            selected.remove(platform)
        else:
            selected.append(platform)
        user_posts[user_id]["platforms"] = selected
        await query.edit_message_text("📤 Выберите платформы для публикации:", reply_markup=platforms_keyboard(selected))

    elif data == "confirm":
        post = user_posts[user_id]
        logging.info(f"✅ Готов к публикации: {post}")
        await query.edit_message_text("✅ Пост готов к публикации!\n\n📆 Дата: {}\n📤 Платформы: {}".format(post['date'], ", ".join(post['platforms'])))
        await context.bot.send_message(chat_id=user_id, text="Новый пост 🆕", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Создать новый пост", callback_data="new_post")]
        ]))
        user_states[user_id] = "awaiting_content"

    elif data == "new_post":
        user_states[user_id] = "awaiting_content"
        user_posts[user_id] = {}
        await context.bot.send_message(chat_id=user_id, text="✏️ Отправьте текст, фото или видео для нового поста")

# === PING SERVER ===
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

# === MAIN ENTRY ===
async def main():
    await start_ping_server()

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_content))
    application.add_handler(CallbackQueryHandler(handle_callback))

    logging.info("🤖 Telegram-бот запущен через polling")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"❌ Ошибка запуска: {e}")
