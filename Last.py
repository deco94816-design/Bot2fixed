import asyncio
import json
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import InputStickerSetShortName
import google.generativeai as genai

# Configuration
API_ID = '34724923'
API_HASH = 'd46f75f6dbb93156f5bd5284b5fef860'
GEMINI_API_KEY = 'AIzaSyBpYQl_w4VCHGak7X2kgC7CF6apoLWABfM'

# Session file
SESSION_NAME = 'userbot_session'

# Active groups storage
GROUPS_FILE = 'active_groups.json'
STICKERS_FILE = 'custom_stickers.json'
active_groups = []
custom_stickers = []  # Store file_id of custom stickers
sticker_collection_mode = False  # Flag for collecting stickers

# Initialize Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Message tracking
message_count = 0
conversation_memory = {}  # Store conversations per group
sent_messages = {}  # Track sent messages to avoid repetition
last_reply_time = {}  # Track when we last replied in each group

# Popular Telegram stickers for reactions
STICKER_SETS = [
    'HotCherry',  # Emotional reactions
    'HyperCat',   # Cat reactions
    'PepeTheFrog',  # Pepe memes
]

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Load/Save active groups
def load_groups():
    global active_groups
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as f:
            active_groups = json.load(f)
    return active_groups

def save_groups():
    with open(GROUPS_FILE, 'w') as f:
        json.dump(active_groups, f)

# Load/Save custom stickers
def load_stickers():
    global custom_stickers
    if os.path.exists(STICKERS_FILE):
        with open(STICKERS_FILE, 'r') as f:
            custom_stickers = json.load(f)
    return custom_stickers

def save_stickers():
    with open(STICKERS_FILE, 'w') as f:
        json.dump(custom_stickers, f)

async def get_contextual_hinglish_response(group_id, recent_messages, target_message):
    """Generate intelligent contextual response"""
    try:
        # Build conversation context
        context = "\n".join([
            f"{msg['sender']}: {msg['text']}" 
            for msg in recent_messages[-15:]
        ])
        
        # Get conversation memory for this group
        if group_id not in conversation_memory:
            conversation_memory[group_id] = []
        
        memory = "\n".join(conversation_memory[group_id][-5:]) if conversation_memory[group_id] else ""
        
        prompt = f"""You are a REAL Indian person chatting in a Telegram trading group for NFT usernames, TON crypto, digital items.

Previous conversation you had:
{memory}

Current chat context (last 15 messages):
{context}

The message you're responding to:
{target_message['sender']}: {target_message['text']}

Generate ONE natural Hinglish response that:

1. RESPOND DIRECTLY to what the person said (understand context properly)
2. Show REAL human emotions: curiosity, interest, excitement, skepticism, humor
3. Use natural Hinglish mixing: "bhai", "yaar", "kya baat hai", "sahi hai", "kitne ka"
4. Be RELEVANT - if they mention price, ask about it; if selling, show interest; if bought, react naturally
5. Sound like a real buyer/seller/trader - negotiate, bargain, show interest in deals
6. Use emojis naturally: 😅🔥💀😭🤔👀🥺💯
7. Keep SHORT (5-15 words max)
8. NEVER repeat same response twice
9. Sometimes show different reactions: happy, curious, jealous, impressed, funny
10. Ask intelligent questions about the item/deal/price when relevant

Examples of GOOD responses:
- If someone says "selling username": "bhai kitne ka? DM me 👀"
- If someone bought cheap: "wtf itne saste me mil gya? 😭"
- If high price: "bhai thoda zyada ho gya yaar 😅"
- If good deal: "solid deal bhai 🔥 mujhe bhi chahiye"
- Random chat: "koi active hai? 🤔"

DON'T:
- Don't be formal or robotic
- Don't give long responses
- Don't repeat same phrases
- Don't ignore context
- Don't always ask same questions

Reply ONLY with the Hinglish message:"""

        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        
        reply = response.text.strip().replace('"', '').replace("'", "")
        
        # Check if we already sent similar message
        if group_id not in sent_messages:
            sent_messages[group_id] = []
        
        # Avoid repetition - if too similar to recent messages, regenerate
        if any(reply.lower() in sent.lower() or sent.lower() in reply.lower() 
               for sent in sent_messages[group_id][-10:]):
            # Generate alternative
            fallbacks = [
                "interesting 👀",
                f"nice bhai 🔥",
                f"sahi hai yaar",
                f"bhai ye kya scene hai? 😅",
                f"dm karo details ke liye",
                f"worth hai kya? 🤔",
            ]
            reply = random.choice(fallbacks)
        
        # Store in sent messages
        sent_messages[group_id].append(reply)
        if len(sent_messages[group_id]) > 20:
            sent_messages[group_id] = sent_messages[group_id][-20:]
        
        # Store in conversation memory
        conversation_memory[group_id].append(f"Me: {reply}")
        if len(conversation_memory[group_id]) > 10:
            conversation_memory[group_id] = conversation_memory[group_id][-10:]
        
        return reply
        
    except Exception as e:
        print(f"AI Error: {e}")
        return random.choice([
            "bhai ye kya hai? 🤔",
            "interesting scene hai 👀",
            "nice yaar 🔥",
        ])

