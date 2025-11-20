import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
import json
import asyncio
from datetime import datetime, timedelta
import os

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8520112186:AAFK7Sydbs1t2n1L7may8zBXdIn9lxmzyK4"
OWNER_ID = 5709159932 # Replace with your Telegram user ID
PROVIDER_TOKEN = ""  # Stars payments don't need provider token
DATABASE_FILE = "database.json"

# Initialize database
def load_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r') as f:
            return json.load(f)
    return {
        "users": {},
        "groups": {},
        "orders": [],
        "packages": {
            "basic": {"name": "🎓 Basic Boost", "boosts": 10, "price": 50, "description": "Perfect for beginners"},
            "pro": {"name": "👨‍🎓 Pro Boost", "boosts": 25, "price": 100, "description": "For growing channels"},
            "elite": {"name": "🎖️ Elite Boost", "boosts": 50, "price": 180, "description": "Maximum impact"}
        },
        "settings": {
            "announcement_interval": 3600,  # 1 hour in seconds
            "last_announcement": None
        }
    }

def save_database(data):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

db = load_database()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Save user to database
    if str(user.id) not in db["users"]:
        db["users"][str(user.id)] = {
            "username": user.username,
            "first_name": user.first_name,
            "joined_date": datetime.now().isoformat(),
            "total_spent": 0,
            "orders": []
        }
        save_database(db)
    
    keyboard = [
        [InlineKeyboardButton("📚 View Packages", callback_data="view_packages")],
        [InlineKeyboardButton("📊 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("💬 Support", callback_data="support"), 
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    
    if user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🎓 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"🎓 *Welcome to Professor's Boost Academy, {user.first_name}!*\n\n"
        "📈 *Elevate your channel to academic excellence!*\n\n"
        "Our premium boost services are designed with scholarly precision "
        "to amplify your channel's reach and engagement.\n\n"
        "🔬 *What we offer:*\n"
        "✓ Genuine channel boosts\n"
        "✓ Instant delivery\n"
        "✓ Secure payment via Telegram Stars ⭐\n"
        "✓ 24/7 scholarly support\n\n"
        "Select an option below to begin your academic journey!"
    )
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

# View packages
async def view_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    text = "🎓 *Professor's Boost Packages*\n\n"
    
    for key, package in db["packages"].items():
        text += f"*{package['name']}*\n"
        text += f"📦 Boosts: {package['boosts']}\n"
        text += f"⭐ Price: {package['price']} Stars\n"
        text += f"📝 {package['description']}\n\n"
        keyboard.append([InlineKeyboardButton(f"🛒 Buy {package['name']}", callback_data=f"buy_{key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Buy package
async def buy_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    package_key = query.data.split("_")[1]
    package = db["packages"][package_key]
    
    keyboard = [
        [InlineKeyboardButton("⭐ Pay with Stars", callback_data=f"pay_{package_key}")],
        [InlineKeyboardButton("🔙 Back", callback_data="view_packages")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        f"🎓 *{package['name']}*\n\n"
        f"📦 *Boosts Included:* {package['boosts']}\n"
        f"⭐ *Price:* {package['price']} Stars\n"
        f"📝 *Description:* {package['description']}\n\n"
        f"*📋 What you'll receive:*\n"
        f"✓ {package['boosts']} genuine channel boosts\n"
        f"✓ Instant activation\n"
        f"✓ Lifetime validity\n"
        f"✓ Full support\n\n"
        f"Ready to proceed with payment?"
    )
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Create invoice
async def create_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    package_key = query.data.split("_")[1]
    package = db["packages"][package_key]
    
    title = package["name"]
    description = f"{package['boosts']} Channel Boosts - {package['description']}"
    payload = f"boost_{package_key}_{query.from_user.id}"
    currency = "XTR"  # Telegram Stars currency
    prices = [LabeledPrice("Channel Boosts", package["price"])]
    
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=currency,
        prices=prices
    )

# Precheckout callback
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

# Successful payment
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payment = update.message.successful_payment
    payload_parts = payment.invoice_payload.split("_")
    package_key = payload_parts[1]
    package = db["packages"][package_key]
    
    # Create order
    order = {
        "order_id": len(db["orders"]) + 1,
        "user_id": user.id,
        "username": user.username,
        "package": package_key,
        "boosts": package["boosts"],
        "price": package["price"],
        "date": datetime.now().isoformat(),
        "telegram_payment_charge_id": payment.telegram_payment_charge_id
    }
    
    db["orders"].append(order)
    db["users"][str(user.id)]["total_spent"] += package["price"]
    db["users"][str(user.id)]["orders"].append(order["order_id"])
    save_database(db)
    
    # Send receipt to user
    receipt_text = (
        f"🎓 *Payment Successful!*\n\n"
        f"*Order ID:* #{order['order_id']}\n"
        f"*Package:* {package['name']}\n"
        f"*Boosts:* {package['boosts']}\n"
        f"*Amount Paid:* {package['price']} ⭐\n"
        f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"✅ Your boosts will be delivered within 24 hours!\n"
        f"📧 Order confirmation sent to your DM.\n\n"
        f"Thank you for choosing Professor's Boost Academy! 🎓"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(receipt_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Notify owner
    owner_text = (
        f"💰 *New Order Received!*\n\n"
        f"*Order ID:* #{order['order_id']}\n"
        f"*Customer:* @{user.username} ({user.id})\n"
        f"*Package:* {package['name']}\n"
        f"*Boosts:* {package['boosts']}\n"
        f"*Amount:* {package['price']} ⭐\n"
        f"*Payment ID:* `{payment.telegram_payment_charge_id}`"
    )
    
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=owner_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Could not send notification to owner: {e}")

# My orders
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_data = db["users"].get(user_id)
    
    if not user_data or not user_data["orders"]:
        text = "📚 *Your Order History*\n\nYou haven't placed any orders yet.\n\nExplore our packages and make your first purchase!"
        keyboard = [[InlineKeyboardButton("📚 View Packages", callback_data="view_packages")],
                   [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    else:
        text = f"📚 *Your Order History*\n\n*Total Spent:* {user_data['total_spent']} ⭐\n\n"
        
        for order_id in user_data["orders"][-5:]:  # Last 5 orders
            order = next((o for o in db["orders"] if o["order_id"] == order_id), None)
            if order:
                pkg = db["packages"][order["package"]]
                text += f"*Order #{order['order_id']}*\n"
                text += f"📦 {pkg['name']} - {order['boosts']} boosts\n"
                text += f"⭐ {order['price']} Stars\n"
                text += f"📅 {order['date'][:10]}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.from_user.id != OWNER_ID:
        await query.answer("⛔ Access denied! Professor privileges required.", show_alert=True)
        return
    
    await query.answer()
    
    total_users = len(db["users"])
    total_orders = len(db["orders"])
    total_revenue = sum(order["price"] for order in db["orders"])
    total_groups = len(db["groups"])
    
    text = (
        f"🎓 *Professor's Admin Panel*\n\n"
        f"📊 *Statistics:*\n"
        f"👥 Total Users: {total_users}\n"
        f"📦 Total Orders: {total_orders}\n"
        f"⭐ Total Revenue: {total_revenue} Stars\n"
        f"💬 Joined Groups: {total_groups}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="broadcast")],
        [InlineKeyboardButton("📊 View All Orders", callback_data="view_all_orders")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Add group command
async def addgg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ This command is restricted to Professor only!")
        return
    
    chat = update.effective_chat
    
    if chat.type in ['group', 'supergroup']:
        group_id = str(chat.id)
        
        if group_id not in db["groups"]:
            db["groups"][group_id] = {
                "title": chat.title,
                "added_date": datetime.now().isoformat(),
                "announcement_enabled": True
            }
            save_database(db)
            
            # Send payment receipt style message in group
            receipt_text = (
                f"✅ *Group Successfully Added!*\n\n"
                f"🎓 *Professor's Boost Academy*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"*Group Name:* {chat.title}\n"
                f"*Group ID:* `{chat.id}`\n"
                f"*Added By:* Professor\n"
                f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"*Status:* 🟢 Active\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📢 Announcements: Enabled\n"
                f"🔔 This group will receive promotional updates!\n\n"
                f"Thank you for joining our academic network! 🎓"
            )
            
            await update.message.reply_text(receipt_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("ℹ️ This group is already in the database!")
    else:
        await update.message.reply_text("⚠️ This command must be used in a group!")

# Periodic announcement
async def send_announcement(context: ContextTypes.DEFAULT_TYPE):
    announcement = (
        f"🎓 *Professor's Boost Academy*\n\n"
        f"📈 *Boost Your Channel to Excellence!*\n\n"
        f"🔬 Premium Channel Boost Services\n"
        f"⭐ Secure Payment via Telegram Stars\n"
        f"🚀 Instant Delivery\n"
        f"💯 100% Genuine Boosts\n\n"
        f"*Special Packages Available!*\n"
        f"🎓 Basic: 10 Boosts - 50 ⭐\n"
        f"👨‍🎓 Pro: 25 Boosts - 100 ⭐\n"
        f"🎖️ Elite: 50 Boosts - 180 ⭐\n\n"
        f"Start your journey now! /start"
    )
    
    for group_id, group_data in db["groups"].items():
        if group_data.get("announcement_enabled", True):
            try:
                await context.bot.send_message(
                    chat_id=int(group_id),
                    text=announcement,
                    parse_mode='Markdown'
                )
                await asyncio.sleep(2)  # Delay between messages
            except Exception as e:
                logger.error(f"Could not send announcement to {group_id}: {e}")

# Back to menu
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("📚 View Packages", callback_data="view_packages")],
        [InlineKeyboardButton("📊 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("💬 Support", callback_data="support"), 
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    
    if user.id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🎓 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"🎓 *Welcome back, {user.first_name}!*\n\n"
        "Select an option to continue:"
    )
    
    await query.edit_message_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

# Support and About handlers
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "💬 *Support Center*\n\n"
        "Need assistance? Our academic advisors are here to help!\n\n"
        "📧 Contact: @YourSupportUsername\n"
        "⏰ Available: 24/7\n\n"
        "We typically respond within 1 hour!"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "ℹ️ *About Professor's Boost Academy*\n\n"
        "We are the leading provider of premium channel boost services, "
        "combining academic excellence with cutting-edge technology.\n\n"
        "🎓 *Our Mission:*\n"
        "To elevate channels to their full potential through genuine, "
        "high-quality boost services.\n\n"
        "✨ *Why Choose Us?*\n"
        "• 100% Genuine Boosts\n"
        "• Instant Delivery\n"
        "• Secure Payments\n"
        "• 24/7 Support\n"
        "• Trusted by Thousands\n\n"
        "Join the academic excellence today! 🚀"
    )
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

# Button callback handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data == "view_packages":
        await view_packages(update, context)
    elif query.data.startswith("buy_"):
        await buy_package(update, context)
    elif query.data.startswith("pay_"):
        await create_invoice(update, context)
    elif query.data == "my_orders":
        await my_orders(update, context)
    elif query.data == "admin_panel":
        await admin_panel(update, context)
    elif query.data == "back_to_menu":
        await back_to_menu(update, context)
    elif query.data == "support":
        await support(update, context)
    elif query.data == "about":
        await about(update, context)

def main():
    """Start the bot."""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addgg", addgg))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    # Schedule periodic announcements (every hour)
    job_queue = application.job_queue
    job_queue.run_repeating(send_announcement, interval=3600, first=10)
    
    # Start the bot
    logger.info("🎓 Professor's Boost Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
