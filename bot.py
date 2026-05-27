import os
import sqlite3
import threading
import os


from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TOKEN") or "8683806147:AAEP4CrAnr0uiYSwgaGYdhme1RzUAJkWNuw"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 495780952)

DB = "shop.db"

def db():
    return sqlite3.connect(DB)

ASK_QTY, ASK_NAME, ASK_PHONE, ASK_ADDRESS, ASK_COMMENT = range(5)





  

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price INTEGER,
            stock INTEGER,
            photo_url TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            name TEXT,
            phone TEXT,
            address TEXT,
            comment TEXT,
            total INTEGER,
            items TEXT,
            status TEXT DEFAULT 'Новый'
        )
    """)

    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
            INSERT INTO products (name, description, price, stock)
            VALUES (?, ?, ?, ?)
        """, [
            [
              ("🚬 Marlboro Gold", "Оригинал", 70, 20),
              ("🚬 Winston Blue", "С кнопкой", 70, 20),
              ("🚬 Parliament Aqua", "Тонкие", 75, 25),
],
        ])

    con.commit()
    con.close()


def menu():
    return ReplyKeyboardMarkup(
        [
            ["🛍 Каталог", "🛒 Корзина"],
            ["✅ Оформить заказ", "🗑 Очистить корзину"],
            ["ℹ️ Помощь"],
        ],
        resize_keyboard=True,
    )


def back_menu():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


def admin_only(user_id):
    return user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.setdefault("cart", {})
    await update.message.reply_text(
        "👋 Добро пожаловать в магазин!\n\nВыбери действие:",
        reply_markup=menu(),
    )


async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, description, price, stock, photo_url FROM products")
    products = cur.fetchall()
    con.close()

    if not products:
        await update.message.reply_text("Каталог пока пустой.", reply_markup=menu())
        return

    buttons = []

    for product_id, name, desc, price, stock, photo in products:
        text = (
            f"📦 {name}\n\n"
            f"📝 {desc}\n"
            f"💰 Цена: {price} ₽\n"
            f"📊 Остаток: {stock} шт."
        )

        if photo:
            await update.message.reply_photo(photo=photo, caption=text)
        else:
            await update.message.reply_text(text)

        if stock > 0:
            buttons.append([f"➕ Добавить {product_id}"])

    buttons.append(["⬅️ Назад"])

    await update.message.reply_text(
        "Выбери товар:",
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True),
    )


async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=menu())
        return ConversationHandler.END

    product_id = text.replace("➕ Добавить ", "").strip()

    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, stock FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    con.close()

    if not product:
        await update.message.reply_text("Товар не найден.", reply_markup=menu())
        return ConversationHandler.END

    context.user_data["selected_product"] = product_id

    await update.message.reply_text(
        f"Сколько штук добавить?\n\n"
        f"📦 {product[1]}\n"
        f"📊 В наличии: {product[2]} шт.",
        reply_markup=back_menu(),
    )

    return ASK_QTY


async def ask_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        await catalog(update, context)
        return ConversationHandler.END

    try:
        qty = int(text)
    except ValueError:
        await update.message.reply_text("Напиши количество числом.")
        return ASK_QTY

    if qty <= 0:
        await update.message.reply_text("Количество должно быть больше нуля.")
        return ASK_QTY

    product_id = context.user_data.get("selected_product")

    con = db()
    cur = con.cursor()
    cur.execute("SELECT name, stock FROM products WHERE id = ?", (product_id,))
    product = cur.fetchone()
    con.close()

    if not product:
        await update.message.reply_text("Товар не найден.", reply_markup=menu())
        return ConversationHandler.END

    name, stock = product

    if qty > stock:
        await update.message.reply_text(f"В наличии только {stock} шт.")
        return ASK_QTY

    cart = context.user_data.setdefault("cart", {})
    cart[product_id] = cart.get(product_id, 0) + qty

    await update.message.reply_text(
        f"✅ Добавлено в корзину:\n\n"
        f"📦 {name}\n"
        f"🔢 Количество: {qty} шт.",
        reply_markup=menu(),
    )

    return ConversationHandler.END


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = context.user_data.get("cart", {})

    if not cart:
        await update.message.reply_text("🛒 Корзина пустая.", reply_markup=menu())
        return

    con = db()
    cur = con.cursor()

    total = 0
    text = "🛒 Ваша корзина:\n\n"

    for product_id, qty in cart.items():
        cur.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
        product = cur.fetchone()

        if product:
            name, price = product
            subtotal = price * qty
            total += subtotal

            text += (
                f"📦 {name}\n"
                f"🔢 Количество: {qty} шт.\n"
                f"💵 Сумма: {subtotal} ₽\n\n"
            )

    con.close()

    text += f"💰 Итого: {total} ₽"

    await update.message.reply_text(text, reply_markup=menu())


