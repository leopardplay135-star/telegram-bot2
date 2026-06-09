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
    raise RuntimeError("❌ ОШИБКА: TOKEN не задан в переменных окружения!")

if ADMIN_ID == 0:
    raise RuntimeError("❌ ОШИБКА: ADMIN_ID не задан в переменных окружения!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

ACCOUNTS_FILE = "accounts.json"
SELL_REQUESTS_FILE = "sell_requests.json"
BUY_REQUESTS_FILE = "buy_requests.json"

def load_data(filename, default):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        print(f"⚠️ Ошибка чтения {filename}, создаю новый файл")
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
    return "Fortnite"

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
                callback_data=f"view_{acc['id']}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return keyboard

def account_action_menu(account_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Купить аккаунт", callback_data=f"buy_account_{account_id}")],
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

def delete_accounts_list(admin_id):
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
        "💰 <b>Продать</b> аккаунт — отправьте скриншоты, админ оценит\n"
        "🛒 <b>Купить</b> аккаунт — выберите игру\n\n"
        "⬇️ Выберите действие:"
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
    
    if user_id in user_temp and user_temp[user_id].get("step") == "selling":
        user_temp[user_id]["screenshots"].append(message.photo[-1].file_id)
        await message.answer(f"✅ Скриншот #{len(user_temp[user_id]['screenshots'])} сохранен!")
        return
    
    if user_id in user_temp and user_temp[user_id].get("step") == "admin_adding":
        user_temp[user_id]["screenshots"].append(message.photo[-1].file_id)
        await message.answer(f"✅ Скриншот #{len(user_temp[user_id]['screenshots'])} сохранен! Отправьте еще или /save_account")
        return

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
        "user_id": user_id,
        "username": username,
        "game_code": user_temp[user_id]["game_code"],
        "screenshots": screenshots,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(SELL_REQUESTS_FILE, sell_requests)
    
    game_name = get_game_display(user_temp[user_id]["game_code"])
    
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ #{request_id}</b>\n\n"
        f"👤 Продавец: @{username}\n"
        f"🎮 Игра: {game_name}\n"
        f"📸 Скриншотов: {len(screenshots)}\n\n"
        f"<b>Чтобы отправить цену:</b>\n"
        f"<code>/price_sell {request_id} ЦЕНА</code>",
        parse_mode="HTML"
    )
    
    for photo in screenshots:
        await bot.send_photo(ADMIN_ID, photo)
    
    await message.answer(
        f"✅ <b>Заявка на продажу отправлена!</b>\n\n"
        f"Номер заявки: <code>{request_id}</code>",
        parse_mode="HTML"
    )
    
    del user_temp[user_id]

@dp.message(Command("price_sell"))
async def admin_send_price(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("❌ Формат: /price_sell НОМЕР ЦЕНА\nПример: /price_sell 123456789 5000")
        return
    
    request_id = parts[1]
    price = parts[2]
    
    if request_id not in sell_requests:
        await message.reply(f"❌ Заявка #{request_id} не найдена!")
        return
    
    req = sell_requests[request_id]
    
    try:
        await bot.send_message(
            int(req["user_id"]),
            f"💰 <b>Ваш аккаунт оценен!</b>\n\n"
            f"Предложенная цена: <b>{price}</b>\n\n"
            f"Если цена устраивает, свяжитесь с админом: @{message.from_user.username}",
            parse_mode="HTML"
        )
        await message.reply(f"✅ Цена отправлена продавцу @{req['username']}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# ==================== ПОКУПКА ====================
@dp.callback_query(lambda c: c.data == "buy")
async def start_buy(callback):
    await callback.message.edit_text(
        "🛒 <b>Покупка аккаунта</b>\n\nВыберите игру:",
        reply_markup=game_menu("buy"),
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("buy_") and not c.data.startswith("buy_account_"))
async def buy_game_selected(callback):
    game_code = callback.data.split("_")[1]
    keyboard = accounts_list_by_game(game_code)
    
    user_id = str(callback.from_user.id)
    if user_id not in user_temp:
        user_temp[user_id] = {}
    user_temp[user_id]["last_game"] = game_code
    
    if not keyboard:
        await callback.message.edit_text(
            f"📭 <b>{get_game_display(game_code)}</b>\n\n"
            f"К сожалению, сейчас нет аккаунтов в продаже.\nЗагляните позже!",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"📱 <b>{get_game_display(game_code)}</b>\n\nДоступные аккаунты:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("view_"))
async def view_account(callback):
    account_id = callback.data.split("_")[1]
    account = None
    for acc in accounts:
        if acc["id"] == account_id:
            account = acc
            break
    
    if not account or account.get("status") != "available":
        await callback.message.answer("❌ Аккаунт больше не доступен!")
        await callback.answer()
        return
    
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

@dp.callback_query(lambda c: c.data.startswith("buy_account_"))
async def buy_account(callback):
    account_id = callback.data.split("_")[2]
    account = None
    for acc in accounts:
        if acc["id"] == account_id:
            account = acc
            break
    
    if not account or account.get("status") != "available":
        await callback.message.answer("❌ Аккаунт уже куплен!")
        await callback.answer()
        return
    
    request_id = str(int(time.time()))
    username = callback.from_user.username or callback.from_user.first_name
    
    buy_requests[request_id] = {
        "user_id": str(callback.from_user.id),
        "username": username,
        "account_id": account_id,
        "account_name": account["name"],
        "login": account.get("login", "не указан"),
        "password": account.get("password", "не указан"),
        "account_data": account.get("login_data", f"{account.get('login', '')}:{account.get('password', '')}"),
        "price": account["price"],
        "game_code": account["game_code"],
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(BUY_REQUESTS_FILE, buy_requests)
    
    await bot.send_message(
        ADMIN_ID,
        f"🛒 <b>НОВЫЙ ЗАПРОС НА ПОКУПКУ #{request_id}</b>\n\n"
        f"👤 Покупатель: @{username}\n"
        f"🎮 Аккаунт: {account['name']}\n"
        f"💰 Сумма: {account['price']} руб.\n\n"
        f"📝 Логин: {account.get('login', 'не указан')}\n"
        f"🔐 Пароль: {account.get('password', 'не указан')}\n\n"
        f"<b>Действия:</b>\n"
        f"✅ Подтвердить: <code>/confirm_buy {request_id}</code>\n"
        f"❌ Отклонить: <code>/reject_buy {request_id}</code>",
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"✅ <b>Запрос на покупку отправлен!</b>\n\n"
        f"Номер запроса: <code>{request_id}</code>\n"
        f"В течение нескольких минут с вами свяжется Админ насчет оплаты.",
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== АДМИН КОМАНДЫ ====================
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.chat.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    await message.answer("👑 <b>Панель администратора</b>\n\nВыберите действие:", reply_markup=admin_menu(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "admin_add_account")
async def admin_add_start(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    user_id = str(callback.from_user.id)
    user_temp[user_id] = {
        "step": "admin_adding",
        "account_data": None,
        "screenshots": []
    }
    
    await callback.message.edit_text(
        "➕ <b>ДОБАВЛЕНИЕ АККАУНТА</b>\n\n"
        "📝 <b>Шаг 1:</b> Отправьте ДАННЫЕ аккаунта в формате:\n\n"
        "<code>brawl:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Или для Fortnite:\n"
        "<code>fortnite:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Пример:\n"
        "<code>brawl:Легендарка:5000:Полный набор скинов:user123:pass123</code>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.chat.id == ADMIN_ID, F.text, ~F.text.startswith("/"))
async def admin_process_data(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "admin_adding":
        return
    
    if user_temp[user_id].get("account_data") is not None:
        return
    
    try:
        parts = message.text.split(":", 5)
        if len(parts) < 6:
            await message.reply("❌ Неверный формат!\n\nНужно: игра:название:цена:описание:логин:пароль")
            return
        
        game_input = parts[0].lower().strip()
        if "brawl" in game_input:
            game_code = GAME_BRAWL
        elif "fortnite" in game_input or game_input == "fort":
            game_code = GAME_FORTNITE
        else:
            await message.reply("❌ Неизвестная игра. Используйте 'brawl' или 'fortnite'")
            return
        
        try:
            price = int(parts[2].strip())
        except ValueError:
            await message.reply("❌ Цена должна быть числом!")
            return
        
        login = parts[4].strip()
        password = parts[5].strip()
        
        user_temp[user_id]["account_data"] = {
            "game_code": game_code,
            "name": parts[1].strip(),
            "price": price,
            "description": parts[3].strip(),
            "login": login,
            "password": password,
            "login_data": f"{login}:{password}"
        }
        
        await message.reply(
            f"✅ <b>Данные приняты!</b>\n\n"
            f"🎮 {get_game_display(game_code)}\n"
            f"🎯 {parts[1]}\n"
            f"💰 {price} руб.\n\n"
            f"📸 <b>Шаг 2:</b> Теперь отправьте СКРИНШОТЫ (можно несколько)\n"
            f"Когда закончите, нажмите <b>/save_account</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(Command("save_account"))
async def admin_save_account(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    user_id = str(message.from_user.id)
    
    if user_id not in user_temp or user_temp[user_id].get("step") != "admin_adding":
        await message.reply("❌ Нет активного добавления. Используйте /admin → 'Добавить аккаунт'")
        return
    
    if user_temp[user_id].get("account_data") is None:
        await message.reply("❌ Сначала отправьте ДАННЫЕ аккаунта текстом!\n\nФормат: brawl:Название:Цена:Описание:Логин:Пароль")
        return
    
    if not user_temp[user_id].get("screenshots"):
        await message.reply("❌ Добавьте хотя бы один скриншот! Отправьте фото и снова /save_account")
        return
    
    acc_data = user_temp[user_id]["account_data"]
    acc = {
        "id": str(int(time.time())),
        "game_code": acc_data["game_code"],
        "name": acc_data["name"],
        "price": acc_data["price"],
        "description": acc_data["description"],
        "login": acc_data["login"],
        "password": acc_data["password"],
        "login_data": acc_data["login_data"],
        "screenshots": user_temp[user_id]["screenshots"],
        "status": "available",
        "created_at": datetime.now().isoformat()
    }
    
    accounts.append(acc)
    save_data(ACCOUNTS_FILE, accounts)
    
    await message.reply(
        f"✅ <b>Аккаунт успешно добавлен!</b>\n\n"
        f"🆔 ID: {acc['id']}\n"
        f"🎮 {get_game_display(acc['game_code'])}\n"
        f"🎯 {acc['name']}\n"
        f"💰 {acc['price']} руб.\n"
        f"📸 Скриншотов: {len(acc['screenshots'])}\n\n"
        f"Теперь аккаунт доступен для покупки! 🎉",
        parse_mode="HTML"
    )
    
    del user_temp[user_id]

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
        game_name = get_game_display(acc.get("game_code", "unknown"))
        text += f"{status_emoji} [{game_name}] <code>{acc['id']}</code> | {acc['name']} | {acc['price']} руб.\n"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_delete_account")
async def admin_delete_list(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    keyboard = delete_accounts_list(callback.from_user.id)
    if not keyboard:
        await callback.message.edit_text("📭 Нет аккаунтов для удаления")
        await callback.answer()
        return
    await callback.message.edit_text("🗑 <b>Выберите аккаунт для удаления:</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("del_acc_"))
async def admin_delete_confirm(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    account_id = callback.data.split("_")[2]
    account = None
    for acc in accounts:
        if acc["id"] == account_id:
            account = acc
            break
    if not account:
        await callback.message.edit_text("❌ Аккаунт не найден!")
        await callback.answer()
        return
    
    user_id = str(callback.from_user.id)
    if user_id not in user_temp:
        user_temp[user_id] = {}
    user_temp[user_id]["delete_acc"] = account_id
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, удалить", callback_data="confirm_delete"),
         InlineKeyboardButton(text="❌ НЕТ, отмена", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить аккаунт '{account['name']}'?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_delete")
async def admin_delete_do(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    user_id = str(callback.from_user.id)
    account_id = user_temp.get(user_id, {}).get("delete_acc")
    
    if account_id:
        global accounts
        accounts = [acc for acc in accounts if acc["id"] != account_id]
        save_data(ACCOUNTS_FILE, accounts)
        await callback.message.edit_text("✅ <b>Аккаунт удален!</b>", parse_mode="HTML")
        if user_id in user_temp and "delete_acc" in user_temp[user_id]:
            del user_temp[user_id]["delete_acc"]
    else:
        await callback.message.edit_text("❌ Ошибка!")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_sell_requests")
async def admin_view_sell(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    pending = {k: v for k, v in sell_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("📭 Нет активных заявок на продажу")
        await callback.answer()
        return
    text = "📝 <b>Заявки на продажу:</b>\n\n"
    for rid, req in pending.items():
        text += f"🆔 {rid} | @{req['username']} | {get_game_display(req['game_code'])}\n"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_buy_requests")
async def admin_view_buy(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    pending = {k: v for k, v in buy_requests.items() if v["status"] == "pending"}
    if not pending:
        await callback.message.edit_text("📭 Нет активных заявок на покупку")
        await callback.answer()
        return
    text = "⏳ <b>Заявки на покупку:</b>\n\n"
    for rid, req in pending.items():
        text += f"🆔 {rid} | @{req['username']} | {req['account_name']} | {req['price']} руб.\n"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.message(Command("confirm_buy"))
async def admin_confirm_buy(message: types.Message):
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
    
    login = req.get("login", "не указан")
    password = req.get("password", "не указан")
    
    await bot.send_message(
        int(req["user_id"]),
        f"✅ <b>Поздравляем с покупкой!</b>\n\n"
        f"🎯 Аккаунт: {req['account_name']}\n"
        f"💰 Цена: {req['price']} руб.\n\n"
        f"🔐 <b>Данные для входа:</b>\n"
        f"📝 Логин: <code>{login}</code>\n"
        f"🔑 Пароль: <code>{password}</code>\n\n"
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
async def admin_reject_buy(message: types.Message):
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
    save_data(BUY_REQUESTS
