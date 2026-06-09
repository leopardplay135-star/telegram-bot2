import asyncio
import json
import os
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

bot = Bot(token=TOKEN)
dp = Dispatcher()

ACCOUNTS_FILE = "accounts.json"
SELL_REQUESTS_FILE = "sell_requests.json"
BUY_REQUESTS_FILE = "buy_requests.json"

def load_data(filename, default):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return default

def save_data(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

accounts = load_data(ACCOUNTS_FILE, [])
sell_requests = load_data(SELL_REQUESTS_FILE, {})
buy_requests = load_data(BUY_REQUESTS_FILE, {})
user_temp = {}

GAME_BRAWL = "brawl"
GAME_FORTNITE = "fortnite"

def get_game_display(game_code):
    return "Brawl Stars" if game_code == GAME_BRAWL else "Fortnite"

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Продать", callback_data="sell"),
         InlineKeyboardButton(text="🛒 Купить", callback_data="buy")]
    ])
    return kb

def game_menu(action):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Brawl Stars", callback_data=f"{action}_{GAME_BRAWL}"),
         InlineKeyboardButton(text="⚔️ Fortnite", callback_data=f"{action}_{GAME_FORTNITE}")]
    ])
    return kb

def accounts_list_by_game(game_code):
    acc_list = [a for a in accounts if a.get("game_code") == game_code and a.get("status") == "available"]
    if not acc_list:
        return None
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for a in acc_list:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{a['name']} - {a['price']} руб.", callback_data=f"view_{a['id']}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return kb

def admin_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="admin_add")],
        [InlineKeyboardButton(text="📋 Список", callback_data="admin_list")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="admin_delete")]
    ])
    return kb

# ==================== СТАРТ ====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("🏪 Добро пожаловать!", reply_markup=main_menu())

# ==================== ПРОДАЖА ====================
@dp.callback_query(lambda c: c.data == "sell")
async def start_sell(callback):
    await callback.message.edit_text("💰 Продажа\nВыберите игру:", reply_markup=game_menu("sell"))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("sell_"))
async def sell_game(callback):
    game_code = callback.data.split("_")[1]
    uid = str(callback.from_user.id)
    user_temp[uid] = {"step": "selling", "game_code": game_code, "photos": []}
    await callback.message.edit_text(f"📱 {get_game_display(game_code)}\n\nОтправьте фото. Когда закончите - /done_sell")
    await callback.answer()

@dp.message(F.photo)
async def save_photo(message: types.Message):
    uid = str(message.from_user.id)
    if uid in user_temp and user_temp[uid].get("step") == "selling":
        user_temp[uid]["photos"].append(message.photo[-1].file_id)
        await message.answer(f"✅ Скриншот #{len(user_temp[uid]['photos'])} сохранен!")
    elif uid in user_temp and user_temp[uid].get("step") == "admin_add":
        user_temp[uid]["photos"].append(message.photo[-1].file_id)
        await message.answer(f"✅ Скриншот #{len(user_temp[uid]['photos'])} сохранен!")

@dp.message(Command("done_sell"))
async def done_sell(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in user_temp or user_temp[uid].get("step") != "selling":
        await message.answer("❌ Нет активной продажи")
        return
    
    if not user_temp[uid]["photos"]:
        await message.answer("❌ Нет фото! Сначала отправьте фото")
        return
    
    rid = str(int(time.time()))
    username = message.from_user.username or message.from_user.first_name
    
    sell_requests[rid] = {
        "user_id": uid, "username": username,
        "game_code": user_temp[uid]["game_code"],
        "photos": user_temp[uid]["photos"], "status": "pending"
    }
    save_data(SELL_REQUESTS_FILE, sell_requests)
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 ЗАЯВКА #{rid}\n👤 @{username}\n🎮 {get_game_display(user_temp[uid]['game_code'])}\n📸 {len(user_temp[uid]['photos'])}\n\n/price {rid} ЦЕНА"
    )
    for p in user_temp[uid]["photos"]:
        await bot.send_photo(ADMIN_ID, p)
    
    await message.answer(f"✅ Заявка #{rid} отправлена!")
    del user_temp[uid]

@dp.message(Command("price"))
async def set_price(message: types.Message):
    if message.chat.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("Формат: /price НОМЕР ЦЕНА")
        return
    rid, price = parts[1], parts[2]
    if rid not in sell_requests:
        await message.reply("Заявка не найдена")
        return
    req = sell_requests[rid]
    await bot.send_message(int(req["user_id"]), f"💰 Ваш аккаунт оценили!\nЦена: {price}\nСвяжитесь с админом: @{message.from_user.username}")
    await message.reply(f"✅ Цена отправлена")

