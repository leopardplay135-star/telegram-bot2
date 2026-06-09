import asyncio
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========== НАСТРОЙКИ ==========
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
            # Сохраняем ID пользователя, чтобы потом знать кому отвечать
            user_data[user_id]["step"] = "waiting_for_price"
            user_data[user_id]["username"] = username
            user_data[user_id]["game"] = data["game"]
            save_data(user_data)
            
            # Отправляем админу с указанием user_id в тексте
            await bot.send_message(
                ADMIN_ID,
                f"🆕 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ!</b>\n\n"
                f"🆔 <b>ID продавца:</b> <code>{user_id}</code>\n"
                f"👤 <b>Username:</b> @{username}\n"
                f"🎮 <b>Игра:</b> {data['game']}\n"
                f"📸 <b>Скриншотов:</b> {len(screenshots)}\n\n"
                f"<i>📝 Напиши цену для этого аккаунта в ответ на это сообщение</i>\n"
                f"(Бот отправит цену автоматически)",
                parse_mode="HTML"
            )
            
            for idx, photo in enumerate(screenshots, 1):
                await bot.send_photo(ADMIN_ID, photo, caption=f"📸 Скриншот #{idx}")
            
            await message.answer(
                f"✅ <b>Заявка отправлена на оценку!</b>\n\n"
                f"Админ скоро напишет цену. Ожидай сообщения 💰",
                parse_mode="HTML"
            )
            
        except Exception as e:
            await message.answer(f"❌ Ошибка при отправке: {e}")
    else:
        await message.answer("⚠️ Админ не настроен")

# ========== ГЛАВНАЯ ФУНКЦИЯ - ОТПРАВКА ЦЕНЫ ПОЛЬЗОВАТЕЛЮ ==========
@dp.message(lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
async def send_price_to_user(message: types.Message):
    """
    Когда админ отвечает на сообщение с заявкой,
    бот отправляет цену пользователю
    """
    # Получаем текст ответа админа (цену)
    price = message.text
    
    # Ищем в переписке с админом сообщение, на которое он ответил
    replied_msg = message.reply_to_message
    
    if not replied_msg:
        await message.answer("❌ Ответь на сообщение с заявкой")
        return
    
    # Из сообщения админу достаем ID пользователя
    # Оно сохранено в тексте: "🆔 ID продавца: 123456789"
    import re
    match = re.search(r'🆔 ID продавца: <code>(\d+)</code>', replied_msg.html_text)
    
    if not match:
        await message.answer("❌ Не удалось найти ID пользователя в сообщении")
        return
    
    user_id = match.group(1)
    game = None
    
    # Ищем игру в данных
    if user_id in user_data:
        game = user_data[user_id].get("game", "аккаунт")
    else:
        # Если данных нет, пробуем найти игру в тексте сообщения
        game_match = re.search(r'🎮 <b>Игра:</b> (.+)', replied_msg.html_text)
        if game_match:
            game = game_match.group(1)
        else:
            game = "аккаунт"
    
    try:
        # Отправляем цену пользователю
        await bot.send_message(
            int(user_id),
            f"💰 <b>Твой {game} оценили!</b>\n\n"
            f"Предложенная цена: <b>{price}</b>\n\n"
            f"Если согласен, свяжись с админом: @{message.from_user.username}\n"
            f"Если нет — начни заново с /start",
            parse_mode="HTML"
        )
        
        # Уведомляем админа об успехе
        await message.reply(f"✅ Цена отправлена пользователю!\n\n💰 Цена: {price}\n🆔 ID: {user_id}")
        
        # Удаляем данные пользователя (заявка обработана)
        if user_id in user_data:
            del user_data[user_id]
            save_data(user_data)
            
    except Exception as e:
        await message.reply(f"❌ Ошибка при отправке пользователю: {e}")

# ========== ЗАПУСК ==========
async def main():
    print("=" * 50)
    print("🤖 ТЕЛЕГРАМ БОТ ЗАПУЩЕН!")
    me = await bot.get_me()
    print(f"✅ Бот: @{me.username}")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
