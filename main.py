import os
import logging
import nest_asyncio
nest_asyncio.apply()
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, ContextTypes, CallbackQueryHandler,
                          CommandHandler, MessageHandler, filters)

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Временное хранилище состояния пользователей
user_state = {}

# === START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state[update.effective_user.id] = {}
    await update.message.reply_text("📥 Отправь текст, фото или видео для поста")

# === Получение текста/фото/видео ===
async def collect_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_state.setdefault(user_id, {})
    
    if update.message.text:
        data['text'] = update.message.text
    if update.message.photo:
        data['photo'] = update.message.photo[-1].file_id
    if update.message.video:
        data['video'] = update.message.video.file_id

    await send_calendar(update, context)

# === Календарь ===
def generate_calendar_keyboard():
    today = datetime.now()
    keyboard = []
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="IGNORE") for day in weekdays])

    first_day = today.replace(day=1)
    next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    days_range = (next_month - first_day).days
    
    row = []
    skip = (first_day.weekday() + 1) % 7
    for _ in range(skip):
        row.append(InlineKeyboardButton(" ", callback_data="IGNORE"))
    
    for day in range(1, days_range + 1):
        current = first_day.replace(day=day)
        row.append(InlineKeyboardButton(str(day), callback_data=f"DATE_{current.strftime('%d.%m.%Y')}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("📅 Опубликовать сейчас", callback_data="NOW"),
        InlineKeyboardButton("✏️ Ввести вручную", callback_data="MANUAL")
    ])
    return InlineKeyboardMarkup(keyboard)

async def send_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗓 Выбери дату публикации:", reply_markup=generate_calendar_keyboard())

# === Обработка нажатий кнопок ===
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data.startswith("DATE_"):
        user_state[user_id]['date'] = data.replace("DATE_", "")
        await query.edit_message_text(text=f"✅ Дата выбрана: {user_state[user_id]['date']}\nТеперь выбери время:",
                                      reply_markup=generate_time_keyboard())
    elif data.startswith("TIME_"):
        time = data.replace("TIME_", "")
        user_state[user_id]['time'] = time
        await query.edit_message_text(text=f"✅ Время выбрано: {time}\nПост готов к публикации. (Платформы будут следующими)")
    elif data == "NOW":
        user_state[user_id]['now'] = True
        await query.edit_message_text(text="✅ Пост будет опубликован сейчас. (Платформы будут следующими)")
    elif data == "MANUAL":
        await query.edit_message_text("Введите дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ")

# === Выбор времени ===
def generate_time_keyboard():
    hours = [f"{i:02d}" for i in range(0, 24)]
    minutes = [f"{i:02d}" for i in range(0, 60, 5)]
    keyboard = []

    hour_row = [InlineKeyboardButton(h, callback_data=f"TIME_{h}:00") for h in hours]
    minute_row = [InlineKeyboardButton(m, callback_data=f"TIME_00:{m}") for m in minutes]

    for i in range(0, 24, 6):
        keyboard.append([InlineKeyboardButton(hours[j], callback_data=f"TIME_{hours[j]}:00") for j in range(i, i+6)])
    keyboard.append([InlineKeyboardButton(m, callback_data=f"TIME_00:{m}") for m in minutes[:6]])
    keyboard.append([InlineKeyboardButton(m, callback_data=f"TIME_00:{m}") for m in minutes[6:12]])

    return InlineKeyboardMarkup(keyboard)

# === MAIN ===
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, collect_post))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logging.info("🤖 Бот запущен")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.run(main())