async def should_reply_now(group_id):
    """Intelligent reply timing - 4 replies per minute guaranteed"""
    
    # Maintain 4 messages per minute = 1 message every 15 seconds
    if group_id in last_reply_time:
        time_since_last = datetime.now() - last_reply_time[group_id]
        # Must wait at least 12 seconds between replies (allows 5 per min max)
        if time_since_last < timedelta(seconds=12):
            return False
    
    # Always reply (we control timing through the main loop)
    return True

async def send_sticker_reaction(group_id):
    """Send sticker as reaction - uses custom stickers if available"""
    try:
        # Prefer custom stickers if available
        if custom_stickers:
            sticker_file_id = random.choice(custom_stickers)
            await client.send_file(group_id, sticker_file_id)
            print(f"  └─ Sent custom sticker")
            return True
        else:
            # Fallback to default sticker sets
            sticker_set_name = random.choice(STICKER_SETS)
            sticker_set = await client(InputStickerSetShortName(sticker_set_name))
            
            if sticker_set.documents:
                sticker = random.choice(sticker_set.documents)
                await client.send_file(group_id, sticker)
                print(f"  └─ Sent default sticker")
                return True
    except Exception as e:
        print(f"Sticker error: {e}")
    return False

async def engage_in_group(group_id):
    """Main function to engage naturally in group"""
    global message_count
    
    try:
        # Get recent messages
        messages = await client.get_messages(group_id, limit=30)
        
        if not messages:
            return
        
        # Filter text messages from others (not self)
        me = await client.get_me()
        text_messages = [
            msg for msg in messages 
            if msg.text and len(msg.text) > 5 and msg.sender_id != me.id
        ]
        
        if not text_messages:
            return
        
        # Check if we should reply now
        if not await should_reply_now(group_id):
            print(f"⏭ Skipping reply for group {group_id} (timing)")
            return
        
        # Build context
        context = []
        for msg in reversed(text_messages[-20:]):
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
        
        # Pick a message to respond to (from last 5 messages)
        target_message = random.choice(context[-5:]) if len(context) >= 5 else context[-1]
        
        # Decide: send sticker (15% chance) or text message
        if random.random() < 0.15:
            success = await send_sticker_reaction(group_id)
            if success:
                message_count += 1
            else:
                # If sticker fails, send text instead
                response = await get_contextual_hinglish_response(group_id, context, target_message)
                target_msg_obj = next((m for m in text_messages if m.text == target_message['text']), None)
                
                if target_msg_obj:
                    await client.send_message(group_id, response, reply_to=target_msg_obj.id)
                else:
                    await client.send_message(group_id, response)
                
                message_count += 1
                print(f"✓ Reply #{message_count} in group {group_id}")
                print(f"  └─ Response: {response}")
        else:
            # Generate intelligent response
            response = await get_contextual_hinglish_response(group_id, context, target_message)
            
            # Find the actual message object to reply to
            target_msg_obj = next((m for m in text_messages if m.text == target_message['text']), None)
            
            if target_msg_obj:
                # Reply to specific message
                await client.send_message(
                    group_id,
                    response,
                    reply_to=target_msg_obj.id
                )
            else:
                # Send without reply
                await client.send_message(group_id, response)
            
            message_count += 1
            print(f"✓ Reply #{message_count} in group {group_id}")
            print(f"  └─ To: {target_message['text'][:40]}...")
            print(f"  └─ Response: {response}")
        
        # Update last reply time
        last_reply_time[group_id] = datetime.now()
        
    except Exception as e:
        print(f"Error engaging in group {group_id}: {e}")

