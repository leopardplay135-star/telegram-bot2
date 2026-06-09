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
    print(f"[DEBUG] Поиск для {game_code}, найдено: {len(acc_list)}")
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

# Обработчик фото для продажи
@dp.message(F.photo)
async def save_sell_photo(message: types.Message):
    user_id = str(message.from_user.id)
    
    # Проверяем, есть ли пользователь в процессе продажи
    if user_id not in user_temp or user_temp[user_id].get("step") != "selling":
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
        await message.answer("❌ Нет активной заявки на продажу. Сначала нажмите /start и выберите 'Продать аккаунт'")
        return
    
    data = user_temp[user_id]
    screenshots = data.get("screenshots", [])
    
    if not screenshots:
        await message.answer("❌ Вы не отправили ни одного скриншота! Сначала отправьте фото, потом /done_sell")
        return
    
    request_id = str(int(time.time()))
    username = message.from_user.username or message.from_user.first_name
    
    sell_requests[request_id] = {
        "user_id": user_id,
        "username": username,
        "game_code": data["game_code"],
        "screenshots": screenshots,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    save_data(SELL_REQUESTS_FILE, sell_requests)
    
    game_name = get_game_display(data["game_code"])
    
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
    
    for idx, photo in enumerate(screenshots, 1):
        await bot.send_photo(ADMIN_ID, photo, caption=f"Заявка #{request_id} | Скриншот {idx}")
    
    await message.answer(
        f"✅ <b>Заявка на продажу отправлена!</b>\n\n"
        f"Номер заявки: <code>{request_id}</code>\n"
        f"Админ оценит аккаунт и напишет цену.",
        parse_mode="HTML"
    )
    
    del user_temp[user_id]

@dp.message(Command("price_sell"))
async def admin_send_price(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("❌ Формат: /price_sell НОМЕР_ЗАЯВКИ ЦЕНА\nПример: /price_sell 123456789 5000")
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

@dp.callback_query(lambda c: c.data.startswith("buy_") and c.data.count("_") == 1)
async def buy_game_selected(callback):
    game_code = callback.data.split("_")[1]
    keyboard = accounts_list_by_game(game_code)
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

@dp.callback_query(lambda c: c.data.startswith("view_acc_"))
async def view_account(callback):
    account_id = callback.data.split("_")[2]
    print(f"[DEBUG] Просмотр аккаунта с ID: {account_id}")
    
    account = None
    for acc in accounts:
        if acc["id"] == account_id:
            account = acc
            break
    
    if not account:
        await callback.message.answer("❌ Аккаунт не найден!")
        await callback.answer()
        return
    
    if account.get("status") != "available":
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

@dp.callback_query(lambda c: c.data.startswith("buy_acc_"))
async def buy_account(callback):
    account_id = callback.data.split("_")[2]
    print(f"[DEBUG] Покупка аккаунта с ID: {account_id}")
    
    account = None
    for acc in accounts:
        if acc["id"] == account_id:
            account = acc
            break
    
    if not account:
        await callback.message.answer("❌ Аккаунт не найден!")
        await callback.answer()
        return
    
    if account.get("status") != "available":
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
        "account_data": account.get("login_data", "Данные выдаст админ после оплаты"),
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
    user_temp["admin"] = {"step": "waiting_data", "account": None}
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\n"
        "📝 <b>Шаг 1:</b> Отправьте данные аккаунта в формате:\n\n"
        "<code>brawl:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Или для Fortnite:\n"
        "<code>fortnite:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Пример:\n"
        "<code>brawl:Легендарка:5000:Полный набор скинов:user123:pass123</code>",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(lambda m: m.chat.id == ADMIN_ID and user_temp.get("admin", {}).get("step") == "waiting_data")
async def admin_add_data(message: types.Message):
    try:
        parts = message.text.split(":", 5)
        if len(parts) < 6:
            await message.reply("❌ Неверный формат!\n\nНужно: игра:название:цена:описание:логин:пароль\n\nПример:\n<code>brawl:Легендарка:5000:Описание:login:pass</code>", parse_mode="HTML")
            return
        
        game_input = parts[0].lower().strip()
        if "brawl" in game_input:
            game_code = GAME_BRAWL
        elif "fortnite" in game_input or game_input == "fort":
            game_code = GAME_FORTNITE
        else:
            await message.reply(f"❌ Неизвестная игра: {game_input}\nИспользуйте 'brawl' или 'fortnite'")
            return
        
        # Сохраняем данные аккаунта
        user_temp["admin"]["account"] = {
            "game_code": game_code,
            "name": parts[1].strip(),
            "price": int(parts[2].strip()),
            "description": parts[3].strip(),
            "login_data": f"{parts[4].strip()}:{parts[5].strip()}",
            "screenshots": []
        }
        user_temp["admin"]["step"] = "waiting_screenshots"
        
        await message.reply(
            f"✅ <b>Данные приняты!</b>\n\n"
            f"🎮 Игра: {get_game_display(game_code)}\n"
            f"🎯 Название: {parts[1]}\n"
            f"💰 Цена: {parts[2]} руб.\n"
            f"📝 Описание: {parts[3]}\n\n"
            f"📸 <b>Шаг 2:</b> Теперь отправьте СКРИНШОТЫ аккаунта (можно несколько)\n"
            f"Когда закончите, нажмите <b>/done_account</b>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

# Обработчик фото для админа
@dp.message(F.photo, lambda m: m.chat.id == ADMIN_ID)
async def admin_add_screenshot(message: types.Message):
    # Проверяем, есть ли активный процесс добавления аккаунта
    if "admin" not in user_temp or user_temp["admin"].get("step") != "waiting_screenshots":
        await message.reply("❌ Сначала отправьте ДАННЫЕ аккаунта текстом!\nИспользуйте /admin → 'Добавить аккаунт'")
        return
    
    if user_temp["admin"]["account"] is None:
        await message.reply("❌ Ошибка! Сначала отправьте данные аккаунта.")
        return
    
    photo = message.photo[-1].file_id
    user_temp["admin"]["account"]["screenshots"].append(photo)
    count = len(user_temp["admin"]["account"]["screenshots"])
    await message.reply(f"✅ Скриншот #{count} сохранен!\nОтправьте еще или нажмите /done_account")

@dp.message(Command("done_account"))
async def admin_done_account(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    if "admin" not in user_temp or user_temp["admin"].get("step") != "waiting_screenshots":
        await message.reply("❌ Нет активного добавления аккаунта.\nИспользуйте /admin → 'Добавить аккаунт'")
        return
    
    acc = user_temp["admin"]["account"]
    
    if acc is None:
        await message.reply("❌ Ошибка! Данные аккаунта не найдены.")
        return
    
    if not acc["screenshots"]:
        await message.reply("❌ Добавьте хотя бы один скриншот!\nОтправьте фото и снова /done_account")
        return
    
    # Создаем новый аккаунт
    acc["id"] = str(int(time.time()))
    acc["status"] = "available"
    acc["created_at"] = datetime.now().isoformat()
    accounts.append(acc)
    save_data(ACCOUNTS_FILE, accounts)
    
    await message.reply(
        f"✅ <b>Аккаунт успешно добавлен!</b>\n\n"
        f"🆔 ID: {acc['id']}\n"
        f"🎮 {get_game_display(acc['game_code'])}\n"
        f"🎯 {acc['name']}\n"
        f"💰 {acc['price']} руб.\n\n"
        f"📸 Скриншотов: {len(acc['screenshots'])}\n\n"
        f"Теперь аккаунт доступен для покупки! 🎉",
        parse_mode="HTML"
    )
    
    # Очищаем временные данные
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
        game_name = get_game_display(acc.get("game_code", "unknown"))
        text += f"{status_emoji} [{game_name}] <code>{acc['id']}</code> | {acc['name']} | {acc['price']} руб.\n"
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_delete_account")
async def admin_delete_list(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    keyboard = delete_accounts_list()
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
    user_temp["delete_acc"] = account_id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, удалить", callback_data="del_yes"),
         InlineKeyboardButton(text="❌ НЕТ, отмена", callback_data="del_no")]
    ])
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить аккаунт '{account['name']}'?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "del_yes")
async def admin_delete_do(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    account_id = user_temp.get("delete_acc")
    if account_id:
        global accounts
        accounts = [acc for acc in accounts if acc["id"] != account_id]
        save_data(ACCOUNTS_FILE, accounts)
        await callback.message.edit_text("✅ <b>Аккаунт удален!</b>", parse_mode="HTML")
        del user_temp["delete_acc"]
    else:
        await callback.message.edit_text("❌ Ошибка!")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "del_no")
async def admin_delete_cancel(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    if "delete_acc" in user_temp:
        del user_temp["delete_acc"]
    await callback.message.edit_text("❌ Удаление отменено.", parse_mode="HTML")
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
    await bot.send_message(
        int(req["user_id"]),
        f"✅ <b>Поздравляем с покупкой!</b>\n\n"
        f"🎯 Аккаунт: {req['account_name']}\n"
        f"💰 Цена: {req['price']} руб.\n\n"
        f"🔐 Данные для входа:\n<code>{req['account_data']}</code>\n\n"
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
    save_data(BUY_REQUESTS_FILE, buy_requests)
    await bot.send_message(
        int(req["user_id"]),
        f"❌ <b>К сожалению, оплата не прошла.</b>\n\n"
        f"Пожалуйста, свяжитесь с админом: @{message.from_user.username}\n"
        f"Вы можете попробовать снова с /start",
        parse_mode="HTML"
    )
    await message.reply(f"❌ Запрос #{request_id} отклонен. Пользователь уведомлен.")

@dp.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    await callback.message.edit_text("👑 <b>Панель администратора</b>\n\nВыберите действие:", reply_markup=admin_menu(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback):
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
    await callback.message.edit_text(welcome_text, reply_markup=main_menu(), parse_mode="HTML")
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
