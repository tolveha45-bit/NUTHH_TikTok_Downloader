import os
import secrets
import string

from datetime import (
    datetime,
    timedelta,
    timezone
)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)

from telegram.constants import ChatAction

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    DATABASE_PATH,
    DOWNLOAD_DIR,
    MAX_FILE_SIZE_MB
)

from database import Database

from downloader import (
    download,
    valid_tiktok_url
)


db = Database(
    DATABASE_PATH
)

os.makedirs(
    DOWNLOAD_DIR,
    exist_ok=True
)


MAIN_MENU = ReplyKeyboardMarkup(

    [
        [
            "🎬 Download Video",
            "🎵 Download MP3"
        ],
        [
            "🔑 Activate Key",
            "📊 My Account"
        ],
        [
            "ℹ️ Help",
            "🏠 Main Menu"
        ]
    ],

    resize_keyboard=True
)


def admin_menu():

    return InlineKeyboardMarkup(

        [
            [
                InlineKeyboardButton(
                    "🔑 Create Key",
                    callback_data="admin_create"
                )
            ],

            [
                InlineKeyboardButton(
                    "📊 Statistics",
                    callback_data="admin_stats"
                )
            ]
        ]
    )


def is_admin(user_id):

    return user_id in ADMIN_IDS


def generate_key():

    chars = (
        string.ascii_uppercase
        + string.digits
    )

    parts = [

        "".join(
            secrets.choice(chars)
            for _ in range(4)
        )

        for _ in range(4)
    ]

    return "NUTHH-" + "-".join(parts)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    db.add_user(
        user.id,
        user.username
    )

    await update.message.reply_text(

        "🎬 *NUTHH DOWNLOADER*\n\n"

        "🔗 Send a TikTok link.\n"
        "🎬 Download Video\n"
        "🎵 Download MP3\n\n"

        "🔐 Access Key is required.",

        parse_mode="Markdown",

        reply_markup=MAIN_MENU
    )


async def help_command(
    update,
    context
):

    await update.message.reply_text(

        "ℹ️ *NUTHH DOWNLOADER HELP*\n\n"

        "1️⃣ Activate your Access Key.\n"
        "2️⃣ Select Video or MP3.\n"
        "3️⃣ Send TikTok URL.\n"
        "4️⃣ Wait for processing.\n\n"

        "⚡ Automatic cleanup\n"
        "🔐 Key protection\n"
        "📊 Download limits",

        parse_mode="Markdown",

        reply_markup=MAIN_MENU
    )


async def process_download(

    update,
    context,
    url,
    audio
):

    user_id = (
        update.effective_user.id
    )

    processing = await update.message.reply_text(
        "⏳ Processing...\n\n"
        "Please wait."
    )

    try:

        await update.message.chat.send_action(

            ChatAction.UPLOAD_AUDIO
            if audio
            else ChatAction.UPLOAD_VIDEO
        )

        path, title = await download(

            url,
            DOWNLOAD_DIR,
            audio
        )

        if not os.path.exists(path):

            raise RuntimeError(
                "Downloaded file not found."
            )

        size_mb = (
            os.path.getsize(path)
            / (1024 * 1024)
        )

        if size_mb > MAX_FILE_SIZE_MB:

            raise RuntimeError(
                f"File size {size_mb:.1f} MB "
                f"is above configured limit."
            )

        with open(path, "rb") as file:

            if audio:

                await update.message.reply_audio(

                    audio=file,

                    caption=f"🎵 {title}"
                )

            else:

                await update.message.reply_video(

                    video=file,

                    caption=f"🎬 {title}",

                    supports_streaming=True
                )

        db.log_download(
            user_id,
            url,
            "mp3" if audio else "video",
            "success"
        )

        await processing.edit_text(
            "✅ Download completed!"
        )

        os.remove(path)

    except Exception as error:

        db.log_download(

            user_id,
            url,

            "mp3"
            if audio
            else "video",

            "failed"
        )

        await processing.edit_text(

            "❌ Download failed.\n\n"
            f"{str(error)[:700]}"
        )


