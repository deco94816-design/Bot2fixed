"""
Telegram Channel Boost Bot - Custom Stars Payment
Installation: 
pip install python-telegram-bot[job-queue] --upgrade

Requirements: 
python-telegram-bot>=20.0
APScheduler (included with job-queue extras)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, 
    CommandHandler, 
    CallbackQueryHandler, 
    MessageHandler, 
    PreCheckoutQueryHandler, 
    ContextTypes, 
    filters,
    ConversationHandler
)
import json
import asyncio
from datetime import datetime
import os

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "8520112186:AAFK7Sydbs1t2n1L7may8zBXdIn9lxmzyK4"
OWNER_ID = 5709159932
SUPPORT_USERNAME = "@GiftingSupportBot"
DATABASE_FILE = "database.json"

# Conversation states
ASKING_BOOSTS, ASKING_LINK = range(2)

# Initialize database
def load_database():
    """Load database from JSON file with error handling"""
    try:
        if os.path.exists(DATABASE_FILE):
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        logger.info("Database file not found. Creating new database.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding database JSON: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading database: {e}")
    
    # Return default database structure
    return {
        "users": {},
        "groups": {},
        "orders": [],
        "settings": {
            "announcement_interval": 3600,
            "last_announcement": None,
            "price_per_boost": 5  # 5 stars per boost
        }
    }

def save_database(data):
    """Save database to JSON file with error handling"""
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info("Database saved successfully")
    except Exception as e:
        logger.error(f"Error saving database: {e}")
        raise

db = load_database()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with error handling"""
    try:
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
            logger.info(f"New user registered: {user.id} - {user.username}")
        
        welcome_text = (
            "⭐ *Stars*\n\n"
            "➤ Crypto payments only\n"
            "➤ Manually processed\n"
            "➤ Limited slots available\n\n"
            "*View Channel/Group Perks*\n\n"
            "Note: All boosts are legitimate and obtained through fragment.com\n\n"
            "Due to the nature of this service, orders are handled carefully and on a "
            "first-come, first-served basis"
        )
        
        # Menu buttons inline keyboard
        keyboard = [
            [InlineKeyboardButton("⚡ Start Order", callback_data="start_order")],
            [InlineKeyboardButton("🔙 Back To Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown', 
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred. Please try again later or contact support."
        )

# Show menu with custom keyboard
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu with custom reply keyboard"""
    try:
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        
        # Create custom keyboard
        keyboard = [
            [KeyboardButton("💰 Balance"), KeyboardButton("📞 Contact Support")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        menu_text = (
            "📋 *Main Menu*\n\n"
            "Select an option from the menu below:"
        )
        
        if update.callback_query:
            await update.callback_query.message.reply_text(
                menu_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                menu_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"Error showing menu: {e}")

# Start order process
async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the order process"""
    try:
        query = update.callback_query
        await query.answer()
        
        keyboard = [[InlineKeyboardButton("🔙 Back To Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "🎯 *New Order*\n\n"
            "Please enter the number of boosts you need:\n\n"
            f"💎 Price: {db['settings']['price_per_boost']} ⭐ per boost\n\n"
            "Example: `10` for 10 boosts\n"
            "_(Send a number between 1 and 1000)_"
        )
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
        return ASKING_BOOSTS
        
    except Exception as e:
        logger.error(f"Error starting order: {e}")
        await query.edit_message_text("⚠️ Error starting order. Please try again.")
        return ConversationHandler.END

# Handle boost count input
async def receive_boost_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and validate boost count"""
    try:
        user_input = update.message.text.strip()
        
        # Validate input
        if not user_input.isdigit():
            await update.message.reply_text(
                "❌ Please send a valid number.\n\nExample: `10`",
                parse_mode='Markdown'
            )
            return ASKING_BOOSTS
        
        boost_count = int(user_input)
        
        if boost_count < 1 or boost_count > 1000:
            await update.message.reply_text(
                "❌ Please enter a number between 1 and 1000.",
                parse_mode='Markdown'
            )
            return ASKING_BOOSTS
        
        # Store boost count in context
        context.user_data['boost_count'] = boost_count
        price = boost_count * db['settings']['price_per_boost']
        context.user_data['price'] = price
        
        keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"✅ *Boost Count: {boost_count}*\n"
            f"💰 *Total Price: {price} ⭐*\n\n"
            "Now, please send your channel or group link:\n\n"
            "📝 *Accepted formats:*\n"
            "• `@channelname`\n"
            "• `https://t.me/channelname`\n"
            "• `t.me/channelname`"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
        return ASKING_LINK
        
    except Exception as e:
        logger.error(f"Error receiving boost count: {e}")
        await update.message.reply_text(
            "⚠️ An error occurred. Please start over with /start"
        )
        return ConversationHandler.END

# Handle channel/group link
async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive and process channel/group link"""
    try:
        link = update.message.text.strip()
        boost_count = context.user_data.get('boost_count')
        price = context.user_data.get('price')
        
        if not boost_count or not price:
            await update.message.reply_text("⚠️ Session expired. Please start over.")
            return ConversationHandler.END
        
        # Basic link validation
        if not (link.startswith('@') or 't.me' in link.lower() or 'telegram.me' in link.lower()):
            await update.message.reply_text(
                "❌ Invalid link format.\n\n"
                "Please send a valid Telegram channel/group link:\n"
                "• `@channelname`\n"
                "• `https://t.me/channelname`",
                parse_mode='Markdown'
            )
            return ASKING_LINK
        
        # Store link
        context.user_data['link'] = link
        
        # Create invoice
        title = f"{boost_count} Channel Boosts"
        description = f"Boost your channel/group: {link}"
        payload = f"boost_{update.effective_user.id}_{datetime.now().timestamp()}"
        currency = "XTR"  # Telegram Stars
        prices = [LabeledPrice("Channel Boosts", price)]
        
        keyboard = [[InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",  # Empty for Stars
            currency=currency,
            prices=prices,
            reply_markup=reply_markup
        )
        
        # Store order info temporarily
        context.user_data['payload'] = payload
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error receiving link: {e}")
        await update.message.reply_text(
            "⚠️ Error processing your request. Please contact support."
        )
        return ConversationHandler.END

# Precheckout callback
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pre-checkout query"""
    try:
        query = update.pre_checkout_query
        await query.answer(ok=True)
        logger.info(f"Pre-checkout approved for user {query.from_user.id}")
    except Exception as e:
        logger.error(f"Error in precheckout: {e}")
        await query.answer(ok=False, error_message="Payment processing error. Please try again.")

# Successful payment
async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment"""
    try:
        user = update.effective_user
        payment = update.message.successful_payment
        
        # Retrieve order details from context
        boost_count = context.user_data.get('boost_count', 0)
        link = context.user_data.get('link', 'N/A')
        price = context.user_data.get('price', 0)
        
        # Create order
        order = {
            "order_id": len(db["orders"]) + 1,
            "user_id": user.id,
            "username": user.username or "N/A",
            "boost_count": boost_count,
            "link": link,
            "price": price,
            "date": datetime.now().isoformat(),
            "telegram_payment_charge_id": payment.telegram_payment_charge_id,
            "status": "pending"
        }
        
        db["orders"].append(order)
        
        # Update user data
        if str(user.id) in db["users"]:
            db["users"][str(user.id)]["total_spent"] += price
            db["users"][str(user.id)]["orders"].append(order["order_id"])
        
        save_database(db)
        
        logger.info(f"Order #{order['order_id']} created for user {user.id}")
        
        # Send receipt to user
        receipt_text = (
            "✅ *Payment Successful!*\n\n"
            f"*Order ID:* #{order['order_id']}\n"
            f"*Boosts:* {boost_count}\n"
            f"*Channel/Group:* `{link}`\n"
            f"*Amount Paid:* {price} ⭐\n"
            f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"*Status:* ⏳ Pending\n\n"
            "📋 Your order is being processed manually.\n"
            "⏱️ Delivery within 1-24 hours.\n\n"
            f"Need help? Contact {SUPPORT_USERNAME}\n\n"
            "Thank you for your order! 🎉"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back To Menu", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(receipt_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Notify owner
        owner_text = (
            "🔔 *New Order Received!*\n\n"
            f"*Order ID:* #{order['order_id']}\n"
            f"*Customer:* {user.first_name} (@{user.username or 'no_username'})\n"
            f"*User ID:* `{user.id}`\n"
            f"*Boosts:* {boost_count}\n"
            f"*Channel/Group:* `{link}`\n"
            f"*Amount:* {price} ⭐\n"
            f"*Payment ID:* `{payment.telegram_payment_charge_id}`\n"
            f"*Status:* Pending\n\n"
            "⚠️ Please process this order manually."
        )
        
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=owner_text,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Could not send notification to owner: {e}")
        
        # Clear user data
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error processing successful payment: {e}")
        await update.message.reply_text(
            f"⚠️ Payment received but error saving order. Please contact {SUPPORT_USERNAME} immediately!"
        )

# Balance button handler
async def balance_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle balance button press"""
    try:
        text = (
            "💰 *Balance*\n\n"
            "This bot uses Telegram Stars for payments.\n\n"
            "You can purchase Stars directly from Telegram:\n"
            "Settings → Telegram Stars → Buy Stars\n\n"
            f"💎 Current Rate: {db['settings']['price_per_boost']} ⭐ per boost\n\n"
            "Need help? Contact support!"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error displaying balance: {e}")
        await update.message.reply_text("⚠️ Error loading balance info.")

# Contact support button handler
async def contact_support_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact support button press"""
    try:
        keyboard = [
            [InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            "📞 *Contact Support*\n\n"
            f"Need assistance? Our support team is here to help!\n\n"
            f"Click the button below to contact: {SUPPORT_USERNAME}\n\n"
            "⏰ Available 24/7"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error showing support: {e}")
        await update.message.reply_text("⚠️ Error loading support info.")

# Admin panel (hidden from regular users)
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin panel - command based, not button"""
    try:
        if update.effective_user.id != OWNER_ID:
            return
        
        total_users = len(db["users"])
        total_orders = len(db["orders"])
        pending_orders = len([o for o in db["orders"] if o["status"] == "pending"])
        total_revenue = sum(order["price"] for order in db["orders"])
        total_groups = len(db["groups"])
        
        text = (
            "👨‍💼 *Admin Panel*\n\n"
            f"👥 Total Users: {total_users}\n"
            f"📦 Total Orders: {total_orders}\n"
            f"⏳ Pending Orders: {pending_orders}\n"
            f"⭐ Total Revenue: {total_revenue} Stars\n"
            f"💬 Joined Groups: {total_groups}\n\n"
            "Use /vieworders to see recent orders"
        )
        
        await update.message.reply_text(text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error displaying admin panel: {e}")

# Add group command
async def addgg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add group to database"""
    try:
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ This command is restricted to owner only!")
            return
        
        chat = update.effective_chat
        
        if chat.type not in ['group', 'supergroup']:
            await update.message.reply_text("⚠️ This command must be used in a group!")
            return
        
        group_id = str(chat.id)
        
        if group_id not in db["groups"]:
            db["groups"][group_id] = {
                "title": chat.title,
                "added_date": datetime.now().isoformat(),
                "announcement_enabled": True
            }
            save_database(db)
            logger.info(f"Group added: {chat.title} ({chat.id})")
            
            receipt_text = (
                "✅ *Group Successfully Added!*\n\n"
                "⭐ *Stars Boost Service*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"*Group Name:* {chat.title}\n"
                f"*Group ID:* `{chat.id}`\n"
                f"*Added By:* Owner\n"
                f"*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"*Status:* 🟢 Active\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "📢 Announcements: Enabled\n"
                "🔔 This group will receive promotional updates!\n\n"
                "Thank you for joining! 🎉"
            )
            
            await update.message.reply_text(receipt_text, parse_mode='Markdown')
        else:
            await update.message.reply_text("ℹ️ This group is already registered!")
            
    except Exception as e:
        logger.error(f"Error adding group: {e}")
        await update.message.reply_text("⚠️ Error adding group. Please try again.")

# Periodic announcement
async def send_announcement(context: ContextTypes.DEFAULT_TYPE):
    """Send periodic announcements to all groups"""
    try:
        announcement = (
            "⭐ *Stars Boost Service*\n\n"
            "🚀 *Boost Your Channel Today!*\n\n"
            "✨ Custom boost packages\n"
            "⚡ Fast delivery (1-24 hours)\n"
            "💎 Secure payment via Telegram Stars\n"
            "🔒 100% Legitimate boosts\n\n"
            f"💰 Starting from {db['settings']['price_per_boost']} ⭐ per boost\n\n"
            "Ready to grow? Start your order now!\n"
            "Use /start to begin! 🎯"
        )
        
        sent_count = 0
        failed_count = 0
        
        for group_id, group_data in db["groups"].items():
            if group_data.get("announcement_enabled", True):
                try:
                    await context.bot.send_message(
                        chat_id=int(group_id),
                        text=announcement,
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Could not send announcement to {group_id}: {e}")
                    failed_count += 1
        
        logger.info(f"Announcements sent: {sent_count} succeeded, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Error in announcement task: {e}")

# Back to menu
async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    try:
        query = update.callback_query
        await query.answer()
        
        welcome_text = (
            "⭐ *Stars*\n\n"
            "➤ Crypto payments only\n"
            "➤ Manually processed\n"
            "➤ Limited slots available\n\n"
            "*View Channel/Group Perks*\n\n"
            "Note: All boosts are legitimate and obtained through fragment.com\n\n"
            "Due to the nature of this service, orders are handled carefully and on a "
            "first-come, first-served basis"
        )
        
        keyboard = [
            [InlineKeyboardButton("⚡ Start Order", callback_data="start_order")],
            [InlineKeyboardButton("🔙 Back To Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Show custom keyboard again
        from telegram import ReplyKeyboardMarkup, KeyboardButton
        keyboard_menu = [
            [KeyboardButton("💰 Balance"), KeyboardButton("📞 Contact Support")],
        ]
        reply_markup_menu = ReplyKeyboardMarkup(keyboard_menu, resize_keyboard=True)
        
        await query.message.reply_text(
            "Use the menu buttons below:",
            reply_markup=reply_markup_menu
        )
        
    except Exception as e:
        logger.error(f"Error returning to menu: {e}")

# Cancel order
async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel ongoing order"""
    try:
        query = update.callback_query
        await query.answer("Order cancelled", show_alert=True)
        
        context.user_data.clear()
        await back_to_menu(update, context)
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return ConversationHandler.END

# Button callback handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    try:
        query = update.callback_query
        
        if query.data == "start_order":
            return await start_order(update, context)
        elif query.data == "back_to_menu":
            await back_to_menu(update, context)
        elif query.data == "cancel_order":
            return await cancel_order(update, context)
        else:
            await query.answer("Feature coming soon!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error handling button callback: {e}")
        try:
            await query.answer("Error processing request", show_alert=True)
        except:
            pass

def main():
    """Start the bot"""
    try:
        logger.info("Starting bot...")
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Conversation handler for orders
        order_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(start_order, pattern="^start_order$")],
            states={
                ASKING_BOOSTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_boost_count)],
                ASKING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            },
            fallbacks=[CallbackQueryHandler(cancel_order, pattern="^cancel_order$")],
        )
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("addgg", addgg))
        application.add_handler(CommandHandler("admin", admin))
        application.add_handler(order_conv_handler)
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
        application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
        
        # Handle custom keyboard buttons
        application.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance_button))
        application.add_handler(MessageHandler(filters.Regex("^📞 Contact Support$"), contact_support_button))
        
        # Schedule periodic announcements
        job_queue = application.job_queue
        job_queue.run_repeating(
            send_announcement, 
            interval=db['settings']['announcement_interval'], 
            first=10
        )
        
        logger.info("⭐ Stars Boost Bot started successfully!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.critical(f"Critical error starting bot: {e}")
        raise

if __name__ == '__main__':
    main()