# ==================== ПОКУПКА ====================
@dp.callback_query(lambda c: c.data == "buy")
async def start_buy(callback):
    await callback.message.edit_text("🛒 Покупка\nВыберите игру:", reply_markup=game_menu("buy"))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_game(callback):
    game_code = callback.data.split("_")[1]
    kb = accounts_list_by_game(game_code)
    if not kb:
        await callback.message.edit_text(f"📭 {get_game_display(game_code)}\nНет аккаунтов")
        return
    await callback.message.edit_text(f"📱 {get_game_display(game_code)}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_"))
async def view_account(callback):
    acc_id = callback.data.split("_")[1]
    acc = None
    for a in accounts:
        if a["id"] == acc_id:
            acc = a
            break
    
    if not acc or acc["status"] != "available":
        await callback.message.answer("❌ Аккаунт не доступен")
        return
    
    for p in acc.get("photos", []):
        await callback.message.answer_photo(p)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_acc_{acc_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_accounts")]
    ])
    await callback.message.answer(f"🎮 {acc['name']}\n💰 {acc['price']} руб.\n📝 {acc['description']}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_acc_"))
async def buy_account(callback):
    acc_id = callback.data.split("_")[2]
    acc = None
    for a in accounts:
        if a["id"] == acc_id:
            acc = a
            break
    
    if not acc or acc["status"] != "available":
        await callback.message.answer("❌ Аккаунт уже куплен")
        return
    
    rid = str(int(time.time()))
    username = callback.from_user.username or callback.from_user.first_name
    
    buy_requests[rid] = {
        "user_id": str(callback.from_user.id), "username": username,
        "account_id": acc_id, "account_name": acc["name"],
        "account_data": acc.get("login_data", ""), "price": acc["price"],
        "status": "pending"
    }
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(ADMIN_ID, f"🛒 ЗАПРОС #{rid}\n👤 @{username}\n🎮 {acc['name']}\n💰 {acc['price']} руб.\n\n/confirm {rid}\n/reject {rid}")
    await callback.message.edit_text(f"✅ Запрос #{rid} отправлен!\nАдмин свяжется с вами")
    await callback.answer()

# ==================== АДМИН ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID: return
    await message.answer("👑 Админ панель", reply_markup=admin_menu())

# ДОБАВЛЕНИЕ АККАУНТА - ПРОСТОЙ СПОСОБ
@dp.callback_query(lambda c: c.data == "admin_add")
async def admin_add_start(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещен!")
        return
    
    uid = str(callback.from_user.id)
    user_temp[uid] = {"step": "admin_add", "account": {}, "photos": []}
    
    await callback.message.edit_text(
        "➕ <b>ДОБАВЛЕНИЕ АККАУНТА</b>\n\n"
        "Сначала отправьте данные в формате:\n"
        "<code>brawl:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Пример:\n"
        "<code>brawl:Легендарка:5000:Полный набор:user:pass</code>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.text, lambda m: m.chat.id == ADMIN_ID)
async def admin_add_data(message: types.Message):
    uid = str(message.from_user.id)
    
    if uid not in user_temp or user_temp[uid].get("step") != "admin_add":
        return
    
    parts = message.text.split(":", 5)
    if len(parts) < 6:
        await message.reply("❌ Формат: игра:название:цена:описание:логин:пароль")
        return
    
    game_input = parts[0].lower()
    if "brawl" in game_input:
        game_code = GAME_BRAWL
    elif "fort" in game_input:
        game_code = GAME_FORTNITE
    else:
        await message.reply("❌ Игра: brawl или fortnite")
        return
    
    user_temp[uid]["account"] = {
        "game_code": game_code,
        "name": parts[1].strip(),
        "price": int(parts[2].strip()),
        "description": parts[3].strip(),
        "login_data": f"{parts[4].strip()}:{parts[5].strip()}"
    }
    
    await message.reply(
        f"✅ Данные приняты!\n"
        f"🎮 {get_game_display(game_code)}\n"
        f"🎯 {parts[1]}\n"
        f"💰 {parts[2]} руб.\n\n"
        f"📸 Теперь отправьте СКРИНШОТЫ (можно несколько)\n"
        f"Когда закончите - /save"
    )

@dp.message(Command("save"))
async def admin_save_account(message: types.Message):
    if message.chat.id != ADMIN_ID: return
    
    uid = str(message.from_user.id)
    
    if uid not in user_temp or user_temp[uid].get("step") != "admin_add":
        await message.reply("❌ Нет активного добавления. Используйте /admin → Добавить")
        return
    
    if not user_temp[uid]["photos"]:
        await message.reply("❌ Нет скриншотов! Сначала отправьте фото")
        return
    
    acc = user_temp[uid]["account"]
    acc["photos"] = user_temp[uid]["photos"]
    acc["id"] = str(int(time.time()))
    acc["status"] = "available"
    acc["created_at"] = datetime.now().isoformat()
    
    accounts.append(acc)
    save_data(ACCOUNTS_FILE, accounts)
    
    await message.reply(
        f"✅ <b>Аккаунт добавлен!</b>\n\n"
        f"🎮 {get_game_display(acc['game_code'])}\n"
        f"🎯 {acc['name']}\n"
        f"💰 {acc['price']} руб.\n"
        f"📸 {len(acc['photos'])} скриншотов",
        parse_mode="HTML"
    )
    
    del user_temp[uid]

@dp.callback_query(lambda c: c.data == "admin_list")
async def admin_list(callback):
    if callback.from_user.id != ADMIN_ID: return
    if not accounts:
        await callback.message.edit_text("Нет аккаунтов")
        return
    text = "📋 Аккаунты:\n"
    for a in accounts:
        emoji = "🟢" if a["status"] == "available" else "🔴"
        text += f"{emoji} {a['name']} - {a['price']} руб.\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_delete")
async def admin_delete_list(callback):
    if callback.from_user.id != ADMIN_ID: return
    if not accounts:
        await callback.message.edit_text("Нет аккаунтов")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for a in accounts:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {a['name']}", callback_data=f"del_{a['id']}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")])
    await callback.message.edit_text("🗑 Выберите аккаунт для удаления:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_"))
