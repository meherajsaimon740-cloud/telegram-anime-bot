import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import math
import re

# Database setup
class MediaDatabase:
    def __init__(self, db_name='media_bot.db'):
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
        
        # Anime Episodes table with video support
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS anime_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                episode_number INTEGER,
                title TEXT,
                description TEXT,
                air_date TEXT,
                filler BOOLEAN DEFAULT 0,
                video_url TEXT,
                video_file_id TEXT,
                channel_username TEXT,
                channel_message_id INTEGER,
                streaming_url TEXT,
                FOREIGN KEY (anime_id) REFERENCES anime (id)
            )
        ''')
        
        # Video sources table (for multiple sources per episode)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER,
                source_type TEXT CHECK(source_type IN ('direct', 'telegram', 'streaming', 'torrent')),
                source_url TEXT,
                quality TEXT,
                language TEXT,
                FOREIGN KEY (episode_id) REFERENCES anime_episodes (id)
            )
        ''')
        
        # Telegram channels table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS telegram_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_username TEXT UNIQUE,
                channel_title TEXT,
                description TEXT,
                episode_range_start INTEGER,
                episode_range_end INTEGER,
                last_checked TIMESTAMP
            )
        ''')
        
        # Movies table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                rating REAL,
                duration INTEGER,
                genre TEXT,
                release_year INTEGER,
                image_url TEXT,
                video_url TEXT,
                video_file_id TEXT
            )
        ''')
        
        # TV Shows table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tv_shows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                rating REAL,
                seasons INTEGER,
                episodes_per_season INTEGER,
                status TEXT DEFAULT 'Ongoing',
                image_url TEXT
            )
        ''')
        
        # TV Show Episodes table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tv_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                show_id INTEGER,
                season_number INTEGER,
                episode_number INTEGER,
                title TEXT,
                description TEXT,
                air_date TEXT,
                video_url TEXT,
                video_file_id TEXT,
                FOREIGN KEY (show_id) REFERENCES tv_shows (id)
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
        
        # User video preferences
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id INTEGER PRIMARY KEY,
                preferred_quality TEXT DEFAULT '720p',
                preferred_language TEXT DEFAULT 'sub',
                auto_play BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        self.conn.commit()
    
    def add_user(self, user_id, username, first_name):
        self.cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, joined_date, last_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, first_name, datetime.now(), datetime.now()))
        self.conn.commit()
        
        # Create user preferences if not exists
        self.cursor.execute('''
            INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)
        ''', (user_id,))
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
    
    def get_episode_video_sources(self, episode_id):
        """Get all video sources for an episode"""
        self.cursor.execute('''
            SELECT * FROM video_sources WHERE episode_id = ? ORDER BY 
            CASE source_type
                WHEN 'direct' THEN 1
                WHEN 'telegram' THEN 2
                WHEN 'streaming' THEN 3
                ELSE 4
            END
        ''', (episode_id,))
        return self.cursor.fetchall()
    
    def add_video_source(self, episode_id, source_type, source_url, quality='720p', language='sub'):
        """Add a video source for an episode"""
        self.cursor.execute('''
            INSERT INTO video_sources (episode_id, source_type, source_url, quality, language)
            VALUES (?, ?, ?, ?, ?)
        ''', (episode_id, source_type, source_url, quality, language))
        self.conn.commit()
    
    def update_video_file_id(self, episode_id, file_id):
        """Store Telegram file_id after sending video"""
        self.cursor.execute('''
            UPDATE anime_episodes SET video_file_id = ? WHERE id = ?
        ''', (file_id, episode_id))
        self.conn.commit()
    
    def add_telegram_channel(self, channel_username, channel_title, description, 
                            ep_start, ep_end):
        """Add a Telegram channel as video source"""
        self.cursor.execute('''
            INSERT OR REPLACE INTO telegram_channels 
            (channel_username, channel_title, description, episode_range_start, episode_range_end, last_checked)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (channel_username, channel_title, description, ep_start, ep_end, datetime.now()))
        self.conn.commit()
    
    def get_channels_for_episode(self, episode_number):
        """Find channels that have this episode"""
        self.cursor.execute('''
            SELECT * FROM telegram_channels 
            WHERE episode_range_start <= ? AND episode_range_end >= ?
        ''', (episode_number, episode_number))
        return self.cursor.fetchall()
    
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
    
    def get_user_preferences(self, user_id):
        self.cursor.execute('''
            SELECT preferred_quality, preferred_language, auto_play 
            FROM user_preferences WHERE user_id = ?
        ''', (user_id,))
        return self.cursor.fetchone()

