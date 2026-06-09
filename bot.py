import asyncio
import json
import os
import re
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

# Файлы для хранения данных
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

# Хранилища
accounts = load_data(ACCOUNTS_FILE, [])
sell_requests = load_data(SELL_REQUESTS_FILE, {})
buy_requests = load_data(BUY_REQUESTS_FILE, {})
user_temp = {}

# Нормализация названий игр
def normalize_game(game_name):
    game_map = {
        "brawl": "brawl",
        "brawl stars": "brawl",
        "brawlstars": "brawl",
        "fortnite": "fortnite",
        "Brawl Stars": "brawl",
        "Fortnite": "fortnite"
    }
    return game_map.get(game_name.lower(), game_name.lower())

def get_game_display(game_code):
    return "Brawl Stars" if game_code == "brawl" else "Fortnite"

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Продать аккаунт", callback_data="sell"),
         InlineKeyboardButton(text="🛒 Купить аккаунт", callback_data="buy")]
    ])
    return keyboard

def game_menu(action):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Brawl Stars", callback_data=f"{action}_brawl"),
         InlineKeyboardButton(text="⚔️ Fortnite", callback_data=f"{action}_fortnite")]
    ])
    return keyboard

def accounts_list_by_game(game_code):
    # Ищем аккаунты с таким же game_code
    acc_list = [acc for acc in accounts if acc.get("game_code") == game_code and acc.get("status") == "available"]
    
    if not acc_list:
        return None
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for acc in acc_list:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🎮 {acc['name']} - {acc['price']} руб.",
                callback_data=f"view_{acc['id']}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return keyboard

def account_action_menu(account_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить аккаунт", callback_data=f"buy_now_{account_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_accounts")]
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
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} {acc['name']} - {acc['price']} руб. [{acc['status']}]",
                callback_data=f"del_acc_{acc['id']}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад в админку", callback_data="back_to_admin")])
    return keyboard