async def admin_delete_confirm(callback):
    if callback.from_user.id != ADMIN_ID: return
    acc_id = callback.data.split("_")[1]
    acc = next((a for a in accounts if a["id"] == acc_id), None)
    if not acc:
        await callback.message.edit_text("Не найден")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА", callback_data=f"del_yes_{acc_id}"),
         InlineKeyboardButton(text="❌ НЕТ", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(f"Удалить {acc['name']}?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_yes_"))
async def admin_delete_do(callback):
    if callback.from_user.id != ADMIN_ID: return
    acc_id = callback.data.split("_")[2]
    global accounts
    accounts = [a for a in accounts if a["id"] != acc_id]
    save_data(ACCOUNTS_FILE, accounts)
    await callback.message.edit_text("✅ Удалено")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_sell")
async def view_sell(callback):
    if callback.from_user.id != ADMIN_ID: return
    pending = {k:v for k,v in sell_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("Нет заявок")
        return
    text = "📝 Заявки:\n"
    for rid, req in pending.items():
        text += f"{rid} | @{req['username']}\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_buy")
async def view_buy(callback):
    if callback.from_user.id != ADMIN_ID: return
    pending = {k:v for k,v in buy_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("Нет заявок")
        return
    text = "⏳ Заявки на покупку:\n"
    for rid, req in pending.items():
        text += f"{rid} | @{req['username']} | {req['account_name']} | {req['price']} руб.\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.message(Command("confirm"))
async def confirm_buy(message: types.Message):
    if message.chat.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Формат: /confirm НОМЕР")
        return
    rid = parts[1]
    if rid not in buy_requests:
        await message.reply("Не найдено")
        return
    req = buy_requests[rid]
    req["status"] = "confirmed"
    save_data(BUY_REQUESTS_FILE, buy_requests)
    await bot.send_message(int(req["user_id"]), f"✅ Покупка подтверждена!\n🎯 {req['account_name']}\n🔐 Данные: {req['account_data']}")
    for a in accounts:
        if a["id"] == req["account_id"]:
            a["status"] = "sold"
            save_data(ACCOUNTS_FILE, accounts)
            break
    await message.reply(f"✅ Подтверждено")

@dp.message(Command("reject"))
async def reject_buy(message: types.Message):
    if message.chat.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Формат: /reject НОМЕР")
        return
    rid = parts[1]
    if rid not in buy_requests:
        await message.reply("Не найдено")
        return
    req = buy_requests[rid]
    req["status"] = "rejected"
    save_data(BUY_REQUESTS_FILE, buy_requests)
    await bot.send_message(int(req["user_id"]), "❌ Оплата не прошла. Свяжитесь с админом")
    await message.reply(f"❌ Отклонено")

@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text("👑 Админ панель", reply_markup=admin_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback):
    await callback.message.edit_text("🏪 Добро пожаловать!", reply_markup=main_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_accounts")
async def back_to_accounts(callback):
    await start_buy(callback)

async def main():
    print("🤖 БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
