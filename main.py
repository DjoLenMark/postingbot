
from keep_alive import keep_alive
keep_alive()

import datetime
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN = os.getenv("TELEGRAM_TOKEN")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "ContentItems")

GET_IMAGE, GET_VIDEO, GET_TEXT, GET_DATE, GET_PLATFORM = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    skip_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_image")]])
    await update.message.reply_text("📸 Загрузите изображение или нажмите 'Пропустить'", reply_markup=skip_markup)
    return GET_IMAGE

async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        context.user_data["image"] = update.message.photo[-1].file_id
    return await ask_video(update, context)

async def skip_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_video(update, context)

async def ask_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    skip_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_video")]])
    await update.effective_message.reply_text("🎥 Загрузите видео или нажмите 'Пропустить'", reply_markup=skip_markup)
    return GET_VIDEO

async def get_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        if update.message.video:
            context.user_data["video"] = update.message.video.file_id
        elif update.message.document and update.message.document.mime_type.startswith("video"):
            context.user_data["video"] = update.message.document.file_id
    return await ask_text(update, context)

async def skip_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_text(update, context)

async def ask_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    skip_markup = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Пропустить", callback_data="skip_text")]])
    await update.effective_message.reply_text("📝 Введите текст поста или нажмите 'Пропустить'", reply_markup=skip_markup)
    return GET_TEXT

async def get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data["text"] = update.message.text
    return await ask_date(update, context)

async def skip_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await ask_date(update, context)

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Опубликовать сейчас", callback_data="publish_now")]])
    await update.effective_message.reply_text("⏰ Укажите дату публикации (ДД.ММ.ГГГГ) или нажмите 'Опубликовать сейчас'", reply_markup=markup)
    return GET_DATE

async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt = datetime.datetime.strptime(update.message.text, "%d.%m.%Y")
        context.user_data["publish_date"] = dt.strftime("%Y-%m-%d")
    except:
        await update.message.reply_text("❌ Неверный формат. Пример: 17.05.2025")
        return GET_DATE
    return await ask_platforms(update, context)

async def publish_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["publish_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
    return await ask_platforms(update, context)

async def ask_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["platforms"] = []
    return await update_platforms(update, context)

async def update_platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platforms = context.user_data.get("platforms", [])
    text = f"✅ Выбрано: {', '.join(platforms)}" if platforms else "📲 Выберите платформы:"
    keyboard = [
        [InlineKeyboardButton("📢 Telegram", callback_data="Telegram")],
        [InlineKeyboardButton("📷 Instagram", callback_data="Instagram")],
        [InlineKeyboardButton("📰 VK", callback_data="VK")],
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_platforms")]
    ]
    await update.callback_query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_PLATFORM

async def get_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    platforms = context.user_data.setdefault("platforms", [])

    if data == "confirm_platforms":
        return await finalize_post(update, context)

    if data in platforms:
        platforms.remove(data)
    else:
        platforms.append(data)

    return await update_platforms(update, context)

async def finalize_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    record = {
        "fields": {
            "Text": context.user_data.get("text", ""),
            "Platform": context.user_data.get("platforms", []),
            "Creation Date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "Scheduled Publish Date": context.user_data.get("publish_date", ""),
            "Status": "Scheduled"
        }
    }

    response = requests.post(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}",
        json=record,
        headers={
            "Authorization": f"Bearer {AIRTABLE_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    if response.status_code in (200, 201):
        await update.callback_query.message.reply_text("✅ Пост добавлен в Airtable!")
        await update.callback_query.message.reply_text("🟢 Нажмите /start, чтобы создать новый пост.")
    else:
        await update.callback_query.message.reply_text(f"❌ Ошибка: {response.text}")

    if "Telegram" in context.user_data.get("platforms", []):
        try:
            text = context.user_data.get("text", "📝 Пост без текста.")
            video_id = context.user_data.get("video")
            image_id = context.user_data.get("image")

            if video_id:
                await context.bot.send_video(chat_id=-1002519590738, video=video_id, caption=text)
            elif image_id:
                await context.bot.send_photo(chat_id=-1002519590738, photo=image_id, caption=text)
            else:
                await context.bot.send_message(chat_id=-1002519590738, text=text)
        except Exception as e:
            await update.callback_query.message.reply_text(f"⚠️ Ошибка при публикации в канал: {e}")

    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, get_image),
                CallbackQueryHandler(skip_image, pattern="^skip_image$")
            ],
            GET_VIDEO: [
                MessageHandler(filters.VIDEO | filters.Document.VIDEO, get_video),
                CallbackQueryHandler(skip_video, pattern="^skip_video$")
            ],
            GET_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_text),
                CallbackQueryHandler(skip_text, pattern="^skip_text$")
            ],
            GET_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_date),
                CallbackQueryHandler(publish_now, pattern="^publish_now$")
            ],
            GET_PLATFORM: [CallbackQueryHandler(get_platform)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(conv)
    app.run_polling()

if __name__ == "__main__":
    main()
