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

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не задан!")
    exit(1)

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
        json.dump(data, f, indent=2, ensure_ascii=False)

accounts = load_data(ACCOUNTS_FILE, [])
sell_requests = load_data(SELL_REQUESTS_FILE, {})
buy_requests = load_data(BUY_REQUESTS_FILE, {})
user_temp = {}

GAME_BRAWL = "brawl"
GAME_FORTNITE = "fortnite"

def get_game_display(game_code):
    if game_code == GAME_BRAWL:
        return "Brawl Stars"
    elif game_code == GAME_FORTNITE:
        return "Fortnite"
    return "Неизвестно"

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Продать аккаунт", callback_data="sell"),
         InlineKeyboardButton(text="🛒 Купить аккаунт", callback_data="buy")]
    ])
    return keyboard

def game_menu(action):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Brawl Stars", callback_data=f"{action}_{GAME_BRAWL}"),
         InlineKeyboardButton(text="⚔️ Fortnite", callback_data=f"{action}_{GAME_FORTNITE}")]
    ])
    return keyboard

def accounts_list_by_game(game_code):
    acc_list = [acc for acc in accounts if acc.get("game_code") == game_code and acc.get("status") == "available"]
    if not acc_list:
        return None
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for acc in acc_list:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🎮 {acc['name']} - {acc['price']} руб.",
                callback_data=f"view_acc_{acc['id']}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return keyboard

def account_action_menu(account_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить аккаунт", callback_data=f"buy_acc_{account_id}")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="back_to_accounts")]
    ])
    return keyboard

def admin_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="admin_add_account")],
        [InlineKeyboardButton(text="📋 Список аккаунтов", callback_data="admin_list_accounts")],
        [InlineKeyboardButton(text="🗑 Удалить аккаунт", callback_data="admin_delete_account")],
        [InlineKeyboardButton(text="⏳ Заявки на покупку", callback_data="admin_view_buy_requests")],
        [InlineKeyboardButton(text="📝 Заявки на продажу", callback_data="admin_view_sell_requests")]
    ])
    return keyboard

def delete_accounts_list():
    if not accounts:
        return None
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for acc in accounts:
        status_emoji = "🟢" if acc["status"] == "available" else "🔴"
        game_name = get_game_display(acc.get("game_code", "unknown"))
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} [{game_name}] {acc['name']} - {acc['price']} руб.",
                callback_data=f"del_acc_{acc['id']}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")])
    return keyboard