# Initialize database
db = MediaDatabase()

# Bot configuration
BOT_TOKEN = '8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac'  # Replace with your bot token

# Known Telegram channels for One Piece (from search results)
ONE_PIECE_CHANNELS = [
    {
        'username': '@onepiecedeluxe',
        'title': 'One Piece Deluxe',
        'description': 'HD episodes with multiple qualities',
        'ep_start': 1,
        'ep_end': 1070
    },
    {
        'username': '@mugiwaraitalia',
        'title': 'Mugiwara Italia',
        'description': 'All episodes, movies, and specials in Italian',
        'ep_start': 1,
        'ep_end': 1070
    },
    {
        'username': '@Onepiece_canal',
        'title': 'One piece Canal™',
        'description': '96.9K subscribers with 782 videos',
        'ep_start': 1,
        'ep_end': 782
    },
    {
        'username': '@onepiece_latino_oficial',
        'title': 'One Piece Latino',
        'description': 'Spanish dubbed episodes',
        'ep_start': 1,
        'ep_end': 950
    },
    {
        'username': '@onepiece_sub_espanol',
        'title': 'One Piece Sub Español',
        'description': 'Spanish subtitled episodes',
        'ep_start': 1,
        'ep_end': 1070
    },
    {
        'username': '@Remux_2160P',
        'title': 'Remux 2160P',
        'description': '4K One Piece content',
        'ep_start': 900,
        'ep_end': 1070
    }
]

def setup_telegram_channels():
    """Add known Telegram channels to database"""
    for channel in ONE_PIECE_CHANNELS:
        db.add_telegram_channel(
            channel['username'],
            channel['title'],
            channel['description'],
            channel['ep_start'],
            channel['ep_end']
        )
    print(f"Added {len(ONE_PIECE_CHANNELS)} Telegram channels")

def generate_one_piece_episodes_with_videos():
    """Generate One Piece episodes with multiple video sources"""
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
                        desc = "Luffy begins his journey by saving Coby and meets Roronoa Zoro. The East Blue saga begins!"
                    elif ep_num == 1155:
                        title = "The Beginning of the New Era! Luffy's Final Battle!"
                        desc = "The epic conclusion of the Egghead arc begins as Luffy faces the Elders."
                    else:
                        # Generate dynamic titles based on arcs
                        filler_text = " (Filler)" if ep_num % 10 == 0 else ""
                        title = f"Episode {ep_num}: {arc_name}{filler_text}"
                        desc = f"{arc_desc} - Part {((ep_num - arc_start) // 5) + 1} of the {arc_name}."
                    
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
                    
                    episode_id = db.cursor.lastrowid
                    
                    # Add video sources for this episode
                    add_video_sources_for_episode(episode_id, ep_num)
        
        db.conn.commit()
        print(f"Generated {1155} One Piece episodes with video sources!")

