import asyncio
import logging
import sys
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

# .env file se secure credentials load karna
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Agar token nahi mila toh error throw karega
if not API_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN is missing! Please set it in the .env file.")

BINANCE_PAY_UID = "973903765"
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


async def get_main_menu(message: types.Message):
    user = message.from_user
    user_name = user.first_name
    username = f"@{user.username}" if user.username else "Not Set"
    user_id = user.id
    
    welcome_text = (
        f"👋 Welcome back, {user_name} to **TradeHub**!\n"
        f"Quality digital products at cheapest rates\n\n"
        f"________________________________________\n\n"
        f"🏷️ Username: {username}\n"
        f"🆔 UserID: {user_id}\n"
        f"👑 Membership: 🥉 Bronze\n"
        f"💎 Total Spent: $0.00\n"
        f"💰 Balance: $0.00\n"
        f"🤝 Referrals: 0\n"
        f"📜 Referral Earning: $0.00\n"
        f"🔗 Referral Link: https://t.me/{(await bot.get_me()).username}?start={user_id}\n\n"
        f"________________________________________\n\n"
        f"Choose an option below to get started."
    )

    kb = [
        [types.InlineKeyboardButton(text="🛒 Shop", callback_data="shop")],
        [
            types.InlineKeyboardButton(text="💰 Wallet", callback_data="wallet"),
            types.InlineKeyboardButton(text="🤝 Referral", callback_data="referral")
        ],
        [types.InlineKeyboardButton(text="📜 Order History", callback_data="orders")],
        [types.InlineKeyboardButton(text="🛠️ Support", url=f"https://t.me/{ADMIN_USERNAME}")]
    ]
    return welcome_text, types.InlineKeyboardMarkup(inline_keyboard=kb)


@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    text, keyboard = await get_main_menu(message)
    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


