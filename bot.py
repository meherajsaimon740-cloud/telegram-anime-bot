import sqlite3
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

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
                episodes INTEGER,
                image_url TEXT,
                status TEXT DEFAULT 'Ongoing'
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
        
        # User interactions table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                media_type TEXT,
                media_id INTEGER,
                action TEXT,
                timestamp TIMESTAMP,
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
    
    def update_last_active(self, user_id):
        self.cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                          (datetime.now(), user_id))
        self.conn.commit()
    
    def log_interaction(self, user_id, media_type, media_id, action):
        self.cursor.execute('''
            INSERT INTO user_interactions (user_id, media_type, media_id, action, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, media_type, media_id, action, datetime.now()))
        self.conn.commit()
    
    # ANIME METHODS
    def get_anime_by_type(self, anime_type):
        self.cursor.execute('''
            SELECT * FROM anime WHERE type = ? ORDER BY rating DESC
        ''', (anime_type,))
        return self.cursor.fetchall()
    
    def get_anime_details(self, anime_id):
        self.cursor.execute('SELECT * FROM anime WHERE id = ?', (anime_id,))
        return self.cursor.fetchone()
    
    # MOVIE METHODS
    def get_all_movies(self):
        self.cursor.execute('SELECT * FROM movies ORDER BY rating DESC')
        return self.cursor.fetchall()
    
    def get_movie_details(self, movie_id):
        self.cursor.execute('SELECT * FROM movies WHERE id = ?', (movie_id,))
        return self.cursor.fetchone()
    
    # TV SHOW METHODS
    def get_all_tv_shows(self):
        self.cursor.execute('SELECT * FROM tv_shows ORDER BY rating DESC')
        return self.cursor.fetchall()
    
    def get_tv_show_details(self, show_id):
        self.cursor.execute('SELECT * FROM tv_shows WHERE id = ?', (show_id,))
        return self.cursor.fetchone()

# Initialize database
db = MediaDatabase()

# Bot configuration
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Replace with your bot token

# Sample data to populate the database
def add_sample_data():
    # Sample Anime
    anime_samples = [
        # Manga
        ('One Piece', 'Manga', 'Follow Monkey D. Luffy in his quest to become the Pirate King', 9.8, 1080, 'Ongoing'),
        ('Naruto', 'Manga', 'The story of Naruto Uzumaki, a ninja with dreams of becoming Hokage', 9.5, 700, 'Completed'),
        ('Attack on Titan', 'Manga', 'Humanity fights for survival against giant humanoid Titans', 9.7, 139, 'Completed'),
        
        # EP (Episodes/Anime Series)
        ('Demon Slayer', 'EP', 'Tanjiro fights demons to save his sister', 9.6, 55, 'Ongoing'),
        ('Jujutsu Kaisen', 'EP', 'A boy fights curses to protect the world', 9.4, 47, 'Ongoing'),
        ('Chainsaw Man', 'EP', 'Denji merges with his pet devil to become Chainsaw Man', 9.3, 12, 'Ongoing'),
        
        # OVA
        ('One Piece: Strong World', 'OVA', 'Luffy fights against the legendary pirate Shiki', 9.2, 1, 'Completed'),
        ('Naruto: The Last', 'OVA', 'Naruto and Hinata\'s romantic adventure', 9.1, 1, 'Completed'),
        ('Attack on Titan: No Regrets', 'OVA', 'The backstory of Captain Levi', 9.4, 2, 'Completed')
    ]
    
    # Sample Movies
    movie_samples = [
        ('Inception', 'A thief who steals corporate secrets through dream-sharing technology', 9.0, 148, 'Sci-Fi', 2010),
        ('The Dark Knight', 'Batman fights against the Joker in Gotham City', 9.3, 152, 'Action', 2008),
        ('Spirited Away', 'A young girl enters a mysterious world of spirits', 9.5, 125, 'Animation', 2001),
        ('Your Name', 'Two teenagers discover a mysterious connection', 9.4, 106, 'Animation', 2016)
    ]
    
    # Sample TV Shows
    tv_samples = [
        ('Breaking Bad', 'A chemistry teacher turns to cooking meth', 9.8, 5, 13, 'Completed'),
        ('Game of Thrones', 'Noble families fight for control of the Iron Throne', 9.5, 8, 10, 'Completed'),
        ('Stranger Things', 'Kids encounter supernatural forces in 1980s Indiana', 9.2, 4, 9, 'Ongoing'),
        ('The Witcher', 'A monster hunter navigates a chaotic world', 8.9, 3, 8, 'Ongoing')
    ]
    
    # Insert anime samples
    for anime in anime_samples:
        try:
            db.cursor.execute('''
                INSERT OR IGNORE INTO anime (title, type, description, rating, episodes, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', anime)
        except:
            pass
    
    # Insert movie samples
    for movie in movie_samples:
        try:
            db.cursor.execute('''
                INSERT OR IGNORE INTO movies (title, description, rating, duration, genre, release_year)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', movie)
        except:
            pass
    
    # Insert TV show samples
    for tv in tv_samples:
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
    
    # Details views
    elif query.data.startswith('anime_detail_'):
        anime_id = int(query.data.split('_')[2])
        await show_anime_details(query, anime_id)
    
    elif query.data.startswith('movie_detail_'):
        movie_id = int(query.data.split('_')[2])
        await show_movie_details(query, movie_id)
    
    elif query.data.startswith('tv_detail_'):
        show_id = int(query.data.split('_')[2])
        await show_tv_details(query, show_id)
    
    # Back navigation
    elif query.data == 'back_to_anime_menu':
        await show_anime_menu(query)
    
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
        # anime: (id, title, type, description, rating, episodes, image_url, status)
        button_text = f"{anime[1]} ⭐{anime[4]}"
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
    
    # anime: (id, title, type, description, rating, episodes, image_url, status)
    emoji_map = {'Manga': '📚', 'EP': '📺', 'OVA': '💿'}
    
    text = (
        f"{emoji_map.get(anime[2], '📺')} *{anime[1]}*\n\n"
        f"📌 *Type:* {anime[2]}\n"
        f"⭐ *Rating:* {anime[4]}/10\n"
        f"📊 *Episodes/Chapters:* {anime[5]}\n"
        f"📈 *Status:* {anime[7]}\n\n"
        f"📝 *Description:*\n{anime[3]}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data=f'anime_{anime[2].lower()}')],
        [InlineKeyboardButton("🏠 Main Menu", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Log interaction
    db.log_interaction(query.from_user.id, 'anime', anime_id, 'view_details')

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
    
    # Log interaction
    db.log_interaction(query.from_user.id, 'movie', movie_id, 'view_details')

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
    
    # Log interaction
    db.log_interaction(query.from_user.id, 'tv', show_id, 'view_details')

def main():
    # Add sample data to database
    add_sample_data()
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    print("Anime/Movie/TV Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()










