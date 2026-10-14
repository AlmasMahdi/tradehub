import asyncio
import logging
import sys
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not API_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN is missing! Please set it in the .env file.")

BINANCE_PAY_UID = "516051485"
ADMIN_USERNAME = "lorem_3"

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            link TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_spent REAL DEFAULT 0.0,
            referred_by INTEGER,
            referral_earnings REAL DEFAULT 0.0
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

def get_stock_count(product_name: str) -> int:
    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM stock WHERE product_name = ?", (product_name,))
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


async def get_main_menu(message: types.Message, referrer_id: int = None):
    user = message.from_user
    username = f"@{user.username}" if user.username else "Not Set"
    user_id = user.id
    bot_user = (await bot.get_me()).username
    
    db_user = get_or_create_user(user_id, username, referrer_id)
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
    return welcome_text, types.InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    args = message.text.split()
    referrer_id = None
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        
    text, keyboard = await get_main_menu(message, referrer_id)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


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


@dp.message(Command("bulkstock"))
async def bulk_add_stock(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ You are not authorized!")
        return
    
    lines = message.text.split("\n")
    if len(lines) < 2:
        await message.answer("⚠️ Format:\n/bulkstock\nlink1\nlink2")
        return
    
    links_to_add = [line.strip() for line in lines[1:] if line.strip()]
    if not links_to_add:
        await message.answer("⚠️ No valid links found!")
        return

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    data_to_insert = [("Gemini Pro 18m Link", link) for link in links_to_add]
    cursor.executemany("INSERT INTO stock (product_name, link) VALUES (?, ?)", data_to_insert)
    conn.commit()
    conn.close()
    
    total_stock = get_stock_count("Gemini Pro 18m Link")
    await message.answer(f"✅ Successfully added {len(links_to_add)} items!\n📦 Total TradeHub Stock: {total_stock}")


@dp.callback_query(F.data == "shop")
async def open_shop(callback: types.CallbackQuery):
    stock = get_stock_count("Gemini Pro 18m Link")
    shop_text = "🛒 <b>TradeHub Store - All Products</b>\n📦 <b>Page 1 of 1</b>\n⬇️ <b>Choose a product to buy:</b>"
    kb = [
        [types.InlineKeyboardButton(text=f"✨ Gemini Pro 18m Link - $0.38 (Stock: {stock})", callback_data="prod_gemini")],
        [types.InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    await callback.message.edit_text(shop_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "prod_gemini")
async def gemini_detail(callback: types.CallbackQuery):
    stock = get_stock_count("Gemini Pro 18m Link")
    product_desc = (
        "✨ <b>Gemini Pro 18m Link</b>\n\n"
        "📦 <b>Description:</b>\n• 18 Months Plan | 5TB Cloud Storage\n• 100% Private — No Sharing\n\n"
        f"💵 <b>Standard Price:</b> $0.38\n📦 <b>Available Stock:</b> {stock}\n\n🔢 <b>Choose Buy Quantity:</b>"
    )
    kb = [
        [types.InlineKeyboardButton(text="1", callback_data="buy_gemini_qty_1"),
         types.InlineKeyboardButton(text="2", callback_data="buy_gemini_qty_2"),
         types.InlineKeyboardButton(text="3", callback_data="buy_gemini_qty_3")],
        [types.InlineKeyboardButton(text="4", callback_data="buy_gemini_qty_4"),
         types.InlineKeyboardButton(text="5", callback_data="buy_gemini_qty_5")],
        [types.InlineKeyboardButton(text="🔙 Back to Shop", callback_data="shop")]
    ]
    await callback.message.edit_text(product_desc, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_gemini_qty_"))
async def checkout_confirmation(callback: types.CallbackQuery):
    qty = int(callback.data.split("_")[-1])
    stock = get_stock_count("Gemini Pro 18m Link")
    if qty > stock:
        await callback.answer(f"⚠️ Stock insufficient! Available stock: {stock}", show_alert=True)
        return

    total_price = qty * 0.38
    checkout_text = (
        f"🛒 <b>TradeHub - Checkout Confirmation</b>\n\n📦 <b>Product:</b> Gemini Pro 18m Link\n"
        f"🔢 <b>Quantity:</b> {qty}\n💵 <b>Unit Rate:</b> $0.38\n💰 <b>Total Amount:</b> ${total_price:.2f}\n\n⬇️ <b>Select Payment Method:</b>"
    )
    kb = [
        [types.InlineKeyboardButton(text="💎 Pay with Crypto (Binance Pay Auto)", callback_data=f"pay_crypto_{qty}_{total_price:.2f}")],
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="shop")]
    ]
    await callback.message.edit_text(checkout_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_crypto_"))
async def crypto_payment(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    qty = parts[2]
    amount = parts[3]

    binance_text = (
        f"💳 <b>TradeHub Payment Instructions</b>\n\n💰 <b>Amount to Pay:</b> ${amount}\n🌐 <b>Method:</b> Binance Pay Auto\n\n"
        f"📌 <b>Send EXACTLY ${amount} to Binance Pay UID:</b>\n<code>{BINANCE_PAY_UID}</code>\n\n"
        f"⚠️ <b>Important:</b> After making the payment, click <b>'Submit TxID Now'</b> and send your transaction hash."
    )
    kb = [
        [types.InlineKeyboardButton(text="✍️ Submit TxID Now", callback_data=f"enter_tx_{qty}_{amount}")],
        [types.InlineKeyboardButton(text="🔙 Back", callback_data="prod_gemini")]
    ]
    await callback.message.edit_text(binance_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    await callback.answer()


waiting_for_tx = {}

@dp.callback_query(F.data.startswith("enter_tx_"))
async def ask_txid(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    qty = parts[2]
    amount = parts[3]
    
    waiting_for_tx[callback.from_user.id] = {"qty": int(qty), "amount": float(amount)}
    await callback.message.answer("✍️ Please reply to this chat with your <b>TxID (Transaction Hash)</b> or payment proof:", parse_mode="HTML")
    await callback.answer()


@dp.message(F.text & ~F.text.startswith("/"))
async def receive_txid(message: types.Message):
    user_id = message.from_user.id
    if user_id not in waiting_for_tx:
        return
    
    order_data = waiting_for_tx.pop(user_id)
    qty = order_data["qty"]
    amount = order_data["amount"]
    txid = message.text
    username = f"@{message.from_user.username}" if message.from_user.username else str(user_id)

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, username, product_name, quantity, amount, txid, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, username, "Gemini Pro 18m Link", qty, amount, txid, "pending")
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    await message.answer("✅ Your TxID has been received! TradeHub Admin will verify it and deliver your product shortly.")

    admin_text = (
        f"🔔 <b>TradeHub - New Order Verification!</b>\n\n"
        f"👤 <b>User:</b> {username} (<code>{user_id}</code>)\n"
        f"📦 <b>Product:</b> Gemini Pro 18m Link (Qty: {qty})\n"
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
        stock = get_stock_count(product_name)
        if stock < qty:
            await callback.answer(f"⚠️ Stock insufficient! Available: {stock}", show_alert=True)
            conn.close()
            return

        cursor.execute("SELECT id, link FROM stock WHERE product_name = ? LIMIT ?", (product_name, qty))
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
                await bot.send_message(referrer_id, f"🎉 <b>Referral Bonus!</b> Your referred user made a purchase and you earned a <b>${commission:.2f}</b> referral commission!", parse_mode="HTML")
            except:
                pass

        conn.commit()
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
async def back_to_menu(callback: types.CallbackQuery):
    text, keyboard = await get_main_menu(callback.message)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


async def main():
    print("TradeHub Store is running...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
