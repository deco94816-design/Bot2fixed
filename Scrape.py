import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPeerUser, InputPhoneContact

# Configuration
API_ID = 'YOUR_API_ID'
API_HASH = 'YOUR_API_HASH'
SESSION_FOLDER = 'sessions'
DATA_FOLDER = 'data'
CONFIG_FILE = 'bot_config.json'

# Create necessary folders
os.makedirs(SESSION_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

class ContactBasedUserbotManager:
    def __init__(self):
        self.clients = []
        self.config = self.load_config()
        self.added_users_file = os.path.join(DATA_FOLDER, 'added_users.json')
        self.members_file = os.path.join(DATA_FOLDER, 'scraped_members.json')
        self.saved_contacts_file = os.path.join(DATA_FOLDER, 'saved_contacts.json')
        self.added_users = self.load_added_users()
        self.saved_contacts = self.load_saved_contacts()
        
    def load_config(self):
        """Load bot configuration"""
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {
            'bots': [],
            'target_group': '',
            'backup_group': '',
            'users_per_bot': 50,
            'delay_between_adds': 60,
            'save_contacts_delay': 3
        }
    
    def save_config(self):
        """Save bot configuration"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def load_added_users(self):
        """Load the list of already added users"""
        if os.path.exists(self.added_users_file):
            with open(self.added_users_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def save_added_user(self, user_id):
        """Save a successfully added user ID"""
        self.added_users.add(user_id)
        with open(self.added_users_file, 'w') as f:
            json.dump(list(self.added_users), f, indent=2)
    
    def load_saved_contacts(self):
        """Load the list of users saved as contacts"""
        if os.path.exists(self.saved_contacts_file):
            with open(self.saved_contacts_file, 'r') as f:
                return set(json.load(f))
        return set()
    
    def save_contact_record(self, user_id):
        """Record a user who has been saved as contact"""
        self.saved_contacts.add(user_id)
        with open(self.saved_contacts_file, 'w') as f:
            json.dump(list(self.saved_contacts), f, indent=2)
    
    async def setup_bots(self):
        """Setup and configure bot accounts"""
        print(f"\n{'='*60}")
        print("🔧 USERBOT SETUP")
        print(f"{'='*60}\n")
        
        num_bots = int(input("How many userbots? (5-6 recommended): "))
        
        bot_contacts = []
        for i in range(num_bots):
            print(f"\n--- Bot {i+1} ---")
            phone = input(f"Enter phone number (with country code, e.g., +1234567890): ")
            first_name = input(f"Enter name for this bot (e.g., Bot{i+1}): ") or f"Bot{i+1}"
            
            bot_contacts.append({
                'phone': phone,
                'first_name': first_name,
                'bot_number': i + 1
            })
        
        self.config['bots'] = bot_contacts
        self.save_config()
        
        print(f"\n✓ Saved {num_bots} bot configurations")
    
    async def login_all_bots(self):
        """Login all configured bots"""
        print(f"\n{'='*60}")
        print("🔐 LOGGING IN ALL USERBOTS")
        print(f"{'='*60}\n")
        
        if not self.config['bots']:
            print("❌ No bots configured. Please run setup first.")
            return False
        
        for bot_info in self.config['bots']:
            phone = bot_info['phone']
            bot_num = bot_info['bot_number']
            
            session_name = os.path.join(SESSION_FOLDER, f'userbot_{bot_num}')
            client = TelegramClient(session_name, API_ID, API_HASH)
            
            await client.connect()
            
            if not await client.is_user_authorized():
                print(f"\n--- Bot {bot_num}: {phone} ---")
                await client.send_code_request(phone)
                code = input(f"Enter code for {phone}: ")
                try:
                    await client.sign_in(phone, code)
                except errors.SessionPasswordNeededError:
                    password = input("2FA enabled. Enter password: ")
                    await client.sign_in(password=password)
            
            me = await client.get_me()
            print(f"✓ Bot {bot_num}: {me.first_name} (@{me.username or 'no username'})")
            
            self.clients.append(client)
        
        print(f"\n✓ All {len(self.clients)} bots logged in!\n")
        return True
    
    async def load_existing_sessions(self):
        """Load all existing session files"""
        session_files = sorted([f for f in os.listdir(SESSION_FOLDER) if f.startswith('userbot_')])
        
        if not session_files:
            print("❌ No sessions found. Please login bots first.")
            return False
        
        print(f"Loading {len(session_files)} sessions...\n")
        
        for session_file in session_files:
            session_path = os.path.join(SESSION_FOLDER, session_file.replace('.session', ''))
            client = TelegramClient(session_path, API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"✓ {me.first_name} (@{me.username or 'no username'})")
                self.clients.append(client)
        
        print(f"\n✓ {len(self.clients)} sessions loaded\n")
        return True
    
    async def save_all_as_contacts(self, client, bot_num, members_chunk, delay=3):
        """Save users as contacts in the userbot's phone"""
        print(f"\n[Bot {bot_num}] 💾 Saving {len(members_chunk)} users as contacts...")
        
        saved_count = 0
        failed_count = 0
        
        # Process in batches of 50 (Telegram limit)
        batch_size = 50
        
        for i in range(0, len(members_chunk), batch_size):
            batch = members_chunk[i:i+batch_size]
            contacts_to_import = []
            
            for member in batch:
                if member['phone'] and member['id'] not in self.saved_contacts:
                    contact = InputPhoneContact(
                        client_id=member['id'],
                        phone=member['phone'],
                        first_name=member['first_name'] or 'User',
                        last_name=member['last_name'] or ''
                    )
                    contacts_to_import.append(contact)
            
            if contacts_to_import:
                try:
                    result = await client(ImportContactsRequest(contacts_to_import))
                    
                    for imported_user in result.users:
                        self.save_contact_record(imported_user.id)
                        saved_count += 1
                    
                    print(f"[Bot {bot_num}] ✓ Batch saved: {len(contacts_to_import)} contacts ({saved_count} total)")
                    await asyncio.sleep(delay)
                    
                except errors.FloodWaitError as e:
                    print(f"[Bot {bot_num}] ⏳ FloodWait {e.seconds}s - Waiting...")
                    await asyncio.sleep(e.seconds + 5)
                    
                except Exception as e:
                    print(f"[Bot {bot_num}] ⚠️ Error saving batch: {str(e)}")
                    failed_count += len(contacts_to_import)
        
        print(f"[Bot {bot_num}] 📊 Contacts saved: {saved_count} | Failed: {failed_count}")
        return saved_count
    
    async def scrape_from_target_group(self):
        """Scrape all members from target group"""
        print(f"\n{'='*60}")
        print("📥 STEP 1: SCRAPING FROM TARGET GROUP")
        print(f"{'='*60}\n")
        
        if not self.clients:
            if not await self.load_existing_sessions():
                return []
        
        target_group = self.config.get('target_group')
        if not target_group:
            target_group = input("Enter TARGET group username/link: ")
            self.config['target_group'] = target_group
            self.save_config()
        
        client = self.clients[0]
        
        try:
            group = await client.get_entity(target_group)
            print(f"📱 Connected to: {group.title}")
            print("⏳ Fetching members...\n")
            
            all_members = []
            count = 0
            
            async for user in client.iter_participants(group, aggressive=True):
                if not user.bot:
                    member_data = {
                        'id': user.id,
                        'access_hash': user.access_hash,
                        'username': user.username,
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'phone': user.phone or ''
                    }
                    all_members.append(member_data)
                    count += 1
                    
                    if count % 100 == 0:
                        print(f"Scraped {count} members...")
            
            # Save members
            with open(self.members_file, 'w') as f:
                json.dump(all_members, f, indent=2)
            
            # Filter members with phone numbers
            members_with_phone = [m for m in all_members if m['phone']]
            
            print(f"\n{'='*60}")
            print(f"✓ SCRAPING COMPLETE!")
            print(f"   • Total members: {len(all_members)}")
            print(f"   • Members with phone: {len(members_with_phone)}")
            print(f"   • Saved to: {self.members_file}")
            print(f"{'='*60}\n")
            
            return all_members
            
        except Exception as e:
            print(f"❌ Error scraping: {str(e)}")
            return []
    
    async def save_contacts_parallel(self):
        """Save contacts using all bots in parallel"""
        print(f"\n{'='*60}")
        print("💾 STEP 2: SAVING ALL USERS AS CONTACTS")
        print(f"{'='*60}\n")
        
        if not os.path.exists(self.members_file):
            print("❌ No scraped members. Please scrape first.")
            return
        
        with open(self.members_file, 'r') as f:
            all_members = json.load(f)
        
        # Filter members with phone numbers that haven't been saved
        members_with_phone = [
            m for m in all_members 
            if m['phone'] and m['id'] not in self.saved_contacts
        ]
        
        if not members_with_phone:
            print("✓ All contacts already saved!")
            return
        
        print(f"📊 Total contacts to save: {len(members_with_phone)}")
        print(f"🤖 Using {len(self.clients)} bots\n")
        
        # Distribute members among bots
        chunk_size = len(members_with_phone) // len(self.clients) + 1
        chunks = [members_with_phone[i:i+chunk_size] for i in range(0, len(members_with_phone), chunk_size)]
        
        # Display distribution
        for i, chunk in enumerate(chunks[:len(self.clients)]):
            print(f"Bot {i+1}: {len(chunk)} contacts")
        
        print(f"\n🚀 Starting contact save process...\n")
        
        # Save contacts in parallel
        tasks = []
        delay = self.config.get('save_contacts_delay', 3)
        
        for i, (client, chunk) in enumerate(zip(self.clients, chunks)):
            if chunk:
                task = self.save_all_as_contacts(client, i+1, chunk, delay)
                tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        total_saved = sum(results)
        
        print(f"\n{'='*60}")
        print(f"✅ CONTACT SAVING COMPLETE!")
        print(f"   • Total saved: {total_saved}")
        print(f"{'='*60}\n")
    
    def assign_chunks(self, members, users_per_bot):
        """Assign unique chunks of users to each bot"""
        chunks = []
        start_idx = 0
        
        for i in range(len(self.clients)):
            end_idx = min(start_idx + users_per_bot, len(members))
            chunk = members[start_idx:end_idx]
            chunks.append(chunk)
            start_idx = end_idx
            
            if start_idx >= len(members):
                break
        
        return chunks
    
    async def add_to_backup_group(self):
        """Add members to backup group"""
        print(f"\n{'='*60}")
        print("📤 STEP 3: ADDING MEMBERS TO BACKUP GROUP")
        print(f"{'='*60}\n")
        
        if not os.path.exists(self.members_file):
            print("❌ No scraped members found.")
            return
        
        with open(self.members_file, 'r') as f:
            all_members = json.load(f)
        
        # Filter out already added users
        members_to_add = [m for m in all_members if m['id'] not in self.added_users]
        
        if not members_to_add:
            print("✓ All members already added!")
            return
        
        # Get backup group
        backup_group = self.config.get('backup_group')
        if not backup_group:
            backup_group = input("Enter BACKUP group username/link: ")
            self.config['backup_group'] = backup_group
            self.save_config()
        
        users_per_bot = self.config.get('users_per_bot', 50)
        delay = self.config.get('delay_between_adds', 60)
        
        print(f"📊 Addition Configuration:")
        print(f"   • Members to add: {len(members_to_add)}")
        print(f"   • Active bots: {len(self.clients)}")
        print(f"   • Users per bot: {users_per_bot}")
        print(f"   • Delay: {delay}s")
        print(f"   • Backup group: {backup_group}\n")
        
        # Assign chunks
        chunks = self.assign_chunks(members_to_add, users_per_bot)
        
        print("📋 Work Distribution:")
        for i, chunk in enumerate(chunks):
            if chunk:
                print(f"   Bot {i+1}: {len(chunk)} users")
        
        print(f"\n🚀 Starting addition...\n")
        
        # Add members in parallel
        tasks = []
        for i, (client, chunk) in enumerate(zip(self.clients, chunks)):
            if chunk:
                task = self.add_chunk(client, i+1, backup_group, chunk, delay)
                tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        print(f"\n{'='*60}")
        print("✅ ADDITION COMPLETE!")
        print(f"✅ Total users added: {len(self.added_users)}")
        print(f"{'='*60}\n")
    
    async def add_chunk(self, client, bot_num, backup_group, chunk, delay):
        """Add a chunk of users to backup group"""
        try:
            target = await client.get_entity(backup_group)
        except Exception as e:
            print(f"❌ Bot {bot_num}: Cannot access backup group - {str(e)}")
            return
        
        added_count = 0
        failed_count = 0
        
        for idx, member in enumerate(chunk, 1):
            try:
                user_to_add = InputPeerUser(member['id'], member['access_hash'])
                
                await client(InviteToChannelRequest(target, [user_to_add]))
                
                username_str = f"@{member['username']}" if member['username'] else member['first_name']
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] ✓ Bot {bot_num}: {username_str} ({idx}/{len(chunk)})")
                
                self.save_added_user(member['id'])
                added_count += 1
                
                await asyncio.sleep(delay)
                
            except errors.FloodWaitError as e:
                wait_time = e.seconds
                wait_minutes = wait_time // 60
                print(f"⏳ Bot {bot_num}: FloodWait {wait_minutes}m {wait_time % 60}s")
                await asyncio.sleep(wait_time + 5)
                
            except (errors.UserPrivacyRestrictedError, 
                    errors.UserNotMutualContactError, 
                    errors.UserChannelsTooMuchError):
                failed_count += 1
                
            except errors.PeerFloodError:
                print(f"⚠️ Bot {bot_num}: Peer flood - Stopping")
                break
                
            except Exception as e:
                failed_count += 1
        
        print(f"\n📊 Bot {bot_num}: ✓ {added_count} added | ✗ {failed_count} failed\n")
    
    async def run_complete_automation(self):
        """Run the complete 3-step automation process"""
        print(f"\n{'='*60}")
        print("🤖 COMPLETE AUTOMATION PROCESS")
        print(f"{'='*60}\n")
        print("This will execute:")
        print("1️⃣  Scrape all members from TARGET group")
        print("2️⃣  Save all users as contacts (parallel)")
        print("3️⃣  Add members to BACKUP group (parallel)\n")
        
        input("Press Enter to start automation...")
        
        # Load sessions
        if not self.clients:
            await self.load_existing_sessions()
        
        # Step 1: Scrape from target group
        await self.scrape_from_target_group()
        
        # Step 2: Save all as contacts
        await self.save_contacts_parallel()
        
        # Step 3: Add to backup group
        await self.add_to_backup_group()
        
        print(f"\n{'='*60}")
        print("🎉 AUTOMATION COMPLETED SUCCESSFULLY!")
        print(f"{'='*60}\n")
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        for client in self.clients:
            await client.disconnect()
        self.clients = []