def add_video_sources_for_episode(episode_id, episode_number):
    """Add multiple video sources for an episode"""
    
    # 1. Direct download links (example - replace with actual links)
    # You would need to host these files or find reliable sources
    direct_urls = [
        {
            'url': f"https://example.com/one-piece/episode-{episode_number:04d}.mp4",
            'quality': '1080p',
            'language': 'sub'
        },
        {
            'url': f"https://example.com/one-piece/episode-{episode_number:04d}-720p.mp4",
            'quality': '720p',
            'language': 'sub'
        }
    ]
    
    # 2. Streaming service links
    streaming_urls = [
        {
            'url': f"https://www.crunchyroll.com/watch/one-piece-episode-{episode_number}",
            'quality': 'variable',
            'language': 'sub'
        },
        {
            'url': f"https://www.funimation.com/shows/one-piece/episode-{episode_number}",
            'quality': 'variable',
            'language': 'dub'
        },
        {
            'url': f"https://9anime.to/watch/one-piece.{episode_number}",
            'quality': 'variable',
            'language': 'sub'
        }
    ]
    
    # 3. Add direct sources
    for source in direct_urls:
        try:
            db.add_video_source(episode_id, 'direct', source['url'], 
                              source['quality'], source['language'])
        except:
            pass
    
    # 4. Add streaming sources
    for source in streaming_urls:
        try:
            db.add_video_source(episode_id, 'streaming', source['url'],
                              source['quality'], source['language'])
        except:
            pass
    
    # 5. Add Telegram channel info (will be used to generate channel links)
    channels = db.get_channels_for_episode(episode_number)
    for channel in channels:
        channel_url = f"https://t.me/{channel[1].replace('@', '')}"
        try:
            db.add_video_source(episode_id, 'telegram', channel_url,
                              'variable', 'multiple')
        except:
            pass