# ==================== ПРОДАЖА АККАУНТА ====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "🏪 <b>Добро пожаловать в магазин аккаунтов!</b>\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "sell")
async def start_sell(callback):
    await callback.message.edit_text(
        "💰 <b>Продажа аккаунта</b>\n\n"
        "Выберите игру:",
        reply_markup=game_menu("sell"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("sell_"))
async def sell_game_selected(callback):
    game_code = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    game_name = get_game_display(game_code)
    
    user_temp[user_id] = {
        "step": "selling",
        "game": game_name,
        "game_code": game_code,
        "screenshots": []
    }
    
    await callback.message.edit_text(
        f"📱 <b>Выбрано: {game_name}</b>\n\n"
        f"Отправьте скриншоты аккаунта (можно несколько)\n"
        f"Когда закончите, нажмите /done_sell",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo, lambda message: message.chat.id != ADMIN_ID)
async def save_sell_photo(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "selling":
        await message.answer("❌ Сначала нажмите /start и выберите 'Продать аккаунт'")
        return
    
    photo = message.photo[-1].file_id
    user_temp[user_id]["screenshots"].append(photo)
    
    await message.answer(
        f"✅ Скриншот #{len(user_temp[user_id]['screenshots'])} сохранен!\n"
        f"Отправьте еще или нажмите /done_sell"
    )

@dp.message(Command("done_sell"))
async def finish_sell(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "selling":
        await message.answer("❌ Нет активной заявки на продажу")
        return
    
    data = user_temp[user_id]
    screenshots = data.get("screenshots", [])
    
    if not screenshots:
        await message.answer("❌ Отправьте хотя бы один скриншот!")
        return
    
    request_id = str(int(time.time()))
    username = message.from_user.username or message.from_user.first_name
    
    sell_requests[request_id] = {
        "user_id": user_id,
        "username": username,
        "game": data["game"],
        "game_code": data["game_code"],
        "screenshots": screenshots,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(SELL_REQUESTS_FILE, sell_requests)
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ #{request_id}</b>\n\n"
        f"👤 Продавец: @{username}\n"
        f"🎮 Игра: {data['game']}\n"
        f"📸 Скриншотов: {len(screenshots)}\n\n"
        f"<b>Чтобы отправить цену продавцу, напишите:</b>\n"
        f"<code>/price_sell {request_id} ЦЕНА</code>\n\n"
        f"Пример: <code>/price_sell {request_id} 5000 рублей</code>",
        parse_mode="HTML"
    )
    
    for idx, photo in enumerate(screenshots, 1):
        await bot.send_photo(ADMIN_ID, photo, caption=f"Заявка #{request_id} | Скриншот {idx}")
    
    await message.answer(
        f"✅ <b>Заявка на продажу отправлена!</b>\n\n"
        f"Номер заявки: <code>{request_id}</code>\n"
        f"Админ оценит аккаунт и напишет цену в ближайшее время.",
        parse_mode="HTML"
    )
    
    del user_temp[user_id]

@dp.message(Command("price_sell"))
async def admin_send_price(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply(
            "❌ Формат: /price_sell НОМЕР_ЗАЯВКИ ЦЕНА\n"
            "Пример: /price_sell 123456789 5000 рублей"
        )
        return
    
    request_id = parts[1]
    price = parts[2]
    
    if request_id not in sell_requests:
        await message.reply(f"❌ Заявка #{request_id} не найдена!")
        return
    
    request = sell_requests[request_id]
    
    try:
        await bot.send_message(
            int(request["user_id"]),
            f"💰 <b>Ваш аккаунт {request['game']} оценили!</b>\n\n"
            f"Предложенная цена: <b>{price}</b>\n\n"
            f"Если цена устраивает, свяжитесь с админом: @{message.from_user.username}\n"
            f"Если нет - можете начать заново с /start",
            parse_mode="HTML"
        )
        
        sell_requests[request_id]["status"] = "priced"
        sell_requests[request_id]["price"] = price
        save_data(SELL_REQUESTS_FILE, sell_requests)
        
        await message.reply(
            f"✅ Цена отправлена продавцу!\n\n"
            f"👤 Продавец: @{request['username']}\n"
            f"💰 Цена: {price}\n"
            f"🆔 Заявка: #{request_id}"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ==================== ПОКУПКА АККАУНТА ====================
@dp.callback_query(lambda c: c.data == "buy")
async def start_buy(callback):
    await callback.message.edit_text(
        "🛒 <b>Покупка аккаунта</b>\n\n"
        "Выберите игру:",
        reply_markup=game_menu("buy"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_"))
async def buy_game_selected(callback):
    game_code = callback.data.split("_")[1]  # "brawl" или "fortnite"
    game_name = get_game_display(game_code)
    
    keyboard = accounts_list_by_game(game_code)
    
    if not keyboard:
        await callback.message.edit_text(
            f"📭 <b>{game_name}</b>\n\n"
            f"К сожалению, сейчас нет аккаунтов в продаже.\n"
            f"Загляните позже!",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"📱 <b>{game_name}</b>\n\n"
        f"Доступные аккаунты:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_"))
async def view_account(callback):
    account_id = callback.data.split("_")[1]
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    
    if not account or account.get("status") != "available":
        await callback.message.edit_text("❌ Аккаунт больше не доступен!")
        await callback.answer()
        return
    
    # Отправляем фото аккаунта
    if account.get("screenshots"):
        for photo in account["screenshots"]:
            await callback.message.answer_photo(photo)
    
    text = (
        f"🎮 <b>{account['name']}</b>\n\n"
        f"💰 Цена: <b>{account['price']} руб.</b>\n"
        f"🎯 Игра: {get_game_display(account['game_code'])}\n"
        f"📝 Описание:\n{account['description']}\n\n"
        f"⚠️ После оплаты вы получите логин и пароль"
    )
    
    await callback.message.answer(
        text,
        reply_markup=account_action_menu(account_id),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_now_"))
async def buy_account(callback):
    account_id = callback.data.split("_")[2]
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    
    if not account or account.get("status") != "available":
        await callback.message.edit_text("❌ Аккаунт уже куплен!")
        await callback.answer()
        return
    
    user_id = str(callback.from_user.id)
    username = callback.from_user.username or callback.from_user.first_name
    
    request_id = str(int(time.time()))
    buy_requests[request_id] = {
        "user_id": user_id,
        "username": username,
        "account_id": account_id,
        "account_name": account["name"],
        "account_data": account.get("login_data", "Данные выдаст админ после оплаты"),
        "price": account["price"],
        "game": get_game_display(account["game_code"]),
        "game_code": account["game_code"],
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(
        ADMIN_ID,
        f"🛒 <b>НОВЫЙ ЗАПРОС НА ПОКУПКУ #{request_id}</b>\n\n"
        f"👤 Покупатель: @{username}\n"
        f"🎮 Игра: {get_game_display(account['game_code'])}\n"
        f"🎯 Аккаунт: {account['name']}\n"
        f"💰 Сумма: {account['price']} руб.\n\n"
        f"<b>Действия:</b>\n"
        f"✅ Подтвердить: <code>/confirm_buy {request_id}</code>\n"
        f"❌ Отклонить: <code>/reject_buy {request_id}</code>\n\n"
        f"Данные аккаунта:\n<code>{account.get('login_data', 'Не указаны')}</code>",
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"✅ <b>Запрос на покупку отправлен!</b>\n\n"
        f"Номер запроса: <code>{request_id}</code>\n"
        f"Админ свяжется с вами после проверки оплаты.\n\n"
        f"Ожидайте подтверждения!",
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== АДМИН КОМАНДЫ ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    await message.answer(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "admin_delete_account")
async def admin_delete_account_menu(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    keyboard = delete_accounts_list()
    
    if not keyboard:
        await callback.message.edit_text("📭 Нет аккаунтов для удаления")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🗑 <b>Удаление аккаунта</b>\n\n"
        "Выберите аккаунт для удаления:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_acc_"))
async def admin_confirm_delete(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    account_id = callback.data.split("_")[2]
    account = next((acc for acc in accounts if acc["id"] == account_id), None)
    
    if not account:
        await callback.message.edit_text("❌ Аккаунт не найден!")
        await callback.answer()
        return
    
    user_temp["admin_delete"] = {"account_id": account_id, "account_name": account["name"]}
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, удалить", callback_data="confirm_delete_yes"),
         InlineKeyboardButton(text="❌ НЕТ, отмена", callback_data="confirm_delete_no")]
    ])
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить аккаунт?\n\n"
        f"🎮 {get_game_display(account['game_code'])}\n"
        f"🎯 {account['name']}\n"
        f"💰 {account['price']} руб.\n"
        f"📝 {account['description']}\n\n"
        f"<i>Это действие нельзя отменить!</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_delete_yes")
async def admin_delete_confirm(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    if "admin_delete" not in user_temp:
        await callback.message.edit_text("❌ Ошибка! Попробуйте снова.")
        await callback.answer()
        return
    
    account_id = user_temp["admin_delete"]["account_id"]
    account_name = user_temp["admin_delete"]["account_name"]
    
    global accounts
    accounts = [acc for acc in accounts if acc["id"] != account_id]
    save_data(ACCOUNTS_FILE, accounts)
    
    del user_temp["admin_delete"]
    
    await callback.message.edit_text(
        f"✅ <b>Аккаунт удален!</b>\n\n"
        f"Аккаунт '{account_name}' успешно удален из базы.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_delete_no")
async def admin_delete_cancel(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    if "admin_delete" in user_temp:
        del user_temp["admin_delete"]
    
    await callback.message.edit_text("❌ Удаление отменено.", parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    await callback.message.edit_text(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=admin_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_add_account")
async def admin_add_account_start(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    user_temp["admin"] = {"step": "waiting_for_account_data"}
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\n"
        "Сначала отправьте ДАННЫЕ аккаунта в формате:\n\n"
        "<code>Игра:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Игра пишется строго:\n"
        "• <code>Brawl Stars</code>\n"
        "• <code>Fortnite</code>\n\n"
        "Пример:\n"
        "<code>Brawl Stars:Легендарка:5000:Полный набор всех скинов:user123:pass123</code>\n\n"
        "После этого отправьте СКРИНШОТЫ (можно несколько).\n"
        "Когда закончите, нажмите /done_account",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(lambda message: message.chat.id == ADMIN_ID and user_temp.get("admin", {}).get("step") == "waiting_for_account_data")
async def admin_add_account_data(message: types.Message):
    try:
        data = message.text.split(":")
        if len(data) < 6:
            await message.reply("❌ Неверный формат! Нужно 6 полей через двоеточие\n\nПример:\nBrawl Stars:Легендарка:5000:Описание:логин:пароль")
            return
        
        game, name, price, description, login, password = data[0], data[1], data[2], data[3], data[4], data[5]
        
        # Нормализуем игру
        game_code = normalize_game(game)
        
        user_temp["admin"]["temp_account"] = {
            "game_display": game.strip(),
            "game_code": game_code,
            "name": name.strip(),
            "price": int(price.strip()),
            "description": description.strip(),
            "login_data": f"{login.strip()}:{password.strip()}",
            "screenshots": []
        }
        user_temp["admin"]["step"] = "waiting_for_screenshots"
        
        await message.reply(
            f"✅ Данные приняты!\n\n"
            f"🎮 {game}\n"
            f"🎯 {name}\n"
            f"💰 {price} руб.\n\n"
            f"📸 Теперь отправьте СКРИНШОТЫ аккаунта (можно несколько)\n"
            f"Когда закончите, нажмите /done_account"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.photo, lambda message: message.chat.id == ADMIN_ID)
async def admin_add_screenshots(message: types.Message):
    if "admin" not in user_temp or user_temp["admin"].get("step") != "waiting_for_screenshots":
        await message.reply("❌ Сначала отправьте данные аккаунта текстом!\nИспользуйте /admin → 'Добавить аккаунт'")
        return
    
    photo = message.photo[-1].file_id
    user_temp["admin"]["temp_account"]["screenshots"].append(photo)
    await message.reply(f"✅ Скриншот #{len(user_temp['admin']['temp_account']['screenshots'])} сохранен!\nОтправьте еще или /done_account")

@dp.message(Command("done_account"))
async def admin_finish_account(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    if "admin" not in user_temp or user_temp["admin"].get("step") != "waiting_for_screenshots":
        await message.reply("❌ Нет активного добавления аккаунта.\nИспользуйте /admin → 'Добавить аккаунт'")
        return
    
    temp = user_temp["admin"]["temp_account"]
    
    if not temp["screenshots"]:
        await message.reply("❌ Добавьте хотя бы один скриншот!")
        return
    
    account_id = str(int(time.time()))
    accounts.append({
        "id": account_id,
        "game_display": temp["game_display"],
        "game_code": temp["game_code"],
        "name": temp["name"],
        "price": temp["price"],
        "description": temp["description"],
        "login_data": temp["login_data"],
        "screenshots": temp["screenshots"],
        "status": "available",
        "created_at": datetime.now().isoformat()
    })
    save_data(ACCOUNTS_FILE, accounts)
    
    await message.reply(
        f"✅ <b>Аккаунт добавлен!</b>\n\n"
        f"🆔 ID: {account_id}\n"
        f"🎮 {temp['game_display']}\n"
        f"🎯 {temp['name']}\n"
        f"💰 {temp['price']} руб.\n\n"
        f"Теперь аккаунт доступен для покупки!",
        parse_mode="HTML"
    )
    
    del user_temp["admin"]

@dp.callback_query(lambda c: c.data == "admin_list_accounts")
async def admin_list_accounts(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    if not accounts:
        await callback.message.edit_text("📭 Нет добавленных аккаунтов")
        await callback.answer()
        return
    
    text = "📋 <b>Список аккаунтов:</b>\n\n"
    for acc in accounts:
        status_emoji = "🟢" if acc["status"] == "available" else "🔴"
        text += f"{status_emoji} <code>{acc['id']}</code> | {acc['name']} | {acc['price']} руб.\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_sell_requests")
async def admin_view_sell_requests(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    pending = {k: v for k, v in sell_requests.items() if v["status"] == "pending"}
    
    if not pending:
        await callback.message.edit_text("📭 Нет активных заявок на продажу")
        await callback.answer()
        return
    
    text = "📝 <b>Заявки на продажу:</b>\n\n"
    for req_id, req in pending.items():
        text += f"🆔 {req_id} | @{req['username']} | {req['game']}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_buy_requests")
async def admin_view_buy_requests(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    pending = {k: v for k, v in buy_requests.items() if v["status"] == "pending"}
    
    if not pending:
        await callback.message.edit_text("📭 Нет активных заявок на покупку")
        await callback.answer()
        return
    
    text = "⏳ <b>Заявки на покупку:</b>\n\n"
    for req_id, req in pending.items():
        text += f"🆔 {req_id} | @{req['username']} | {req['account_name']} | {req['price']} руб.\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.message(Command("confirm_buy"))
async def confirm_payment(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Формат: /confirm_buy НОМЕР_ЗАПРОСА")
        return
    
    request_id = parts[1]
    
    if request_id not in buy_requests:
        await message.reply("❌ Запрос не найден!")
        return
    
    req = buy_requests[request_id]
    req["status"] = "confirmed"
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(
        int(req["user_id"]),
        f"✅ <b>Поздравляем с покупкой!</b>\n\n"
        f"🎯 Аккаунт: {req['account_name']}\n"
        f"💰 Цена: {req['price']} руб.\n\n"
        f"🔐 <b>Данные для входа:</b>\n"
        f"<code>{req['account_data']}</code>\n\n"
        f"Спасибо за покупку! 🎉",
        parse_mode="HTML"
    )
    
    for acc in accounts:
        if acc["id"] == req["account_id"]:
            acc["status"] = "sold"
            save_data(ACCOUNTS_FILE, accounts)
            break
    
    await message.reply(f"✅ Покупка подтверждена! Данные отправлены @{req['username']}")

@dp.message(Command("reject_buy"))
async def reject_payment(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Формат: /reject_buy НОМЕР_ЗАПРОСА")
        return
    
    request_id = parts[1]
    
    if request_id not in buy_requests:
        await message.reply("❌ Запрос не найден!")
        return
    
    req = buy_requests[request_id]
    req["status"] = "rejected"
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(
        int(req["user_id"]),
        f"❌ <b>К сожалению, оплата не прошла.</b>\n\n"
        f"Пожалуйста, свяжитесь с админом для уточнения деталей.\n"
        f"Вы можете попробовать снова с /start",
        parse_mode="HTML"
    )
    
    await message.reply(f"❌ Запрос #{request_id} отклонен. Пользователь уведомлен.")

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback):
    await callback.message.edit_text(
        "🏪 <b>Добро пожаловать в магазин аккаунтов!</b>\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_accounts")
async def back_to_accounts(callback):
    await start_buy(callback)

# ==================== ЗАПУСК ====================
async def main():
    print("=" * 50)
    print("🤖 МАГАЗИН АККАУНТОВ ЗАПУЩЕН!")
    me = await bot.get_me()
    print(f"✅ Бот: @{me.username}")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"📦 Аккаунтов в базе: {len(accounts)}")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