async def main():
    manager = ContactBasedUserbotManager()
    
    print("\n" + "="*60)
    print("🤖 TELEGRAM USERBOT - CONTACT SAVE & ADD SYSTEM")
    print("="*60)
    
    while True:
        print("\n📋 MAIN MENU:")
        print("1. 🔧 Setup Userbots")
        print("2. 🔐 Login All Bots")
        print("3. 🚀 RUN COMPLETE AUTOMATION (All 3 Steps)")
        print("4. 📥 Step 1: Scrape from Target Group")
        print("5. 💾 Step 2: Save All as Contacts")
        print("6. 📤 Step 3: Add to Backup Group")
        print("7. ⚙️  Configure Settings")
        print("8. 📊 View Statistics")
        print("9. 🚪 Exit")
        
        choice = input("\n👉 Enter choice (1-9): ").strip()
        
        if choice == '1':
            await manager.setup_bots()
            
        elif choice == '2':
            await manager.login_all_bots()
            
        elif choice == '3':
            await manager.run_complete_automation()
            
        elif choice == '4':
            await manager.scrape_from_target_group()
            
        elif choice == '5':
            await manager.save_contacts_parallel()
            
        elif choice == '6':
            await manager.add_to_backup_group()
            
        elif choice == '7':
            print("\n⚙️  CONFIGURATION:")
            print(f"Users per bot: {manager.config.get('users_per_bot', 50)}")
            new = input("New users per bot (Enter to skip): ")
            if new.strip():
                manager.config['users_per_bot'] = int(new)
            
            print(f"Delay between adds: {manager.config.get('delay_between_adds', 60)}s")
            new = input("New delay (Enter to skip): ")
            if new.strip():
                manager.config['delay_between_adds'] = int(new)
            
            print(f"Contact save delay: {manager.config.get('save_contacts_delay', 3)}s")
            new = input("New contact delay (Enter to skip): ")
            if new.strip():
                manager.config['save_contacts_delay'] = int(new)
            
            manager.save_config()
            print("✓ Saved!")
            
        elif choice == '8':
            print("\n📊 STATISTICS:")
            print(f"   • Configured bots: {len(manager.config.get('bots', []))}")
            print(f"   • Active sessions: {len([f for f in os.listdir(SESSION_FOLDER) if f.startswith('userbot_')])}")
            print(f"   • Saved contacts: {len(manager.saved_contacts)}")
            print(f"   • Added to backup: {len(manager.added_users)}")
            
            if os.path.exists(manager.members_file):
                with open(manager.members_file, 'r') as f:
                    members = json.load(f)
                print(f"   • Scraped members: {len(members)}")
            
        elif choice == '9':
            await manager.disconnect_all()
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice")

if __name__ == '__main__':
    asyncio.run(main())