async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cart"] = {}
    await update.message.reply_text("🗑 Корзина очищена.", reply_markup=menu())


async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("cart"):
        await update.message.reply_text("🛒 Корзина пустая.", reply_markup=menu())
        return ConversationHandler.END

    await update.message.reply_text("👤 Напиши имя:", reply_markup=back_menu())
    return ASK_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("Главное меню:", reply_markup=menu())
        return ConversationHandler.END

    context.user_data["customer_name"] = update.message.text

    phone_button = KeyboardButton(
        "📞 Отправить номер телефона",
        request_contact=True,
    )

    await update.message.reply_text(
        "📞 Отправь номер телефона:",
        reply_markup=ReplyKeyboardMarkup(
            [[phone_button], ["⬅️ Назад"]],
            resize_keyboard=True,
        ),
    )

    return ASK_PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("👤 Напиши имя:", reply_markup=back_menu())
        return ASK_NAME

    if update.message.contact:
        context.user_data["customer_phone"] = update.message.contact.phone_number
    else:
        context.user_data["customer_phone"] = update.message.text

    await update.message.reply_text("📍 Напиши адрес доставки:", reply_markup=back_menu())
    return ASK_ADDRESS


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        phone_button = KeyboardButton(
            "📞 Отправить номер телефона",
            request_contact=True,
        )

        await update.message.reply_text(
            "📞 Отправь номер телефона:",
            reply_markup=ReplyKeyboardMarkup(
                [[phone_button], ["⬅️ Назад"]],
                resize_keyboard=True,
            ),
        )

        return ASK_PHONE

    context.user_data["customer_address"] = update.message.text

    await update.message.reply_text(
        "💬 Напиши комментарий к заказу или отправь «-»:",
        reply_markup=back_menu(),
    )

    return ASK_COMMENT


