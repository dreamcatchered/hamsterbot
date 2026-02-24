import asyncio
import logging
import html
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from config import BOT_TOKEN, DEVELOPER, WEB_DOMAIN
from database import db
from dataset_manager import dataset_manager

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Логирование при импорте
logger.info("=" * 50)
logger.info("BOT MODULE LOADING")
logger.info(f"Python version: {__import__('sys').version}")
logger.info(f"Working directory: {__import__('os').getcwd()}")
logger.info(f"Bot file location: {__file__}")
logger.info("=" * 50)

class BotStates:
    MAIN_MENU = "main_menu"
    RECORDING_SESSION = "recording_session"
    WAITING_VOICE = "waiting_voice"
    SEARCH_MODE = "search_mode"

def escape_html(text: str) -> str:
    return html.escape(str(text))

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎙️ начать озвучку", callback_data="start_recording")],
        [InlineKeyboardButton("📊 мои записи", callback_data="my_stats")],
        [InlineKeyboardButton("🔍 найти хомяка", callback_data="search_hamster")],
        [InlineKeyboardButton("ℹ️ помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_recording_keyboard(current_index: int, total: int, session_id: str, voiced_count: int = 0):
    keyboard = []
    
    nav_buttons = []
    if current_index > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"nav_prev_{session_id}"))
    nav_buttons.append(InlineKeyboardButton(f"{current_index + 1}/{total}", callback_data="nav_info"))
    if current_index < total - 1:
        nav_buttons.append(InlineKeyboardButton("➡️", callback_data=f"nav_next_{session_id}"))
    
    keyboard.append(nav_buttons)
    keyboard.append([
        InlineKeyboardButton("🔍 найти по описанию", callback_data=f"search_in_session_{session_id}")
    ])
    
    if voiced_count > 0:
        keyboard.append([
            InlineKeyboardButton(f"👀 посмотреть результат ({voiced_count} озвучено)", callback_data=f"preview_session_{session_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("⏸️ завершить и получить ссылку", callback_data=f"stop_session_{session_id}")
    ])
    keyboard.append([
        InlineKeyboardButton("🏠 главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_search_results_keyboard(results: list, session_id: str):
    keyboard = []
    for result in results[:5]:
        idx = result["index"]
        comment = result["data"]["comment"][:40]
        keyboard.append([
            InlineKeyboardButton(
                f"🐹 {comment}...",
                callback_data=f"jump_to_{session_id}_{idx}"
            )
        ])
    keyboard.append([InlineKeyboardButton("◀️ назад", callback_data=f"back_to_session_{session_id}")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"START command received from user {user.id} (@{user.username})")
    logger.debug(f"User data: {user}")
    
    username = escape_html(user.username or "")
    first_name = escape_html(user.first_name or "пользователь")
    
    db.save_user(user.id, username, first_name)
    logger.info(f"User {user.id} saved to database")
    
    welcome_text = (
        f"привет, <b>{first_name}</b>! 👋\n\n"
        f"я бот для озвучивания картинок с хомяками 🐹\n\n"
        f"<b>что я умею:</b>\n"
        f"• показываю тебе забавные картинки хомяков\n"
        f"• ты озвучиваешь их голосовыми сообщениями\n"
        f"• в конце создаю уникальную ссылку на сайт с твоими озвучками\n\n"
        f"можешь озвучить всех или только тех, кто тебе понравится 😊\n\n"
        f"<i>разработчик: {DEVELOPER}</i>"
    )
    
    if update.message:
        await update.message.reply_text(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
    elif update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=welcome_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = update.effective_user
    logger.info(f"Button pressed: {data} by user {user.id}")
    logger.debug(f"Callback query: {query}")
    
    if data == "main_menu":
        await start(update, context)
    
    elif data == "start_recording":
        user_sessions = db.get_user_sessions(user.id)
        active_session = next((s for s in user_sessions if not s["completed"]), None)
        
        if active_session:
            voiced_count = len(active_session["voiced_images"])
            keyboard = [
                [InlineKeyboardButton(f"✅ продолжить ({voiced_count} озвучено)", callback_data=f"continue_session_{active_session['session_id']}")],
                [InlineKeyboardButton("🆕 начать новую сессию", callback_data="force_new_session")],
                [InlineKeyboardButton("◀️ назад", callback_data="main_menu")]
            ]
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ у тебя есть незавершенная сессия\n\nозвучено: <b>{voiced_count}</b> хомяков\n\nхочешь продолжить или начать новую?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            session_id = db.create_session(user.id)
            context.user_data["session_id"] = session_id
            context.user_data["state"] = BotStates.RECORDING_SESSION
            
            await show_current_image(update, context, session_id, 0)
    
    elif data == "force_new_session":
        session_id = db.create_session(user.id)
        context.user_data["session_id"] = session_id
        context.user_data["state"] = BotStates.RECORDING_SESSION
        
        try:
            await query.message.delete()
        except:
            pass
        
        await show_current_image(update, context, session_id, 0)
    
    elif data == "my_stats":
        await show_user_stats(update, context)
    
    elif data == "search_hamster":
        context.user_data["state"] = BotStates.SEARCH_MODE
        try:
            await query.message.edit_text(
                "🔍 <b>поиск хомяка</b>\n\n"
                "опиши хомяка, которого хочешь найти\n"
                "например: <i>грустный</i>, <i>в очках</i>, <i>с цветком</i>\n\n"
                "или нажми кнопку ниже, чтобы вернуться",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ назад", callback_data="main_menu")
                ]])
            )
        except:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🔍 <b>поиск хомяка</b>\n\nопиши хомяка, которого хочешь найти\nнапример: <i>грустный</i>, <i>в очках</i>, <i>с цветком</i>\n\nили нажми кнопку ниже, чтобы вернуться",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ назад", callback_data="main_menu")
                ]])
            )
    
    elif data == "help":
        help_text = (
            "📖 <b>как пользоваться ботом</b>\n\n"
            "<b>🎙️ начать озвучку</b>\n"
            "начинаешь сессию озвучивания. бот показывает картинку, "
            "ты отправляешь голосовое сообщение. можно листать стрелками "
            "или искать конкретного хомяка по описанию\n\n"
            "<b>📊 мои записи</b>\n"
            "смотришь статистику: сколько озвучил, можешь продолжить "
            "незавершенную сессию\n\n"
            "<b>🔍 найти хомяка</b>\n"
            "ищешь хомяка по описанию эмоции или предмета\n\n"
            "<b>⏸️ остановить</b>\n"
            "завершаешь сессию и получаешь ссылку на сайт "
            "с твоими озвучками\n\n"
            f"<i>вопросы? пиши {DEVELOPER}</i>"
        )
        try:
            await query.message.edit_text(
                help_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ назад", callback_data="main_menu")
                ]])
            )
        except:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=help_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ назад", callback_data="main_menu")
                ]])
            )
    
    elif data.startswith("nav_prev_"):
        session_id = data.replace("nav_prev_", "")
        session = db.get_session(session_id)
        if session:
            new_index = max(0, session["current_index"] - 1)
            await show_current_image(update, context, session_id, new_index, edit=True)
    
    elif data.startswith("nav_next_"):
        session_id = data.replace("nav_next_", "")
        session = db.get_session(session_id)
        if session:
            new_index = min(dataset_manager.get_total_images() - 1, session["current_index"] + 1)
            await show_current_image(update, context, session_id, new_index, edit=True)
    
    elif data.startswith("search_in_session_"):
        session_id = data.replace("search_in_session_", "")
        context.user_data["search_session_id"] = session_id
        context.user_data["state"] = BotStates.SEARCH_MODE
        
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔍 <b>поиск хомяка</b>\n\nопиши хомяка: эмоцию, предмет, позу...\nнапример: <i>злой</i>, <i>с сердечками</i>, <i>плачет</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ назад", callback_data=f"back_to_session_{session_id}")
            ]])
        )
    
    elif data.startswith("show_search_"):
        parts = data.replace("show_search_", "").split("_")
        session_id = parts[0]
        image_index = int(parts[1])
        
        image_data = dataset_manager.get_image_data(image_index)
        
        if image_data and 'file_id' in image_data:
            caption = (
                f"<b>#{image_index}</b> · {escape_html(image_data['comment'])}\n"
                f"эмоция: {escape_html(image_data['emotion'])}"
            )
            
            keyboard = [
                [InlineKeyboardButton("🎙️ озвучить этого", callback_data=f"jump_to_{session_id}_{image_index}")],
                [
                    InlineKeyboardButton("🔍 новый поиск", callback_data=f"search_in_session_{session_id}"),
                    InlineKeyboardButton("◀️ назад", callback_data=f"back_to_session_{session_id}")
                ]
            ]
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=image_data['file_id'],
                caption=caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    elif data.startswith("jump_to_"):
        parts = data.replace("jump_to_", "").split("_")
        session_id = parts[0]
        image_index = int(parts[1])
        
        db.update_session(session_id, {"current_index": image_index})
        context.user_data["state"] = BotStates.RECORDING_SESSION
        await show_current_image(update, context, session_id, image_index, edit=True)
    
    elif data.startswith("back_to_session_"):
        session_id = data.replace("back_to_session_", "")
        session = db.get_session(session_id)
        if session:
            context.user_data["state"] = BotStates.RECORDING_SESSION
            await show_current_image(update, context, session_id, session["current_index"], edit=True)
    
    elif data.startswith("preview_session_"):
        session_id = data.replace("preview_session_", "")
        await preview_session(update, context, session_id)
    
    elif data.startswith("stop_session_"):
        session_id = data.replace("stop_session_", "")
        await stop_session(update, context, session_id)
    
    elif data.startswith("back_to_recording_"):
        session_id = data.replace("back_to_recording_", "")
        session = db.get_session(session_id)
        if session:
            context.user_data["session_id"] = session_id
            context.user_data["state"] = BotStates.RECORDING_SESSION
            try:
                await query.message.delete()
            except:
                pass
            await show_current_image(update, context, session_id, session["current_index"])
    
    elif data.startswith("continue_session_"):
        session_id = data.replace("continue_session_", "")
        session = db.get_session(session_id)
        if session and not session["completed"]:
            context.user_data["session_id"] = session_id
            context.user_data["state"] = BotStates.RECORDING_SESSION
            try:
                await query.message.delete()
            except:
                pass
            await show_current_image(update, context, session_id, session["current_index"])
    
    elif data.startswith("view_session_"):
        session_id = data.replace("view_session_", "")
        await show_session_details(update, context, session_id)
    
    elif data.startswith("delete_session_"):
        session_id = data.replace("delete_session_", "")
        await delete_session(update, context, session_id)