# ==================== ПРОДАЖА ====================
@dp.message(Command("start"))
async def start(message: types.Message):
    welcome_text = (
        "🏪 <b>ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН АККАУНТОВ!</b>\n\n"
        "Здесь вы можете:\n"
        "💰 <b>Продать</b> свой аккаунт — отправьте скриншоты, и админ оценит его\n"
        "🛒 <b>Купить</b> аккаунт — выберите игру и просмотрите доступные аккаунты\n\n"
        "🔥 <b>Почему выбирают нас?</b>\n"
        "• Быстрая оценка аккаунтов\n"
        "• Безопасные сделки\n"
        "• Поддержка 24/7\n\n"
        "⬇️ <b>Выберите действие ниже:</b>"
    )
    await message.answer(welcome_text, reply_markup=main_menu(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "sell")
async def start_sell(callback):
    await callback.message.edit_text(
        "💰 <b>Продажа аккаунта</b>\n\nВыберите игру:",
        reply_markup=game_menu("sell"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("sell_"))
async def sell_game_selected(callback):
    game_code = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    user_temp[user_id] = {"step": "selling", "game_code": game_code, "screenshots": []}
    await callback.message.edit_text(
        f"📱 <b>Выбрано: {get_game_display(game_code)}</b>\n\n"
        f"Отправьте скриншоты аккаунта (можно несколько)\n"
        f"Когда закончите, нажмите /done_sell",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo)
async def save_sell_photo(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "selling":
        return
    
    photo = message.photo[-1].file_id
    user_temp[user_id]["screenshots"].append(photo)
    await message.answer(f"✅ Скриншот #{len(user_temp[user_id]['screenshots'])} сохранен!")

@dp.message(Command("done_sell"))
async def finish_sell(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "selling":
        await message.answer("❌ Нет активной заявки. Нажмите /start и выберите 'Продать'")
        return
    
    screenshots = user_temp[user_id].get("screenshots", [])
    
    if not screenshots:
        await message.answer("❌ Вы не отправили ни одного скриншота! Сначала отправьте фото, потом /done_sell")
        return
    
    request_id = str(int(time.time()))
    username = message.from_user.username or message.from_user.first_name
    
    sell_requests[request_id] = {
        "user_id": user_id, "username": username,
        "game_code": user_temp[user_id]["game_code"],
        "screenshots": screenshots, "status": "pending"
    }
    save_data(SELL_REQUESTS_FILE, sell_requests)
    
    game_name = get_game_display(user_temp[user_id]["game_code"])
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 ЗАЯВКА #{request_id}\n👤 @{username}\n🎮 {game_name}\n📸 {len(screenshots)}\n\n/price_sell {request_id} ЦЕНА",
        parse_mode="HTML"
    )
    
    for photo in screenshots:
        await bot.send_photo(ADMIN_ID, photo)
    
    await message.answer(f"✅ Заявка #{request_id} отправлена!")
    del user_temp[user_id]

@dp.message(Command("price_sell"))
async def admin_send_price(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("Формат: /price_sell НОМЕР ЦЕНА")
        return
    
    request_id, price = parts[1], parts[2]
    
    if request_id not in sell_requests:
        await message.reply("Заявка не найдена")
        return
    
    req = sell_requests[request_id]
    await bot.send_message(int(req["user_id"]), f"💰 Ваш аккаунт оценили!\nЦена: {price}\nСвяжитесь с админом: @{message.from_user.username}")
    await message.reply(f"✅ Цена отправлена @{req['username']}")

# ==================== ПОКУПКА ====================
@dp.callback_query(lambda c: c.data == "buy")
async def start_buy(callback):
    await callback.message.edit_text(
        "🛒 <b>Покупка аккаунта</b>\n\nВыберите игру:",
        reply_markup=game_menu("buy"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_") and c.data.count("_") == 1)
async def buy_game_selected(callback):
    game_code = callback.data.split("_")[1]
    keyboard = accounts_list_by_game(game_code)
    if not keyboard:
        await callback.message.edit_text(f"📭 {get_game_display(game_code)}\n\nНет аккаунтов в продаже")
        await callback.answer()
        return
    await callback.message.edit_text(f"📱 {get_game_display(game_code)}\n\nДоступные аккаунты:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_acc_"))
async def view_account(callback):
    account_id = callback.data.split("_")[2]
    account = next((a for a in accounts if a["id"] == account_id), None)
    
    if not account or account["status"] != "available":
        await callback.message.answer("❌ Аккаунт не доступен")
        return
    
    for photo in account.get("screenshots", []):
        await callback.message.answer_photo(photo)
    
    await callback.message.answer(
        f"🎮 {account['name']}\n💰 {account['price']} руб.\n📝 {account['description']}",
        reply_markup=account_action_menu(account_id)
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_acc_"))
async def buy_account(callback):
    account_id = callback.data.split("_")[2]
    account = next((a for a in accounts if a["id"] == account_id), None)
    
    if not account or account["status"] != "available":
        await callback.message.answer("❌ Аккаунт уже куплен")
        return
    
    request_id = str(int(time.time()))
    username = callback.from_user.username or callback.from_user.first_name
    
    buy_requests[request_id] = {
        "user_id": str(callback.from_user.id), "username": username,
        "account_id": account_id, "account_name": account["name"],
        "account_data": account.get("login_data", ""), "price": account["price"],
        "game_code": account["game_code"], "status": "pending"
    }
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(
        ADMIN_ID,
        f"🛒 ЗАПРОС #{request_id}\n👤 @{username}\n🎮 {account['name']}\n💰 {account['price']} руб.\n\n/confirm_buy {request_id}\n/reject_buy {request_id}"
    )
    
    await callback.message.edit_text(f"✅ Запрос #{request_id} отправлен!\nВ течение нескольких минут с вами свяжется Админ насчет оплаты.")
    await callback.answer()

# ==================== АДМИН КОМАНДЫ ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    await message.answer("👑 Панель администратора", reply_markup=admin_menu())

# ПРОСТОЙ СПОСОБ ДОБАВЛЕНИЯ АККАУНТА - через команду!
@dp.message(Command("add_acc"))
async def add_account_command(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=6)
    if len(parts) < 7:
        await message.reply(
            "❌ ФОРМАТ:\n"
            "/add_acc игра название цена описание логин пароль\n\n"
            "Пример:\n"
            "/add_acc brawl Легендарка 5000 Полный_набор login pass\n\n"
            "Игра: brawl или fortnite\n"
            "Описание пишите без пробелов или с нижним подчеркиванием"
        )
        return
    
    game_input = parts[1].lower()
    name = parts[2]
    price = int(parts[3])
    description = parts[4].replace("_", " ")
    login = parts[5]
    password = parts[6]
    
    if "brawl" in game_input:
        game_code = GAME_BRAWL
    elif "fortnite" in game_input:
        game_code = GAME_FORTNITE
    else:
        await message.reply("Игра должна быть brawl или fortnite")
        return
    
    # Сохраняем аккаунт без скриншотов (скриншоты добавятся отдельно)
    if "temp_account" not in user_temp:
        user_temp["temp_account"] = None
    
    user_temp["temp_account"] = {
        "game_code": game_code,
        "name": name,
        "price": price,
        "description": description,
        "login_data": f"{login}:{password}",
        "screenshots": [],
        "status": "available"
    }
    
    await message.reply(
        f"✅ Данные сохранены!\n\n"
        f"🎮 {get_game_display(game_code)}\n"
        f"🎯 {name}\n"
        f"💰 {price} руб.\n\n"
        f"📸 Теперь отправьте СКРИНШОТЫ (можно несколько)\n"
        f"Когда закончите, нажмите /save_acc"
    )

@dp.message(F.photo, lambda m: m.chat.id == ADMIN_ID)
async def save_account_photos(message: types.Message):
    if user_temp.get("temp_account") is None:
        await message.reply("❌ Сначала используйте /add_acc с данными аккаунта")
        return
    
    user_temp["temp_account"]["screenshots"].append(message.photo[-1].file_id)
    count = len(user_temp["temp_account"]["screenshots"])
    await message.reply(f"✅ Скриншот #{count} сохранен! Отправьте еще или /save_acc")

@dp.message(Command("save_acc"))
async def save_account(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    if user_temp.get("temp_account") is None:
        await message.reply("❌ Нет данных. Сначала используйте /add_acc")
        return
    
    acc = user_temp["temp_account"]
    
    if not acc["screenshots"]:
        await message.reply("❌ Добавьте хотя бы один скриншот! Отправьте фото и /save_acc")
        return
    
    acc["id"] = str(int(time.time()))
    acc["created_at"] = datetime.now().isoformat()
    accounts.append(acc)
    save_data(ACCOUNTS_FILE, accounts)
    
    await message.reply(
        f"✅ <b>Аккаунт добавлен!</b>\n\n"
        f"🆔 ID: {acc['id']}\n"
        f"🎮 {get_game_display(acc['game_code'])}\n"
        f"🎯 {acc['name']}\n"
        f"💰 {acc['price']} руб.\n"
        f"📸 Скриншотов: {len(acc['screenshots'])}",
        parse_mode="HTML"
    )
    
    del user_temp["temp_account"]

@dp.callback_query(lambda c: c.data == "admin_add_account")
async def admin_add_account_start(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта (ПРОСТОЙ СПОСОБ)</b>\n\n"
        "Используйте команду:\n\n"
        "<code>/add_acc игра название цена описание логин пароль</code>\n\n"
        "Пример:\n"
        "<code>/add_acc brawl Легендарка 5000 Полный_набор_скинов user123 pass123</code>\n\n"
        "После этого отправьте скриншоты и нажмите /save_acc",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_list_accounts")
async def admin_list_accounts(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    if not accounts:
        await callback.message.edit_text("📭 Нет аккаунтов")
        return
    text = "📋 Аккаунты:\n"
    for a in accounts:
        emoji = "🟢" if a["status"] == "available" else "🔴"
        text += f"{emoji} [{get_game_display(a['game_code'])}] {a['name']} - {a['price']} руб.\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_delete_account")
async def admin_delete_list(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    keyboard = delete_accounts_list()
    if not keyboard:
        await callback.message.edit_text("📭 Нет аккаунтов")
        return
    await callback.message.edit_text("🗑 Выберите аккаунт:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_acc_"))
async def admin_delete_confirm(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    account_id = callback.data.split("_")[2]
    account = next((a for a in accounts if a["id"] == account_id), None)
    if not account:
        await callback.message.edit_text("❌ Не найден")
        return
    user_temp["delete_acc"] = account_id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА", callback_data="del_yes"),
         InlineKeyboardButton(text="❌ НЕТ", callback_data="del_no")]
    ])
    await callback.message.edit_text(f"Удалить {account['name']}?", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "del_yes")
async def admin_delete_do(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    account_id = user_temp.get("delete_acc")
    if account_id:
        global accounts
        accounts = [a for a in accounts if a["id"] != account_id]
        save_data(ACCOUNTS_FILE, accounts)
        await callback.message.edit_text("✅ Удалено")
        del user_temp["delete_acc"]
    else:
        await callback.message.edit_text("❌ Ошибка")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "del_no")
async def admin_delete_cancel(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    if "delete_acc" in user_temp:
        del user_temp["delete_acc"]
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_sell_requests")
async def admin_view_sell(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    pending = {k: v for k, v in sell_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("📭 Нет заявок")
        return
    text = "📝 Заявки на продажу:\n"
    for rid, req in pending.items():
        text += f"{rid} | @{req['username']} | {get_game_display(req['game_code'])}\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_buy_requests")
async def admin_view_buy(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    pending = {k: v for k, v in buy_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("📭 Нет заявок")
        return
    text = "⏳ Заявки на покупку:\n"
    for rid, req in pending.items():
        text += f"{rid} | @{req['username']} | {req['account_name']} | {req['price']} руб.\n"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.message(Command("confirm_buy"))
async def admin_confirm_buy(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Формат: /confirm_buy НОМЕР")
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
    await message.reply(f"✅ Подтверждено @{req['username']}")

@dp.message(Command("reject_buy"))
async def admin_reject_buy(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Формат: /reject_buy НОМЕР")
        return
    rid = parts[1]
    if rid not in buy_requests:
        await message.reply("Не найдено")
        return
    req = buy_requests[rid]
    req["status"] = "rejected"
    save_data(BUY_REQUESTS_FILE, buy_requests)
    await bot.send_message(int(req["user_id"]), "❌ Оплата не прошла. Свяжитесь с админом")
    await message.reply(f"❌ Отклонено @{req['username']}")

@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    await callback.message.edit_text("👑 Панель администратора", reply_markup=admin_menu())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback):
    welcome_text = (
        "🏪 <b>ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН АККАУНТОВ!</b>\n\n"
        "💰 <b>Продать</b> аккаунт — отправьте скриншоты\n"
        "🛒 <b>Купить</b> аккаунт — выберите игру\n\n"
        "⬇️ Выберите действие:"
    )
    await callback.message.edit_text(welcome_text, reply_markup=main_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_accounts")
async def back_to_accounts(callback):
    await start_buy(callback)

async def main():
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН!")
    me = await bot.get_me()
    print(f"✅ @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
