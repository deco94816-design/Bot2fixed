import logging
import random
import json
import os
from datetime import datetime
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, MessageHandler, filters, ContextTypes
)

# ---------------- BOT CONFIG ----------------
BOT_TOKEN = "8348955915:AAHlMAcCsUO6yL_0odTGKqf7JPuvAmHas-U"
ADMIN_IDS = [5709159932]  # Replace with your Telegram ID
STARS_TO_TICKETS_RATIO = 2  # 1 Star = 2 Tickets

# JSON file paths
USERS_FILE = "users_data.json"
TRANSACTIONS_FILE = "transactions.json"
CONFIG_FILE = "config.json"

# Star packages
STAR_PACKAGES = [
    {"stars": 1, "tickets": 2},
    {"stars": 5, "tickets": 10},
    {"stars": 10, "tickets": 20},
    {"stars": 25, "tickets": 50},
]

# Confirmation image
CONFIRMATION_IMAGE = "https://i.pinimg.com/736x/d4/fc/6a/d4fc6a3e8f8e8c0c8f8e8c0c8f8e8c0c.jpg"

# ---------------- LOGGING ----------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- DATA ----------------
users_data = {}
transactions = []
config = {
    "giveaway_active": False,
    "total_pot": 0,
    "banned_users": [],
    "announcement_groups": []
}

# ---------------- HELPER FUNCTIONS ----------------
def load_data():
    """Load all JSON data safely"""
    global users_data, transactions, config
    
    # Load users
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users_data_raw = json.load(f)
                # Convert string keys to int and fix missing fields
                users_data.clear()
                for k, v in users_data_raw.items():
                    users_data[int(k)] = {
                        "tickets": v.get("tickets", 0),
                        "stars_paid": v.get("stars_paid", 0),
                        "username": v.get("username", "Unknown"),
                        "first_name": v.get("first_name", "")
                    }
            logger.info(f"Loaded {len(users_data)} users")
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            users_data.clear()
    
    # Load transactions
    if os.path.exists(TRANSACTIONS_FILE):
        try:
            with open(TRANSACTIONS_FILE, 'r', encoding='utf-8') as f:
                transactions.clear()
                transactions.extend(json.load(f))
            logger.info(f"Loaded {len(transactions)} transactions")
        except Exception as e:
            logger.error(f"Error loading transactions: {e}")
            transactions.clear()
    
    # Load config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
            logger.info("Loaded config")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

