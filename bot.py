import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import math

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
        
        # Anime Episodes table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS anime_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                anime_id INTEGER,
                episode_number INTEGER,
                title TEXT,
                description TEXT,
                air_date TEXT,
                filler BOOLEAN DEFAULT 0,
                FOREIGN KEY (anime_id) REFERENCES anime (id)
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
                image_url TEXT
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
        self.cursor.execute('SELECT * FROM anime_episodes WHERE id = ?', (episode_id,))
        return self.cursor.fetchone()
    
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

# Initialize database
db = MediaDatabase()

# Bot configuration
BOT_TOKEN = '8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac'  # Replace with your bot token

# Function to generate One Piece episodes (1-1155)
def generate_one_piece_episodes():
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
        # Generate episodes 1-1155
        episodes = []
        
        # Arc definitions for better episode descriptions
        arcs = [
            (1, 61, "East Blue Saga", "Luffy begins his journey and gathers his first crew members"),
            (62, 77, "Arabasta Saga", "The crew enters the Grand Line and faces Baroque Works"),
            (78, 153, "Sky Island Saga", "Adventure in the clouds with Cricket and the Skypeians"),
            (154, 195, "Water 7 Saga", "The crew faces the CP9 and fights to save Robin"),
            (196, 228, "Thriller Bark Saga", "Battle against Gecko Moria in a haunted ship"),
            (229, 325, "Summit War Saga", "The crew separates as Luffy fights to save Ace"),
            (326, 384, "Fish-Man Island Saga", "Underwater adventure and prophecy of the Poseidon"),
            (385, 516, "Dressrosa Saga", "Luffy fights Doflamingo to save a kingdom"),
            (517, 574, "Whole Cake Island Saga", "Sanji's wedding and battle against Big Mom"),
            (575, 1155, "Wano Country Saga", "The final battle against Kaido in samurai country")
        ]
        
        for arc_start, arc_end, arc_name, arc_desc in arcs:
            for ep_num in range(arc_start, arc_end + 1):
                if ep_num <= 1155:
                    if ep_num == 1:
                        title = "I'm Luffy! The Man Who Will Become the Pirate King!"
                        desc = "Luffy begins his journey by saving Coby and meets Roronoa Zoro."
                    elif ep_num == 1155:
                        title = "The Beginning of the New Era! Luffy's Final Battle!"
                        desc = "The epic conclusion of the Wano arc begins as Luffy faces Kaido."
                    else:
                        # Generate episode title based on arc
                        if ep_num <= 61:
                            title = f"Episode {ep_num}: East Blue - {['Romance Dawn', 'Orange Town', 'Syrup Village', 'Baratie', 'Arlong Park'][(ep_num-1)//12 % 5]} Arc Part {((ep_num-1)%12)+1}"
                            desc = f"Luffy continues his journey through the East Blue. Part of the {arc_name}."
                        elif ep_num <= 77:
                            title = f"Episode {ep_num}: Loguetown - The Town of Beginning and End"
                            desc = f"The crew arrives at Loguetown, where Gol D. Roger was born and executed."
                        elif ep_num <= 153:
                            title = f"Episode {ep_num}: Skypeia - Adventure in the White Sea"
                            desc = f"The crew explores the sky island and faces Enel. Part of the {arc_name}."
                        elif ep_num <= 195:
                            title = f"Episode {ep_num}: Water 7 - The Sea Train and CP9"
                            desc = f"Robin's past is revealed as the crew fights CP9. Part of the {arc_name}."
                        elif ep_num <= 228:
                            title = f"Episode {ep_num}: Thriller Bark - Gecko Moria's Kingdom"
                            desc = f"The crew faces the Shichibukai Gecko Moria. Part of the {arc_name}."
                        elif ep_num <= 325:
                            title = f"Episode {ep_num}: Summit War - The Battle of Marineford"
                            desc = f"The war between Whitebeard and the Marines intensifies."
                        elif ep_num <= 384:
                            title = f"Episode {ep_num}: Fish-Man Island - The Promise with Shirahoshi"
                            desc = f"The crew dives to Fish-Man Island and meets the mermaid princess."
                        elif ep_num <= 516:
                            title = f"Episode {ep_num}: Dressrosa - The Colosseum and Doflamingo"
                            desc = f"Luffy enters the Colosseum to win the Mera Mera no Mi."
                        elif ep_num <= 574:
                            title = f"Episode {ep_num}: Whole Cake Island - Sanji's Wedding"
                            desc = f"The crew infiltrates Big Mom's territory to rescue Sanji."
                        else:
                            title = f"Episode {ep_num}: Wano - The Land of Samurai"
                            desc = f"The final battle against Kaido continues in the land of Wano."
                    
                    episodes.append((one_piece_id, ep_num, title, desc, 
                                   f"202{ep_num//100+1}-{(ep_num%12)+1:02d}-01", 
                                   1 if ep_num % 10 == 0 else 0))  # Mark some episodes as filler
        
        # Insert episodes in batches
        db.cursor.executemany('''
            INSERT INTO anime_episodes (anime_id, episode_number, title, description, air_date, filler)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', episodes)
        db.conn.commit()
        print(f"Generated {len(episodes)} One Piece episodes!")

def add_sample_data():
    # Add other anime
    other_anime = [
        ('Naruto', 'EP', 'The story of Naruto Uzumaki, a ninja with dreams of becoming Hokage', 9.5, 720, 'Completed'),
        ('Attack on Titan', 'EP', 'Humanity fights for survival against giant humanoid Titans', 9.7, 139, 'Completed'),
        ('Demon Slayer', 'EP', 'Tanjiro fights demons to save his sister', 9.6, 55, 'Ongoing'),
        ('Jujutsu Kaisen', 'EP', 'A boy fights curses to protect the world', 9.4, 47, 'Ongoing'),
        ('Chainsaw Man', 'EP', 'Denji merges with his pet devil to become Chainsaw Man', 9.3, 12, 'Ongoing'),
        
        # Manga
        ('Berserk', 'Manga', 'A dark fantasy tale of revenge and survival', 9.7, 364, 'Ongoing'),
        ('Vagabond', 'Manga', 'The life of legendary swordsman Miyamoto Musashi', 9.6, 327, 'Hiatus'),
        
        # OVA
        ('Naruto: The Last', 'OVA', 'Naruto and Hinata\'s romantic adventure', 9.1, 1, 'Completed'),
        ('Attack on Titan: No Regrets', 'OVA', 'The backstory of Captain Levi', 9.4, 2, 'Completed')
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
        parts = query.data.split('_')
        episode_id = int(parts[1])
        await show_episode_details(query, episode_id)
    
    elif query.data.startswith('mark_watched_'):
        parts = query.data.split('_')
        episode_id = int(parts[2])
        await mark_episode_watched(query, episode_id, user_id)
    
    # Movie and TV show details
    elif query.data.startswith('movie_detail_'):
        movie_id = int(query.data.split('_')[2])
        await show_movie_details(query, movie_id)
    
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

async def show_main_menu(query):
    keyboard = [
        [InlineKeyboardButton("📺 ANIME", callback_data='main_anime')],
        [InlineKeyboardButton("🎬 MOVIE", callback_data='main_movie')],
        [InlineKeyboardButton("📱 TV", callback_data='main_tv')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Main Menu - Choose a category:", reply_markup=reply_markup)

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
        "📺 *EP* - TV series episodes\n"
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
        button_text = f"{anime[1]} ⭐{anime[4]}{episodes_text}"
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
    
    text = (
        f"{emoji_map.get(anime[2], '📺')} *{anime[1]}*\n\n"
        f"📌 *Type:* {anime[2]}\n"
        f"⭐ *Rating:* {anime[4]}/10\n"
        f"📊 *Total Episodes/Chapters:* {anime[5] if anime[5] else 'N/A'}\n"
        f"📈 *Status:* {anime[7]}\n\n"
        f"📝 *Description:*\n{anime[3]}"
    )
    
    keyboard = []
    
    # Add "View Episodes" button only for EP type
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
    episodes_per_page = 20
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
        button_text = f"{watched_icon}{filler_icon}Episode {ep_num}: {episode[3][:30]}..."
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'episode_{episode[0]}')])
    
    # Add pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f'ep_page_{anime_id}_{page-1}'))
    
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f'ep_page_{anime_id}_{page+1}'))
    
    keyboard.append(nav_buttons)
    
    # Add back button
    keyboard.append([InlineKeyboardButton("🔙 Back to Anime", callback_data=f'anime_detail_{anime_id}')])
    
    progress_text = f"📺 *{anime[1]} Episodes*\n"
    progress_text += f"📊 Progress: Episode {last_watched}/{total_episodes}\n"
    progress_text += f"📌 Page {page}/{total_pages}\n\n"
    progress_text += "✅ = Watched | ⚠️ = Filler Episode"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(progress_text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_episode_details(query, episode_id):
    """Show detailed information about an episode"""
    episode = db.get_episode_details(episode_id)
    
    if not episode:
        await query.edit_message_text("Episode not found!")
        return
    
    # episode: (id, anime_id, episode_number, title, description, air_date, filler)
    filler_text = "⚠️ FILLER EPISODE" if episode[6] else "📺 Canon Episode"
    
    text = (
        f"📺 *Episode {episode[2]}: {episode[3]}*\n\n"
        f"📌 {filler_text}\n"
        f"📅 *Air Date:* {episode[5]}\n\n"
        f"📝 *Description:*\n{episode[4]}"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Mark as Watched", callback_data=f'mark_watched_ep_{episode[0]}')],
        [InlineKeyboardButton("🔙 Back to Episodes", callback_data='back_to_episodes')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ]
    
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
    movies = db.get_all_movies()
    
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
        # movie: (id, title, description, rating, duration, genre, release_year, image_url)
        button_text = f"{movie[1]} ({movie[6]}) ⭐{movie[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'movie_detail_{movie[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🎬 *Movie List:*", reply_markup=reply_markup, parse_mode='Markdown')

async def show_movie_details(query, movie_id):
    """Show detailed information about a movie"""
    movie = db.get_movie_details(movie_id)
    
    if not movie:
        await query.edit_message_text("Movie not found!")
        return
    
    # movie: (id, title, description, rating, duration, genre, release_year, image_url)
    text = (
        f"🎬 *{movie[1]}*\n\n"
        f"⭐ *Rating:* {movie[3]}/10\n"
        f"📅 *Year:* {movie[6]}\n"
        f"🎭 *Genre:* {movie[5]}\n"
        f"⏱️ *Duration:* {movie[4]} minutes\n\n"
        f"📝 *Description:*\n{movie[2]}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Movies", callback_data='main_movie')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_tv_shows(query):
    """Show all TV shows"""
    shows = db.get_all_tv_shows()
    
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
        button_text = f"{show[1]} ⭐{show[3]}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'tv_detail_{show[0]}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main", callback_data='back_to_main')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📱 *TV Shows List:*", reply_markup=reply_markup, parse_mode='Markdown')

async def show_tv_details(query, show_id):
    """Show detailed information about a TV show"""
    show = db.get_tv_show_details(show_id)
    
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
    
    # Generate One Piece episodes (1-1155)
    generate_one_piece_episodes()
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    print("Anime/Movie/TV Bot is starting with 1155 One Piece episodes...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
