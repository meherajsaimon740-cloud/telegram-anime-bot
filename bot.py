import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import math
import os
import asyncio

# Database setup
class MediaDatabase:
    def __init__(self, db_name='anime_bot.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        # Users table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_date TIMESTAMP,
                last_active TIMESTAMP
            )
        ''')
        
        # Anime table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS anime (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT CHECK(type IN ('Manga', 'EP', 'OVA')),
                description TEXT,
                rating REAL,
                total_episodes INTEGER,
                image_url TEXT,
                status TEXT DEFAULT 'Ongoing'
            )
        ''')
        
        # Anime Episodes table with Telegram File ID support
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS anime_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                episode_number INTEGER,
                title TEXT,
                description TEXT,
                air_date TEXT,
                filler BOOLEAN DEFAULT 0,
                telegram_file_id TEXT,
                thumbnail_file_id TEXT,
                duration INTEGER,
                file_size INTEGER,
                upload_date TIMESTAMP,
                FOREIGN KEY (anime_id) REFERENCES anime (id)
            )
        ''')
        
        # User progress table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                anime_id INTEGER,
                last_watched_episode INTEGER DEFAULT 0,
                last_updated TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (anime_id) REFERENCES anime (id)
            )
        ''')
        
        # Upload queue table for batch uploads
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS upload_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                episode_number INTEGER,
                file_path TEXT,
                status TEXT DEFAULT 'pending',
                upload_attempts INTEGER DEFAULT 0,
                last_attempt TIMESTAMP,
                FOREIGN KEY (anime_id) REFERENCES anime (id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, joined_date, last_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now(), datetime.now()))
        self.conn.commit()
    
    def update_last_active(self, user_id):
        self.cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                          (datetime.now(), user_id))
        self.conn.commit()
    
    # ANIME METHODS
    def get_anime_by_type(self, anime_type):
        self.cursor.execute('''
            SELECT * FROM anime WHERE type = ? ORDER BY title
        ''', (anime_type,))
        return self.cursor.fetchall()
    
    def get_anime_details(self, anime_id):
        self.cursor.execute('SELECT * FROM anime WHERE id = ?', (anime_id,))
        return self.cursor.fetchone()
    
    def get_anime_episodes(self, anime_id, page=1, episodes_per_page=20):
        offset = (page - 1) * episodes_per_page
        self.cursor.execute('''
            SELECT * FROM anime_episodes 
            WHERE anime_id = ? 
            ORDER BY episode_number 
            LIMIT ? OFFSET ?
        ''', (anime_id, episodes_per_page, offset))
        return self.cursor.fetchall()
    
    def get_total_episodes_count(self, anime_id):
        self.cursor.execute('''
            SELECT COUNT(*) FROM anime_episodes WHERE anime_id = ?
        ''', (anime_id,))
        return self.cursor.fetchone()[0]
    
    def get_episode_details(self, episode_id):
        self.cursor.execute('''
            SELECT * FROM anime_episodes WHERE id = ?
        ''', (episode_id,))
        return self.cursor.fetchone()
    
    def update_episode_telegram_file_id(self, episode_id, file_id, thumbnail_id=None, duration=None, file_size=None):
        """Store Telegram file_id after sending video"""
        self.cursor.execute('''
            UPDATE anime_episodes 
            SET telegram_file_id = ?, thumbnail_file_id = ?, duration = ?, file_size = ?, upload_date = ?
            WHERE id = ?
        ''', (file_id, thumbnail_id, duration, file_size, datetime.now(), episode_id))
        self.conn.commit()
    
    def update_user_progress(self, user_id, anime_id, episode):
        self.cursor.execute('''
            INSERT OR REPLACE INTO user_progress (user_id, anime_id, last_watched_episode, last_updated)
            VALUES (?, ?, ?, ?)
        ''', (user_id, anime_id, episode, datetime.now()))
        self.conn.commit()
    
    def get_user_progress(self, user_id, anime_id):
        self.cursor.execute('''
            SELECT last_watched_episode FROM user_progress 
            WHERE user_id = ? AND anime_id = ?
        ''', (user_id, anime_id))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    # Upload queue methods
    def add_to_upload_queue(self, anime_id, episode_number, file_path):
        self.cursor.execute('''
            INSERT INTO upload_queue (anime_id, episode_number, file_path, status)
            VALUES (?, ?, ?, ?)
        ''', (anime_id, episode_number, file_path, 'pending'))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_pending_uploads(self, limit=10):
        self.cursor.execute('''
            SELECT * FROM upload_queue 
            WHERE status = 'pending' OR (status = 'failed' AND upload_attempts < 3)
            ORDER BY episode_number
            LIMIT ?
        ''', (limit,))
        return self.cursor.fetchall()
    
    def update_upload_status(self, queue_id, status, attempts=None):
        if attempts is not None:
            self.cursor.execute('''
                UPDATE upload_queue 
                SET status = ?, upload_attempts = ?, last_attempt = ?
                WHERE id = ?
            ''', (status, attempts, datetime.now(), queue_id))
        else:
            self.cursor.execute('''
                UPDATE upload_queue 
                SET status = ?, last_attempt = ?
                WHERE id = ?
            ''', (status, datetime.now(), queue_id))
        self.conn.commit()