def add_sample_data():
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
    
    # Add sample movies
    movies = [
        ('Inception', 'A thief who steals corporate secrets through dream-sharing technology', 9.0, 148, 'Sci-Fi', 2010),
        ('The Dark Knight', 'Batman fights against the Joker in Gotham City', 9.3, 152, 'Action', 2008),
        ('Spirited Away', 'A young girl enters a mysterious world of spirits', 9.5, 125, 'Animation', 2001),
        ('Your Name', 'Two teenagers discover a mysterious connection', 9.4, 106, 'Animation', 2016),
        ('Interstellar', 'A team of explorers travel through a wormhole in space', 9.4, 169, 'Sci-Fi', 2014)
    ]
    
    for movie in movies:
        try:
            db.cursor.execute('''
                INSERT OR IGNORE INTO movies (title, description, rating, duration, genre, release_year)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', movie)
        except:
            pass
    
    # Add sample TV shows
    tv_shows = [
        ('Breaking Bad', 'A chemistry teacher turns to cooking meth', 9.8, 5, 13, 'Completed'),
        ('Game of Thrones', 'Noble families fight for control of the Iron Throne', 9.5, 8, 10, 'Completed'),
        ('Stranger Things', 'Kids encounter supernatural forces in 1980s Indiana', 9.2, 4, 9, 'Ongoing'),
        ('The Witcher', 'A monster hunter navigates a chaotic world', 8.9, 3, 8, 'Ongoing'),
        ('The Mandalorian', 'A lone bounty hunter in the Star Wars universe', 9.4, 3, 8, 'Ongoing')
    ]
    
    for tv in tv_shows:
        try:
            db.cursor.execute('''
                INSERT OR IGNORE INTO tv_shows (title, description, rating, seasons, episodes_per_season, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', tv)
        except:
            pass
    
    db.conn.commit()
    print("Sample data added!")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Add user to database
    db.add_user(user.id, user.username, user.first_name)
    
    # Create main menu with 3 buttons
    keyboard = [
        [InlineKeyboardButton("📺 ANIME", callback_data='main_anime')],
        [InlineKeyboardButton("🎬 MOVIE", callback_data='main_movie')],
        [InlineKeyboardButton("📱 TV", callback_data='main_tv')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"Welcome {user.first_name}! 🎉\n\n"
        "Choose a category to explore:\n\n"
        "📺 *Anime* - Watch episodes with video playback\n"
        "🎬 *Movies* - Full-length feature films\n"
        "📱 *TV Shows* - Series and seasons"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

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
    
    elif query.data.startswith('play_video_'):
        await play_video(update, context)
    
    elif query.data.startswith('play_source_'):
        await play_from_source(update, context)
    
    elif query.data.startswith('mark_watched_'):
        parts = query.data.split('_')
        episode_id = int(parts[2])
        await mark_episode_watched(query, episode_id, user_id)
    
    # Movie and TV show details
    elif query.data.startswith('movie_detail_'):
        movie_id = int(query.data.split('_')[2])
        await show_movie_details(query, movie_id)
    
    elif query.data.startswith('play_movie_'):
        await play_movie(update, context)
    
    elif query.data.startswith('tv_detail_'):
        show_id = int(query.data.split('_')[2])
        await show_tv_details(query, show_id)
    
    # Back navigation
    elif query.data == 'back_to_anime_menu':
        await show_anime_menu(query)
    
    elif query.data == 'back_to_episodes':
        anime_id = context.user_data.get('current_anime', 1)
        await show_episode_list(query, anime_id, 1)
    
    elif query.data == 'back_to_main':
        await show_main_menu(query)
    
    # Preferences
    elif query.data == 'preferences':
        await show_preferences(query, user_id)
    
    elif query.data.startswith('set_quality_'):
        quality = query.data.split('_')[2]
        await set_preference(query, user_id, 'quality', quality)
    
    elif query.data.startswith('set_lang_'):
        lang = query.data.split('_')[2]
        await set_preference(query, user_id, 'language', lang)

async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📺 ANIME", callback_data='main_anime')],
        [InlineKeyboardButton("🎬 MOVIE", callback_data='main_movie')],
        [InlineKeyboardButton("📱 TV", callback_data='main_tv')],
        [InlineKeyboardButton("⚙️ Preferences", callback_data='preferences')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Main Menu - Choose a category:", reply_markup=reply_markup)

async def show_preferences(query, user_id):
    """Show user preferences menu"""
    prefs = db.get_user_preferences(user_id)
    
    if prefs:
        quality, language, auto_play = prefs
    else:
        quality, language, auto_play = "720p", "sub", 0
    
    text = (
        "⚙️ *Your Preferences*\n\n"
        f"🎬 Preferred Quality: {quality}\n"
        f"🌐 Preferred Language: {'Subtitled' if language == 'sub' else 'Dubbed'}\n"
        f"▶️ Auto Play: {'On' if auto_play else 'Off'}\n\n"
        "Select quality:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("480p", callback_data='set_quality_480p'),
            InlineKeyboardButton("720p", callback_data='set_quality_720p'),
            InlineKeyboardButton("1080p", callback_data='set_quality_1080p')
        ],
        [
            InlineKeyboardButton("4K", callback_data='set_quality_4K')
        ],
        [
            InlineKeyboardButton("Subtitled", callback_data='set_lang_sub'),
            InlineKeyboardButton("Dubbed", callback_data='set_lang_dub')
        ],
        [InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def set_preference(query, user_id, pref_type, value):
    """Set user preference"""
    if pref_type == 'quality':
        db.cursor.execute('''
            UPDATE user_preferences SET preferred_quality = ? WHERE user_id = ?
        ''', (value, user_id))
    elif pref_type == 'language':
        db.cursor.execute('''
            UPDATE user_preferences SET preferred_language = ? WHERE user_id = ?
        ''', (value, user_id))
    
    db.conn.commit()
    await query.answer(f"✅ {pref_type.capitalize()} set to {value}")
    await show_preferences(query, user_id)

async def show_anime_menu(query):
    """Show anime submenu with Manga, EP, OVA options"""
    keyboard = [
        [InlineKeyboardButton("📚 MANGA", callback_data='anime_manga')],
        [InlineKeyboardButton("📺 EP (Episodes)", callback_data='anime_ep')],
        [InlineKeyboardButton("💿 OVA (Original Video Animation)", callback_data='anime_ova')],
        [InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "📺 *ANIME MENU*\n\n"
        "Choose what type of anime you're interested in:\n\n"
        "📚 *Manga* - Comic books/graphic novels\n"
        "📺 *EP* - TV series episodes (with video!)\n"
        "💿 *OVA* - Original Video Animation (specials/movies)"
    )
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_anime_by_type(query, anime_type):
    """Show all anime of a specific type"""
    anime_list = db.get_anime_by_type(anime_type)
    
    if not anime_list:
        await query.edit_message_text(
            f"No {anime_type} found! 😢",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Anime Menu", callback_data='back_to_anime_menu')
            ]])
        )
        return
    
    keyboard = []
    for anime in anime_list:
        # anime: (id, title, type, description, rating, total_episodes, image_url, status)
        episodes_text = f" - {anime[5]} eps" if anime[5] else ""
        video_icon = "🎬 " if anime[2] == 'EP' else ""
        button_text = f"{video_icon}{anime[1]} ⭐{anime[4]}{episodes_text}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'anime_detail_{anime[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Anime Menu", callback_data='back_to_anime_menu')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"📋 {anime_type} List:", reply_markup=reply_markup)

async def show_anime_details(query, anime_id):
    """Show detailed information about an anime"""
    anime = db.get_anime_details(anime_id)
    
    if not anime:
        await query.edit_message_text("Anime not found!")
        return
    
    # anime: (id, title, type, description, rating, total_episodes, image_url, status)
    emoji_map = {'Manga': '📚', 'EP': '📺', 'OVA': '💿'}
    video_available = "🎬 Video Available!" if anime[2] == 'EP' and anime[5] else ""
    
    text = (
        f"{emoji_map.get(anime[2], '📺')} *{anime[1]}*\n\n"
        f"{video_available}\n"
        f"📌 *Type:* {anime[2]}\n"
        f"⭐ *Rating:* {anime[4]}/10\n"
        f"📊 *Total Episodes/Chapters:* {anime[5] if anime[5] else 'N/A'}\n"
        f"📈 *Status:* {anime[7]}\n\n"
        f"📝 *Description:*\n{anime[3]}"
    )
    
    keyboard = []
    
    # Add "Watch Episodes" button only for EP type
    if anime[2] == 'EP' and anime[5] and anime[5] > 0:
        keyboard.append([InlineKeyboardButton("🎬 WATCH EPISODES", callback_data=f'show_episodes_{anime_id}')])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Back", callback_data=f'anime_{anime[2].lower()}'),
        InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_episode_list(query, anime_id, page=1):
    """Show paginated list of episodes"""
    episodes_per_page = 15  # Slightly smaller for better mobile viewing
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
                InlineKeyboardButton("🔙 Back to Anime", callback_data=f'anime_detail_{anime_id}')
            ]])
        )
        return
    
    # Create episode buttons
    keyboard = []
    for episode in episodes:
        # episode: (id, anime_id, episode_number, title, description, air_date, filler)
        ep_num = episode[2]
        filler_icon = "⚠️ " if episode[6] else ""
        watched_icon = "✅ " if ep_num <= last_watched else ""
        play_icon = "🎬 "
        
        # Check if episode has video sources
        video_sources = db.get_episode_video_sources(episode[0])
        video_indicator = "📺 " if video_sources else "❌ "
        
        button_text = f"{watched_icon}{play_icon}{video_indicator}Ep {ep_num}: {episode[3][:25]}..."
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'episode_{episode[0]}')])
    
    # Add pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f'ep_page_{anime_id}_{page-1}'))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f'ep_page_{anime_id}_{page+1}'))
    
    keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Anime", callback_data=f'anime_detail_{anime_id}')])
    
    progress_text = f"📺 *{anime[1]} Episodes*\n"
    progress_text += f"📊 Progress: Episode {last_watched}/{total_episodes}\n"
    progress_text += f"📌 Page {page}/{total_pages}\n\n"
    progress_text += "✅ = Watched | ⚠️ = Filler | 🎬 = Play | 📺 = Video Available | ❌ = No Video"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(progress_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_episode_details(query, episode_id, context):
    """Show detailed information about an episode with play options"""
    episode = db.get_episode_details(episode_id)
    
    if not episode:
        await query.edit_message_text("Episode not found!")
        return
    
    # Get video sources
    video_sources = db.get_episode_video_sources(episode_id)
    user_prefs = db.get_user_preferences(query.from_user.id)
    
    # episode: (id, anime_id, episode_number, title, description, air_date, filler)
    filler_text = "⚠️ FILLER EPISODE" if episode[6] else "📺 Canon Episode"
    video_count = len(video_sources)
    
    # Get user preferences
    pref_quality, pref_lang, auto_play = user_prefs if user_prefs else ("720p", "sub", 0)
    
    text = (
        f"📺 *Episode {episode[2]}: {episode[3]}*\n\n"
        f"📌 {filler_text}\n"
        f"📅 *Air Date:* {episode[5]}\n"
        f"🎬 *Video Sources:* {video_count} available\n\n"
        f"📝 *Description:*\n{episode[4]}"
    )
    
    # Create keyboard with play options
    keyboard = []
    
    # Add Play button
    if video_sources > 0:
        # Filter sources based on preferences
        preferred_sources = [s for s in video_sources if s[4] == pref_quality and s[5] == pref_lang]
        
        if preferred_sources:
            # Has preferred quality/language
            keyboard.append([InlineKeyboardButton(
                f"▶️ PLAY (with your preferences)", 
                callback_data=f'play_video_{episode_id}'
            )])
        
        # Add "More Sources" button if multiple sources
        if len(video_sources) > 1:
            keyboard.append([InlineKeyboardButton(
                "📋 Select Video Source", 
                callback_data=f'show_sources_{episode_id}'
            )])
        else:
            # Single source play button
            keyboard.append([InlineKeyboardButton(
                "▶️ PLAY EPISODE", 
                callback_data=f'play_video_{episode_id}'
            )])
    
    # Add source buttons
    keyboard.extend([
        [InlineKeyboardButton("✅ Mark as Watched", callback_data=f'mark_watched_ep_{episode_id}')],
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f'episode_prev_{episode_id}'),
            InlineKeyboardButton("Next ➡️", callback_data=f'episode_next_{episode_id}')
        ],
        [InlineKeyboardButton("🔙 Back to Episodes", callback_data='back_to_episodes')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ])
    
    # Store current episode in context for prev/next navigation
    context.user_data['current_episode'] = episode_id
    context.user_data['current_anime'] = episode[1]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def play_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play video for selected episode"""
    query = update.callback_query
    await query.answer()
    
    episode_id = int(query.data.split('_')[2])
    episode = db.get_episode_details(episode_id)
    user_prefs = db.get_user_preferences(query.from_user.id)
    
    if not episode:
        await query.message.reply_text("Episode not found!")
        return
    
    # Get video sources
    video_sources = db.get_episode_video_sources(episode_id)
    
    if not video_sources:
        await query.message.reply_text(
            "❌ No video sources available for this episode.\n\n"
            "Try checking these Telegram channels:\n"
            "• @onepiecedeluxe\n"
            "• @mugiwaraitalia\n"
            "• @Onepiece_canal"
        )
        return
    
    # Find best source based on user preferences
    pref_quality, pref_lang, auto_play = user_prefs if user_prefs else ("720p", "sub", 0)
    
    # Try to find preferred source
    preferred_source = None
    for source in video_sources:
        if source[4] == pref_quality and source[5] == pref_lang:
            preferred_source = source
            break
    
    # If no preferred source, use first available
    if not preferred_source and video_sources:
        preferred_source = video_sources[0]
    
    if not preferred_source:
        await query.message.reply_text("No suitable video source found!")
        return
    
    source_id, episode_id, source_type, source_url, quality, language = preferred_source
    
    # Create caption
    caption = (
        f"📺 *Episode {episode[2]}: {episode[3]}*\n"
        f"🎬 Quality: {quality} | 🌐 {language}\n"
        f"📌 Source: {source_type}"
    )
    
    # Send video based on source type
    try:
        if source_type == 'direct' and source_url.endswith(('.mp4', '.mkv', '.avi')):
            # Send direct video file
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=source_url,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
            
        elif source_type == 'streaming':
            # Send streaming link
            await query.message.reply_text(
                f"🎬 *Watch Episode {episode[2]}*\n\n"
                f"Click the link below to watch:\n{source_url}\n\n"
                f"Quality: {quality} | Language: {language}",
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        elif source_type == 'telegram':
            # Send Telegram channel link
            channel_info = f"Join this Telegram channel to watch:\n{source_url}"
            
            # Also try to find if the channel has the video
            await query.message.reply_text(
                f"📺 *Telegram Source*\n\n"
                f"{channel_info}\n\n"
                f"Look for Episode {episode[2]} in the channel.",
                parse_mode='Markdown'
            )
            
            # Option: forward from channel if you have message ID
            # This would require mapping episode numbers to message IDs
        
        # Mark as watched if auto-play is on
        if auto_play:
            db.update_user_progress(query.from_user.id, episode[1], episode[2])
            await query.message.reply_text(f"✅ Auto-marked Episode {episode[2]} as watched!")
            
    except Exception as e:
        await query.message.reply_text(f"Error playing video: {str(e)}\n\nTry another source.")
        
        # Show other sources
        await show_video_sources(query, episode_id, context)

async def play_from_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play video from a specific source"""
    query = update.callback_query
    await query.answer()
    
    source_id = int(query.data.split('_')[2])
    
    # Get source details from database
    db.cursor.execute('''
        SELECT * FROM video_sources WHERE id = ?
    ''', (source_id,))
    source = db.cursor.fetchone()
    
    if not source:
        await query.message.reply_text("Source not found!")
        return
    
    source_id, episode_id, source_type, source_url, quality, language = source
    episode = db.get_episode_details(episode_id)
    
    caption = (
        f"📺 *Episode {episode[2]}: {episode[3]}*\n"
        f"🎬 Quality: {quality} | 🌐 {language}"
    )
    
    try:
        if source_type == 'direct':
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=source_url,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        else:
            await query.message.reply_text(
                f"📺 *Watch Here*\n\n{source_url}",
                parse_mode='Markdown'
            )
    except Exception as e:
        await query.message.reply_text(f"Error: {str(e)}")