@dp.message(Command("bulkstock"))
async def bulk_add_stock(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⚠️ You are not authorized!")
        return
    
    lines = message.text.split("\n")
    if len(lines) < 2:
        await message.answer("⚠️ Format:\n`/bulkstock`\n`link1`\n`link2`", parse_mode="Markdown")
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
    shop_text = "🛒 **TradeHub Store - All Products**\n📦 **Page 1 of 1**\n⬇️ **Choose a product to buy:**"
    kb = [
        [types.InlineKeyboardButton(text=f"✨ Gemini Pro 18m Link - $0.38 (Stock: {stock})", callback_data="prod_gemini")],
        [types.InlineKeyboardButton(text="🔙 Back to Menu", callback_data="back_to_menu")]
    ]
    await callback.message.edit_text(shop_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data == "prod_gemini")
async def gemini_detail(callback: types.CallbackQuery):
    stock = get_stock_count("Gemini Pro 18m Link")
    product_desc = (
        "✨ **Gemini Pro 18m Link**\n\n"
        "📦 **Description:**\n• 18 Months Plan | 5TB Cloud Storage\n• 100% Private — No Sharing\n\n"
        f"💵 **Standard Price:** $0.38\n📦 **Available Stock:** {stock}\n\n🔢 **Choose Buy Quantity:**"
    )
    kb = [
        [types.InlineKeyboardButton(text="1", callback_data="buy_gemini_qty_1"),
         types.InlineKeyboardButton(text="2", callback_data="buy_gemini_qty_2"),
         types.InlineKeyboardButton(text="3", callback_data="buy_gemini_qty_3")],
        [types.InlineKeyboardButton(text="4", callback_data="buy_gemini_qty_4"),
         types.InlineKeyboardButton(text="5", callback_data="buy_gemini_qty_5")],
        [types.InlineKeyboardButton(text="🔙 Back to Shop", callback_data="shop")]
    ]
    await callback.message.edit_text(product_desc, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
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
        f"🛒 **TradeHub - Checkout Confirmation**\n\n📦 **Product:** Gemini Pro 18m Link\n"
        f"🔢 **Quantity:** {qty}\n💵 **Unit Rate:** $0.38\n💰 **Total Amount:** ${total_price:.2f}\n\n⬇️ **Select Payment Method:**"
    )
    kb = [
        [types.InlineKeyboardButton(text="💎 Pay with Crypto (Binance Pay Auto)", callback_data=f"pay_crypto_{qty}_{total_price:.2f}")],
        [types.InlineKeyboardButton(text="❌ Cancel", callback_data="shop")]
    ]
    await callback.message.edit_text(checkout_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()


@dp.callback_query(F.data.startswith("pay_crypto_"))
async def crypto_payment(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    qty = parts[2]
    amount = parts[3]

    binance_text = (
        f"💳 **TradeHub Payment Instructions**\n\n💰 **Amount to Pay:** ${amount}\n🌐 **Method:** Binance Pay Auto\n\n"
        f"📌 **Send EXACTLY ${amount} to Binance Pay UID:**\n`{BINANCE_PAY_UID}`\n\n"
        f"⚠️ **Important:** Payment karne ke baad **'Submit TxID Now'** button dabayein aur apna transaction hash bhein."
    )
    kb = [
        [types.InlineKeyboardButton(text="✍️ Submit TxID Now", callback_data=f"enter_tx_{qty}_{amount}")],
        [types.InlineKeyboardButton(text="🔙 Back", callback_data="prod_gemini")]
    ]
    await callback.message.edit_text(binance_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()


waiting_for_tx = {}

@dp.callback_query(F.data.startswith("enter_tx_"))
async def ask_txid(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    qty = parts[2]
    amount = parts[3]
    
    waiting_for_tx[callback.from_user.id] = {"qty": int(qty), "amount": float(amount)}
    await callback.message.answer("✍️ Meherbani kar ke apni payment ka **TxID (Transaction Hash)** ya payment screenshot/text yahan chat mein reply bhej dein:")
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

    await message.answer("✅ Aapka TxID receive ho gaya hai! TradeHub Admin verification ke baad product foran deliver kar diya jayega.")

    admin_text = (
        f"🔔 **TradeHub - New Order Verification!**\n\n"
        f"👤 **User:** {username} (`{user_id}`)\n"
        f"📦 **Product:** Gemini Pro 18m Link (Qty: {qty})\n"
        f"💰 **Amount:** ${amount}\n"
        f"🆔 **TxID:** `{txid}`\n\n"
        f"Approve this transaction?"
    )
    kb = [
        [
            types.InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"adm_app_{order_id}"),
            types.InlineKeyboardButton(text="❌ Reject", callback_data=f"adm_rej_{order_id}")
        ]
    ]
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")


@dp.callback_query(F.data.startswith("adm_app_") | F.data.startswith("adm_rej_"))
async def admin_decision(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⚠️ Unauthorized!", show_alert=True)
        return

    action, _, order_id_str = callback.data.rpartition("_")
    order_id = int(order_id_str)

    conn = sqlite3.connect("tradehub_shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, product_name, quantity, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()

    if not order or order[3] != "pending":
        await callback.answer("⚠️ Order already processed or not found.", show_alert=True)
        conn.close()
        return

    user_id, product_name, qty, _ = order

    if "app" in action:
        stock = get_stock_count(product_name)
        if stock < qty:
            await callback.answer(f"⚠️ Stock khatam ho chuka hai! Available: {stock}", show_alert=True)
            conn.close()
            return

        cursor.execute("SELECT id, link FROM stock WHERE product_name = ? LIMIT ?", (product_name, qty))
        rows = cursor.fetchall()
        link_ids = [r[0] for r in rows]
        links = [r[1] for r in rows]

        cursor.executemany("DELETE FROM stock WHERE id = ?", [(i,) for i in link_ids])
        cursor.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        delivered_links = "\n".join([f"🔗 {l}" for l in links])

        await bot.send_message(
            user_id,
            f"🎉 **TradeHub - Payment Verified & Approved!**\n\n📦 **Product:** {product_name} (Qty: {qty})\n\n"
            f"🔑 **Your Item(s):**\n{delivered_links}\n\nThank you for shopping with TradeHub!"
        )
        await callback.message.edit_text(callback.message.text + "\n\n✅ **Status: APPROVED & DELIVERED**")
        await callback.answer("Order approved and items dispatched!")

    else:
        cursor.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        await bot.send_message(user_id, "❌ TradeHub: Aapki payment verify nahi ho saki aur order reject kar diya gaya hai.")
        await callback.message.edit_text(callback.message.text + "\n\n❌ **Status: REJECTED**")
        await callback.answer("Order rejected.")


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    text, keyboard = await get_main_menu(callback.message)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


async def main():
    print("TradeHub Automated Store is running securely...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())