from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# 1. YOUR BOT TOKEN
TOKEN = "8074691861:AAFti_NIEmQj3HRwgT8UHSBio4_9qwkDFac"

# 2. YOUR TELEGRAM USER ID (To use the "Get ID" tool)
ADMIN_ID = 7378129112  # <--- REPLACE THIS WITH YOUR ID

# ===============================
# 🔥 DATABASE (USE FILE IDs HERE)
# ===============================
ANIME_DATA = {
    "One Piece": {
        "Anime": {
            # Send a video to your bot to get these long ID strings!
            "Episode 1": "921260484", 
            "Episode 2": "BAACAgIAAxkBAA...",
        },
        "Manga": {
            "Chapter 1": "https://link-to-manga.com",
        }
    },
    "Naruto": {
        "Anime": {
            "Episode 1": "BAACAgIAAxkBAA...",
        }
    }
}

# ===============================
# GET FILE ID TOOL (ADMIN ONLY)
# ===============================
async def get_file_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return # Ignore non-admins

    file_id = None
    if update.message.video:
        file_id = update.message.video.file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    if file_id:
        await update.message.reply_text(f"✅ **File ID Found:**\n\n`{file_id}`\n\nCopy this into your ANIME_DATA.")

# ===============================
# MAIN MENU
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎌 Open Anime List", callback_data="anime_menu")]]
    await update.message.reply_text(
        "🔥 **Welcome to the Anime Bot**\nSelect a category below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ===============================
# BUTTON & NAVIGATION HANDLER
# ===============================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    data = query.data

    # --- ANIME LIST ---
    if data == "anime_menu":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"anime_{name}")] for name in ANIME_DATA.keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="back_main")])
        await message.edit_text("🎌 **Select Anime:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- BACK TO MAIN ---
    elif data == "back_main":
        keyboard = [[InlineKeyboardButton("🎌 Open Anime List", callback_data="anime_menu")]]
        await message.edit_text("🔥 **Main Menu**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- SELECT ANIME ---
    elif data.startswith("anime_"):
        anime_name = data.replace("anime_", "")
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{anime_name}_{cat}")] for cat in ANIME_DATA[anime_name].keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data="anime_menu")])
        await message.edit_text(f"📂 **{anime_name}**\nChoose format:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- SELECT CATEGORY ---
    elif data.startswith("cat_"):
        _, anime_name, category = data.split("_", 2)
        keyboard = [[InlineKeyboardButton(ep, callback_data=f"ep_{anime_name}_{category}_{ep}")] for ep in ANIME_DATA[anime_name][category].keys()]
        keyboard.append([InlineKeyboardButton("⬅ Back", callback_data=f"anime_{anime_name}")])
        await message.edit_text(f"🎬 **{anime_name} - {category}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # --- SEND VIDEO (EPISODE) ---
    elif data.startswith("ep_"):
        _, anime_name, category, episode = data.split("_", 3)
        content = ANIME_DATA[anime_name][category][episode]

        video_kb = [
            [
                InlineKeyboardButton("⬅ Back", callback_data=f"cat_{anime_name}_{category}"),
                InlineKeyboardButton("❌ Delete", callback_data="delete_msg")
            ]
        ]

        # Check if the content is a File ID (Videos) or a URL (Manga)
        if content.startswith("BAA") or len(content) > 50: # Simple check for File ID
            await context.bot.send_video(
                chat_id=message.chat_id,
                video=content,
                caption=f"🎬 **{anime_name}**\n📺 {episode}\n📂 {category}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(video_kb)
            )
        else:
            await message.reply_text(f"🎬 {anime_name}\n📺 {episode}\n🔗 Link: {content}", reply_markup=InlineKeyboardMarkup(video_kb))

    # --- DELETE BUTTON ---
    elif data == "delete_msg":
        await message.delete()

# ===============================
# RUN BOT
# ===============================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.VIDEO | filters.DOCUMENT, get_file_id))

print("Bot is running...")
app.run_polling()