async def show_video_sources(query, episode_id, context):
    """Show all available video sources for an episode"""
    sources = db.get_episode_video_sources(episode_id)
    episode = db.get_episode_details(episode_id)
    
    if not sources:
        await query.edit_message_text(
            f"No video sources found for Episode {episode[2]}!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data=f'episode_{episode_id}')
            ]])
        )
        return
    
    text = f"📺 *Episode {episode[2]} - Video Sources*\n\n"
    
    keyboard = []
    for source in sources:
        source_id, _, source_type, _, quality, language = source
        source_emoji = {
            'direct': '📁',
            'streaming': '🌐',
            'telegram': '📱',
            'torrent': '🧲'
        }.get(source_type, '📺')
        
        text += f"{source_emoji} {source_type.upper()} - {quality} - {language}\n"
        
        button_text = f"{source_emoji} {quality} - {language}"
        keyboard.append([InlineKeyboardButton(
            button_text, 
            callback_data=f'play_source_{source_id}'
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f'episode_{episode_id}')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def mark_episode_watched(query, episode_id, user_id):
    """Mark an episode as watched and update progress"""
    episode = db.get_episode_details(episode_id)
    
    if episode:
        anime_id = episode[1]
        episode_num = episode[2]
        
        # Update user progress
        db.update_user_progress(user_id, anime_id, episode_num)
        
        await query.answer(f"✅ Marked Episode {episode_num} as watched!")
        
        # Show updated episode list
        await show_episode_list(query, anime_id, 1)

async def show_movies(query):
    """Show all movies"""
    db.cursor.execute('SELECT * FROM movies ORDER BY rating DESC')
    movies = db.cursor.fetchall()
    
    if not movies:
        await query.edit_message_text(
            "No movies found! 😢",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')
            ]])
        )
        return
    
    keyboard = []
    for movie in movies:
        # movie: (id, title, description, rating, duration, genre, release_year, image_url, video_url, video_file_id)
        button_text = f"🎬 {movie[1]} ({movie[6]}) ⭐{movie[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'movie_detail_{movie[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🎬 *Movie List:*", reply_markup=reply_markup, parse_mode='Markdown')

