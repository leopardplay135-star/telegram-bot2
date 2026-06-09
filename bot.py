import asyncio
import json
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не задан!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "user_data.json"

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f)

user_data = load_data()

# Временное хранилище для связи заявка -> пользователь
pending_orders = {}

@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    user_data[user_id] = {"step": "game"}
    save_data(user_data)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Brawl Stars", callback_data="brawl"),
         InlineKeyboardButton(text="⚔️ Fortnite", callback_data="fortnite")]
    ])
    await message.answer(
        "🎮 <b>Добро пожаловать!</b>\n\nВыбери игру:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data in ["brawl", "fortnite"])
async def choose_game(callback):
    user_id = str(callback.from_user.id)
    game = "Brawl Stars" if callback.data == "brawl" else "Fortnite"
    user_data[user_id] = {"step": "screenshots", "game": game, "screenshots": []}
    save_data(user_data)
    await callback.message.edit_text(
        f"📱 <b>Выбрано: {game}</b>\n\n"
        f"Отправь скриншоты. Когда закончишь - нажми /done",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo)
async def save_photo(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_data or user_data[user_id].get("step") != "screenshots":
        await message.answer("❌ Сначала /start и выбери игру")
        return
    
    photo = message.photo[-1].file_id
    user_data[user_id]["screenshots"].append(photo)
    save_data(user_data)
    
    count = len(user_data[user_id]["screenshots"])
    await message.answer(f"✅ Скриншот #{count} сохранен!\nОтправь еще или /done")

@dp.message(Command("done"))
async def send_to_admin(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_data:
        await message.answer("❌ Нет активной заявки. Начни с /start")
        return
    
    data = user_data[user_id]
    screenshots = data.get("screenshots", [])
    
    if not screenshots:
        await message.answer("❌ Нет скриншотов!")
        return
    
    username = message.from_user.username or message.from_user.first_name
    game = data["game"]
    
    # Создаем уникальный ID заявки
    import time
    order_id = str(int(time.time()))
    
    # Сохраняем связь заявка -> пользователь
    pending_orders[order_id] = {
        "user_id": user_id,
        "username": username,
        "game": game
    }
    
    # Отправляем админу
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>НОВАЯ ЗАЯВКА #{order_id}</b>\n\n"
        f"👤 Продавец: @{username}\n"
        f"🎮 Игра: {game}\n"
        f"📸 Скриншотов: {len(screenshots)}\n\n"
        f"<b>Чтобы отправить цену, напиши:</b>\n"
        f"<code>/price {order_id} СУММА</code>\n\n"
        f"Пример: <code>/price {order_id} 500 рублей</code>",
        parse_mode="HTML"
    )
    
    for idx, photo in enumerate(screenshots, 1):
        await bot.send_photo(ADMIN_ID, photo, caption=f"Скриншот #{idx}")
    
    await message.answer(
        f"✅ Заявка отправлена!\n\n"
        f"Номер заявки: <code>{order_id}</code>\n"
        f"Админ скоро напишет цену.",
        parse_mode="HTML"
    )
    
    # Очищаем данные пользователя
    del user_data[user_id]
    save_data(user_data)

# ========== НОВАЯ КОМАНДА ДЛЯ АДМИНА ==========
@dp.message(Command("price"))
async def admin_send_price(message: types.Message):
    # Проверяем, что админ
    if message.chat.id != ADMIN_ID:
        return
    
    # Разбираем команду: /price 123456789 500 рублей
    parts = message.text.split(maxsplit=2)
    
    if len(parts) < 3:
        await message.reply(
            "❌ Неправильный формат!\n\n"
            "Используй: <code>/price НОМЕР_ЗАЯВКИ ЦЕНА</code>\n"
            "Пример: <code>/price 123456789 500 рублей</code>",
            parse_mode="HTML"
        )
        return
    
    order_id = parts[1]
    price = parts[2]
    
    # Ищем заявку
    if order_id not in pending_orders:
        await message.reply(f"❌ Заявка #{order_id} не найдена!\nВозможно, уже обработана.")
        return
    
    order = pending_orders[order_id]
    user_id = order["user_id"]
    game = order["game"]
    username = order["username"]
    
    try:
        # Отправляем цену пользователю
        await bot.send_message(
            int(user_id),
            f"💰 <b>Твой аккаунт {game} оценили!</b>\n\n"
            f"💰 Цена: <b>{price}</b>\n\n"
            f"📞 Свяжись с админом: @{message.from_user.username}\n"
            f"✅ Если согласен, напиши ему.\n"
            f"❌ Если нет - начни заново с /start",
            parse_mode="HTML"
        )
        
        # Удаляем заявку из ожидания
        del pending_orders[order_id]
        
        await message.reply(
            f"✅ Цена отправлена пользователю!\n\n"
            f"👤 Пользователь: @{username}\n"
            f"💰 Цена: {price}\n"
            f"🆔 Заявка: #{order_id}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message()
async def unknown(message: types.Message):
    # Если админ просто пишет что-то не в команду
    if message.chat.id == ADMIN_ID:
        await message.reply(
            "📝 <b>Как отправить цену:</b>\n\n"
            "Используй команду:\n"
            "<code>/price НОМЕР_ЗАЯВКИ ЦЕНА</code>\n\n"
            "Пример: <code>/price 123456789 500 рублей</code>\n\n"
            "Номер заявки приходит в сообщении с заявкой.",
            parse_mode="HTML"
        )

async def main():
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН!")
    me = await bot.get_me()
    print(f"✅ Бот: @{me.username}")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