async def show_current_image(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str, image_index: int, edit: bool = False):
    session = db.get_session(session_id)
    if not session:
        return
    
    db.update_session(session_id, {"current_index": image_index})
    
    image_data = dataset_manager.get_image_data(image_index)
    if not image_data or 'file_id' not in image_data:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ошибка загрузки изображения"
        )
        return
    
    file_id = image_data['file_id']
    comment = escape_html(image_data['comment'])
    emotion = escape_html(image_data['emotion'])
    total = dataset_manager.get_total_images()
    
    voiced_indices = [v["index"] for v in session["voiced_images"]]
    voiced_count = len(session["voiced_images"])
    status = "✅ озвучено" if image_index in voiced_indices else "⏺️ ожидает озвучки"
    
    caption = (
        f"<b>#{image_index}</b> · {comment}\n"
        f"эмоция: {emotion}\n\n"
        f"{status}\n"
        f"озвучено всего: <b>{voiced_count}</b>\n\n"
        f"отправь голосовое сообщение для озвучки 🎙️"
    )
    
    keyboard = get_recording_keyboard(image_index, total, session_id, voiced_count)
    
    context.user_data["waiting_voice_for"] = image_index
    context.user_data["state"] = BotStates.WAITING_VOICE
    
    if edit and update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
    
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=file_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != BotStates.WAITING_VOICE:
        await update.message.reply_text("сначала начни сессию озвучивания 😊")
        return
    
    session_id = context.user_data.get("session_id")
    image_index = context.user_data.get("waiting_voice_for")
    
    if not session_id or image_index is None:
        return
    
    voice = update.message.voice
    
    # Сохраняем только file_id, не скачиваем файл
    # Аудио будет получаться из Telegram API при необходимости
    voice_file_id = voice.file_id
    
    db.add_voiced_image(session_id, image_index, voice_file_id)
    
    await update.message.reply_text(
        "✅ отлично! голос сохранен\n\n"
        "листай дальше или останови сессию 👇"
    )
    
    session = db.get_session(session_id)
    next_index = min(image_index + 1, dataset_manager.get_total_images() - 1)
    
    if next_index < dataset_manager.get_total_images():
        await show_current_image(update, context, session_id, next_index)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == BotStates.SEARCH_MODE:
        query_text = update.message.text
        results = dataset_manager.search_by_description(query_text)
        
        if not results:
            await update.message.reply_text(
                "😔 ничего не нашел по запросу\n"
                "попробуй другое описание",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ назад", callback_data="main_menu")
                ]])
            )
            return
        
        session_id = context.user_data.get("search_session_id")
        
        # Показываем первую найденную картинку
        top_result = results[0]
        image_index = top_result["index"]
        image_data = top_result["data"]
        
        if 'file_id' not in image_data:
            await update.message.reply_text("ошибка загрузки картинки")
            return
        
        caption = (
            f"🔍 <b>найдено: {len(results)} хомяков</b>\n\n"
            f"<b>#{image_index}</b> · {escape_html(image_data['comment'])}\n"
            f"эмоция: {escape_html(image_data['emotion'])}"
        )
        
        keyboard = []
        
        if session_id:
            # Если в сессии - кнопка озвучить
            keyboard.append([
                InlineKeyboardButton("🎙️ озвучить этого", callback_data=f"jump_to_{session_id}_{image_index}")
            ])
            
            # Показываем другие результаты
            if len(results) > 1:
                other_buttons = []
                for i, result in enumerate(results[1:4], 2):
                    other_buttons.append(
                        InlineKeyboardButton(
                            f"#{result['index']}", 
                            callback_data=f"show_search_{session_id}_{result['index']}"
                        )
                    )
                if other_buttons:
                    keyboard.append(other_buttons)
            
            keyboard.append([
                InlineKeyboardButton("🔍 новый поиск", callback_data=f"search_in_session_{session_id}"),
                InlineKeyboardButton("◀️ назад", callback_data=f"back_to_session_{session_id}")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🎙️ начать озвучку", callback_data="start_recording")
            ])
            keyboard.append([
                InlineKeyboardButton("◀️ назад", callback_data="main_menu")
            ])
        
        await update.message.reply_photo(
            photo=image_data['file_id'],
            caption=caption,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data["state"] = None

async def show_user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.callback_query.message.edit_text(
            "у тебя пока нет записей 😊\n"
            "начни озвучивать хомяков!",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    sessions = db.get_user_sessions(user.id)
    total_voiced = user_data.get("total_voiced", 0)
    
    active_sessions = [s for s in sessions if not s["completed"]]
    completed_sessions = [s for s in sessions if s["completed"] and len(s["voiced_images"]) > 0]
    
    stats_text = (
        f"📊 <b>твоя статистика</b>\n\n"
        f"🎙️ всего озвучено: <b>{total_voiced}</b> хомяков\n"
        f"📝 завершенных сессий: <b>{len(completed_sessions)}</b>\n"
        f"⏸️ активных сессий: <b>{len(active_sessions)}</b>\n\n"
    )
    
    keyboard = []
    
    if active_sessions:
        stats_text += "<b>незавершенные сессии:</b>\n"
        for i, session in enumerate(active_sessions[:3], 1):
            voiced_count = len(session["voiced_images"])
            stats_text += f"{i}. озвучено {voiced_count} из {dataset_manager.get_total_images()}\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"▶️ продолжить запись #{i} ({voiced_count} озвучено)",
                    callback_data=f"continue_session_{session['session_id']}"
                )
            ])
        stats_text += "\n"
    
    if completed_sessions:
        stats_text += "<b>завершенные сессии:</b>\n"
        for i, session in enumerate(completed_sessions[-5:], 1):
            voiced_count = len(session["voiced_images"])
            stats_text += f"{i}. озвучено {voiced_count} хомяков\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"📼 запись #{i} ({voiced_count} хомяков)",
                    callback_data=f"view_session_{session['session_id']}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("◀️ назад", callback_data="main_menu")])
    
    try:
        await update.callback_query.message.edit_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        await update.callback_query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=stats_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def preview_session(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    session = db.get_session(session_id)
    if not session:
        return
    
    voiced_count = len(session["voiced_images"])
    
    if voiced_count == 0:
        await update.callback_query.answer("пока нет озвученных хомяков 😊", show_alert=True)
        return
    
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    share_url = f"https://{WEB_DOMAIN}/session/{session_id}"
    
    preview_text = (
        f"👀 <b>предпросмотр результата</b>\n\n"
        f"озвучено хомяков: <b>{voiced_count}</b>\n\n"
        f"<i>это временная ссылка для просмотра.\n"
        f"чтобы получить постоянную ссылку,\n"
        f"заверши сессию кнопкой 'завершить'</i>\n\n"
        f"🔗 временная ссылка:\n"
        f"{share_url}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🌐 открыть сайт", url=share_url)],
        [InlineKeyboardButton("◀️ вернуться к записи", callback_data=f"back_to_recording_{session_id}")],
        [InlineKeyboardButton("⏸️ завершить и получить постоянную ссылку", callback_data=f"stop_session_{session_id}")],
        [InlineKeyboardButton("🏠 главное меню", callback_data="main_menu")]
    ]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=preview_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_session_details(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    session = db.get_session(session_id)
    if not session:
        await update.callback_query.answer("сессия не найдена", show_alert=True)
        return
    
    voiced_count = len(session["voiced_images"])
    total_images = dataset_manager.get_total_images()
    share_url = f"https://{WEB_DOMAIN}/session/{session_id}"
    
    if session["completed"]:
        details_text = (
            f"📼 <b>детали записи</b>\n\n"
            f"озвучено хомяков: <b>{voiced_count}</b> из {total_images}\n\n"
            f"🔗 ссылка на запись:\n"
            f"{share_url}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌐 открыть сайт", url=share_url)],
            [InlineKeyboardButton("▶️ продолжить озвучивание", callback_data=f"reopen_session_{session_id}")],
            [InlineKeyboardButton("🗑️ удалить запись", callback_data=f"delete_session_{session_id}")],
            [InlineKeyboardButton("◀️ назад к записям", callback_data="my_stats")],
            [InlineKeyboardButton("🏠 главное меню", callback_data="main_menu")]
        ]
    else:
        details_text = (
            f"📼 <b>активная сессия</b>\n\n"
            f"озвучено хомяков: <b>{voiced_count}</b> из {total_images}\n\n"
            f"🔗 временная ссылка:\n"
            f"{share_url}"
        )
        
        keyboard = [
            [InlineKeyboardButton("🌐 открыть сайт", url=share_url)],
            [InlineKeyboardButton("▶️ продолжить запись", callback_data=f"continue_session_{session_id}")],
            [InlineKeyboardButton("⏸️ завершить сессию", callback_data=f"stop_session_{session_id}")],
            [InlineKeyboardButton("◀️ назад к записям", callback_data="my_stats")],
            [InlineKeyboardButton("🏠 главное меню", callback_data="main_menu")]
        ]
    
    try:
        await update.callback_query.message.edit_text(
            details_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        await update.callback_query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=details_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def reopen_session(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    session = db.get_session(session_id)
    if not session:
        await update.callback_query.answer("сессия не найдена", show_alert=True)
        return
    
    db.update_session(session_id, {"completed": False})
    
    context.user_data["session_id"] = session_id
    context.user_data["state"] = BotStates.RECORDING_SESSION
    
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    await show_current_image(update, context, session_id, session["current_index"])

async def delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    session = db.get_session(session_id)
    if not session:
        await update.callback_query.answer("сессия не найдена", show_alert=True)
        return
    
    user_id = session["user_id"]
    voiced_count = len(session["voiced_images"])
    
    db.delete_session(session_id, user_id, voiced_count)
    
    await update.callback_query.answer("✅ запись удалена", show_alert=True)
    await show_user_stats(update, context)

async def stop_session(update: Update, context: ContextTypes.DEFAULT_TYPE, session_id: str):
    session = db.get_session(session_id)
    if not session:
        return
    
    voiced_count = len(session["voiced_images"])
    
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    if voiced_count == 0:
        db.delete_session(session_id, session["user_id"], 0)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="😔 ты не озвучил ни одного хомяка\nсессия не сохранена",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    db.complete_session(session_id)
    
    share_url = f"https://{WEB_DOMAIN}/session/{session_id}"
    
    result_text = (
        f"🎉 <b>отлично!</b>\n\n"
        f"ты озвучил <b>{voiced_count}</b> хомяков!\n\n"
        f"🔗 твоя уникальная ссылка:\n"
        f"{share_url}\n\n"
        f"на сайте можно посмотреть все озвученные картинки "
        f"и послушать твои голосовые 🎧\n\n"
        f"делись с друзьями! 😊"
    )
    
    keyboard = [
        [InlineKeyboardButton("🌐 открыть сайт", url=share_url)],
        [InlineKeyboardButton("🏠 главное меню", callback_data="main_menu")]
    ]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    logger.info("=" * 50)
    logger.info("MAIN FUNCTION STARTING")
    logger.info(f"BOT_TOKEN: {BOT_TOKEN[:20]}...")
    logger.info(f"WEB_DOMAIN: {WEB_DOMAIN}")
    logger.info("=" * 50)
    
    application = Application.builder().token(BOT_TOKEN).build()
    logger.info("Application builder created")
    
    application.add_handler(CommandHandler("start", start))
    logger.info("CommandHandler 'start' registered")
    
    application.add_handler(CallbackQueryHandler(button_handler))
    logger.info("CallbackQueryHandler registered")
    
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))
    logger.info("MessageHandler for VOICE registered")
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    logger.info("MessageHandler for TEXT registered")
    
    logger.info("=" * 50)
    logger.info("БОТ ЗАПУЩЕН! Ожидание сообщений...")
    logger.info("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Polling stopped")

if __name__ == "__main__":
    main()