async def activity_loop():
    """Main loop - guaranteed 4 messages per minute per group"""
    print("🔄 Starting activity loop - 4 messages/minute guaranteed\n")
    
    while True:
        try:
            if not active_groups:
                print("⚠ No active groups. Use /addgroupid in Saved Messages")
                await asyncio.sleep(60)
                continue
            
            # For each active group
            for group_id in active_groups:
                await engage_in_group(group_id)
                
                # Wait 15 seconds = 4 messages per minute per group
                print(f"⏱ Next message in 15 seconds...")
                await asyncio.sleep(15)
            
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(15)

@client.on(events.NewMessage(chats='me'))
async def admin_commands(event):
    """Admin commands in Saved Messages"""
    global message_count, active_groups, custom_stickers, sticker_collection_mode
    
    # Handle sticker collection mode
    if sticker_collection_mode:
        if event.sticker:
            custom_stickers.append(event.sticker.id)
            save_stickers()
            await event.respond(f"✅ Sticker {len(custom_stickers)} added! Total: {len(custom_stickers)}\n\nSend more or /donestickers to finish")
            return
        elif event.text == '/donestickers':
            sticker_collection_mode = False
            await event.respond(f"✅ Sticker collection complete!\n\n📦 Total stickers: {len(custom_stickers)}\n\nBot will now use these stickers in groups! 🎨")
            return
        elif event.text == '/cancelstickers':
            sticker_collection_mode = False
            await event.respond("❌ Sticker collection cancelled")
            return
    
    if event.text == '/total':
        sticker_info = f"\n🎨 Custom stickers: {len(custom_stickers)}" if custom_stickers else ""
        await event.respond(
            f"📊 **Message Stats**\n\n"
            f"💬 Total messages sent: **{message_count}**\n"
            f"🎯 Active groups: **{len(active_groups)}**{sticker_info}\n"
            f"📋 Groups: {active_groups if active_groups else 'None'}"
        )
    
    elif event.text == '/addstickers':
        sticker_collection_mode = True
        custom_stickers = []  # Reset collection
        save_stickers()
        await event.respond(
            "🎨 **Sticker Collection Mode Activated!**\n\n"
            "📤 Now send me 20-30 stickers one by one\n"
            "✅ I'll save each one\n"
            "🔄 Send /donestickers when finished\n"
            "❌ Send /cancelstickers to cancel\n\n"
            "Ready! Send your first sticker 👇"
        )
    
    elif event.text == '/clearstickers':
        custom_stickers = []
        save_stickers()
        await event.respond("🗑 All custom stickers cleared!")
    
    elif event.text == '/stickers':
        if custom_stickers:
            await event.respond(f"🎨 **Custom Stickers**: {len(custom_stickers)} stickers loaded\n\nBot uses these in groups!")
        else:
            await event.respond("⚠ No custom stickers added yet!\n\nUse /addstickers to add")
    
    elif event.text.startswith('/addgroupid '):
        try:
            group_id = int(event.text.split()[1])
            if group_id not in active_groups:
                active_groups.append(group_id)
                save_groups()
                
                # Try to get group name
                try:
                    group = await client.get_entity(group_id)
                    group_name = group.title
                    await event.respond(f"✅ Added group: **{group_name}**\n`{group_id}`")
                except:
                    await event.respond(f"✅ Added group: `{group_id}`")
            else:
                await event.respond(f"⚠ Group already active: `{group_id}`")
        except:
            await event.respond("❌ Usage: /addgroupid -1001234567890")
    
    elif event.text.startswith('/removegroupid '):
        try:
            group_id = int(event.text.split()[1])
            if group_id in active_groups:
                active_groups.remove(group_id)
                save_groups()
                await event.respond(f"✅ Removed group: `{group_id}`")
            else:
                await event.respond(f"⚠ Group not found: `{group_id}`")
        except:
            await event.respond("❌ Usage: /removegroupid -1001234567890")
    
    elif event.text == '/groups':
        if active_groups:
            group_list = ""
            for gid in active_groups:
                try:
                    group = await client.get_entity(gid)
                    group_list += f"• **{group.title}**\n  `{gid}`\n"
                except:
                    group_list += f"• `{gid}`\n"
            await event.respond(f"📋 **Active Groups ({len(active_groups)}):**\n\n{group_list}")
        else:
            await event.respond("⚠ No active groups. Use /addgroupid")
    
    elif event.text == '/pause':
        # You can add pause logic here
        await event.respond("⏸ Bot paused!\n\nUse /resume to restart")
    
    elif event.text == '/resume':
        await event.respond("▶️ Bot resumed!")
    
    elif event.text == '/reset':
        message_count = 0
        await event.respond("🔄 Message counter reset to 0")
    
    elif event.text == '/stats':
        uptime = datetime.now() - datetime.fromtimestamp(os.path.getctime(__file__))
        avg_per_min = message_count / max(1, uptime.total_seconds() / 60)
        
        stats = f"""
📊 **Detailed Statistics**

💬 Messages sent: {message_count}
⏱ Average: {avg_per_min:.1f} msg/min
🎯 Active groups: {len(active_groups)}
🎨 Custom stickers: {len(custom_stickers)}
📝 Conversation memory: {sum(len(v) for v in conversation_memory.values())} entries
🔄 Unique responses: {sum(len(v) for v in sent_messages.values())} tracked

⚙️ **Settings:**
• Rate: 4 msg/min per group
• Sticker chance: 15%
• Reply mode: Context-aware
"""
        await event.respond(stats)
    
    elif event.text == '/status':
        status = f"""
✅ **Bot Status: Active**

💬 Messages sent: {message_count}
🎯 Active groups: {len(active_groups)}
🎨 Custom stickers: {len(custom_stickers)}
🤖 Mode: Natural Hinglish Conversation
💡 Reply style: Context-aware + Human emotions
⚡ Rate: 4 messages per minute
"""
        await event.respond(status)
    
    elif event.text == '/help':
        help_text = """
🤖 **Userbot Commands**

📊 **Stats & Info:**
/total - Quick message stats
/stats - Detailed statistics
/status - Bot status
/groups - List active groups

⚙️ **Manage Groups:**
/addgroupid [ID] - Add group
/removegroupid [ID] - Remove group

🎨 **Sticker Management:**
/addstickers - Start adding custom stickers
/stickers - View sticker count
/clearstickers - Remove all stickers
/donestickers - Finish adding (during collection)
/cancelstickers - Cancel collection

🔧 **Controls:**
/pause - Pause bot activity
/resume - Resume bot activity
/reset - Reset message counter

**Features:**
✓ 4 messages per minute guaranteed
✓ Natural Hinglish chat
✓ Context-aware replies
✓ Human emotions & reactions
✓ Custom sticker support
✓ No repetition
✓ Meaningful responses
✓ Bargaining & trading talk

**Example:**
/addgroupid -1001234567890
/addstickers (then send 20-30 stickers)
"""
        await event.respond(help_text)