# Initialize database
db = MediaDatabase()

# Bot configuration
BOT_TOKEN = '8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac'  # Replace with your bot token
STORAGE_CHANNEL_ID = '@your_storage_channel'  # Replace with your channel username or ID

# Function to generate One Piece episodes
def generate_one_piece_episodes():
    """Generate One Piece episodes in database"""
    # First, add One Piece to anime table if not exists
    db.cursor.execute('''
        INSERT OR IGNORE INTO anime (title, type, description, rating, total_episodes, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('One Piece', 'EP', 'Follow Monkey D. Luffy in his quest to become the Pirate King', 
          9.8, 1155, 'Ongoing'))
    db.conn.commit()
    
    # Get One Piece ID
    db.cursor.execute('SELECT id FROM anime WHERE title = "One Piece"')
    one_piece_id = db.cursor.fetchone()[0]
    
    # Check if episodes already exist
    db.cursor.execute('SELECT COUNT(*) FROM anime_episodes WHERE anime_id = ?', (one_piece_id,))
    count = db.cursor.fetchone()[0]
    
    if count == 0:
        # Arc definitions
        arcs = [
            (1, 61, "East Blue Saga", "Luffy begins his journey and gathers his first crew members"),
            (62, 77, "Loguetown Arc", "The crew arrives at Loguetown, where Gol D. Roger was born"),
            (78, 153, "Sky Island Saga", "Adventure in the clouds with Cricket and the Skypeians"),
            (154, 195, "Water 7 Saga", "The crew faces the CP9 and fights to save Robin"),
            (196, 228, "Thriller Bark Saga", "Battle against Gecko Moria in a haunted ship"),
            (229, 325, "Summit War Saga", "The crew separates as Luffy fights to save Ace"),
            (326, 384, "Fish-Man Island Saga", "Underwater adventure and prophecy of the Poseidon"),
            (385, 516, "Dressrosa Saga", "Luffy fights Doflamingo to save a kingdom"),
            (517, 574, "Whole Cake Island Saga", "Sanji's wedding and battle against Big Mom"),
            (575, 746, "Wano Country Act 1-2", "The samurai country arc begins"),
            (747, 877, "Wano Country Act 3", "The raid on Onigashima begins"),
            (878, 982, "Wano Country Act 3 Continues", "Luffy vs Kaido"),
            (983, 1054, "Wano Country Final Act", "The climax of the Wano arc"),
            (1055, 1085, "Egghead Arc", "The crew visits Dr. Vegapunk"),
            (1086, 1155, "Egghead Arc Continues", "Revelations about the Void Century")
        ]
        
        for arc_start, arc_end, arc_name, arc_desc in arcs:
            for ep_num in range(arc_start, arc_end + 1):
                if ep_num <= 1155:
                    # Generate episode title and description
                    if ep_num == 1:
                        title = "I'm Luffy! The Man Who Will Become the Pirate King!"
                        desc = "Luffy begins his journey by saving Coby and meets Roronoa Zoro."
                    elif ep_num == 1155:
                        title = "The Beginning of the New Era! Luffy's Final Battle!"
                        desc = "The epic conclusion of the Egghead arc begins as Luffy faces the Elders."
                    else:
                        title = f"Episode {ep_num}: {arc_name}"
                        desc = f"{arc_desc} - Part {((ep_num - arc_start) // 5) + 1}."
                    
                    # Insert episode
                    db.cursor.execute('''
                        INSERT INTO anime_episodes 
                        (anime_id, episode_number, title, description, air_date, filler)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        one_piece_id, 
                        ep_num, 
                        title, 
                        desc, 
                        f"20{(ep_num//100)+19}-{(ep_num%12)+1:02d}-01",
                        1 if ep_num % 10 == 0 else 0
                    ))
        
        db.conn.commit()
        print(f"✅ Generated {1155} One Piece episodes in database!")

