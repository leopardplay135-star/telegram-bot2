import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== НАСТРОЙКИ (берутся из переменных окружения) ==========
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не задан!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Файл для хранения данных
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
        "🎮 <b>Добро пожаловать в бот по продаже аккаунтов!</b>\n\nВыбери игру:",
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
        f"Отправь скриншоты аккаунта (можно несколько фото)\n\n"
        f"Когда закончишь, напиши команду <b>/done</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo)
async def save_photo(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_data:
        await message.answer("❌ Сначала нажми /start и выбери игру")
        return
    
    if user_data[user_id].get("step") != "screenshots":
        await message.answer("❌ Сначала выбери игру через /start")
        return
    
    photo = message.photo[-1].file_id
    user_data[user_id]["screenshots"].append(photo)
    save_data(user_data)
    
    count = len(user_data[user_id]["screenshots"])
    await message.answer(
        f"✅ <b>Скриншот #{count} сохранен!</b>\n\n"
        f"Отправь еще или напиши /done",
        parse_mode="HTML"
    )

@dp.message(Command("done"))
async def send_to_admin(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_data:
        await message.answer("❌ Нет активной заявки. Начни с /start")
        return
    
    data = user_data[user_id]
    screenshots = data.get("screenshots", [])
    
    if not screenshots:
        await message.answer("❌ Ты не отправил ни одного скриншота!")
        return
    
    username = message.from_user.username or message.from_user.first_name
    
    if ADMIN_ID:
        try:
            # Отправляем админу
            await bot.send_message(
                ADMIN_ID,
                f"🆕 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ!</b>\n\n"
                f"👤 <b>Продавец:</b> @{username}\n"
                f"🎮 <b>Игра:</b> {data['game']}\n"
                f"📸 <b>Скриншотов:</b> {len(screenshots)}\n\n"
                f"<i>Напиши цену для этого аккаунта в ответ на это сообщение</i>",
                parse_mode="HTML"
            )
            
            for idx, photo in enumerate(screenshots, 1):
                await bot.send_photo(ADMIN_ID, photo, caption=f"📸 Скриншот #{idx}")
            
            await message.answer(
                f"✅ <b>Заявка отправлена на оценку!</b>\n\n"
                f"Админ скоро напишет цену. Ожидай сообщения 💰",
                parse_mode="HTML"
            )
            
            del user_data[user_id]
            save_data(user_data)
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке: {e}")
    else:
        await message.answer(
            f"✅ <b>Заявка принята!</b>\n\n"
            f"Игра: {data['game']}\n"
            f"Скриншотов: {len(screenshots)}\n\n"
            f"⚠️ Админ еще не настроен, но твои данные сохранены.",
            parse_mode="HTML"
        )

@dp.message()
async def admin_response(message: types.Message):
    # Если админ отвечает на сообщение с заявкой
    if ADMIN_ID and message.chat.id == ADMIN_ID and message.reply_to_message:
        # Здесь можно добавить логику ответа пользователю
        await message.reply("✅ Цена отправлена (функция дорабатывается)")

async def main():
    print("=" * 50)
    print("🤖 ТЕЛЕГРАМ БОТ ЗАПУЩЕН!")
    me = await bot.get_me()
    print(f"✅ Бот: @{me.username}")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