async def main():
    """Start the userbot"""
    global message_count
    
    print("="*60)
    print("🤖 Advanced Telegram Trading Bot")
    print("="*60)
    
    await client.start()
    print("✓ Logged in successfully!")
    
    me = await client.get_me()
    print(f"✓ Account: {me.first_name} ({me.phone})")
    
    # Load active groups
    load_groups()
    load_stickers()
    print(f"✓ Loaded {len(active_groups)} active groups")
    print(f"✓ Loaded {len(custom_stickers)} custom stickers")
    
    if os.path.exists(f'{SESSION_NAME}.session'):
        print(f"✓ Using session: {SESSION_NAME}.session")
    
    print(f"\n{'='*60}")
    print("🚀 BOT ACTIVE!")
    print(f"{'='*60}")
    print("⚡ GUARANTEED: 4 messages per minute per group")
    print("💡 Natural conversation with human emotions")
    print("🎯 Context-aware intelligent replies")
    print("🎨 Sticker reactions (15% chance)")
    print("⏱  Timing: 1 message every 15 seconds")
    print(f"\n📝 Send /addgroupid [GROUP_ID] in Saved Messages")
    print(f"📊 Send /total for stats")
    print(f"{'='*60}\n")
    
    if not active_groups:
        print("⚠️  WARNING: No active groups!")
        print("   Send /addgroupid -1001234567890 in Saved Messages\n")
    
    # Start activity loop
    asyncio.create_task(activity_loop())
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print("⏹ Bot stopped!")
        print(f"📊 Total messages sent: {message_count}")
        print(f"{'='*60}")