async def get_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "⬅️ Назад":
        await update.message.reply_text("📍 Напиши адрес доставки:", reply_markup=back_menu())
        return ASK_ADDRESS

    comment = update.message.text
    if comment == "-":
        comment = "Без комментария"

    cart = context.user_data.get("cart", {})
    customer_name = context.user_data["customer_name"]
    phone = context.user_data["customer_phone"]
    address = context.user_data["customer_address"]

    user = update.effective_user
    username = f"@{user.username}" if user.username else "Без username"

    con = db()
    cur = con.cursor()

    total = 0
    items_text = ""

    for product_id, qty in cart.items():
        cur.execute(
            "SELECT name, description, price, stock FROM products WHERE id = ?",
            (product_id,),
        )
        product = cur.fetchone()

        if not product:
            continue

        name, desc, price, stock = product

        if qty > stock:
            await update.message.reply_text(
                f"❌ Недостаточно товара: {name}\n"
                f"В наличии: {stock} шт.",
                reply_markup=menu(),
            )
            con.close()
            return ConversationHandler.END

        subtotal = price * qty
        total += subtotal

        items_text += (
            f"📦 {name}\n"
            f"📝 {desc}\n"
            f"🔢 Количество: {qty} шт.\n"
            f"💵 Сумма: {subtotal} ₽\n\n"
        )

        cur.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (qty, product_id),
        )

    cur.execute("""
        INSERT INTO orders 
        (user_id, username, name, phone, address, comment, total, items)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user.id,
        username,
        customer_name,
        phone,
        address,
        comment,
        total,
        items_text,
    ))

    order_id = cur.lastrowid

    con.commit()
    con.close()

    client_text = (
        f"✅ Заказ оформлен!\n\n"
        f"🧾 Номер заказа: #{order_id}\n"
        f"💰 Сумма: {total} ₽\n\n"
        f"Мы скоро свяжемся с вами."
    )

    admin_text = (
        f"🛒 НОВЫЙ ЗАКАЗ #{order_id}\n\n"
        f"👤 Клиент: {customer_name}\n"
        f"🆔 Telegram ID: {user.id}\n"
        f"🔗 Username: {username}\n"
        f"📞 Телефон: {phone}\n"
        f"📍 Адрес: {address}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"📦 Товары:\n\n"
        f"{items_text}"
        f"💰 Итого: {total} ₽"
    )

    await update.message.reply_text(client_text, reply_markup=menu())
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text)

    context.user_data["cart"] = {}

    return ConversationHandler.END


async def help_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Помощь\n\n"
        "1. Нажми «🛍 Каталог»\n"
        "2. Выбери товар\n"
        "3. Укажи количество\n"
        "4. Проверь корзину\n"
        "5. Нажми «✅ Оформить заказ»\n\n"
        "👑 Админ-команды:\n"
        "/admin\n"
        "/add Название | Описание | Цена | Количество | Фото_URL\n"
        "/stock\n"
        "/orders\n"
        "/status ID Статус",
        reply_markup=menu(),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    await update.message.reply_text(
        "👑 Админ-панель\n\n"
        "/add Название | Описание | Цена | Количество | Фото_URL\n"
        "/stock — остатки\n"
        "/orders — последние заказы\n"
        "/status ID Статус — изменить статус заказа"
    )


async def add_admin_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    raw = update.message.text.replace("/add", "", 1).strip()
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) < 4:
        await update.message.reply_text(
            "Формат:\n"
            "/add Название | Описание | Цена | Количество | Фото_URL\n\n"
            "Фото_URL можно не указывать."
        )
        return

    try:
        name = parts[0]
        desc = parts[1]
        price = int(parts[2])
        stock = int(parts[3])
        photo = parts[4] if len(parts) >= 5 else ""
    except ValueError:
        await update.message.reply_text("Цена и количество должны быть числами.")
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO products (name, description, price, stock, photo_url)
        VALUES (?, ?, ?, ?, ?)
    """, (name, desc, price, stock, photo))

    con.commit()
    con.close()

    await update.message.reply_text("✅ Товар добавлен.")


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    con = db()
    cur = con.cursor()
    cur.execute("SELECT id, name, stock, price FROM products")
    products = cur.fetchall()
    con.close()

    if not products:
        await update.message.reply_text("Товаров нет.")
        return

    text = "📊 Остатки товаров:\n\n"

    for product_id, name, stock_count, price in products:
        text += f"{product_id}. {name} — {stock_count} шт. — {price} ₽\n"

    await update.message.reply_text(text)


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        SELECT id, name, phone, address, total, status
        FROM orders
        ORDER BY id DESC
        LIMIT 10
    """)

    rows = cur.fetchall()
    con.close()

    if not rows:
        await update.message.reply_text("Заказов пока нет.")
        return

    text = "🧾 Последние заказы:\n\n"

    for order_id, name, phone, address, total, status in rows:
        text += (
            f"#{order_id}\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"📍 {address}\n"
            f"💰 {total} ₽\n"
            f"📌 Статус: {status}\n\n"
        )

    await update.message.reply_text(text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_only(update.effective_user.id):
        await update.message.reply_text("⛔ Нет доступа.")
        return

    args = context.args

    if len(args) < 2:
        await update.message.reply_text("Формат:\n/status ID Статус")
        return

    order_id = args[0]
    new_status = " ".join(args[1:])

    con = db()
    cur = con.cursor()
    cur.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    con.commit()
    con.close()

    await update.message.reply_text(
        f"✅ Статус заказа #{order_id} изменён на: {new_status}"
    )


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню:", reply_markup=menu())
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=menu())
    return ConversationHandler.END


def main():
    init_db()

    web_thread = threading.Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    app = Application.builder().token(TOKEN).build()

    add_to_cart = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Добавить \\d+$"), add_product),
        ],
        states={
            ASK_QTY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_qty),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    checkout_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✅ Оформить заказ$"), checkout),
        ],
        states={
            ASK_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            ASK_PHONE: [
                MessageHandler(
                    (filters.TEXT | filters.CONTACT) & ~filters.COMMAND,
                    get_phone,
                ),
            ],
            ASK_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_address),
            ],
            ASK_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_comment),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("add", add_admin_product))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("status", status))

    app.add_handler(add_to_cart)
    app.add_handler(checkout_handler)

    app.add_handler(MessageHandler(filters.Regex("^🛍 Каталог$"), catalog))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Корзина$"), show_cart))
    app.add_handler(MessageHandler(filters.Regex("^🗑 Очистить корзину$"), clear_cart))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Помощь$"), help_text))
    app.add_handler(MessageHandler(filters.Regex("^⬅️ Назад$"), back_to_menu))

    print("Бот запущен...")

    import asyncio

    asyncio.set_event_loop(asyncio.new_event_loop())

    app.run_polling()


if __name__ == "__main__":
    main()