def add_sample_data():
    """Add other anime, movies, and TV shows"""
    # Add other anime
    other_anime = [
        ('Naruto', 'EP', 'The story of Naruto Uzumaki, a ninja with dreams of becoming Hokage', 9.5, 720, 'Completed'),
        ('Naruto Shippuden', 'EP', 'The continuation of Naruto\'s journey', 9.6, 500, 'Completed'),
        ('Attack on Titan', 'EP', 'Humanity fights for survival against giant humanoid Titans', 9.7, 139, 'Completed'),
        ('Demon Slayer', 'EP', 'Tanjiro fights demons to save his sister', 9.6, 55, 'Ongoing'),
        ('Jujutsu Kaisen', 'EP', 'A boy fights curses to protect the world', 9.4, 47, 'Ongoing'),
        ('Chainsaw Man', 'EP', 'Denji merges with his pet devil to become Chainsaw Man', 9.3, 12, 'Ongoing'),
        ('Bleach', 'EP', 'A teenager becomes a Soul Reaper', 9.2, 366, 'Completed'),
        ('My Hero Academia', 'EP', 'A boy without powers in a world of superheroes', 9.4, 138, 'Ongoing'),
        
        # Manga
        ('Berserk', 'Manga', 'A dark fantasy tale of revenge and survival', 9.7, 364, 'Ongoing'),
        ('Vagabond', 'Manga', 'The life of legendary swordsman Miyamoto Musashi', 9.6, 327, 'Hiatus'),
        ('One Punch Man', 'Manga', 'A hero who can defeat anyone with one punch', 9.5, 200, 'Ongoing'),
        
        # OVA
        ('Naruto: The Last', 'OVA', 'Naruto and Hinata\'s romantic adventure', 9.1, 1, 'Completed'),
        ('Attack on Titan: No Regrets', 'OVA', 'The backstory of Captain Levi', 9.4, 2, 'Completed'),
        ('One Piece: Strong World', 'OVA', 'Luffy fights against the legendary pirate Shiki', 9.2, 1, 'Completed')
    ]
    
    for anime in other_anime:
        try:
            db.cursor.execute('''
                INSERT OR IGNORE INTO anime (title, type, description, rating, total_episodes, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', anime)
        except:
            pass
    
    db.conn.commit()
    print("✅ Sample anime data added!")

# Function to add episodes to upload queue (run this when you have video files)
def add_videos_to_upload_queue(video_folder):
    """Add all video files from a folder to upload queue"""
    import os
    
    # Get One Piece ID
    db.cursor.execute('SELECT id FROM anime WHERE title = "One Piece"')
    one_piece_id = db.cursor.fetchone()[0]
    
    video_extensions = ('.mp4', '.mkv', '.avi', '.mov')
    files_added = 0
    
    for filename in sorted(os.listdir(video_folder)):
        if filename.lower().endswith(video_extensions):
            # Try to extract episode number from filename
            import re
            match = re.search(r'ep[_. ]?(\d+)', filename, re.I)
            
            if match:
                episode_num = int(match.group(1))
                if 1 <= episode_num <= 1155:
                    file_path = os.path.join(video_folder, filename)
                    db.add_to_upload_queue(one_piece_id, episode_num, file_path)
                    files_added += 1
                    print(f"  Added to queue: Episode {episode_num} - {filename}")
    
    print(f"✅ Added {files_added} episodes to upload queue!")

# Upload videos to Telegram and get file_ids
async def process_upload_queue(context: ContextTypes.DEFAULT_TYPE):
    """Process pending uploads from queue"""
    pending = db.get_pending_uploads(5)  # Process 5 at a time
    
    if not pending:
        return
    
    for upload in pending:
        queue_id, anime_id, episode_num, file_path, status, attempts, last_attempt = upload
        
        print(f"📤 Uploading Episode {episode_num}...")
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                db.update_upload_status(queue_id, 'failed', attempts + 1)
                print(f"  ❌ File not found: {file_path}")
                continue
            
            # Upload to Telegram storage channel
            with open(file_path, 'rb') as video_file:
                message = await context.bot.send_video(
                    chat_id=STORAGE_CHANNEL_ID,
                    video=video_file,
                    caption=f"One Piece Episode {episode_num}",
                    supports_streaming=True,
                    filename=f"One_Piece_Episode_{episode_num}.mp4"
                )
            
            # Get file_id from the sent message
            file_id = message.video.file_id
            thumbnail_id = message.video.thumbnail.file_id if message.video.thumbnail else None
            duration = message.video.duration
            file_size = message.video.file_size
            
            # Update episode with file_id
            episode_record = db.cursor.execute('''
                SELECT id FROM anime_episodes 
                WHERE anime_id = ? AND episode_number = ?
            ''', (anime_id, episode_num)).fetchone()
            
            if episode_record:
                episode_id = episode_record[0]
                db.update_episode_telegram_file_id(
                    episode_id, file_id, thumbnail_id, duration, file_size
                )
            
            # Update queue status
            db.update_upload_status(queue_id, 'completed', attempts + 1)
            print(f"  ✅ Episode {episode_num} uploaded! File ID: {file_id[:20]}...")
            
            # Small delay to avoid flooding
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"  ❌ Error uploading Episode {episode_num}: {e}")
            db.update_upload_status(queue_id, 'failed', attempts + 1)

# Command to manually upload a specific episode
async def upload_episode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to upload a specific episode - /upload 123"""
    try:
        episode_num = int(context.args[0])
        
        # Get One Piece ID
        db.cursor.execute('SELECT id FROM anime WHERE title = "One Piece"')
        one_piece_id = db.cursor.fetchone()[0]
        
        # Get episode details
        db.cursor.execute('''
            SELECT id FROM anime_episodes 
            WHERE anime_id = ? AND episode_number = ?
        ''', (one_piece_id, episode_num))
        result = db.cursor.fetchone()
        
        if not result:
            await update.message.reply_text(f"❌ Episode {episode_num} not found in database!")
            return
        
        episode_id = result[0]
        
        # Ask user to send the video
        await update.message.reply_text(
            f"📤 Please send the video file for One Piece Episode {episode_num}\n"
            f"(MP4 format recommended for better streaming)"
        )
        
        # Store episode_id in context for next message
        context.user_data['waiting_for_video'] = episode_id
        context.user_data['episode_num'] = episode_num
        
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /upload [episode_number]")

# Handle video messages from users
async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video files sent by users"""
    if 'waiting_for_video' not in context.user_data:
        return
    
    episode_id = context.user_data['waiting_for_video']
    episode_num = context.user_data.get('episode_num', 'unknown')
    
    if update.message.video:
        video = update.message.video
        
        # Get file_id
        file_id = video.file_id
        thumbnail_id = video.thumbnail.file_id if video.thumbnail else None
        duration = video.duration
        file_size = video.file_size
        
        # Update database
        db.update_episode_telegram_file_id(episode_id, file_id, thumbnail_id, duration, file_size)
        
        await update.message.reply_text(
            f"✅ Episode {episode_num} uploaded successfully!\n"
            f"File ID: `{file_id}`",
            parse_mode='Markdown'
        )
        
        # Clear user data
        del context.user_data['waiting_for_video']
        del context.user_data['episode_num']
    
    elif update.message.document:
        # Handle document (might be video file)
        await update.message.reply_text(
            "Please send as video (not document) for better streaming.\n"
            "Use /upload again and send as video."
        )

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Add user to database
    db.add_user(user.id, user.username, user.first_name)
    
    # Create main menu
    keyboard = [
        [InlineKeyboardButton("📺 ANIME", callback_data='main_anime')],
        [InlineKeyboardButton("🎬 MOVIE", callback_data='main_movie')],
        [InlineKeyboardButton("📱 TV", callback_data='main_tv')]
    ]
    
    # Add admin button for upload (only for specific users)
    if user.id in [123456789]:  # Replace with your Telegram user ID
        keyboard.append([InlineKeyboardButton("📤 Admin Upload", callback_data='admin_upload')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"Welcome {user.first_name}! 🎉\n\n"
        "Choose a category to explore:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    db.update_last_active(user_id)
    
    # Main menu navigation
    if query.data == 'main_anime':
        await show_anime_menu(query)
    
    elif query.data == 'main_movie':
        await show_movies(query)
    
    elif query.data == 'main_tv':
        await show_tv_shows(query)
    
    elif query.data == 'admin_upload':
        await show_admin_menu(query)
    
    # Anime submenu options
    elif query.data == 'anime_manga':
        await show_anime_by_type(query, 'Manga')
    
    elif query.data == 'anime_ep':
        await show_anime_by_type(query, 'EP')
    
    elif query.data == 'anime_ova':
        await show_anime_by_type(query, 'OVA')
    
    # Anime details and episodes
    elif query.data.startswith('anime_detail_'):
        anime_id = int(query.data.split('_')[2])
        await show_anime_details(query, anime_id)
    
    elif query.data.startswith('show_episodes_'):
        anime_id = int(query.data.split('_')[2])
        context.user_data['current_anime'] = anime_id
        await show_episode_list(query, anime_id, 1)
    
    elif query.data.startswith('ep_page_'):
        parts = query.data.split('_')
        anime_id = int(parts[2])
        page = int(parts[3])
        await show_episode_list(query, anime_id, page)
    
    elif query.data.startswith('episode_'):
        episode_id = int(query.data.split('_')[1])
        await show_episode_details(query, episode_id, context)
    
    elif query.data.startswith('play_episode_'):
        episode_id = int(query.data.split('_')[2])
        await play_episode(update, context, episode_id)
    
    elif query.data.startswith('mark_watched_'):
        parts = query.data.split('_')
        episode_id = int(parts[2])
        await mark_episode_watched(query, episode_id, user_id)
    
    # Admin functions
    elif query.data == 'upload_queue':
        await show_upload_queue(query)
    
    elif query.data.startswith('process_queue'):
        await process_upload_queue(context)
        await query.edit_message_text("✅ Processing upload queue... Check console for progress.")
    
    elif query.data == 'back_to_admin':
        await show_admin_menu(query)
    
    # Back navigation
    elif query.data == 'back_to_anime_menu':
        await show_anime_menu(query)
    
    elif query.data == 'back_to_episodes':
        anime_id = context.user_data.get('current_anime', 1)
        await show_episode_list(query, anime_id, 1)
    
    elif query.data == 'back_to_main':
        await show_main_menu(query)

async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📺 ANIME", callback_data='main_anime')],
        [InlineKeyboardButton("🎬 MOVIE", callback_data='main_movie')],
        [InlineKeyboardButton("📱 TV", callback_data='main_tv')]
    ]
    
    # Check if admin
    if query.from_user.id in [123456789]:  # Replace with your ID
        keyboard.append([InlineKeyboardButton("📤 Admin Panel", callback_data='admin_upload')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Main Menu - Choose a category:", reply_markup=reply_markup)

async def show_admin_menu(query):
    """Show admin menu for uploads"""
    # Get queue stats
    db.cursor.execute("SELECT COUNT(*) FROM upload_queue WHERE status = 'pending'")
    pending = db.cursor.fetchone()[0]
    
    db.cursor.execute("SELECT COUNT(*) FROM upload_queue WHERE status = 'completed'")
    completed = db.cursor.fetchone()[0]
    
    db.cursor.execute("SELECT COUNT(*) FROM upload_queue WHERE status = 'failed'")
    failed = db.cursor.fetchone()[0]
    
    db.cursor.execute("SELECT COUNT(*) FROM anime_episodes WHERE telegram_file_id IS NOT NULL")
    uploaded_eps = db.cursor.fetchone()[0]
    
    text = (
        "📤 *Admin Upload Panel*\n\n"
        f"📊 *Upload Statistics:*\n"
        f"✅ Uploaded Episodes: {uploaded_eps}/1155\n"
        f"⏳ Pending in Queue: {pending}\n"
        f"✅ Completed Uploads: {completed}\n"
        f"❌ Failed Uploads: {failed}\n\n"
        "Options:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 Show Upload Queue", callback_data='upload_queue')],
        [InlineKeyboardButton("▶️ Process Queue", callback_data='process_queue')],
        [InlineKeyboardButton("📤 Manual Upload", callback_data='manual_upload')],
        [InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_upload_queue(query):
    """Show current upload queue"""
    db.cursor.execute('''
        SELECT * FROM upload_queue 
        WHERE status IN ('pending', 'failed')
        ORDER BY episode_number
        LIMIT 20
    ''')
    queue = db.cursor.fetchall()
    
    if not queue:
        await query.edit_message_text(
            "📋 Upload queue is empty!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Admin", callback_data='back_to_admin')
            ]])
        )
        return
    
    text = "📋 *Upload Queue (First 20):*\n\n"
    
    for item in queue:
        queue_id, anime_id, ep_num, file_path, status, attempts, last_attempt = item
        status_emoji = "⏳" if status == 'pending' else "❌"
        text += f"{status_emoji} Episode {ep_num}: {status} (attempts: {attempts})\n"
    
    keyboard = [
        [InlineKeyboardButton("▶️ Process Now", callback_data='process_queue')],
        [InlineKeyboardButton("🔙 Back to Admin", callback_data='back_to_admin')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_anime_menu(query):
    """Show anime submenu"""
    keyboard = [
        [InlineKeyboardButton("📚 MANGA", callback_data='anime_manga')],
        [InlineKeyboardButton("📺 EP (Episodes)", callback_data='anime_ep')],
        [InlineKeyboardButton("💿 OVA", callback_data='anime_ova')],
        [InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "📺 *ANIME MENU*\n\n"
        "Choose what type of anime you're interested in:"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_anime_by_type(query, anime_type):
    """Show all anime of a specific type"""
    anime_list = db.get_anime_by_type(anime_type)
    
    if not anime_list:
        await query.edit_message_text(
            f"No {anime_type} found! 😢",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='back_to_anime_menu')
            ]])
        )
        return
    
    keyboard = []
    for anime in anime_list:
        episodes_text = f" - {anime[5]} eps" if anime[5] else ""
        button_text = f"{anime[1]} ⭐{anime[4]}{episodes_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'anime_detail_{anime[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_to_anime_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"📋 {anime_type} List:", reply_markup=reply_markup)

async def show_anime_details(query, anime_id):
    """Show detailed information about an anime"""
    anime = db.get_anime_details(anime_id)
    
    if not anime:
        await query.edit_message_text("Anime not found!")
        return
    
    emoji_map = {'Manga': '📚', 'EP': '📺', 'OVA': '💿'}
    
    text = (
        f"{emoji_map.get(anime[2], '📺')} *{anime[1]}*\n\n"
        f"📌 *Type:* {anime[2]}\n"
        f"⭐ *Rating:* {anime[4]}/10\n"
        f"📊 *Total Episodes:* {anime[5] if anime[5] else 'N/A'}\n"
        f"📈 *Status:* {anime[7]}\n\n"
        f"📝 *Description:*\n{anime[3]}"
    )
    
    keyboard = []
    
    if anime[2] == 'EP' and anime[5] and anime[5] > 0:
        keyboard.append([InlineKeyboardButton("📺 View Episodes", callback_data=f'show_episodes_{anime_id}')])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data=f'anime_{anime[2].lower()}'),
        InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_episode_list(query, anime_id, page=1):
    """Show paginated list of episodes"""
    episodes_per_page = 15
    episodes = db.get_anime_episodes(anime_id, page, episodes_per_page)
    total_episodes = db.get_total_episodes_count(anime_id)
    total_pages = math.ceil(total_episodes / episodes_per_page)
    
    anime = db.get_anime_details(anime_id)
    user_id = query.from_user.id
    last_watched = db.get_user_progress(user_id, anime_id)
    
    if not episodes:
        await query.edit_message_text(
            "No episodes found!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data=f'anime_detail_{anime_id}')
            ]])
        )
        return
    
    keyboard = []
    for episode in episodes:
        ep_num = episode[2]
        has_video = "🎬" if episode[7] else "❌"  # Check if has telegram_file_id
        filler_icon = "⚠️" if episode[6] else ""
        watched_icon = "✅" if ep_num <= last_watched else "⭕"
        
        button_text = f"{watched_icon}{has_video}{filler_icon} Ep {ep_num}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'episode_{episode[0]}')])
    
    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f'ep_page_{anime_id}_{page-1}'))
    
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f'ep_page_{anime_id}_{page+1}'))
    
    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f'anime_detail_{anime_id}')])
    
    progress_text = f"📺 *{anime[1]}*\n"
    progress_text += f"📊 Progress: {last_watched}/{total_episodes}\n\n"
    progress_text += "✅=Watched ⭕=Unwatched 🎬=Video ❌=NoVideo ⚠️=Filler"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(progress_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_episode_details(query, episode_id, context):
    """Show episode details"""
    episode = db.get_episode_details(episode_id)
    
    if not episode:
        await query.edit_message_text("Episode not found!")
        return
    
    has_video = "✅ Available" if episode[7] else "❌ Not Available"
    filler_text = "⚠️ Filler Episode" if episode[6] else "📺 Canon Episode"
    
    text = (
        f"📺 *Episode {episode[2]}: {episode[3]}*\n\n"
        f"📌 {filler_text}\n"
        f"🎬 Video: {has_video}\n"
        f"📅 Air Date: {episode[5]}\n\n"
        f"📝 *Description:*\n{episode[4]}"
    )
    
    keyboard = []
    
    if episode[7]:  # Has video
        keyboard.append([InlineKeyboardButton("▶️ PLAY EPISODE", callback_data=f'play_episode_{episode_id}')])
    
    keyboard.extend([
        [InlineKeyboardButton("✅ Mark Watched", callback_data=f'mark_watched_{episode_id}')],
        [InlineKeyboardButton("🔙 Back to Episodes", callback_data='back_to_episodes')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ])
    
    context.user_data['current_episode'] = episode_id
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def play_episode(update: Update, context: ContextTypes.DEFAULT_TYPE, episode_id):
    """Play episode using Telegram file_id"""
    query = update.callback_query
    await query.answer()
    
    episode = db.get_episode_details(episode_id)
    
    if not episode or not episode[7]:  # Check if has file_id
        await query.message.reply_text("❌ Video not available for this episode!")
        return
    
    file_id = episode[7]
    title = episode[3]
    ep_num = episode[2]
    
    caption = f"📺 *One Piece Episode {ep_num}*\n{title}"
    
    try:
        # Send video using file_id (instant playback, no upload needed)
        await context.bot.send_video(
            chat_id=query.message.chat_id,
            video=file_id,
            caption=caption,
            parse_mode='Markdown',
            supports_streaming=True
        )
        
        # Auto-mark as watched (optional)
        user_id = query.from_user.id
        db.update_user_progress(user_id, episode[1], ep_num)
        
    except Exception as e:
        await query.message.reply_text(f"❌ Error playing video: {str(e)}")

async def mark_episode_watched(query, episode_id, user_id):
    """Mark episode as watched"""
    episode = db.get_episode_details(episode_id)
    
    if episode:
        db.update_user_progress(user_id, episode[1], episode[2])
        await query.answer(f"✅ Marked Episode {episode[2]} as watched!")
        await show_episode_list(query, episode[1], 1)

async def show_movies(query):
    """Show movies list"""
    db.cursor.execute('SELECT * FROM movies ORDER BY rating DESC')
    movies = db.cursor.fetchall()
    
    if not movies:
        await query.edit_message_text(
            "No movies found!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='back_to_main')
            ]])
        )
        return
    
    keyboard = []
    for movie in movies:
        button_text = f"🎬 {movie[1]} ⭐{movie[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'movie_detail_{movie[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🎬 *Movie List:*", reply_markup=reply_markup, parse_mode='Markdown')

async def show_tv_shows(query):
    """Show TV shows list"""
    db.cursor.execute('SELECT * FROM tv_shows ORDER BY rating DESC')
    shows = db.cursor.fetchall()
    
    if not shows:
        await query.edit_message_text(
            "No TV shows found!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data='back_to_main')
            ]])
        )
        return
    
    keyboard = []
    for show in shows:
        button_text = f"📱 {show[1]} ⭐{show[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'tv_detail_{show[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📱 *TV Shows List:*", reply_markup=reply_markup, parse_mode='Markdown')

# Function to manually add a Telegram file_id to an episode
def add_telegram_file_id_manually():
    """Manually add Telegram file_id to an episode"""
    print("=== Add Telegram File ID to Episode ===")
    
    episode_num = int(input("Enter episode number: "))
    file_id = input("Enter Telegram file_id: ")
    
    # Get One Piece ID
    db.cursor.execute('SELECT id FROM anime WHERE title = "One Piece"')
    one_piece_id = db.cursor.fetchone()[0]
    
    # Get episode ID
    db.cursor.execute('''
        SELECT id FROM anime_episodes 
        WHERE anime_id = ? AND episode_number = ?
    ''', (one_piece_id, episode_num))
    result = db.cursor.fetchone()
    
    if result:
        episode_id = result[0]
        db.update_episode_telegram_file_id(episode_id, file_id)
        print(f"✅ Added file_id to Episode {episode_num}")
    else:
        print(f"❌ Episode {episode_num} not found!")

def main():
    # Initialize database with episodes
    generate_one_piece_episodes()
    add_sample_data()
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("upload", upload_episode_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handle video uploads
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add a job to process upload queue every hour (optional)
    # job_queue = application.job_queue
    # job_queue.run_repeating(process_upload_queue, interval=3600, first=10)
    
    # Start the bot
    print("🎬 Anime Bot with Telegram File IDs is starting...")
    print(f"📺 One Piece: 1155 episodes in database")
    print("\n📤 To upload videos:")
    print("1. Place video files in a folder")
    print("2. Use add_videos_to_upload_queue('/path/to/videos')")
    print("3. Or use /upload command in Telegram")
    print("\n⚙️ Don't forget to set your STORAGE_CHANNEL_ID!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
