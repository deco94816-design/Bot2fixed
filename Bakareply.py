import asyncio
import logging
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError, 
    ChatWriteForbiddenError, 
    UserBannedInChannelError,
    MessageIdInvalidError
)
from telethon.tl.types import User, Channel, Chat
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('userbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
API_ID = 34724923  # Get from my.telegram.org
API_HASH = 'd46f75f6dbb93156f5bd5284b5fef860'  # Get from my.telegram.org
PHONE_NUMBER = '+447552437615'  # Your phone number with country code
SESSION_NAME = 'userbot_session'

TARGET_GROUP_ID = -1002870635857  # Target group chat ID (use negative for supergroups)
BOT_USERNAME = '@im_bakabot'  # The bot username that gives replies
REPLY_DELAY = 2  # Delay in seconds before checking for bot reply

# Store message mapping: {user_message_id: original_message_object}
message_map = {}

class UserbotForwarder:
    def __init__(self):
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.bot_entity = None
        self.target_group_entity = None
        
    async def start(self):
        """Start the userbot client"""
        try:
            await self.client.start(phone=PHONE_NUMBER)
            logger.info("Userbot started successfully!")
            
            # Get bot entity
            try:
                self.bot_entity = await self.client.get_entity(BOT_USERNAME)
                logger.info(f"Bot entity retrieved: {BOT_USERNAME}")
            except Exception as e:
                logger.error(f"Failed to get bot entity: {e}")
                return False
            
            # Get target group entity
            try:
                self.target_group_entity = await self.client.get_entity(TARGET_GROUP_ID)
                logger.info(f"Target group entity retrieved: {TARGET_GROUP_ID}")
            except Exception as e:
                logger.error(f"Failed to get target group entity: {e}")
                return False
            
            # Verify bot is accessible
            try:
                await self.client.send_message(self.bot_entity, "/start")
                logger.info("Bot is accessible and ready")
            except Exception as e:
                logger.error(f"Cannot send message to bot: {e}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start userbot: {e}")
            return False
    
    async def forward_to_bot(self, message):
        """Forward message to bot and wait for reply"""
        try:
            # Send message to bot
            sent_msg = await self.client.send_message(
                self.bot_entity,
                message.text or message.message or "[Media/Sticker]"
            )
            logger.info(f"Message forwarded to bot. Original ID: {message.id}")
            
            # Store mapping
            message_map[sent_msg.id] = message
            
            # Wait for bot reply
            await asyncio.sleep(REPLY_DELAY)
            
            # Get bot's reply
            async for msg in self.client.iter_messages(
                self.bot_entity,
                limit=10
            ):
                # Check if this is a reply to our message
                if msg.reply_to and msg.reply_to.reply_to_msg_id == sent_msg.id:
                    logger.info(f"Bot reply received: {msg.text[:50]}...")
                    return msg.text or msg.message
            
            # If no reply found in recent messages, wait a bit more
            await asyncio.sleep(3)
            async for msg in self.client.iter_messages(
                self.bot_entity,
                limit=5
            ):
                if msg.reply_to and msg.reply_to.reply_to_msg_id == sent_msg.id:
                    logger.info(f"Bot reply received (delayed): {msg.text[:50]}...")
                    return msg.text or msg.message
            
            logger.warning("No reply from bot found")
            return None
            
        except FloodWaitError as e:
            logger.error(f"FloodWait error: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return None
        except Exception as e:
            logger.error(f"Error forwarding to bot: {e}")
            return None
    
    async def send_reply_to_group(self, original_message, bot_reply):
        """Send bot reply to target group as reply to original message"""
        try:
            await self.client.send_message(
                self.target_group_entity,
                bot_reply,
                reply_to=original_message.id
            )
            logger.info(f"Reply sent to group successfully")
            return True
            
        except ChatWriteForbiddenError:
            logger.error("Cannot write to target group - no permission")
            return False
        except UserBannedInChannelError:
            logger.error("User is banned in target group")
            return False
        except MessageIdInvalidError:
            logger.error("Original message not found - may be deleted")
            return False
        except FloodWaitError as e:
            logger.error(f"FloodWait error: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error sending reply to group: {e}")
            return False
    
    async def handle_new_message(self, event):
        """Handle new messages in target group"""
        try:
            message = event.message
            
            # Ignore messages from self
            if message.out:
                logger.debug("Ignoring own message")
                return
            
            # Ignore messages from bots (except specific interactions)
            sender = await message.get_sender()
            if isinstance(sender, User) and sender.bot:
                logger.debug("Ignoring bot message")
                return
            
            logger.info(f"New message from {sender.first_name if isinstance(sender, User) else 'Unknown'}: {message.text[:50] if message.text else '[Media]'}...")
            
            # Forward to bot and get reply
            bot_reply = await self.forward_to_bot(message)
            
            if bot_reply:
                # Send reply back to group
                success = await self.send_reply_to_group(message, bot_reply)
                if success:
                    logger.info("Message cycle completed successfully")
            else:
                logger.warning("No reply from bot, skipping")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}", exc_info=True)
    
    async def run(self):
        """Main run loop"""
        try:
            # Register event handler
            @self.client.on(events.NewMessage(chats=TARGET_GROUP_ID))
            async def message_handler(event):
                await self.handle_new_message(event)
            
            logger.info("Userbot is now running and monitoring messages...")
            logger.info(f"Target Group: {TARGET_GROUP_ID}")
            logger.info(f"Bot: {BOT_USERNAME}")
            logger.info("Press Ctrl+C to stop")
            
            # Keep running
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("Userbot stopped by user")
        except Exception as e:
            logger.error(f"Error in run loop: {e}", exc_info=True)
        finally:
            await self.client.disconnect()
            logger.info("Userbot disconnected")

async def main():
    """Main entry point"""
    logger.info("="*50)
    logger.info("Telegram Userbot Message Forwarder")
    logger.info("="*50)
    
    # Create and start userbot
    userbot = UserbotForwarder()
    
    if await userbot.start():
        await userbot.run()
    else:
        logger.error("Failed to start userbot. Check configuration and try again.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
