import asyncio
import json
import os
import random
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import google.generativeai as genai

# Configuration
API_ID = '34724923'
API_HASH = 'd46f75f6dbb93156f5bd5284b5fef860'
PHONE = '+447552437615'
GEMINI_API_KEY = 'AIzaSyBpYQl_w4VCHGak7X2kgC7CF6apoLWABfM'
TARGET_GROUP_ID = -1001234567890  # Your group ID

SESSION_FILE = 'userbot_session.txt'

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Message counter
message_count = 0
last_processed_messages = []
MAX_CONTEXT = 15

# Hinglish responses for buying/selling context
CASUAL_RESPONSES = [
    "bhai kitne ka de rha? 🤔",
    "yaar thoda kam kar de na 🥺",
    "bhai negotiable hai kya?",
    "dm kar price bata",
    "escrow accept krta?",
    "ton hai kya bro?",
    "bhai ye available hai abhi?",
    "screenshot bhej bhai",
    "last price bata do yaar",
    "bhai inr me lega?",
]

# Load/save session
def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_session(session_string):
    with open(SESSION_FILE, 'w') as f:
        f.write(session_string)

session_string = load_session()
if session_string:
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
else:
    client = TelegramClient(StringSession(), API_ID, API_HASH)

async def get_hinglish_response(context_messages):
    """Generate natural Hinglish response based on context"""
    try:
        # Build context from messages
        context = "\n".join([
            f"{msg['sender']}: {msg['text']}" 
            for msg in context_messages[-10:]
        ])
        
        prompt = f"""You are a casual Indian buyer/seller in a Telegram trading group. Group mainly trades NFT usernames, TON, dollars, and digital items.

Chat context:
{context}

Generate ONE natural Hinglish response (mix of Hindi-English) like a real Indian trader would write:

RULES:
1. Use Hinglish (Hindi+English mixed) - Examples: "bhai kitne ka?", "yaar thoda kam kar", "koi selling?"
2. Be casual, use "bhai", "yaar", "bro", "kya", "hai", "ka", "de rha"
3. Ask about prices, negotiate, show interest in items being sold
4. Use emojis naturally: 🤔😅🥺💀😭🔥👀
5. Keep it SHORT - max 1-2 lines
6. Act like a buyer interested in deals OR casual observer
7. Ask questions about: price, negotiation, escrow, availability, TON
8. Use slang: "lele", "dm kar", "kitne ka", "worth", "offer", "last price"
9. React to deals happening: "nice bhai", "good deal", "mujhe bhi chahiye"
10. DON'T sound robotic or formal
11. Sometimes just send emojis or short reactions

Reply ONLY with the Hinglish message, nothing else:"""

        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        
        reply = response.text.strip()
        
        # Fallback if response too long or formal
        if len(reply) > 100 or not any(word in reply.lower() for word in ['bhai', 'yaar', 'ka', 'kya', 'hai']):
            return random.choice(CASUAL_RESPONSES)
        
        return reply
        
    except Exception as e:
        print(f"Gemini error: {e}")
        return random.choice(CASUAL_RESPONSES)

