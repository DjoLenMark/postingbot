import os
import logging
import asyncio
from aiohttp import web
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CallbackQueryHandler,
    MessageHandler, CommandHandler, filters
)
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Хранилище данных поста
user_post_data = {}

# ==== ШАГ 1: ПОЛУЧЕНИЕ МЕДИА ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_post_data[update.effective_user.id] = {"step": 1}
    await update.message.reply_text("📥 Отправьте текст, фото и/или видео для будущего поста")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    state = user_post_data.get(uid, {})
    if state.get("step") != 1:
        return

    text = update.message.caption or update.message.text or ""
    photo = update.message.photo[-1].file_id if update.message.photo else None
    video = update.message.video.file_id if update.message.video else None

    user_post_data[uid].update({"text": text, "photo": photo, "video": video, "step": 2})
    await send_calendar(update, context)

# ==== ШАГ 2: КАЛЕНДАРЬ ====
async def send_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    keyboard = []
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    for i in range(0, 42):
        day = now + timedelta(days=i)
        button = InlineKeyboardButton(str(day.day), callback_data=f"date:{day.strftime('%d.%m.%Y')}")
        if i % 7 == 0:
            keyboard.append([])
        keyboard[-1].append(button)

    keyboard.append([
        InlineKeyboardButton("📅 Ввести вручную", callback_data="manual_date"),
        InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data="now")
    ])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🗓 Выберите дату публикации:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==== ШАГ 3: ВЫБОР ПЛАТФОРМ ====
PLATFORMS = ["Telegram", "VK", "Instagram", "YouTube", "Tilda"]

async def ask_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_post_data[uid]["step"] = 3
    selected = user_post_data[uid].get("platforms", [])

    buttons = []
    for platform in PLATFORMS:
        selected_marker = "✅" if platform in selected else "➕"
        buttons.append(
            InlineKeyboardButton(f"{selected_marker} {platform}", callback_data=f"platform:{platform}")
        )

    buttons.append(InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_platforms"))
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📲 Выберите платформы для публикации:",
        reply_markup=InlineKeyboardMarkup(rows)
    )

# ==== ОБРАБОТЧИКИ ====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if query.data.startswith("date:"):
        user_post_data[uid]["date"] = query.data.split(":")[1]
        await query.edit_message_text(f"🗓 Дата выбрана: {user_post_data[uid]['date']}")
        await ask_platforms(update, context)

    elif query.data.startswith("platform:"):
        platform = query.data.split(":")[1]
        selected = user_post_data[uid].get("platforms", [])
        if platform in selected:
            selected.remove(platform)
        else:
            selected.append(platform)
        user_post_data[uid]["platforms"] = selected
        await ask_platforms(update, context)

    elif query.data == "confirm_platforms":
        post = user_post_data.get(uid, {})
        result = "🎉 Пост сохранён!

"
        result += f"📄 Текст: {post.get('text', '')}
"
        result += f"📆 Дата: {post.get('date', 'Сейчас')}
"
        result += f"📲 Платформы: {', '.join(post.get('platforms', []))}"
        await query.edit_message_text(result)
        await context.bot.send_message(chat_id=uid, text="🔁 Новый пост", reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Создать новый пост", callback_data="new_post")
        ]]))

    elif query.data == "new_post":
        user_post_data[uid] = {"step": 1}
        await context.bot.send_message(chat_id=uid, text="📥 Отправьте текст, фото и/или видео для нового поста")

# ==== PING-SERVER ====
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

# ==== MAIN ====
async def main():
    await start_ping_server()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_media))
    app.add_handler(CallbackQueryHandler(button_handler))
    logging.info("🤖 Telegram-бот запущен через polling")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await app.updater.idle()

if __name__ == "__main__":
    asyncio.run(main())
