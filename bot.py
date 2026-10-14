import asyncio
import logging
import sys
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not API_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN is missing! Please set it in the .env file.")

BINANCE_PAY_UID = "516051485"
ADMIN_USERNAME = "lorem_3"
REQUIRED_CHANNEL = "tradehub_buy_sell"

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban = State()
    waiting_for_unban = State()
    waiting_stock_input = State()

def init_db():
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            link TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_spent REAL DEFAULT 0.0,
            referred_by INTEGER,
            referral_earnings REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_name TEXT,
            quantity INTEGER,
            amount REAL,
            txid TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def seed_default_products():
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO products (name, price, description) VALUES (?, ?, ?)",
                       ("Gemini Pro 18m Link", 0.38, "18 Months Plan | 5TB Cloud Storage\n• 100% Private — No Sharing"))
        conn.commit()
    conn.close()

seed_default_products()

def get_stock_count(product_id: int) -> int:
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock WHERE product_id = ?", (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_or_create_user(user_id: int, username: str, referrer_id: int = None):
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        ref = None
        if referrer_id and referrer_id != user_id:
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (referrer_id,))
            if cursor.fetchone():
                ref = referrer_id
                
        cursor.execute(
            "INSERT INTO users (user_id, username, referred_by) VALUES (?, ?, ?)",
            (user_id, username, ref)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

async def check_user_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=f"@{REQUIRED_CHANNEL}", user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception as e:
        print(f"Subscription check error: {e}")
        return True


async def get_main_menu(message: types.Message, referrer_id: int = None):
    user = message.from_user
    username = f"@{user.username}" if user.username else "Not Set"
    user_id = user.id
    bot_user = (await bot.get_me()).username
    
    db_user = get_or_create_user(user_id, username, referrer_id)
    if db_user[5] == 1:
        return None, None
        
    total_spent = db_user[2]
    
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    referral_count = cursor.fetchone()[0]
    referral_earnings = db_user[4]
    conn.close()
    
    welcome_text = (
        f"👋 Welcome back, <b>{user.first_name}</b> to <b>TradeHub</b>!\n"
        f"Quality digital products at cheapest rates\n\n"
        f"________________________________________\n\n"
        f"🏷️ Username: {username}\n"
        f"🆔 UserID: {user_id}\n"
        f"👑 Membership: 🥉 Bronze\n"
        f"💎 Total Spent: ${total_spent:.2f}\n"
        f"🤝 Referrals: {referral_count}\n"
        f"📜 Referral Earning: ${referral_earnings:.2f}\n"
        f"🔗 Referral Link: https://t.me/{bot_user}?start={user_id}\n\n"
        f"________________________________________\n\n"
        f"Choose an option below to get started."
    )

    kb = [
        [types.InlineKeyboardButton(text="🛒 Shop", callback_data="shop")],
        [
            types.InlineKeyboardButton(text="💰 Wallet (Disabled)", callback_data="wallet_disabled"),
            types.InlineKeyboardButton(text="🤝 Referral", callback_data="referral")
        ],
        [types.InlineKeyboardButton(text="📜 Order History", callback_data="orders")],
        [types.InlineKeyboardButton(text="🛠️ Support", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    
    if user_id == ADMIN_ID:
        kb.insert(0, [types.InlineKeyboardButton(text="⚡ Admin Control Panel", callback_data="admin_panel")])

    return welcome_text, types.InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def send_welcome(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    is_subscribed = await check_user_subscription(user_id)
    if not is_subscribed:
        kb = [
            [types.InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL}")],
            [types.InlineKeyboardButton(text="🔄 Check Membership", callback_data="check_sub")]
        ]
        await message.answer(
            "⚠️ <b>Access Denied!</b>\n\n"
            f"You must join our official channel to use this bot:\n👉 @{REQUIRED_CHANNEL}\n\n"
            "After joining the channel, click the <b>'Check Membership'</b> button below.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        
    text, keyboard = await get_main_menu(message, referrer_id)
    if not keyboard:
        await message.answer("⚠️ Your account has been banned from TradeHub.")
        return
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query(F.data == "check_sub")
async def verify_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    is_subscribed = await check_user_subscription(user_id)
    
    if not is_subscribed:
        await callback.answer("⚠️ You have not joined the channel yet!", show_alert=True)
        return

    text, keyboard = await get_main_menu(callback.message)
    if not keyboard:
        await callback.answer("Your account is banned.", show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Membership verified successfully!")


@dp.callback_query(F.data == "wallet_disabled")
async def wallet_disabled_alert(callback: types.CallbackQuery):
    await callback.answer("⚠️ Wallet feature is currently disabled by Admin.", show_alert=True)


@dp.callback_query(F.data == "referral")
async def open_referral(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_user = (await bot.get_me()).username
    
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    ref_count = cursor.fetchone()[0]
    cursor.execute("SELECT referral_earnings FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    ref_earn = res[0] if res else 0.0
    conn.close()
    
    ref_text = (
        f"🤝 <b>TradeHub Referral Program</b>\n\n"
        f"Invite your friends and earn a <b>5% commission</b> on their successful purchases!\n\n"
        f"👥 <b>Total Referred Users:</b> {ref_count}\n"
        f"💵 <b>Total Referral Earnings:</b> ${ref_earn:.2f}\n\n"
        f"🔗 <b>Your Personal Invite Link:</b>\n<code>https://t.me/{bot_user}?start={user_id}</code>"
    )
    kb = [[types.InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]]
    await callback.message.edit_text(ref_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "orders")
async def open_orders(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT product_name, quantity, amount, status FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
    orders = cursor.fetchall()
    conn.close()
    
    orders_text = "📜 <b>Your Recent Order History (Last 5):</b>\n\n"
    if not orders:
        orders_text += "<i>You haven't placed any orders yet.</i>"
    else:
        for idx, ord in enumerate(orders, 1):
            p_name, qty, amt, status = ord
            status_emoji = "✅ Approved" if status == "approved" else ("❌ Rejected" if status == "rejected" else "⏳ Pending")
            orders_text += f"{idx}. <b>{p_name}</b> (Qty: {qty}) - ${amt:.2f}\nStatus: {status_emoji}\n\n"
            
    kb = [[types.InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]]
    await callback.message.edit_text(orders_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "admin_panel")
async def admin_panel_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Unauthorized!", show_alert=True)
        return
    await state.clear()
    
    admin_text = (
        f"⚡ <b>TradeHub Admin Control Panel</b>\n\n"
        f"Manage your store effortlessly using the buttons below:"
    )
    kb = [
        [types.InlineKeyboardButton(text="📦 View Stock & Add Items", callback_data="adm_stock")],
        [types.InlineKeyboardButton(text="📢 Broadcast Message", callback_data="adm_broadcast")],
        [types.InlineKeyboardButton(text="📊 Store Statistics", callback_data="adm_stats")],
        [types.InlineKeyboardButton(text="🚫 Ban User", callback_data="adm_ban"),
         types.InlineKeyboardButton(text="✅ Unban User", callback_data="adm_unban")],
        [types.InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="back_to_menu")]
    ]
    await callback.message.edit_text(admin_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "adm_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(amount) FROM orders WHERE status = 'approved'")
    total_revenue = cursor.fetchone()[0] or 0.0
    conn.close()

    stats_text = (
        f"📊 <b>TradeHub Live Statistics</b>\n\n"
        f"👥 Total Registered Users: <b>{total_users}</b>\n"
        f"📦 Total Orders Placed: <b>{total_orders}</b>\n"
        f"💰 Total Approved Revenue: <b>${total_revenue:.2f}</b>"
    )
    kb = [[types.InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_panel")]]
    await callback.message.edit_text(stats_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "adm_stock")
async def admin_stock_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM products")
    prods = cursor.fetchall()
    
    stock_summary = "📦 <b>Product Stock Status:</b>\n\n"
    kb = []
    for p in prods:
        p_id, p_name = p
        count = get_stock_count(p_id)
        stock_summary += f"• <b>{p_name}</b> (ID: {p_id}) — Stock: <b>{count}</b>\n"
        kb.append([types.InlineKeyboardButton(text=f"➕ Add Stock for {p_name}", callback_data=f"add_stock_prompt_{p_id}")])
    conn.close()
    
    stock_summary += "\n<i>Click a button below to add stock links:</i>"
    kb.append([types.InlineKeyboardButton(text="🔙 Back to Admin Panel", callback_data="admin_panel")])
    
    await callback.message.edit_text(stock_summary, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("add_stock_prompt_"))
async def prompt_add_stock(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    p_id = int(callback.data.split("_")[-1])
    await state.update_data(product_id=p_id)
    await state.set_state(AdminStates.waiting_stock_input)
    
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id = ?", (p_id,))
    p_name = cursor.fetchone()[0]
    conn.close()

    kb = [[types.InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]]
    await callback.message.edit_text(
        f"📦 <b>Add Stock for: {p_name}</b>\n\n"
        f"Please send the links now (each link on a new line):",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(AdminStates.waiting_stock_input)
async def process_bulk_stock_input(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    p_id = data.get("product_id")
    
    links_to_add = [line.strip() for line in message.text.split("\n") if line.strip()]
    if not links_to_add:
        await message.answer("⚠️ No valid links found! Please send valid links.")
        return

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    data_to_insert = [(p_id, link) for link in links_to_add]
    cursor.executemany("INSERT INTO stock (product_id, link) VALUES (?, ?)", data_to_insert)
    conn.commit()
    conn.close()
    
    total_stock = get_stock_count(p_id)
    await state.clear()
    await message.answer(f"✅ Successfully added {len(links_to_add)} items!\n📦 Total Stock for this product: {total_stock}")


@dp.callback_query(F.data == "adm_broadcast")
async def prompt_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_broadcast)
    kb = [[types.InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]]
    await callback.message.edit_text("📢 <b>Broadcast Message</b>\n\nPlease send the message you want to broadcast to all users:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def execute_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    text_to_broadcast = message.text
    await state.clear()

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = cursor.fetchall()
    conn.close()

    success, failed = 0, 0
    for u in users:
        try:
            await bot.send_message(u[0], f"📢 <b>TradeHub Announcement</b>\n\n{text_to_broadcast}", parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await message.answer(f"📢 Broadcast Complete!\n✅ Success: {success}\n❌ Failed: {failed}")


@dp.callback_query(F.data == "adm_ban")
async def prompt_ban(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_ban)
    kb = [[types.InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]]
    await callback.message.edit_text("🚫 <b>Ban User</b>\n\nPlease send the User ID you want to ban:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()

@dp.message(AdminStates.waiting_for_ban)
async def execute_ban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text.isdigit():
        await message.answer("⚠️ Please send a valid numeric User ID.")
        return
    target_id = int(message.text)
    await state.clear()

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await message.answer(f"🚫 User ID <code>{target_id}</code> has been banned successfully.", parse_mode="HTML")


@dp.callback_query(F.data == "adm_unban")
async def prompt_unban(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_unban)
    kb = [[types.InlineKeyboardButton(text="❌ Cancel", callback_data="admin_panel")]]
    await callback.message.edit_text("✅ <b>Unban User</b>\n\nPlease send the User ID you want to unban:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()

@dp.message(AdminStates.waiting_for_unban)
async def execute_unban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.text.isdigit():
        await message.answer("⚠️ Please send a valid numeric User ID.")
        return
    target_id = int(message.text)
    await state.clear()

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))
    conn.commit()
    conn.close()
    await message.answer(f"✅ User ID <code>{target_id}</code> has been unbanned successfully.", parse_mode="HTML")


# --- DIRECT SHOP & PRODUCTS (NO CATEGORIES) ---
@dp.callback_query(F.data == "shop")
async def open_shop(callback: types.CallbackQuery):
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products")
    products = cursor.fetchall()
    conn.close()

    kb = []
    for prod in products:
        p_id, p_name, p_price = prod
        stock = get_stock_count(p_id)
        kb.append([types.InlineKeyboardButton(text=f"✨ {p_name} - ${p_price:.2f} (Stock: {stock})", callback_data=f"prod_{p_id}")])
    kb.append([types.InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")])

    shop_text = "🛒 <b>TradeHub Store - All Products</b>\n📦 <b>Page 1 of 1</b>\n⬇️ <b>Choose a product to buy:</b>"
    await callback.message.edit_text(shop_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("prod_"))
async def product_detail(callback: types.CallbackQuery):
    p_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, description FROM products WHERE id = ?", (p_id,))
    prod = cursor.fetchone()
    conn.close()

    if not prod:
        await callback.answer("Product not found!", show_alert=True)
        return

    p_name, p_price, p_desc = prod
    stock = get_stock_count(p_id)

    desc_text = (
        f"✨ <b>{p_name}</b>\n\n"
        f"📦 <b>Description:</b>\n{p_desc}\n\n"
        f"💵 <b>Price:</b> ${p_price:.2f}\n📦 <b>Available Stock:</b> {stock}\n\n🔢 <b>Choose Buy Quantity:</b>"
    )
    kb = [
        [types.InlineKeyboardButton(text="1", callback_data=f"buy_{p_id}_1"),
         types.InlineKeyboardButton(text="2", callback_data=f"buy_{p_id}_2"),
         types.InlineKeyboardButton(text="3", callback_data=f"buy_{p_id}_3")],
        [types.InlineKeyboardButton(text="4", callback_data=f"buy_{p_id}_4"),
         types.InlineKeyboardButton(text="5", callback_data=f"buy_{p_id}_5")],
        [types.InlineKeyboardButton(text="🔙 Back to Shop", callback_data="shop")]
    ]
    await callback.message.edit_text(desc_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_"))
async def checkout_confirmation(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    p_id = int(parts[1])
    qty = int(parts[2])

    stock = get_stock_count(p_id)
    if qty > stock:
        await callback.answer(f"⚠️ Stock insufficient! Available stock: {stock}", show_alert=True)
        return

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (p_id,))
    prod = cursor.fetchone()
    conn.close()

    p_name, p_price = prod
    total_price = qty * p_price

    checkout_text = (
        f"🛒 <b>TradeHub - Checkout Confirmation</b>\n\n📦 <b>Product:</b> {p_name}\n"
        f"🔢 <b>Quantity:</b> {qty}\n💵 <b>Unit Rate:</b> ${p_price:.2f}\n💰 <b>Total Amount:</b> ${total_price:.2f}\n\n⬇️ <b>Select Payment Method:</b>"
    )
    kb = [
        [types.InlineKeyboardButton(text="💎 Pay with Crypto (Binance Pay Auto)", callback_data=f"pay_crypto_{p_id}_{qty}_{total_price:.2f}")],
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="shop")]
    ]
    await callback.message.edit_text(checkout_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_crypto_"))
async def crypto_payment(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    p_id = parts[2]
    qty = parts[3]
    amount = parts[4]

    binance_text = (
        f"💳 <b>TradeHub Payment Instructions</b>\n\n💰 <b>Amount to Pay:</b> ${amount}\n🌐 <b>Method:</b> Binance Pay Auto\n\n"
        f"📌 <b>Send EXACTLY ${amount} to Binance Pay UID:</b>\n<code>{BINANCE_PAY_UID}</code>\n\n"
        f"⚠️ <b>Important:</b> After making payment, click <b>'Submit TxID Now'</b> and send your transaction hash."
    )
    kb = [
        [types.InlineKeyboardButton(text="✍️ Submit TxID Now", callback_data=f"enter_tx_{p_id}_{qty}_{amount}")],
        [types.InlineKeyboardButton(text="🔙 Back", callback_data=f"prod_{p_id}")]
    ]
    await callback.message.edit_text(binance_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


waiting_for_tx = {}

@dp.callback_query(F.data.startswith("enter_tx_"))
async def ask_txid(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    p_id = int(parts[2])
    qty = int(parts[3])
    amount = float(parts[4])
    
    waiting_for_tx[callback.from_user.id] = {"p_id": p_id, "qty": qty, "amount": amount}
    await callback.message.answer("✍️ Please reply to this chat with your <b>TxID (Transaction Hash)</b> or payment proof:", parse_mode="HTML")
    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def receive_txid(message: types.Message):
    user_id = message.from_user.id
    if user_id not in waiting_for_tx:
        return
    
    order_data = waiting_for_tx.pop(user_id)
    p_id = order_data["p_id"]
    qty = order_data["qty"]
    amount = order_data["amount"]
    txid = message.text
    username = f"@{message.from_user.username}" if message.from_user.username else str(user_id)

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id = ?", (p_id,))
    p_name = cursor.fetchone()[0]

    cursor.execute(
        "INSERT INTO orders (user_id, username, product_name, quantity, amount, txid, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, p_name, qty, amount, txid, "pending")
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await message.answer("✅ Your TxID has been received! TradeHub Admin will verify it and deliver your product shortly.")

    admin_text = (
        f"🔔 <b>TradeHub - New Order Verification!</b>\n\n"
        f"👤 <b>User:</b> {username} (<code>{user_id}</code>)\n"
        f"📦 <b>Product:</b> {p_name} (Qty: {qty})\n"
        f"💰 <b>Amount:</b> ${amount}\n"
        f"🆔 <b>TxID:</b> <code>{txid}</code>\n\n"
        f"Approve this transaction?"
    )
    kb = [
        [
            types.InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"adm_app_{order_id}"),
            types.InlineKeyboardButton(text="❌ Reject", callback_data=f"adm_rej_{order_id}")
        ]
    ]
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")


@dp.callback_query(F.data.startswith("adm_app_") | F.data.startswith("adm_rej_"))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Unauthorized!", show_alert=True)
        return

    action, _, order_id_str = callback.data.rpartition("_")
    order_id = int(order_id_str)

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product_name, quantity, amount, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()

    if not order or order[4] != "pending":
        await callback.answer("⚠️ Order already processed or not found.", show_alert=True)
        conn.close()
        return

    user_id, product_name, qty, amount, _ = order

    if "app" in action:
        cursor.execute("SELECT id FROM products WHERE name = ?", (product_name,))
        p_row = cursor.fetchone()
        if not p_row:
            await callback.answer("Product error!", show_alert=True)
            conn.close()
            return
        p_id = p_row[0]

        stock = get_stock_count(p_id)
        if stock < qty:
            await callback.answer(f"⚠️ Stock insufficient! Available: {stock}", show_alert=True)
            conn.close()
            return

        cursor.execute("SELECT id, link FROM stock WHERE product_id = ? LIMIT ?", (p_id, qty))
        rows = cursor.fetchall()
        link_ids = [r[0] for r in rows]
        links = [r[1] for r in rows]

        cursor.executemany("DELETE FROM stock WHERE id = ?", [(i,) for i in link_ids])
        cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
        cursor.execute("UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?", (amount, user_id))

        cursor.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,))
        ref_data = cursor.fetchone()
        if ref_data and ref_data[0]:
            referrer_id = ref_data[0]
            commission = amount * 0.05
            cursor.execute("UPDATE users SET referral_earnings = referral_earnings + ? WHERE user_id = ?", (commission, referrer_id))
            try:
                await bot.send_message(referrer_id, f"🎉 <b>Referral Bonus!</b> Your referred user made a purchase and you earned <b>${commission:.2f}</b>!", parse_mode="HTML")
            except:
                pass

        conn.commit()

        remaining_stock = get_stock_count(p_id)
        if remaining_stock <= 3:
            try:
                await bot.send_message(ADMIN_ID, f"⚠️ <b>Low Stock Alert!</b>\nProduct: {product_name}\nRemaining Stock: {remaining_stock}", parse_mode="HTML")
            except:
                pass

        conn.close()

        delivered_links = "\n".join([f"🔗 {l}" for l in links])

        await bot.send_message(
            user_id,
            f"🎉 <b>TradeHub - Payment Verified & Approved!</b>\n\n📦 <b>Product:</b> {product_name} (Qty: {qty})\n\n"
            f"🔑 <b>Your Item(s):</b>\n{delivered_links}\n\nThank you for shopping with TradeHub!",
            parse_mode="HTML"
        )
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Status: APPROVED & DELIVERED</b>", parse_mode="HTML")
        await callback.answer("Order approved and items dispatched!")

    else:
        cursor.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        await bot.send_message(user_id, "❌ TradeHub: Your payment could not be verified and your order has been rejected.")
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Status: REJECTED</b>", parse_mode="HTML")
        await callback.answer("Order rejected.")


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    is_subscribed = await check_user_subscription(user_id)
    if not is_subscribed:
        await callback.answer("⚠️ You must join the channel first!", show_alert=True)
        return

    text, keyboard = await get_main_menu(callback.message)
    if not keyboard:
        await callback.answer("Your account is banned.", show_alert=True)
        return
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


async def main():
    print("TradeHub Store is running...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