async def send_reply_to_group():
    """Send reply to recent messages in group"""
    global message_count, last_processed_messages
    
    try:
        # Get recent messages
        messages = await client.get_messages(TARGET_GROUP_ID, limit=20)
        
        if not messages:
            return
        
        # Filter text messages
        text_messages = [msg for msg in messages if msg.text and len(msg.text) > 3]
        
        if not text_messages:
            return
        
        # Build context
        context = []
        for msg in reversed(text_messages[-MAX_CONTEXT:]):
            try:
                sender = await msg.get_sender()
                sender_name = sender.first_name if sender else "User"
            except:
                sender_name = "User"
            
            context.append({
                'sender': sender_name,
                'text': msg.text,
                'id': msg.id
            })
        
        # Pick a recent message to reply to (from last 5 messages)
        recent_msgs = [msg for msg in text_messages[:5] if msg.id not in last_processed_messages]
        
        if not recent_msgs:
            # If all processed, reset and use latest
            last_processed_messages = []
            recent_msgs = text_messages[:5]
        
        target_message = random.choice(recent_msgs)
        
        # Generate Hinglish response
        response = await get_hinglish_response(context)
        
        # Reply to the message
        await client.send_message(
            TARGET_GROUP_ID,
            response,
            reply_to=target_message.id
        )
        
        message_count += 1
        last_processed_messages.append(target_message.id)
        
        # Keep only last 20 processed IDs
        if len(last_processed_messages) > 20:
            last_processed_messages = last_processed_messages[-20:]
        
        print(f"✓ Reply #{message_count} sent to msg {target_message.id}")
        print(f"  └─ {response[:60]}...")
        
    except Exception as e:
        print(f"Error sending reply: {e}")

async def message_loop():
    """Send 4 replies per minute (every 15 seconds)"""
    print("🔄 Starting reply loop - 4 messages per minute\n")
    
    while True:
        try:
            await send_reply_to_group()
            await asyncio.sleep(15)  # 15 seconds = 4 per minute
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(15)

@client.on(events.NewMessage(chats='me'))
async def admin_commands(event):
    """Admin commands in Saved Messages"""
    global message_count
    
    if event.text == '/total':
        await event.respond(
            f"📊 **Message Stats**\n\n"
            f"💬 Total replies sent: **{message_count}**\n"
            f"⚡ Rate: 4 msg/min\n"
            f"🎯 Group: `{TARGET_GROUP_ID}`"
        )
    
    elif event.text == '/status':
        status = f"""
✅ **Bot Status: Active**

💬 Replies sent: {message_count}
🎯 Target group: {TARGET_GROUP_ID}
⚡ Rate: 4 msg/min
🤖 Mode: Hinglish Buyer/Seller
📝 Reply style: Natural + Reply tags
"""
        await event.respond(status)
    
    elif event.text == '/help':
        help_text = """
🤖 **Userbot Commands**

/total - Total messages sent
/status - Bot status  
/help - This message

**Features:**
✓ Replies with tag to messages
✓ Natural Hinglish responses
✓ Acts as buyer/seller
✓ Negotiates & asks prices
✓ 4 guaranteed msg/min
"""
        await event.respond(help_text)

@client.on(events.NewMessage(chats=TARGET_GROUP_ID))
async def track_messages(event):
    """Track group messages for context"""
    pass  # Just listening for context

async def main():
    """Start the userbot"""
    global message_count
    
    print("="*50)
    print("🤖 Telegram Hinglish Trading Userbot")
    print("="*50)
    
    await client.start(phone=PHONE)
    print("✓ Logged in successfully!")
    
    # Save session
    if not load_session():
        session_string = client.session.save()
        save_session(session_string)
        print("✓ Session saved to file!")
    
    me = await client.get_me()
    print(f"✓ Account: {me.first_name} ({me.phone})")
    
    # Get group info
    try:
        group = await client.get_entity(TARGET_GROUP_ID)
        print(f"✓ Target group: {group.title}")
    except Exception as e:
        print(f"⚠ Warning: {e}")
        print("Make sure GROUP_ID is correct!")
    
    print(f"\n{'='*50}")
    print("🚀 BOT ACTIVE!")
    print(f"{'='*50}")
    print("📊 Rate: 4 replies per minute")
    print("💬 Style: Hinglish with reply tags")
    print("🎯 Mode: Natural buyer/seller")
    print(f"📝 Admin: Send /total in Saved Messages")
    print(f"{'='*50}\n")
    
    # Start reply loop
    asyncio.create_task(message_loop())
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{'='*50}")
        print("⏹ Bot stopped!")
        print(f"📊 Total replies sent: {message_count}")
        print(f"{'='*50}")
