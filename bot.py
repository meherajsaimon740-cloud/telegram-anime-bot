from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ===============================
# ⚙️ CONFIGURATION
# ===============================
TOKEN = "8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac"
ADMIN_ID = 7378129112  # <--- 💡 REPLACE WITH YOUR TELEGRAM ID

# ===============================
# 🔥 DATABASE (EDIT ONLY THIS)
# ===============================
# For Videos: Use the File ID you get from the bot.
# For Manga: Use a standard URL link.
ANIME_DATA = {
    "One Piece": {
        "Anime": {
            "Episode 1": "921260484", # Example: BAACAgIAAxkBAAE...
            "Episode 2": "921260484",
        },
        "Manga": {
            "Chapter 1": "https://link-to-manga.com",
        },
        "Live Action": {
            "Episode 1": "921260484",
        }
    },
    "Naruto": {
        "Anime": {
            "Episode 1": "921260484",
        }
    }
}

# ===============================
# 🛠️ ADMIN TOOL: GET FILE ID
# ===============================
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a video to the bot and it will reply with the File ID (Admin only)"""
    if update.effective_user.id != ADMIN_ID:
        return 

    file_id = None
    if update.message.video:
        file_id = update.message.video.file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if file_id:
        await update.message.reply_text(
            f"✅ **File ID Found!**\n\n`{file_id}`\n\nCopy this into your ANIME_DATA.",
            parse_mode="Markdown"
        )

# ===============================
# 🏠 MAIN MENU
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎌 Open Anime List", callback_data="anime_menu")]]
    await update.message.reply_text(
        "🔥 **Main Menu**\nSelect an option to begin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ===============================
# 🕹️ BUTTON HANDLER
# ===============================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    data = query.data

    # --- LIST ALL ANIME ---
    if data == "anime_menu":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"anime_{name}")] for name in ANIME_DATA.keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="back_main")])
        await message.edit_text("🎌 **Select Anime:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- BACK TO START ---
    elif data == "back_main":
        keyboard = [[InlineKeyboardButton("🎌 Open Anime List", callback_data="anime_menu")]]
        await message.edit_text("🔥 **Main Menu**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- SELECT CATEGORY (Anime/Manga/Live Action) ---
    elif data.startswith("anime_"):
        anime_name = data.replace("anime_", "")
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{anime_name}_{cat}")] for cat in ANIME_DATA[anime_name].keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="anime_menu")])
        await message.edit_text(f"📂 **{anime_name}**\nChoose a category:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown" )

    # --- SELECT EPISODE ---
    elif data.startswith("cat_"):
        _, anime_name, category = data.split("_", 2)
        keyboard = [[InlineKeyboardButton(ep, callback_data=f"ep_{anime_name}_{category}_{ep}")] for ep in ANIME_DATA[anime_name][category].keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data=f"anime_{anime_name}")])
        await message.edit_text(f"🎬 **{anime_name} - {category}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- DELIVER CONTENT (VIDEO OR LINK) ---
    elif data.startswith("ep_"):
        _, anime_name, category, episode = data.split("_", 3)
        content = ANIME_DATA[anime_name][category][episode]

        # Buttons under the video/message
        video_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⬅ Back", callback_data=f"cat_{anime_name}_{category}"),
                InlineKeyboardButton("❌ Delete", callback_data="delete_msg")
            ]
        ])

        # If content looks like a File ID, send video. Otherwise, send text link.
        if len(content) > 30 and not content.startswith("http"):
            try:
                await context.bot.send_video(
                    chat_id=message.chat_id,
                    video=content,
                    caption=f"🎬 **{anime_name}**\n📺 {episode}\n📂 {category}",
                    parse_mode="Markdown",
                    reply_markup=video_kb
                )
            except Exception:
                await message.reply_text(f"❌ Error: Invalid File ID for {episode}. Check your database!")
        else:
            await message.reply_text(
                f"🎬 **{anime_name}**\n📺 {episode}\n\n🔗 [Click to Watch/Read]({content})",
                parse_mode="Markdown",
                reply_markup=video_kb
            )

    # --- DELETE MESSAGE ---
    elif data == "delete_msg":
        await message.delete()

# ===============================
# 🚀 RUN THE BOT
# ===============================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.VIDEO | filters.DOCUMENT, get_file_id))

    print("✅ Bot is running... Send a video to get its File ID!")
    app.run_polling()
