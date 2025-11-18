import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import google.generativeai as genai
import random

# Configuration
API_ID = '34724923'  # Get from my.telegram.org
API_HASH = 'd46f75f6dbb93156f5bd5284b5fef860'  # Get from my.telegram.org
PHONE = '+447552437615'  # Your phone number with country code
GEMINI_API_KEY = 'AIzaSyBpYQl_w4VCHGak7X2kgC7CF6apoLWABfM'  # Get from Google AI Studio
TARGET_GROUP_ID = -1003220013950  # Replace with your group ID (negative for supergroups)
SESSION_FILE = 'userbot_session.txt'

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Message counter
message_count = 0
conversation_history = []
MAX_HISTORY = 10

# Load or create session
def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'r') as f:
            return f.read().strip()
    return None

def save_session(session_string):
    with open(SESSION_FILE, 'w') as f:
        f.write(session_string)

# Initialize client
session_string = load_session()
if session_string:
    client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
else:
    client = TelegramClient(StringSession(), API_ID, API_HASH)

# Emojis and stickers for natural reactions
REACTION_EMOJIS = ['😂', '❤️', '🔥', '👍', '😮', '😊', '🤔', '💯', '😎', '🙌', '👏', '💪']

async def get_ai_response(message_text, context=""):
    """Get response from Gemini API"""
    try:
        prompt = f"""You are chatting naturally in a Telegram group. Keep responses casual, friendly, and conversational.
Previous context: {context}
Message: {message_text}

Respond naturally like a real person would. Keep it brief (1-3 sentences). Use casual language, emojis occasionally, and be engaging."""
        
        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Gemini API error: {e}")
        # Fallback responses
        fallbacks = [
            "Interesting point! 🤔",
            "I totally agree with that",
            "Haha that's funny 😄",
            "Makes sense!",
            "True that 💯"
        ]
        return random.choice(fallbacks)

def should_send_emoji_reaction():
    """Randomly decide if we should react with emoji (30% chance)"""
    return random.random() < 0.3

async def send_message_to_group():
    """Send a contextual message to the group every 15 seconds (4 per minute)"""
    global message_count
    
    try:
        # Get recent messages for context
        messages = await client.get_messages(TARGET_GROUP_ID, limit=5)
        
        if messages:
            # Build context from recent messages
            context = "\n".join([
                f"{msg.sender_id}: {msg.text}" 
                for msg in reversed(messages) 
                if msg.text
            ][-3:])  # Last 3 messages
            
            latest_message = messages[0]
            
            # Sometimes react with emoji
            if should_send_emoji_reaction() and latest_message:
                try:
                    await client.send_reaction(
                        TARGET_GROUP_ID,
                        latest_message.id,
                        random.choice(REACTION_EMOJIS)
                    )
                    print(f"Reacted with emoji to message {latest_message.id}")
                except:
                    pass
            
            # Generate AI response
            if latest_message and latest_message.text:
                response = await get_ai_response(latest_message.text, context)
            else:
                # Send a general engagement message
                prompts = [
                    "What's everyone up to today?",
                    "Any interesting updates?",
                    "How's it going? 😊",
                    "Anyone else online right now?",
                ]
                response = random.choice(prompts)
            
            # Send the message
            await client.send_message(TARGET_GROUP_ID, response)
            message_count += 1
            print(f"✓ Message sent ({message_count}): {response[:50]}...")
            
    except Exception as e:
        print(f"Error sending message: {e}")

async def message_loop():
    """Main loop to send 4 messages per minute (every 15 seconds)"""
    print("Starting message loop - 4 messages per minute")
    while True:
        try:
            await send_message_to_group()
            await asyncio.sleep(15)  # 15 seconds = 4 messages per minute
        except Exception as e:
            print(f"Error in message loop: {e}")
            await asyncio.sleep(15)

@client.on(events.NewMessage(chats='me'))
async def admin_commands(event):
    """Handle admin commands in Saved Messages"""
    global message_count
    
    if event.text == '/total':
        await event.respond(f"📊 **Total Messages Sent:** {message_count}")
    
    elif event.text == '/start':
        await event.respond("✅ Userbot is already running!")
    
    elif event.text == '/help':
        help_text = """
🤖 **Userbot Commands:**

/total - Show total messages sent
/help - Show this help message
/status - Show bot status

**Current Settings:**
• Target Group: {group_id}
• Rate: 4 messages per minute
• AI: Gemini Pro
""".format(group_id=TARGET_GROUP_ID)
        await event.respond(help_text)
    
    elif event.text == '/status':
        status = f"""
✅ **Bot Status: Active**

📨 Messages sent: {message_count}
🎯 Target group: {TARGET_GROUP_ID}
⚡ Rate: 4 msg/min
🤖 AI Model: Gemini Pro
"""
        await event.respond(status)

@client.on(events.NewMessage(chats=TARGET_GROUP_ID))
async def handle_group_messages(event):
    """Listen to group messages for context"""
    global conversation_history
    
    if event.text:
        # Store in conversation history
        conversation_history.append({
            'sender': event.sender_id,
            'text': event.text,
            'time': datetime.now()
        })
        
        # Keep only recent messages
        if len(conversation_history) > MAX_HISTORY:
            conversation_history.pop(0)

async def main():
    """Main function to start the userbot"""
    global message_count
    
    print("Starting Telegram Gemini Userbot...")
    
    await client.start(phone=PHONE)
    print("✓ Client started successfully!")
    
    # Save session for future use
    if not load_session():
        session_string = client.session.save()
        save_session(session_string)
        print("✓ Session saved!")
    
    # Get info about the bot
    me = await client.get_me()
    print(f"✓ Logged in as: {me.first_name} ({me.phone})")
    
    # Try to get group info
    try:
        group = await client.get_entity(TARGET_GROUP_ID)
        print(f"✓ Target group: {group.title}")
    except Exception as e:
        print(f"⚠ Warning: Could not fetch group info: {e}")
        print("Make sure the GROUP_ID is correct and you're a member")
    
    print(f"\n🚀 Bot is running!")
    print(f"📊 Sending 4 messages per minute to group {TARGET_GROUP_ID}")
    print(f"💬 Use /total in Saved Messages to check message count")
    print("\nPress Ctrl+C to stop\n")
    
    # Start the message loop
    asyncio.create_task(message_loop())
    
    # Keep the client running
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✓ Bot stopped by user")
        print(f"📊 Total messages sent: {message_count}")