async def show_movie_details(query, movie_id):
    """Show detailed information about a movie with play option"""
    db.cursor.execute('SELECT * FROM movies WHERE id = ?', (movie_id,))
    movie = db.cursor.fetchone()
    
    if not movie:
        await query.edit_message_text("Movie not found!")
        return
    
    # movie: (id, title, description, rating, duration, genre, release_year, image_url, video_url, video_file_id)
    has_video = movie[8] or movie[9]  # video_url or video_file_id
    
    text = (
        f"🎬 *{movie[1]}*\n\n"
        f"⭐ *Rating:* {movie[3]}/10\n"
        f"📅 *Year:* {movie[6]}\n"
        f"🎭 *Genre:* {movie[5]}\n"
        f"⏱️ *Duration:* {movie[4]} minutes\n\n"
        f"📝 *Description:*\n{movie[2]}"
    )
    
    keyboard = []
    
    if has_video:
        keyboard.append([InlineKeyboardButton("▶️ WATCH MOVIE", callback_data=f'play_movie_{movie_id}')])
    
    keyboard.extend([
        [InlineKeyboardButton("🔙 Back to Movies", callback_data='main_movie')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def play_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play a movie"""
    query = update.callback_query
    await query.answer()
    
    movie_id = int(query.data.split('_')[2])
    
    db.cursor.execute('SELECT * FROM movies WHERE id = ?', (movie_id,))
    movie = db.cursor.fetchone()
    
    if not movie:
        await query.message.reply_text("Movie not found!")
        return
    
    # movie: (id, title, description, rating, duration, genre, release_year, image_url, video_url, video_file_id)
    title, video_url, video_file_id = movie[1], movie[8], movie[9]
    
    caption = f"🎬 *{title}*\n⭐ {movie[3]}/10 | {movie[6]} | {movie[4]} min"
    
    try:
        if video_file_id:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video_file_id,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        elif video_url:
            await context.bot.send_video(
                chat_id=query.message.chat_id,
                video=video_url,
                caption=caption,
                parse_mode='Markdown',
                supports_streaming=True
            )
        else:
            await query.message.reply_text("Video not available for this movie!")
    except Exception as e:
        await query.message.reply_text(f"Error playing movie: {str(e)}")

async def show_tv_shows(query):
    """Show all TV shows"""
    db.cursor.execute('SELECT * FROM tv_shows ORDER BY rating DESC')
    shows = db.cursor.fetchall()
    
    if not shows:
        await query.edit_message_text(
            "No TV shows found! 😢",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')
            ]])
        )
        return
    
    keyboard = []
    for show in shows:
        # show: (id, title, description, rating, seasons, episodes_per_season, status, image_url)
        button_text = f"📱 {show[1]} ⭐{show[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'tv_detail_{show[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📱 *TV Shows List:*", reply_markup=reply_markup, parse_mode='Markdown')

async def show_tv_details(query, show_id):
    """Show detailed information about a TV show"""
    db.cursor.execute('SELECT * FROM tv_shows WHERE id = ?', (show_id,))
    show = db.cursor.fetchone()
    
    if not show:
        await query.edit_message_text("TV show not found!")
        return
    
    # show: (id, title, description, rating, seasons, episodes_per_season, status, image_url)
    total_episodes = show[4] * show[5]
    
    text = (
        f"📱 *{show[1]}*\n\n"
        f"⭐ *Rating:* {show[3]}/10\n"
        f"📊 *Seasons:* {show[4]}\n"
        f"📺 *Episodes per season:* {show[5]}\n"
        f"📈 *Total episodes:* {total_episodes}\n"
        f"📌 *Status:* {show[6]}\n\n"
        f"📝 *Description:*\n{show[2]}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to TV Shows", callback_data='main_tv')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def main():
    # Add sample data
    add_sample_data()
    
    # Setup Telegram channels
    setup_telegram_channels()
    
    # Generate One Piece episodes with video sources
    generate_one_piece_episodes_with_videos()
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    print("🎬 Anime/Movie/TV Bot is starting with video playback!")
    print(f"📺 One Piece: 1155 episodes with multiple video sources")
    print(f"📱 Telegram channels configured: {len(ONE_PIECE_CHANNELS)}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
