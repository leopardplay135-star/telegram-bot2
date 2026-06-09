cat > test_bot.py << 'EOF'
import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Простое хранилище для скриншотов
admin_screenshots = []

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот работает! Отправь фото админу")

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    
    if user_id == ADMIN_ID:
        admin_screenshots.append(photo_id)
        await message.answer(f"✅ Админ, скриншот #{len(admin_screenshots)} получен!")
    else:
        await message.answer(f"✅ Обычный пользователь, фото получено!")

@dp.message(Command("check"))
async def check(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"Скриншотов от админа: {len(admin_screenshots)}")

async def main():
    print("ТЕСТОВЫЙ БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
EOF
