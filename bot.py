from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = "8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac"

# ===============================
# 🔥 DATABASE (EDIT ONLY THIS)
# ===============================

ANIME_DATA = {
    "One Piece": {
        "Manga": {
            "Episode 1": "Link OP Manga 1",
            "Episode 2": "Link OP Manga 2",
        },
        "Anime": {
            "Episode 1": "Link OP Anime 1",
            "Episode 2": "Link OP Anime 2",
        },
        "Live Action": {
            "Episode 1": "Link OP Live 1",
            "Episode 2": "Link OP Live 2",
        }
    },
    "Naruto": {
        "Manga": {
            "Episode 1": "Link Naruto Manga 1",
        },
        "Anime": {
            "Episode 1": "Link Naruto Anime 1",
            "Episode 2": "Link Naruto Anime 2",
        },
        "Live Action": {
            "Episode 1": "Link Naruto Live 1",
        }
    }
}

# ===============================
# MAIN MENU
# ===============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Anime", callback_data="anime_menu")]
    ]
    await update.message.reply_text(
        "🔥 Main Menu",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===============================
# BUTTON HANDLER
# ===============================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    data = query.data

    # ===== ANIME LIST =====
    if data == "anime_menu":
        keyboard = []

        for anime_name in ANIME_DATA.keys():
            keyboard.append(
                [InlineKeyboardButton(anime_name, callback_data=f"anime_{anime_name}")]
            )

        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="back_main")])

        await message.edit_text(
            "🎌 Select Anime:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== BACK TO MAIN =====
    elif data == "back_main":
        keyboard = [[InlineKeyboardButton("Anime", callback_data="anime_menu")]]
        await message.edit_text(
            "🔥 Main Menu",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SELECT ANIME =====
    elif data.startswith("anime_"):
        anime_name = data.replace("anime_", "")

        keyboard = []
        for category in ANIME_DATA[anime_name].keys():
            keyboard.append(
                [InlineKeyboardButton(category, callback_data=f"cat_{anime_name}_{category}")]
            )

        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="anime_menu")])

        await message.edit_text(
            f"📂 {anime_name} Categories:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SELECT CATEGORY (Manga / Anime / Live Action) =====
    elif data.startswith("cat_"):
        parts = data.split("_", 2)
        anime_name = parts[1]
        category = parts[2]

        keyboard = []
        for episode in ANIME_DATA[anime_name][category].keys():
            keyboard.append(
                [InlineKeyboardButton(episode, callback_data=f"ep_{anime_name}_{category}_{episode}")]
            )

        keyboard.append(
            [InlineKeyboardButton("⬅ Back", callback_data=f"anime_{anime_name}")]
        )

        await message.edit_text(
            f"🎬 {anime_name} - {category}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== SELECT EPISODE =====
    elif data.startswith("ep_"):
        parts = data.split("_", 3)
        anime_name = parts[1]
        category = parts[2]
        episode = parts[3]

        link = ANIME_DATA[anime_name][category][episode]

        await message.reply_text(
            f"🎬 {anime_name}\n📂 {category}\n📺 {episode}\n\n🔗 {link}"
        )

# ===============================
# RUN BOT
# ===============================

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.run_polling()