def save_users_data():
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def save_transaction(user_id, username, stars, tickets, transaction_id):
    try:
        transaction = {
            "user_id": user_id,
            "username": username,
            "stars": stars,
            "tickets": tickets,
            "transaction_id": transaction_id,
            "timestamp": datetime.now().isoformat()
        }
        transactions.append(transaction)
        with open(TRANSACTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(transactions, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving transaction: {e}")

def save_config():
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_banned(user_id: int) -> bool:
    return user_id in config.get("banned_users", [])

def is_giveaway_active() -> bool:
    return config.get("giveaway_active", False)

# ---------------- USER COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Welcome to the NFT Giveaway Bot!**\n"
        "_Hosted by @swizzmm_\n\n"
        "💎 Pay Stars to join the giveaway.\n"
        "🎟️ **1 Star = 2 Tickets**\n\n"
        "**Commands:**\n"
        "├─ /join `<stars>` – Enter giveaway\n"
        "├─ /mytickets – Check your tickets\n"
        "├─ /leaderboard – Top participants\n"
        "└─ /rules – Giveaway details\n\n"
        "Good luck! 🎁"
    )
    keyboard = [[InlineKeyboardButton("🎯 Participate Now", callback_data="show_packages")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("❌ You are banned from this giveaway.")
        return
    if not is_giveaway_active():
        await update.message.reply_text("❌ No active giveaway at the moment.")
        return
    await show_star_packages(update, context)

async def show_star_packages(update, context: ContextTypes.DEFAULT_TYPE):
    packages_text = (
        "⭐ **SELECT YOUR PACKAGE** ⭐\n\n"
        "Choose Stars to spend:\n"
        "💎 1 Star = 2 Tickets\n\n"
        "👇 Select a package or enter custom amount:"
    )
    keyboard = [[InlineKeyboardButton(f"⭐ {p['stars']} Stars → 🎟️ {p['tickets']} Tickets", callback_data=f"package_{p['stars']}")] for p in STAR_PACKAGES]
    keyboard.append([InlineKeyboardButton("✏️ Custom Amount", callback_data="custom_amount")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.message.edit_text(packages_text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(packages_text, parse_mode="Markdown", reply_markup=reply_markup)

# ---------------- LEADERBOARD ----------------
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not users_data:
        await update.message.reply_text("📊 No participants yet!")
        return
    try:
        sorted_users = sorted(users_data.items(), key=lambda x: x[1].get("tickets", 0), reverse=True)[:10]
        text = "🏆 **LEADERBOARD - Top 10**\n\n"
        for idx, (uid, data) in enumerate(sorted_users, 1):
            medal = "🥇" if idx==1 else "🥈" if idx==2 else "🥉" if idx==3 else f"{idx}."
            text += f"{medal} **{data.get('username','Unknown')}** └─ {data.get('tickets',0)} tickets ({data.get('stars_paid',0)}⭐)\n\n"
        text += f"👥 Participants: **{len(users_data)}**\n"
        text += f"💰 Total Pot: **{config.get('total_pot',0)}** ⭐\n"
        text += "_Hosted by @swizzmm_"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        await update.message.reply_text("❌ Error loading leaderboard. Please try again later.")

# ---------------- POT ----------------
async def pot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"💰 **Total Pot**\n\n"
        f"⭐ Stars Collected: **{config.get('total_pot',0)}**\n"
        f"🎟️ Total Tickets: **{sum(u.get('tickets',0) for u in users_data.values())}**\n"
        f"👥 Participants: **{len(users_data)}**\n\n"
        "_Hosted by @swizzmm_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ---------------- RULES ----------------
async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = (
        "📜 **GIVEAWAY RULES**\n\n"
        "1️⃣ Pay Stars to join\n"
        "2️⃣ 1 Star = 2 Tickets\n"
        "3️⃣ More tickets = Higher chance\n"
        "4️⃣ Winner selected randomly (weighted)\n"
        "5️⃣ Winner announced in chat\n"
        "6️⃣ No refunds\n\n"
        "_Hosted by @swizzmm_"
    )
    await update.message.reply_text(rules_text, parse_mode="Markdown")

# ---------------- ADMIN COMMANDS ----------------
# Start/End giveaway, pick winner, reset, balance, ban, add/remove/list groups
# ... SAME AS YOUR EXISTING CODE, just ensure using config.get(...) and users_data.get(...)

# ---------------- CALLBACKS ----------------
# Button callback for packages and custom amount
# Payment handlers
# Custom amount handlers
# ... SAME as your existing code, ensure any global variables (total_pot, announcement_groups) are replaced with:
# config.get("total_pot",0) and config.get("announcement_groups",[])

# ---------------- MAIN ----------------
def main():
    load_data()
    application = Application.builder().token(BOT_TOKEN).build()

    # User commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join_command))
    application.add_handler(CommandHandler("mytickets", lambda u,c: None))  # Add your mytickets_command
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("pot", pot_command))
    application.add_handler(CommandHandler("rules", rules_command))

    # Admin commands
    # Add all admin commands handlers here

    # Callback handlers
    application.add_handler(CallbackQueryHandler(lambda u,c: None))  # Add your button_callback

    # Payment handlers
    application.add_handler(PreCheckoutQueryHandler(lambda u,c: None))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, lambda u,c: None))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: None))  # Custom amount

    application.run_polling()

if __name__ == "__main__":
    main()