async def message_handler(

    update,
    context
):

    text = update.message.text.strip()

    user_id = (
        update.effective_user.id
    )

    if text == "🏠 Main Menu":

        return await start(
            update,
            context
        )

    if text == "ℹ️ Help":

        return await help_command(
            update,
            context
        )

    if text == "🔑 Activate Key":

        context.user_data[
            "state"
        ] = "key"

        return await update.message.reply_text(

            "🔑 *ACTIVATE KEY*\n\n"
            "Please send your Access Key:",

            parse_mode="Markdown",

            reply_markup=MAIN_MENU
        )

    if text == "🎬 Download Video":

        context.user_data[
            "state"
        ] = "video"

        return await update.message.reply_text(

            "🎬 *VIDEO DOWNLOADER*\n\n"
            "Send your TikTok URL:",

            parse_mode="Markdown",

            reply_markup=MAIN_MENU
        )

    if text == "🎵 Download MP3":

        context.user_data[
            "state"
        ] = "mp3"

        return await update.message.reply_text(

            "🎵 *MP3 DOWNLOADER*\n\n"
            "Send your TikTok URL:",

            parse_mode="Markdown",

            reply_markup=MAIN_MENU
        )

    if text == "📊 My Account":

        status = db.key_status(
            user_id
        )

        if not status:

            return await update.message.reply_text(

                "🔐 You don't have an active key.",

                reply_markup=MAIN_MENU
            )

        (
            key,
            expires,
            max_downloads,
            used,
            active
        ) = status

        if max_downloads == 0:

            remaining = "Unlimited"

        else:

            remaining = max(
                0,
                max_downloads - used
            )

        await update.message.reply_text(

            "👤 *MY ACCOUNT*\n\n"

            f"🔑 Key: `{key}`\n"
            f"📅 Expires: "
            f"{expires or 'Lifetime'}\n"
            f"📥 Remaining: {remaining}\n"
            f"🟢 Status: "
            f"{'Active' if active else 'Disabled'}",

            parse_mode="Markdown",

            reply_markup=MAIN_MENU
        )

        return

    state = context.user_data.get(
        "state"
    )

    if state == "key":

        success, message = db.activate_key(
            user_id,
            text
        )

        context.user_data[
            "state"
        ] = None

        return await update.message.reply_text(

            message,

            reply_markup=MAIN_MENU
        )

    if state in (
        "video",
        "mp3"
    ):

        if not valid_tiktok_url(text):

            return await update.message.reply_text(

                "❌ Invalid TikTok URL.\n\n"
                "Please send a valid TikTok link."
            )

        allowed, message = db.consume_download(
            user_id
        )

        if not allowed:

            return await update.message.reply_text(
                message,
                reply_markup=MAIN_MENU
            )

        context.user_data[
            "state"
        ] = None

        return await process_download(

            update,
            context,

            text,

            state == "mp3"
        )

    await update.message.reply_text(

        "👇 Please use the buttons below.",

        reply_markup=MAIN_MENU
    )


async def admin_command(

    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):

        return await update.message.reply_text(
            "⛔ Admin only."
        )

    await update.message.reply_text(

        "👑 *NUTHH ADMIN PANEL*",

        parse_mode="Markdown",

        reply_markup=admin_menu()
    )


async def admin_callback(

    update,
    context
):

    query = update.callback_query

    await query.answer()

    if not is_admin(
        query.from_user.id
    ):

        return await query.edit_message_text(
            "⛔ Admin only."
        )

    if query.data == "admin_create":

        context.user_data[
            "state"
        ] = "admin_create"

        return await query.edit_message_text(

            "🔑 *CREATE ACCESS KEY*\n\n"

            "Send:\n"
            "`days downloads max_users`\n\n"

            "Example:\n"
            "`30 100 1`\n\n"

            "0 days = Lifetime\n"
            "0 downloads = Unlimited",

            parse_mode="Markdown"
        )

    if query.data == "admin_stats":

        users, downloads, keys = db.stats()

        return await query.edit_message_text(

            "📊 *BOT STATISTICS*\n\n"

            f"👥 Users: {users}\n"
            f"📥 Downloads: {downloads}\n"
            f"🔑 Keys: {keys}",

            parse_mode="Markdown"
        )


async def admin_key_input(

    update,
    context
):

    if not is_admin(
        update.effective_user.id
    ):

        return

    if context.user_data.get(
        "state"
    ) != "admin_create":

        return

    try:

        days, downloads, max_users = map(

            int,

            update.message.text.split()
        )

        if days < 0:
            raise ValueError

        if downloads < 0:
            raise ValueError

        if max_users < 1:
            raise ValueError

        key = generate_key()

        if days == 0:

            expires = None

        else:

            expires = (

                datetime.now(
                    timezone.utc
                )
                + timedelta(days=days)
            ).isoformat()

        db.create_key(

            key,
            expires,
            downloads,
            max_users
        )

        context.user_data[
            "state"
        ] = None

        await update.message.reply_text(

            "✅ *KEY CREATED*\n\n"

            f"🔑 `{key}`\n"
            f"📅 Expiration: "
            f"{'Lifetime' if not expires else expires}\n"
            f"📥 Downloads: "
            f"{'Unlimited' if downloads == 0 else downloads}\n"
            f"👥 Max Users: {max_users}",

            parse_mode="Markdown",

            reply_markup=MAIN_MENU
        )

    except Exception:

        await update.message.reply_text(

            "❌ Invalid format.\n\n"

            "Example:\n"
            "`30 100 1`",

            parse_mode="Markdown"
        )


def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing."
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_callback
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.User(ADMIN_IDS),
            admin_key_input
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler
        )
    )

    print(
        "🚀 NUTHH Downloader Bot started!"
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":

    main()
