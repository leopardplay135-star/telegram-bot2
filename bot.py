import asyncio
import json
import os
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не задан!")
    exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Файлы для хранения данных
ACCOUNTS_FILE = "accounts.json"
PENDING_ORDERS_FILE = "pending_orders.json"
USER_REQUESTS_FILE = "user_requests.json"

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
accounts = load_data(ACCOUNTS_FILE, [])  # Список аккаунтов на продажу
pending_orders = load_data(PENDING_ORDERS_FILE, {})  # Заявки на продажу
user_requests = load_data(USER_REQUESTS_FILE, {})  # Запросы на покупку

# Временные данные пользователей
user_temp = {}

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

def accounts_list_by_game(game, action="buy"):
    accounts_list = [acc for acc in accounts if acc.get("game") == game and acc.get("status") == "available"]
    if not accounts_list:
        return None
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for acc in accounts_list:
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
        [InlineKeyboardButton(text="⏳ Заявки на покупку", callback_data="admin_view_requests")],
        [InlineKeyboardButton(text="🔄 Заявки на продажу", callback_data="admin_view_sell_orders")]
    ])
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
    game = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    game_name = "Brawl Stars" if game == "brawl" else "Fortnite"
    
    user_temp[user_id] = {
        "step": "selling",
        "game": game_name,
        "game_code": game,
        "screenshots": []
    }
    
    await callback.message.edit_text(
        f"📱 <b>Выбрано: {game_name}</b>\n\n"
        f"Отправьте скриншоты аккаунта (можно несколько)\n"
        f"Когда закончите, нажмите /done_sell",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(F.photo)
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
    
    # Создаем заявку
    order_id = str(int(time.time()))
    username = message.from_user.username or message.from_user.first_name
    
    pending_orders[order_id] = {
        "user_id": user_id,
        "username": username,
        "game": data["game"],
        "screenshots": screenshots,
        "status": "pending"
    }
    save_data(PENDING_ORDERS_FILE, pending_orders)
    
    # Отправляем админу
    await bot.send_message(
        ADMIN_ID,
        f"🆕 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ #{order_id}</b>\n\n"
        f"👤 Продавец: @{username}\n"
        f"🎮 Игра: {data['game']}\n"
        f"📸 Скриншотов: {len(screenshots)}\n\n"
        f"Чтобы принять заявку и добавить аккаунт:\n"
        f"<code>/accept_sell {order_id} НАЗВАНИЕ ЦЕНА ОПИСАНИЕ ЛОГИН_ПАРОЛЬ</code>\n\n"
        f"Пример:\n<code>/accept_sell {order_id} Легендарка 5000 Полный коллекция логин:pass</code>",
        parse_mode="HTML"
    )
    
    for photo in screenshots:
        await bot.send_photo(ADMIN_ID, photo, caption=f"Заявка #{order_id}")
    
    await message.answer(
        f"✅ <b>Заявка на продажу отправлена!</b>\n\n"
        f"Номер заявки: <code>{order_id}</code>\n"
        f"Админ рассмотрит её в ближайшее время.",
        parse_mode="HTML"
    )
    
    del user_temp[user_id]

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
    game = callback.data.split("_")[1]
    game_name = "Brawl Stars" if game == "brawl" else "Fortnite"
    
    keyboard = accounts_list_by_game(game_name, "buy")
    
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
    
    text = (
        f"🎮 <b>{account['name']}</b>\n\n"
        f"💰 Цена: <b>{account['price']} руб.</b>\n"
        f"🎯 Игра: {account['game']}\n"
        f"📝 Описание:\n{account['description']}\n\n"
        f"⚠️ После оплаты вы получите логин и пароль"
    )
    
    # Сохраняем временно ID аккаунта для пользователя
    user_id = str(callback.from_user.id)
    user_temp[user_id] = {"viewing_account": account_id}
    
    await callback.message.edit_text(
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
    
    # Создаем запрос на покупку
    request_id = str(int(time.time()))
    user_requests[request_id] = {
        "user_id": user_id,
        "username": username,
        "account_id": account_id,
        "account_name": account["name"],
        "account_data": account.get("login_data", "Данные выдаст админ после оплаты"),
        "price": account["price"],
        "game": account["game"],
        "status": "pending",  # pending, confirmed, rejected
        "created_at": datetime.now().isoformat()
    }
    save_data(USER_REQUESTS_FILE, user_requests)
    
    # Отправляем админу
    await bot.send_message(
        ADMIN_ID,
        f"🛒 <b>НОВЫЙ ЗАПРОС НА ПОКУПКУ #{request_id}</b>\n\n"
        f"👤 Покупатель: @{username}\n"
        f"🎮 Игра: {account['game']}\n"
        f"🎯 Аккаунт: {account['name']}\n"
        f"💰 Сумма: {account['price']} руб.\n\n"
        f"<b>Действия:</b>\n"
        f"✅ Подтвердить: <code>/confirm_pay {request_id}</code>\n"
        f"❌ Отклонить: <code>/reject_pay {request_id}</code>\n\n"
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

@dp.callback_query(lambda c: c.data == "admin_add_account")
async def admin_add_account_start(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    user_temp["admin"] = {"step": "waiting_for_account_data"}
    await callback.message.edit_text(
        "➕ <b>Добавление аккаунта</b>\n\n"
        "Отправьте данные аккаунта в формате:\n\n"
        "<code>Игра:Название:Цена:Описание:Логин:Пароль</code>\n\n"
        "Пример:\n"
        "<code>Brawl Stars:Легендарка:5000:Полный набор всех скинов:user123:pass123</code>\n\n"
        "Скриншоты отправьте отдельно после этого сообщения.",
        parse_mode="HTML"
    )
    await callback.answer()

@dp.message(lambda message: message.chat.id == ADMIN_ID and user_temp.get("admin", {}).get("step") == "waiting_for_account_data")
async def admin_add_account_data(message: types.Message):
    try:
        data = message.text.split(":")
        if len(data) < 6:
            await message.reply("❌ Неверный формат! Нужно 6 полей через двоеточие")
            return
        
        game, name, price, description, login, password = data[0], data[1], data[2], data[3], data[4], data[5]
        
        # Временно сохраняем данные
        user_temp["admin"]["temp_account"] = {
            "game": game.strip(),
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
            f"📸 Теперь отправьте скриншоты аккаунта (можно несколько)\n"
            f"Когда закончите, нажмите /done_account"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")

@dp.message(F.photo, lambda message: message.chat.id == ADMIN_ID and user_temp.get("admin", {}).get("step") == "waiting_for_screenshots")
async def admin_add_screenshots(message: types.Message):
    photo = message.photo[-1].file_id
    user_temp["admin"]["temp_account"]["screenshots"].append(photo)
    await message.reply(f"✅ Скриншот #{len(user_temp['admin']['temp_account']['screenshots'])} сохранен!")

@dp.message(Command("done_account"))
async def admin_finish_account(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    if "admin" not in user_temp or user_temp["admin"].get("step") != "waiting_for_screenshots":
        await message.reply("❌ Нет активного добавления аккаунта")
        return
    
    temp = user_temp["admin"]["temp_account"]
    
    if not temp["screenshots"]:
        await message.reply("❌ Добавьте хотя бы один скриншот!")
        return
    
    # Сохраняем аккаунт
    account_id = str(int(time.time()))
    accounts.append({
        "id": account_id,
        "game": temp["game"],
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
        f"🎮 {temp['game']}\n"
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
        text += f"🆔 {acc['id']} | {acc['name']} | {acc['price']} руб. | {acc['status']}\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_view_requests")
async def admin_view_requests(callback):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    pending = {k: v for k, v in user_requests.items() if v["status"] == "pending"}
    
    if not pending:
        await callback.message.edit_text("📭 Нет активных запросов на покупку")
        await callback.answer()
        return
    
    text = "⏳ <b>Запросы на покупку:</b>\n\n"
    for req_id, req in pending.items():
        text += f"🆔 {req_id} | @{req['username']} | {req['account_name']} | {req['price']} руб.\n"
    
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

# Команды для админа
@dp.message(Command("accept_sell"))
async def accept_sell(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split(maxsplit=5)
    if len(parts) < 6:
        await message.reply(
            "❌ Формат: /accept_sell НОМЕР_ЗАЯВКИ НАЗВАНИЕ ЦЕНА ОПИСАНИЕ ЛОГИН_ПАРОЛЬ"
        )
        return
    
    order_id = parts[1]
    name = parts[2]
    price = int(parts[3])
    description = parts[4]
    login_data = parts[5]
    
    if order_id not in pending_orders:
        await message.reply("❌ Заявка не найдена!")
        return
    
    order = pending_orders[order_id]
    
    # Создаем аккаунт
    account_id = str(int(time.time()))
    accounts.append({
        "id": account_id,
        "game": order["game"],
        "name": name,
        "price": price,
        "description": description,
        "login_data": login_data,
        "screenshots": order["screenshots"],
        "status": "available",
        "created_at": datetime.now().isoformat()
    })
    save_data(ACCOUNTS_FILE, accounts)
    
    # Удаляем заявку
    del pending_orders[order_id]
    save_data(PENDING_ORDERS_FILE, pending_orders)
    
    # Уведомляем пользователя
    await bot.send_message(
        int(order["user_id"]),
        f"✅ <b>Ваш аккаунт принят на продажу!</b>\n\n"
        f"🎮 Игра: {order['game']}\n"
        f"💰 Цена: {price} руб.\n"
        f"📝 Название: {name}\n\n"
        f"Как только кто-то купит аккаунт, мы свяжемся с вами!",
        parse_mode="HTML"
    )
    
    await message.reply(f"✅ Аккаунт добавлен! ID: {account_id}")

@dp.message(Command("confirm_pay"))
async def confirm_payment(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Формат: /confirm_pay НОМЕР_ЗАПРОСА")
        return
    
    request_id = parts[1]
    
    if request_id not in user_requests:
        await message.reply("❌ Запрос не найден!")
        return
    
    req = user_requests[request_id]
    req["status"] = "confirmed"
    save_data(USER_REQUESTS_FILE, user_requests)
    
    # Отправляем данные аккаунта пользователю
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
    
    # Отмечаем аккаунт как проданный
    for acc in accounts:
        if acc["id"] == req["account_id"]:
            acc["status"] = "sold"
            save_data(ACCOUNTS_FILE, accounts)
            break
    
    await message.reply(f"✅ Покупка подтверждена! Данные отправлены пользователю @{req['username']}")

@dp.message(Command("reject_pay"))
async def reject_payment(message: types.Message):
    if message.chat.id != ADMIN_ID:
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Формат: /reject_pay НОМЕР_ЗАПРОСА")
        return
    
    request_id = parts[1]
    
    if request_id not in user_requests:
        await message.reply("❌ Запрос не найден!")
        return
    
    req = user_requests[request_id]
    req["status"] = "rejected"
    save_data(USER_REQUESTS_FILE, user_requests)
    
    # Уведомляем пользователя
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
