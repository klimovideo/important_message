import logging
import asyncio
import html
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

from config import TELEGRAM_TOKEN, DEFAULT_IMPORTANCE_THRESHOLD, USERBOT_ENABLED
from models import Message, Storage, UserPreferences, PostStatus
from ai_service import evaluate_message_importance
from admin_service import AdminService
from utils import setup_logging

# Import userbot functionality
if USERBOT_ENABLED:
    from userbot import get_userbot, start_userbot, stop_userbot

# Setup logging
setup_logging()

# Enable logging
logger = logging.getLogger(__name__)

# ===========================================
# MAIN MENU KEYBOARDS
# ===========================================

def get_main_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру с reply кнопками"""
    is_admin = Storage.is_admin(user_id)
    
    keyboard = [
        ["📊 Мониторинг", "📝 Предложить пост"],
        ["⚙️ Настройки", "📈 Статистика"],
    ]
    
    if USERBOT_ENABLED:
        keyboard.append(["🤖 Userbot", "🔑 Ключевые слова"])
    else:
        keyboard.append(["🔑 Ключевые слова"])
    
    if is_admin:
        keyboard.append(["🔧 Администрирование"])
    
    keyboard.append(["ℹ️ Справка"])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для администраторов"""
    keyboard = [
        ["📝 Модерация постов", "⚙️ Конфигурация"],
        ["📢 Канал публикации", "👥 Администраторы"],
        ["📊 Статистика админа", "🔙 Главное меню"]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_userbot_reply_keyboard() -> ReplyKeyboardMarkup:
    """Создает клавиатуру для userbot"""
    keyboard = [
        ["🚀 Запустить", "⏹️ Остановить"],
        ["➕ Присоединиться", "➖ Покинуть"],
        ["📊 Статус", "🔄 Сброс сессии"],
        ["🔙 Главное меню"]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ===========================================
# ESSENTIAL COMMANDS (минимум)
# ===========================================

async def start_command(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    welcome_text = (
        f"🤖 <b>Добро пожаловать!</b>\n\n"
        f"Я анализирую сообщения из ваших чатов и каналов с помощью ИИ "
        f"и уведомляю только о важных сообщениях.\n\n"
        f"📊 <b>Ваши настройки:</b>\n"
        f"• Порог важности: {user.importance_threshold}\n"
        f"• Мониторится источников: {len(user.monitored_chats) + len(user.monitored_channels)}\n"
        f"• Ключевых слов: {len(user.keywords)}\n\n"
        f"💡 Используйте кнопки ниже для навигации"
    )
    
    reply_markup = get_main_reply_keyboard(user_id)
    
    await update.message.reply_text(
        welcome_text, 
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def menu_command(update: Update, context: CallbackContext) -> None:
    """Show main menu."""
    user_id = update.effective_user.id
    reply_markup = get_main_reply_keyboard(user_id)
    
    await update.message.reply_text(
        "🎛️ <b>Главное меню</b>\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def admin_command(update: Update, context: CallbackContext) -> None:
    """Quick admin access."""
    user_id = update.effective_user.id
    
    if not Storage.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    reply_markup = get_admin_reply_keyboard()
    
    config = Storage.bot_config
    pending_posts = len(Storage.get_pending_posts(PostStatus.PENDING))
    
    admin_text = (
        f"🔧 <b>Панель администратора</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Администраторов: {len(config.admin_ids)}\n"
        f"• Постов на модерации: {pending_posts}\n"
        f"• Канал публикации: {config.publish_channel_username or 'Не настроен'}\n"
        f"• Автопубликация: {'Включена' if config.auto_publish_enabled else 'Отключена'}\n"
        f"• Требует одобрения: {'Да' if config.require_admin_approval else 'Нет'}\n\n"
        f"🎛️ Используйте кнопки для управления:"
    )
    
    await update.message.reply_text(
        admin_text, 
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def submit_post_command(update: Update, context: CallbackContext) -> None:
    """Submit a post for review - keep for compatibility."""
    user_id = update.effective_user.id
    message_text = ""
    source_info = None
    
    # Check if this is a reply to a forwarded message
    if update.message.reply_to_message:
        if update.message.reply_to_message.text:
            message_text = update.message.reply_to_message.text
            source_info = "Пересланное сообщение"
            
            # Try to get source info from forward_origin
            if hasattr(update.message.reply_to_message, 'forward_origin') and update.message.reply_to_message.forward_origin:
                if hasattr(update.message.reply_to_message.forward_origin, 'chat'):
                    source_chat = update.message.reply_to_message.forward_origin.chat
                    source_info = f"Пересланное из: {html.escape(source_chat.title or 'Неизвестный чат')}"
        else:
            await update.message.reply_text("❌ Пересланное сообщение не содержит текста.")
            return
    elif context.args:
        message_text = " ".join(context.args)
    else:
        # Show submit interface
        await show_submit_post_interface(update, context)
        return
    
    if not message_text.strip():
        await update.message.reply_text("❌ Текст поста не может быть пустым.")
        return
    
    try:
        post_id = await AdminService.submit_post_for_review(user_id, message_text, source_info)
        
        # Notify admins
        post = Storage.get_pending_post(post_id)
        if post:
            await AdminService.notify_admins_about_new_post(context.bot, post)
        
        await update.message.reply_text(
            f"✅ <b>Пост отправлен на модерацию!</b>\n\n"
            f"📋 <b>ID поста:</b> {post_id}\n"
            f"⏳ <b>Статус:</b> Ожидает рассмотрения\n\n"
            f"💡 Вы получите уведомление о результатах модерации.",
            parse_mode=ParseMode.HTML
        )
        
    except PermissionError as e:
        await update.message.reply_text(f"❌ {html.escape(str(e))}")
    except Exception as e:
        logger.error(f"Ошибка при отправке поста: {e}")
        await update.message.reply_text("❌ Произошла ошибка при отправке поста.")

# ===========================================
# REPLY BUTTON HANDLERS
# ===========================================

async def handle_reply_buttons(update: Update, context: CallbackContext) -> bool:
    """Handle reply button presses. Returns True if button was handled."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    text = update.message.text
    
    # Main menu buttons
    if text == "📊 Мониторинг":
        await show_monitoring_interface(update, context, user)
        return True
    
    elif text == "📝 Предложить пост":
        await show_submit_post_interface(update, context)
        return True
    
    elif text == "⚙️ Настройки":
        await show_settings_interface(update, context, user)
        return True
    
    elif text == "📈 Статистика":
        await show_statistics_interface(update, context, user)
        return True
    
    elif text == "🤖 Userbot":
        if USERBOT_ENABLED:
            await show_userbot_interface(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен в конфигурации.")
        return True
    
    elif text == "🔑 Ключевые слова":
        await show_keywords_interface(update, context, user)
        return True
    
    elif text == "🔧 Администрирование":
        if Storage.is_admin(user_id):
            reply_markup = get_admin_reply_keyboard()
            await update.message.reply_text(
                "🔧 <b>Панель администратора</b>\n\nВыберите действие:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "ℹ️ Справка":
        await show_help_interface(update, context)
        return True
    
    # Admin buttons
    elif text == "📝 Модерация постов":
        if Storage.is_admin(user_id):
            await show_posts_moderation(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "⚙️ Конфигурация":
        if Storage.is_admin(user_id):
            await show_admin_config(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "📢 Канал публикации":
        if Storage.is_admin(user_id):
            await show_channel_config(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "👥 Администраторы":
        if Storage.is_admin(user_id):
            await show_admins_management(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "📊 Статистика админа":
        if Storage.is_admin(user_id):
            await show_admin_statistics(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    # Userbot buttons
    elif text == "🚀 Запустить":
        if USERBOT_ENABLED:
            await handle_userbot_start(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    elif text == "⏹️ Остановить":
        if USERBOT_ENABLED:
            await handle_userbot_stop(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    elif text == "➕ Присоединиться":
        if USERBOT_ENABLED:
            await show_userbot_join_interface(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    elif text == "➖ Покинуть":
        if USERBOT_ENABLED:
            await show_userbot_leave_interface(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    elif text == "📊 Статус":
        if USERBOT_ENABLED:
            await show_userbot_status(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    elif text == "🔄 Сброс сессии":
        if USERBOT_ENABLED:
            await handle_userbot_reset_session(update, context)
        else:
            await update.message.reply_text("❌ Userbot отключен.")
        return True
    
    # Back to main menu
    elif text == "🔙 Главное меню":
        reply_markup = get_main_reply_keyboard(user_id)
        await update.message.reply_text(
            "🎛️ <b>Главное меню</b>\n\nВыберите нужный раздел:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return True
    
    # If no button matched, return False
    return False

# ===========================================
# INTERFACE FUNCTIONS
# ===========================================

async def show_monitoring_interface(update: Update, context: CallbackContext, user: UserPreferences) -> None:
    """Show monitoring interface with inline buttons."""
    total_sources = len(user.monitored_chats) + len(user.monitored_channels)
    
    monitoring_text = (
        f"📊 <b>Мониторинг источников</b>\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Всего источников: {total_sources}\n"
        f"• Чатов: {len(user.monitored_chats)}\n"
        f"• Каналов: {len(user.monitored_channels)}\n"
        f"• Порог важности: {user.importance_threshold}\n\n"
        f"💡 <b>Как добавить источник:</b>\n"
        f"1. Перешлите сообщение из чата/канала боту\n"
        f"2. Выберите действие в предложенном меню\n\n"
        f"🤖 <b>Или используйте Userbot для скрытого мониторинга</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📋 Список источников", callback_data="monitoring_list"),
            InlineKeyboardButton("🗑️ Удалить источник", callback_data="monitoring_remove")
        ],
        [
            InlineKeyboardButton("⚙️ Настроить порог", callback_data="monitoring_threshold"),
            InlineKeyboardButton("🧹 Очистить все", callback_data="monitoring_clear")
        ]
    ]
    
    if USERBOT_ENABLED:
        keyboard.append([InlineKeyboardButton("🤖 Перейти к Userbot", callback_data="goto_userbot")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        monitoring_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_submit_post_interface(update: Update, context: CallbackContext) -> None:
    """Show post submission interface."""
    submit_text = (
        f"📝 <b>Предложение поста для публикации</b>\n\n"
        f"🎯 <b>Как предложить пост:</b>\n\n"
        f"1️⃣ <b>Напишите текст:</b>\n"
        f"• Просто отправьте сообщение с текстом поста\n\n"
        f"2️⃣ <b>Пересланное сообщение:</b>\n"
        f"• Перешлите интересное сообщение боту\n"
        f"• Нажмите кнопку для отправки на модерацию\n\n"
        f"3️⃣ <b>Команда:</b>\n"
        f"• /submit_post <текст поста>\n\n"
        f"💡 <b>Ваш пост будет:</b>\n"
        f"• Оценен ИИ на важность\n"
        f"• Рассмотрен администраторами\n"
        f"• Опубликован при одобрении\n\n"
        f"✅ <b>Попробуйте прямо сейчас!</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📄 Мои предложения", callback_data="my_submissions")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        submit_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_settings_interface(update: Update, context: CallbackContext, user: UserPreferences) -> None:
    """Show settings interface with inline buttons."""
    keywords = ", ".join(user.keywords) if user.keywords else "Не указаны"
    exclude_keywords = ", ".join(user.exclude_keywords) if user.exclude_keywords else "Не указаны"
    
    settings_text = (
        f"⚙️ <b>Ваши настройки</b>\n\n"
        f"📊 <b>Основные параметры:</b>\n"
        f"• Порог важности: {user.importance_threshold}\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n"
        f"• Можете предлагать посты: {'Да' if user.can_submit_posts else 'Нет'}\n\n"
        f"🔑 <b>Ключевые слова:</b>\n"
        f"• Важные: {keywords[:100]}{'...' if len(keywords) > 100 else ''}\n"
        f"• Исключаемые: {exclude_keywords[:100]}{'...' if len(exclude_keywords) > 100 else ''}\n\n"
        f"💡 Используйте кнопки для изменения настроек"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📊 Изменить порог", callback_data="settings_threshold"),
            InlineKeyboardButton("🔑 Ключевые слова", callback_data="settings_keywords")
        ],
        [
            InlineKeyboardButton("🗑️ Очистить данные", callback_data="settings_clear"),
            InlineKeyboardButton("🔄 Сброс настроек", callback_data="settings_reset")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        settings_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_statistics_interface(update: Update, context: CallbackContext, user: UserPreferences) -> None:
    """Show user statistics."""
    stats_text = (
        f"📈 <b>Ваша статистика</b>\n\n"
        f"👤 <b>Профиль:</b>\n"
        f"• ID пользователя: {user.user_id}\n"
        f"• Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n"
        f"• Последнее обновление: {user.updated_at.strftime('%d.%m.%Y')}\n\n"
        f"📊 <b>Мониторинг:</b>\n"
        f"• Отслеживаемых чатов: {len(user.monitored_chats)}\n"
        f"• Отслеживаемых каналов: {len(user.monitored_channels)}\n"
        f"• Всего источников: {len(user.monitored_chats) + len(user.monitored_channels)}\n\n"
        f"🔑 <b>Фильтрация:</b>\n"
        f"• Ключевых слов: {len(user.keywords)}\n"
        f"• Исключаемых слов: {len(user.exclude_keywords)}\n"
        f"• Порог важности: {user.importance_threshold}\n\n"
        f"📝 <b>Активность:</b>\n"
        f"• Может предлагать посты: {'Да' if user.can_submit_posts else 'Нет'}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="stats_refresh")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if this is a callback query or regular message
    if update.callback_query:
        # Called from a callback query (button press)
        await update.callback_query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Called from a regular message
        await update.message.reply_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

async def show_keywords_interface(update: Update, context: CallbackContext, user: UserPreferences) -> None:
    """Show keywords management interface."""
    keywords_text = (
        f"🔑 <b>Управление ключевыми словами</b>\n\n"
        f"📈 <b>Важные слова</b> (повышают важность):\n"
    )
    
    if user.keywords:
        keywords_text += "• " + "\n• ".join(user.keywords[:10])
        if len(user.keywords) > 10:
            keywords_text += f"\n• ... и еще {len(user.keywords) - 10}"
    else:
        keywords_text += "Не указаны"
    
    keywords_text += f"\n\n📉 <b>Исключаемые слова</b> (понижают важность):\n"
    
    if user.exclude_keywords:
        keywords_text += "• " + "\n• ".join(user.exclude_keywords[:10])
        if len(user.exclude_keywords) > 10:
            keywords_text += f"\n• ... и еще {len(user.exclude_keywords) - 10}"
    else:
        keywords_text += "Не указаны"
    
    keywords_text += (
        f"\n\n💡 <b>Как добавить:</b>\n"
        f"Просто отправьте сообщение с текстом:\n"
        f"<code>+слово</code> - добавить важное слово\n"
        f"<code>-слово</code> - добавить исключаемое слово"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить важное", callback_data="keywords_add_important"),
            InlineKeyboardButton("➖ Добавить исключаемое", callback_data="keywords_add_exclude")
        ],
        [
            InlineKeyboardButton("🗑️ Удалить важное", callback_data="keywords_remove_important"),
            InlineKeyboardButton("🗑️ Удалить исключаемое", callback_data="keywords_remove_exclude")
        ],
        [
            InlineKeyboardButton("🧹 Очистить все", callback_data="keywords_clear_all")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        keywords_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_help_interface(update: Update, context: CallbackContext) -> None:
    """Show help interface."""
    help_text = (
        f"ℹ️ <b>Справка по боту</b>\n\n"
        f"🤖 <b>Основные возможности:</b>\n"
        f"• Анализ важности сообщений с помощью ИИ\n"
        f"• Мониторинг чатов и каналов\n"
        f"• Скрытый мониторинг через Userbot\n"
        f"• Предложение постов для публикации\n"
        f"• Настройка критериев важности\n\n"
        f"📋 <b>Как начать:</b>\n"
        f"1. Перешлите сообщение из интересного чата/канала\n"
        f"2. Выберите 'Добавить в мониторинг'\n"
        f"3. Настройте ключевые слова и порог важности\n"
        f"4. Получайте уведомления о важных сообщениях!\n\n"
        f"🔥 <b>Userbot режим:</b>\n"
        f"• Полностью скрытый мониторинг\n"
        f"• Работает с закрытыми каналами\n"
        f"• Анализирует ВСЕ сообщения автоматически\n\n"
        f"💡 <b>Советы:</b>\n"
        f"• Используйте кнопки для навигации\n"
        f"• Настройте ключевые слова для лучшей фильтрации\n"
        f"• Экспериментируйте с порогом важности\n"
        f"• Предлагайте интересные посты для публикации"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🚀 Быстрый старт", callback_data="help_quickstart"),
            InlineKeyboardButton("🤖 Настройка Userbot", callback_data="help_userbot")
        ],
        [
            InlineKeyboardButton("💡 Советы", callback_data="help_tips"),
            InlineKeyboardButton("❓ FAQ", callback_data="help_faq")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# ===========================================
# USERBOT INTERFACES  
# ===========================================

async def show_userbot_interface(update: Update, context: CallbackContext) -> None:
    """Show userbot interface."""
    if not USERBOT_ENABLED:
        error_text = (
            "❌ <b>Userbot отключен</b>\n\n"
            "Для включения настройте переменные окружения:\n"
            "• TELEGRAM_API_ID\n"
            "• TELEGRAM_API_HASH\n"
            "• TELEGRAM_PHONE"
        )
        # Check if this is a callback query or regular message
        if update.callback_query:
            await update.callback_query.edit_message_text(error_text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(error_text, parse_mode=ParseMode.HTML)
        return
    
    userbot = get_userbot()
    
    status_text = "🤖 <b>Userbot - Скрытый мониторинг</b>\n\n"
    
    if userbot.is_running:
        status_text += "✅ <b>Статус:</b> Активен\n"
        monitored = userbot.get_monitored_sources()
        status_text += f"📊 <b>Мониторится источников:</b> {len(monitored)}\n"
        if monitored:
            status_text += f"🔍 <b>ID источников:</b> {', '.join(map(str, list(monitored)[:5]))}"
            if len(monitored) > 5:
                status_text += f" и еще {len(monitored) - 5}"
    else:
        status_text += "❌ <b>Статус:</b> Неактивен\n"
    
    status_text += (
        f"\n\n💡 <b>Преимущества Userbot:</b>\n"
        f"• Полная анонимность\n"
        f"• Работает с закрытыми каналами\n"
        f"• Анализирует ВСЕ сообщения\n"
        f"• Не требует прав администратора\n\n"
        f"🎛️ Используйте кнопки для управления:"
    )
    
    reply_markup = get_userbot_reply_keyboard()
    
    # Check if this is a callback query or regular message
    if update.callback_query:
        # Called from a callback query (button press)
        await update.callback_query.edit_message_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Called from a regular message
        await update.message.reply_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

# ===========================================
# ADMIN INTERFACES
# ===========================================

async def show_posts_moderation(update: Update, context: CallbackContext) -> None:
    """Show posts moderation interface."""
    pending_posts = AdminService.get_posts_for_review()
    
    if not pending_posts:
        await update.message.reply_text(
            "✅ <b>Нет постов на модерации</b>\n\n"
            "Все предложенные посты обработаны.",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Show first post
    post = pending_posts[0]
    post_text = (
        f"📝 <b>Пост на модерации</b> (1 из {len(pending_posts)})\n\n"
        f"📋 <b>ID поста:</b> {post.post_id}\n"
        f"👤 <b>От пользователя:</b> {post.user_id}\n"
        f"📅 <b>Время:</b> {post.submitted_at.strftime('%d.%m.%Y %H:%M')}\n"
    )
    
    if post.source_info:
        post_text += f"📋 <b>Источник:</b> {post.source_info}\n"
    
    if post.importance_score:
        post_text += f"⭐ <b>Оценка ИИ:</b> {post.importance_score:.2f}\n"
    
    post_text += f"\n📄 <b>Текст:</b>\n{post.message_text[:400]}"
    
    if len(post.message_text) > 400:
        post_text += "..."
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve_{post.post_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{post.post_id}")
        ],
        [
            InlineKeyboardButton("📄 Полный текст", callback_data=f"admin_full_{post.post_id}"),
            InlineKeyboardButton("⏭️ Следующий", callback_data="admin_next_post")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        post_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# Продолжение будет в следующем блоке...# Продолжение bot_simplified.py

# ===========================================
# ADMIN INTERFACE FUNCTIONS (продолжение)
# ===========================================

async def show_admin_config(update: Update, context: CallbackContext) -> None:
    """Show admin configuration interface."""
    config = Storage.bot_config
    
    config_text = (
        f"⚙️ <b>Конфигурация бота</b>\n\n"
        f"🤖 <b>Автопубликация:</b> {'Включена' if config.auto_publish_enabled else 'Отключена'}\n"
        f"✋ <b>Требует одобрения:</b> {'Да' if config.require_admin_approval else 'Нет'}\n"
        f"📊 <b>Порог важности:</b> {config.importance_threshold}\n"
        f"📢 <b>Канал публикации:</b> {config.publish_channel_username or 'Не настроен'}\n\n"
        f"💡 <b>Используйте кнопки для изменения настроек</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"🤖 Автопубликация: {'✅' if config.auto_publish_enabled else '❌'}", 
                callback_data="admin_toggle_autopublish"
            )
        ],
        [
            InlineKeyboardButton(
                f"✋ Требует одобрения: {'✅' if config.require_admin_approval else '❌'}", 
                callback_data="admin_toggle_approval"
            )
        ],
        [
            InlineKeyboardButton("📊 Изменить порог важности", callback_data="admin_threshold"),
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        config_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_channel_config(update: Update, context: CallbackContext) -> None:
    """Show channel configuration interface."""
    config = Storage.bot_config
    channel_info = f"<code>{html.escape(str(config.publish_channel_id))}</code>" if config.publish_channel_id else "Не настроен"
    username_info = f"@{html.escape(config.publish_channel_username)}" if config.publish_channel_username else "Не указан"
    
    channel_text = (
        f"📢 <b>Настройка канала публикации</b>\n\n"
        f"📋 <b>Текущий канал:</b> {channel_info}\n"
        f"🏷️ <b>Username:</b> {username_info}\n\n"
        f"💡 <b>Для настройки отправьте сообщение с:</b>\n"
        f"• ID канала (например: -1001234567890)\n"
        f"• Username канала (например: @my_channel)\n"
        f"• Ссылку на канал (например: https://t.me/my_channel)\n\n"
        f"🔧 <b>Или используйте команду:</b>\n"
        f"/admin_channel &lt;ID, @username или ссылка&gt;"
    )
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Очистить настройки", callback_data="admin_clear_channel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        channel_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_admins_management(update: Update, context: CallbackContext) -> None:
    """Show admins management interface."""
    config = Storage.bot_config
    
    admins_text = (
        f"👥 <b>Управление администраторами</b>\n\n"
        f"📊 <b>Всего администраторов:</b> {len(config.admin_ids)}\n\n"
        f"📋 <b>Список администраторов:</b>\n"
    )
    
    for i, admin_id in enumerate(config.admin_ids, 1):
        admins_text += f"{i}. {admin_id}\n"
    
    admins_text += (
        f"\n💡 <b>Для добавления/удаления отправьте:</b>\n"
        f"• <code>+123456789</code> - добавить админа\n"
        f"• <code>-123456789</code> - удалить админа\n\n"
        f"🔧 <b>Или используйте команды:</b>\n"
        f"/admin_add <user_id>\n"
        f"/admin_remove <user_id>"
    )
    
    await update.message.reply_text(
        admins_text,
        parse_mode=ParseMode.HTML
    )

async def show_admin_statistics(update: Update, context: CallbackContext) -> None:
    """Show admin statistics."""
    config = Storage.bot_config
    all_users = Storage.get_all_users()
    pending_posts = Storage.get_pending_posts(PostStatus.PENDING)
    approved_posts = Storage.get_pending_posts(PostStatus.APPROVED)
    rejected_posts = Storage.get_pending_posts(PostStatus.REJECTED)
    published_posts = Storage.get_pending_posts(PostStatus.PUBLISHED)
    
    # Count monitored sources
    total_chats = sum(len(user.monitored_chats) for user in all_users.values())
    total_channels = sum(len(user.monitored_channels) for user in all_users.values())
    
    stats_text = (
        f"📊 <b>Статистика администратора</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего пользователей: {len(all_users)}\n"
        f"• Администраторов: {len(config.admin_ids)}\n\n"
        f"📊 <b>Мониторинг:</b>\n"
        f"• Отслеживаемых чатов: {total_chats}\n"
        f"• Отслеживаемых каналов: {total_channels}\n"
        f"• Всего источников: {total_chats + total_channels}\n\n"
        f"📝 <b>Посты:</b>\n"
        f"• На модерации: {len(pending_posts)}\n"
        f"• Одобрено: {len(approved_posts)}\n"
        f"• Отклонено: {len(rejected_posts)}\n"
        f"• Опубликовано: {len(published_posts)}\n\n"
        f"⚙️ <b>Настройки:</b>\n"
        f"• Автопубликация: {'Включена' if config.auto_publish_enabled else 'Отключена'}\n"
        f"• Требует одобрения: {'Да' if config.require_admin_approval else 'Нет'}\n"
        f"• Порог важности: {config.importance_threshold}\n"
        f"• Канал настроен: {'Да' if config.publish_channel_id else 'Нет'}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="admin_stats_refresh")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if this is a callback query or regular message
    if update.callback_query:
        # Called from a callback query (button press)
        await update.callback_query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Called from a regular message
        await update.message.reply_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

# ===========================================
# USERBOT FUNCTIONS
# ===========================================

async def handle_userbot_start(update: Update, context: CallbackContext) -> None:
    """Handle userbot start."""
    try:
        userbot = get_userbot()
        if userbot.is_running:
            await update.message.reply_text("⚠️ Userbot уже запущен.")
            return
        
        await start_userbot()
        await update.message.reply_text(
            "✅ <b>Userbot запущен!</b>\n\n"
            "🤖 Скрытый мониторинг активирован.\n"
            "💡 Теперь можете присоединяться к каналам.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка запуска userbot: {e}")
        await update.message.reply_text(f"❌ Ошибка запуска userbot: {html.escape(str(e))}")

async def handle_userbot_stop(update: Update, context: CallbackContext) -> None:
    """Handle userbot stop."""
    try:
        userbot = get_userbot()
        if not userbot.is_running:
            await update.message.reply_text("⚠️ Userbot уже остановлен.")
            return
        
        await stop_userbot()
        await update.message.reply_text(
            "⏹️ <b>Userbot остановлен</b>\n\n"
            "🤖 Скрытый мониторинг деактивирован.",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        logger.error(f"Ошибка остановки userbot: {e}")
        await update.message.reply_text(f"❌ Ошибка остановки userbot: {html.escape(str(e))}")

async def handle_userbot_reset_session(update: Update, context: CallbackContext) -> None:
    """Handle userbot session reset."""
    try:
        userbot = get_userbot()
        
        # Stop userbot if it's running
        if userbot.is_running:
            await stop_userbot()
        
        # Reset the session
        if userbot.reset_session():
            await update.message.reply_text(
                "🔄 <b>Сессия userbot сброшена</b>\n\n"
                "✅ Файл сессии удален\n"
                "🔐 При следующем запуске потребуется повторная авторизация\n\n"
                "💡 <b>Используйте это, если:</b>\n"
                "• Userbot не может запуститься\n"
                "• Возникают ошибки авторизации\n"
                "• Сменился номер телефона",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text("⚠️ Файл сессии не найден или не удалось его удалить.")
        
    except Exception as e:
        logger.error(f"Ошибка сброса сессии userbot: {e}")
        await update.message.reply_text(f"❌ Ошибка сброса сессии userbot: {html.escape(str(e))}")

async def show_userbot_join_interface(update: Update, context: CallbackContext) -> None:
    """Show userbot join interface."""
    join_text = (
        f"➕ <b>Присоединение к каналу/чату</b>\n\n"
        f"💡 <b>Отправьте ссылку на канал или чат:</b>\n"
        f"• https://t.me/channel_name\n"
        f"• @channel_name\n"
        f"• Ссылку-приглашение\n\n"
        f"🔒 <b>Поддерживаются:</b>\n"
        f"• Публичные каналы\n"
        f"• Приватные каналы (по ссылке-приглашению)\n"
        f"• Группы и супергруппы\n\n"
        f"⚠️ <b>Userbot должен быть запущен</b>"
    )
    
    await update.message.reply_text(join_text, parse_mode=ParseMode.HTML)

async def show_userbot_leave_interface(update: Update, context: CallbackContext) -> None:
    """Show userbot leave interface."""
    try:
        userbot = get_userbot()
        monitored = userbot.get_monitored_sources()
        
        if not monitored:
            await update.message.reply_text(
                "❌ <b>Нет источников для покидания</b>\n\n"
                "Userbot не мониторит ни одного канала или чата.",
                parse_mode=ParseMode.HTML
            )
            return
        
        leave_text = (
            f"➖ <b>Покинуть канал/чат</b>\n\n"
            f"📊 <b>Мониторится источников:</b> {len(monitored)}\n\n"
            f"💡 <b>Отправьте ID источника для покидания:</b>\n"
        )
        
        for source_id in list(monitored)[:10]:
            leave_text += f"• {source_id}\n"
        
        if len(monitored) > 10:
            leave_text += f"• ... и еще {len(monitored) - 10}\n"
        
        leave_text += f"\n📝 <b>Пример:</b> -1001234567890"
        
        await update.message.reply_text(leave_text, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка получения списка источников: {e}")
        await update.message.reply_text("❌ Ошибка получения списка источников.")

async def show_userbot_status(update: Update, context: CallbackContext) -> None:
    """Show detailed userbot status."""
    try:
        userbot = get_userbot()
        user_id = update.effective_user.id
        user = Storage.get_user(user_id)
        
        status_text = "📊 <b>Подробный статус Userbot</b>\n\n"
        
        if userbot.is_running:
            status_text += "✅ <b>Статус:</b> Активен\n"
        else:
            status_text += "❌ <b>Статус:</b> Неактивен\n"
        
        # Monitoring sources
        monitored_userbot = userbot.get_monitored_sources()
        status_text += f"\n📊 <b>Мониторинг через userbot:</b>\n"
        status_text += f"• Источников: {len(monitored_userbot)}\n"
        if monitored_userbot:
            status_text += f"• ID: {', '.join(map(str, list(monitored_userbot)[:5]))}"
            if len(monitored_userbot) > 5:
                status_text += f" и еще {len(monitored_userbot) - 5}"
        
        # User monitoring (passive + active)
        status_text += f"\n\n📋 <b>Ваш личный мониторинг:</b>\n"
        status_text += f"• Чатов: {len(user.monitored_chats)}\n"
        status_text += f"• Каналов: {len(user.monitored_channels)}\n"
        status_text += f"• Порог важности: {user.importance_threshold}\n"
        status_text += f"• Ключевых слов: {len(user.keywords)}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить", callback_data="userbot_status_refresh")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Check if this is a callback query or regular message
        if update.callback_query:
            # Called from a callback query (button press)
            await update.callback_query.edit_message_text(
                status_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        else:
            # Called from a regular message
            await update.message.reply_text(
                status_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        
    except Exception as e:
        logger.error(f"Ошибка получения статуса userbot: {e}")
        # Handle error response based on update type
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text("❌ Ошибка получения статуса userbot.")
            except:
                await update.callback_query.message.reply_text("❌ Ошибка получения статуса userbot.")
        else:
            await update.message.reply_text("❌ Ошибка получения статуса userbot.")

# ===========================================
# TEXT MESSAGE HANDLERS
# ===========================================

async def handle_text_messages(update: Update, context: CallbackContext) -> None:
    """Handle text messages for various inputs."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Handle keyword additions
    if text.startswith('+') and len(text) > 1:
        keyword = text[1:].strip().lower()
        user = Storage.get_user(user_id)
        if keyword not in user.keywords:
            user.keywords.append(keyword)
            Storage.update_user(user)
            await update.message.reply_text(f"✅ Добавлено важное слово: <b>{html.escape(keyword)}</b>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"⚠️ Слово '<b>{html.escape(keyword)}</b>' уже есть в списке важных.", parse_mode=ParseMode.HTML)
        return
    
    # Handle keyword exclusions
    elif text.startswith('-') and len(text) > 1 and not text[1:].isdigit():
        keyword = text[1:].strip().lower()
        user = Storage.get_user(user_id)
        if keyword not in user.exclude_keywords:
            user.exclude_keywords.append(keyword)
            Storage.update_user(user)
            await update.message.reply_text(f"✅ Добавлено исключаемое слово: <b>{html.escape(keyword)}</b>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"⚠️ Слово '<b>{html.escape(keyword)}</b>' уже есть в списке исключаемых.", parse_mode=ParseMode.HTML)
        return
    
    # Handle admin addition (for admins only)
    elif text.startswith('+') and text[1:].isdigit():
        if Storage.is_admin(user_id):
            admin_id = int(text[1:])
            if admin_id not in Storage.bot_config.admin_ids:
                Storage.add_admin(admin_id)
                await update.message.reply_text(f"✅ Пользователь {admin_id} добавлен в администраторы.")
            else:
                await update.message.reply_text(f"⚠️ Пользователь {admin_id} уже является администратором.")
        else:
            await update.message.reply_text("❌ У вас нет прав для добавления администраторов.")
        return
    
    # Handle admin removal (for admins only)
    elif text.startswith('-') and text[1:].isdigit():
        if Storage.is_admin(user_id):
            admin_id = int(text[1:])
            if admin_id == user_id:
                await update.message.reply_text("❌ Нельзя удалить себя из администраторов.")
                return
            if admin_id in Storage.bot_config.admin_ids:
                Storage.remove_admin(admin_id)
                await update.message.reply_text(f"✅ Пользователь {admin_id} удален из администраторов.")
            else:
                await update.message.reply_text(f"❌ Пользователь {admin_id} не является администратором.")
        else:
            await update.message.reply_text("❌ У вас нет прав для удаления администраторов.")
        return
    
    # Handle channel configuration (for admins only)
    elif (text.startswith('@') or text.lstrip('-').isdigit() or 't.me/' in text) and Storage.is_admin(user_id):
        await handle_channel_config_text(update, context, text)
        return
    
    # Handle userbot join links
    elif ('t.me/' in text or text.startswith('@')) and USERBOT_ENABLED:
        await handle_userbot_join_text(update, context, text)
        return
    
    # Handle userbot leave (numeric ID)
    elif text.lstrip('-').isdigit() and USERBOT_ENABLED and len(text) > 5:
        await handle_userbot_leave_text(update, context, text)
        return
    
    # Handle threshold setting
    elif text.replace('.', '').isdigit() and 0 <= float(text) <= 1:
        threshold = float(text)
        user = Storage.get_user(user_id)
        user.importance_threshold = threshold
        Storage.update_user(user)
        await update.message.reply_text(
            f"✅ <b>Порог важности установлен:</b> {threshold}\n\n"
            f"💡 Теперь вы будете получать уведомления о сообщениях с важностью выше {threshold}",
            parse_mode=ParseMode.HTML
        )
        return
    
    # If nothing matched, treat as reply button
    button_handled = await handle_reply_buttons(update, context)
    
    # Handle post submission (regular text) - only if not handled by buttons
    if not button_handled and len(text) > 10 and not text.startswith('/'):
        await handle_post_submission_text(update, context, text)
        return

async def handle_channel_config_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle channel configuration from text input."""
    config = Storage.bot_config
    
    # Helper function to extract username from link
    def extract_username_from_link(link: str) -> str:
        link = link.strip()
        if link.startswith('@'):
            return link
        if 't.me/' in link:
            username = link.split('t.me/')[-1]
            username = username.split('?')[0]
            username = username.rstrip('/')
            return f"@{username}"
        if link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '')
            username = username.split('?')[0]
            username = username.rstrip('/')
            return f"@{username}"
        if not link.startswith('@') and not link.startswith('http'):
            return f"@{link}"
        return link
    
    # Process different formats
    if text.startswith('@'):
        # Username format
        config.publish_channel_username = text[1:]  # Remove @
        try:
            # Try to get channel info to validate and get ID
            chat = await context.bot.get_chat(text)
            config.publish_channel_id = chat.id
            Storage.update_config(config)
            
            await update.message.reply_text(
                f"✅ <b>Канал настроен успешно!</b>\n\n"
                f"📋 <b>ID чата:</b> {chat.id}\n"
                f"🏷️ <b>Username:</b> @{html.escape(config.publish_channel_username)}\n"
                f"📝 <b>Название:</b> {html.escape(chat.title)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {html.escape(str(e))}")
    
    elif 't.me/' in text:
        # Link format
        username = extract_username_from_link(text)
        config.publish_channel_username = username[1:]  # Remove @
        try:
            # Try to get channel info to validate and get ID
            chat = await context.bot.get_chat(username)
            config.publish_channel_id = chat.id
            Storage.update_config(config)
            
            await update.message.reply_text(
                f"✅ <b>Канал настроен успешно!</b>\n\n"
                f"📋 <b>ID чата:</b> {chat.id}\n"
                f"🏷️ <b>Username:</b> @{html.escape(config.publish_channel_username)}\n"
                f"📝 <b>Название:</b> {html.escape(chat.title)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {html.escape(str(e))}")
    
    elif text.lstrip('-').isdigit():
        # ID format
        channel_id = int(text)
        config.publish_channel_id = channel_id
        
        try:
            # Try to get channel info
            chat = await context.bot.get_chat(channel_id)
            if chat.username:
                config.publish_channel_username = chat.username
            Storage.update_config(config)
            
            await update.message.reply_text(
                f"✅ <b>Канал настроен успешно!</b>\n\n"
                f"📋 <b>ID канала:</b> {channel_id}\n"
                f"📝 <b>Название:</b> {html.escape(chat.title)}",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            # Save ID even if we can't get info
            Storage.update_config(config)
            await update.message.reply_text(
                f"⚠️ <b>Канал настроен</b>, но не удалось получить информацию: {html.escape(str(e))}\n\n"
                f"📋 <b>ID канала:</b> {channel_id}",
                parse_mode=ParseMode.HTML
            )

async def handle_userbot_join_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle userbot join from text input."""
    try:
        userbot = get_userbot()
        if not userbot.is_running:
            await update.message.reply_text("❌ Сначала запустите userbot кнопкой '🚀 Запустить'")
            return
        
        # Try to join the channel/chat
        result = await userbot.join_chat(text)
        if result:
            await update.message.reply_text(
                f"✅ <b>Успешно присоединился!</b>\n\n"
                f"🔗 <b>Ссылка:</b> {text}\n"
                f"🤖 Userbot начал мониторинг этого источника.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Не удалось присоединиться</b>\n\n"
                f"🔗 <b>Ссылка:</b> {text}\n"
                f"💡 Проверьте корректность ссылки и доступность канала.",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Ошибка присоединения к {text}: {e}")
        await update.message.reply_text(f"❌ Ошибка присоединения: {html.escape(str(e))}")

async def handle_userbot_leave_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle userbot leave from text input."""
    try:
        userbot = get_userbot()
        if not userbot.is_running:
            await update.message.reply_text("❌ Userbot не запущен")
            return
        
        chat_id = int(text)
        result = await userbot.leave_chat(chat_id)
        if result:
            await update.message.reply_text(
                f"✅ <b>Успешно покинул источник</b>\n\n"
                f"📋 <b>ID чата:</b> {chat_id}\n"
                f"🤖 Userbot прекратил мониторинг этого источника.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Не удалось покинуть источник</b>\n\n"
                f"📋 <b>ID чата:</b> {chat_id}",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Ошибка покидания {text}: {e}")
        await update.message.reply_text(f"❌ Ошибка покидания: {html.escape(str(e))}")

async def handle_post_submission_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle post submission from regular text."""
    user_id = update.effective_user.id
    
    # Show confirmation
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, отправить на модерацию", callback_data=f"confirm_submit_text"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_submit")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the text for later use
    context.user_data['pending_post_text'] = text
    
    await update.message.reply_text(
        f"📝 <b>Отправить этот текст как пост?</b>\n\n"
        f"📄 <b>Текст:</b>\n{text[:300]}{'...' if len(text) > 300 else ''}\n\n"
        f"💡 После отправки пост будет рассмотрен администраторами.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# Продолжение в следующем файле...# Финальная часть bot_simplified.py

# ===========================================
# CALLBACK HANDLERS
# ===========================================

async def callback_handler(update: Update, context: CallbackContext) -> None:
    """Handle inline button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Monitoring callbacks
    if data == "monitoring_list":
        await show_monitoring_list(query, context, user)
    
    elif data == "monitoring_remove":
        await show_monitoring_remove(query, context, user)
    
    elif data == "monitoring_threshold":
        await query.edit_message_text(
            "📊 <b>Настройка порога важности</b>\n\n"
            f"Текущий порог: <b>{user.importance_threshold}</b>\n\n"
            "💡 <b>Отправьте число от 0.0 до 1.0</b>\n"
            "Например: 0.7\n\n"
            "🔍 <b>Рекомендации:</b>\n"
            "• 0.3-0.5 - Только очень важные\n"
            "• 0.5-0.7 - Важные (рекомендуется)\n"
            "• 0.7-0.9 - Большинство сообщений",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "monitoring_clear":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear_monitoring"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ <b>Очистить все источники мониторинга?</b>\n\n"
            "Это действие нельзя отменить.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    # Settings callbacks
    elif data == "settings_threshold":
        await query.edit_message_text(
            "📊 <b>Изменение порога важности</b>\n\n"
            f"Текущий порог: <b>{user.importance_threshold}</b>\n\n"
            "💡 <b>Отправьте новое значение от 0.0 до 1.0</b>",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "settings_keywords":
        await show_keywords_interface(update, context, user)
    
    elif data == "settings_clear":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear_data"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ <b>Очистить все ваши данные?</b>\n\n"
            "Будут удалены:\n"
            "• Все источники мониторинга\n"
            "• Ключевые слова\n"
            "• Настройки\n\n"
            "Это действие нельзя отменить!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    # Keywords callbacks
    elif data == "keywords_add_important":
        await query.edit_message_text(
            "➕ <b>Добавление важного слова</b>\n\n"
            "💡 <b>Отправьте слово или фразу</b>\n"
            "Или используйте формат: <code>+слово</code>\n\n"
            "Примеры:\n"
            "• срочно\n"
            "• важная встреча\n"
            "• дедлайн",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "keywords_add_exclude":
        await query.edit_message_text(
            "➖ <b>Добавление исключаемого слова</b>\n\n"
            "💡 <b>Отправьте слово или фразу</b>\n"
            "Или используйте формат: <code>-слово</code>\n\n"
            "Примеры:\n"
            "• реклама\n"
            "• спам\n"
            "• тест",
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("keywords_remove_"):
        keyword_type = data.replace("keywords_remove_", "")
        await show_keywords_remove(query, context, user, keyword_type)
    
    elif data == "keywords_clear_all":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear_keywords"),
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_clear")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ <b>Очистить все ключевые слова?</b>\n\n"
            "Будут удалены все важные и исключаемые слова.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    # Admin callbacks
    elif data == "admin_toggle_autopublish":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            config.auto_publish_enabled = not config.auto_publish_enabled
            Storage.update_config(config)
            
            await query.edit_message_text(
                f"✅ Автопубликация {'включена' if config.auto_publish_enabled else 'отключена'}.",
            )
    
    elif data == "admin_toggle_approval":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            config.require_admin_approval = not config.require_admin_approval
            Storage.update_config(config)
            
            await query.edit_message_text(
                f"✅ Требование одобрения {'включено' if config.require_admin_approval else 'отключено'}."
            )
    
    elif data.startswith("admin_approve_"):
        if Storage.is_admin(user_id):
            post_id = data.replace("admin_approve_", "")
            success = await AdminService.approve_post(context.bot, post_id, user_id)
            
            if success:
                await query.edit_message_text(f"✅ Пост {post_id} одобрен и опубликован!")
            else:
                await query.edit_message_text(f"❌ Ошибка при одобрении поста {post_id}.")
    
    elif data.startswith("admin_reject_"):
        if Storage.is_admin(user_id):
            post_id = data.replace("admin_reject_", "")
            success = await AdminService.reject_post(context.bot, post_id, user_id, "Отклонен администратором")
            
            if success:
                await query.edit_message_text(f"❌ Пост {post_id} отклонен.")
            else:
                await query.edit_message_text(f"❌ Ошибка при отклонении поста {post_id}.")
    
    elif data.startswith("admin_full_"):
        if Storage.is_admin(user_id):
            post_id = data.replace("admin_full_", "")
            post = Storage.get_pending_post(post_id)
            
            if post:
                full_text = (
                    f"📄 <b>Полный текст поста</b> (ID: {post.post_id})\n\n"
                    f"👤 <b>От:</b> {post.user_id}\n"
                    f"📅 <b>Время:</b> {post.submitted_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"📝 <b>Текст:</b>\n{post.message_text}"
                )
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve_{post.post_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{post.post_id}")
                    ]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(full_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await query.edit_message_text("❌ Пост не найден.")
    
    # Post submission callbacks
    elif data == "confirm_submit_text":
        pending_text = context.user_data.get('pending_post_text')
        if pending_text:
            try:
                post_id = await AdminService.submit_post_for_review(user_id, pending_text)
                
                # Notify admins
                post = Storage.get_pending_post(post_id)
                if post:
                    await AdminService.notify_admins_about_new_post(context.bot, post)
                
                await query.edit_message_text(
                    f"✅ <b>Пост отправлен на модерацию!</b>\n\n"
                    f"📋 <b>ID поста:</b> {post_id}\n"
                    f"⏳ <b>Статус:</b> Ожидает рассмотрения",
                    parse_mode=ParseMode.HTML
                )
                
                # Clear stored text
                context.user_data.pop('pending_post_text', None)
                
            except Exception as e:
                await query.edit_message_text(f"❌ Ошибка при отправке поста: {e}")
        else:
            await query.edit_message_text("❌ Текст поста не найден.")
    
    elif data == "cancel_submit":
        context.user_data.pop('pending_post_text', None)
        await query.edit_message_text("❌ Отправка поста отменена.")
    
    # Confirmation callbacks
    elif data == "confirm_clear_monitoring":
        user.monitored_chats.clear()
        user.monitored_channels.clear()
        Storage.update_user(user)
        await query.edit_message_text("✅ Все источники мониторинга очищены.")
    
    elif data == "confirm_clear_data":
        user.monitored_chats.clear()
        user.monitored_channels.clear()
        user.keywords.clear()
        user.exclude_keywords.clear()
        user.importance_threshold = DEFAULT_IMPORTANCE_THRESHOLD
        Storage.update_user(user)
        await query.edit_message_text("✅ Все ваши данные очищены.")
    
    elif data == "confirm_clear_keywords":
        user.keywords.clear()
        user.exclude_keywords.clear()
        Storage.update_user(user)
        await query.edit_message_text("✅ Все ключевые слова очищены.")
    
    elif data == "cancel_clear":
        await query.edit_message_text("❌ Действие отменено.")
    
    # Refresh callbacks
    elif data == "stats_refresh":
        await show_statistics_interface(update, context, user)
    
    elif data == "admin_stats_refresh":
        if Storage.is_admin(user_id):
            await show_admin_statistics(update, context)
    
    elif data == "userbot_status_refresh":
        if USERBOT_ENABLED:
            await show_userbot_status(update, context)
    
    # Help callbacks
    elif data == "help_quickstart":
        await show_quickstart_help(query)
    
    elif data == "help_userbot":
        await show_userbot_help(query)
    
    elif data == "help_tips":
        await show_tips_help(query)
    
    elif data == "help_faq":
        await show_faq_help(query)
    
    # Navigation callbacks
    elif data == "goto_userbot":
        if USERBOT_ENABLED:
            await show_userbot_interface(update, context)
        else:
            await query.edit_message_text("❌ Userbot отключен.")
    
    # Monitoring callbacks for forwarded messages
    elif data.startswith("add_passive_monitoring_"):
        parts = data.replace("add_passive_monitoring_", "").split("_")
        chat_id = int(parts[0])
        source_type = parts[1]
        
        user = Storage.get_user(user_id)
        if source_type == "channel":
            user.monitored_channels.add(chat_id)
        else:
            user.monitored_chats.add(chat_id)
        
        Storage.update_user(user)
        await query.edit_message_text(
            f"✅ <b>Источник добавлен в мониторинг!</b>\n\n"
            f"📊 {'Канал' if source_type == 'channel' else 'Чат'} (ID: {chat_id}) теперь отслеживается.\n\n"
            f"💡 Пересылайте сообщения из этого источника для автоматического анализа.",
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("analyze_once_"):
        parts = data.replace("analyze_once_", "").split("_")
        chat_id = int(parts[0])
        source_type = parts[1]
        
        # Get the forwarded message from context
        if update.effective_message and hasattr(update.effective_message, 'reply_to_message'):
            forwarded_msg = update.effective_message.reply_to_message
            
            # Create message object for analysis
            message = Message(
                message_id=forwarded_msg.message_id,
                chat_id=chat_id,
                chat_title=f"{'Канал' if source_type == 'channel' else 'Чат'} {chat_id}",
                text=forwarded_msg.text or forwarded_msg.caption or "",
                date=datetime.now(),
                is_channel=source_type == "channel"
            )
            
            # Analyze importance
            user = Storage.get_user(user_id)
            importance_score = await evaluate_message_importance(message, user)
            
            result_text = (
                f"🔍 <b>Анализ завершен</b>\n\n"
                f"📊 <b>Оценка важности:</b> {importance_score:.2f}\n"
                f"🎯 <b>Ваш порог:</b> {user.importance_threshold}\n\n"
                f"{'✅ Сообщение важное!' if importance_score >= user.importance_threshold else '❌ Сообщение не достигает порога важности.'}\n\n"
                f"💡 Источник не сохранен в мониторинг."
            )
            
            await query.edit_message_text(result_text, parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text("❌ Не удалось найти сообщение для анализа.")
    
    elif data == "skip_monitoring":
        await query.edit_message_text("❌ Мониторинг пропущен.")
    
    elif data.startswith("submit_forwarded_"):
        message_id = data.replace("submit_forwarded_", "")
        
        # Get the original forwarded message
        try:
            # This is a simplified approach - in a real implementation,
            # you might want to store the message content temporarily
            await query.edit_message_text(
                "📝 <b>Функция в разработке</b>\n\n"
                "Используйте кнопку 'Предложить пост' в главном меню "
                "или команду /submit_post для отправки поста на модерацию.",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке submit_forwarded: {e}")
            await query.edit_message_text("❌ Ошибка при отправке поста.")
    
    # Source removal callbacks
    elif data.startswith("remove_chat_"):
        chat_id = int(data.replace("remove_chat_", ""))
        user.monitored_chats.discard(chat_id)
        Storage.update_user(user)
        await query.edit_message_text(f"✅ Чат {chat_id} удален из мониторинга.")
    
    elif data.startswith("remove_channel_"):
        channel_id = int(data.replace("remove_channel_", ""))
        user.monitored_channels.discard(channel_id)
        Storage.update_user(user)
        await query.edit_message_text(f"✅ Канал {channel_id} удален из мониторинга.")
    
    # Keyword removal callbacks
    elif data.startswith("delete_keyword_"):
        parts = data.replace("delete_keyword_", "").split("_", 2)
        keyword_type = parts[0]
        keyword = "_".join(parts[1:])  # Rejoin in case keyword contains underscores
        
        if keyword_type == "important":
            if keyword in user.keywords:
                user.keywords.remove(keyword)
                Storage.update_user(user)
                await query.edit_message_text(f"✅ Важное слово '{keyword}' удалено.")
            else:
                await query.edit_message_text(f"❌ Слово '{keyword}' не найдено.")
        else:
            if keyword in user.exclude_keywords:
                user.exclude_keywords.remove(keyword)
                Storage.update_user(user)
                await query.edit_message_text(f"✅ Исключаемое слово '{keyword}' удалено.")
            else:
                await query.edit_message_text(f"❌ Слово '{keyword}' не найдено.")

# ===========================================
# HELPER FUNCTIONS FOR CALLBACKS
# ===========================================

async def show_monitoring_list(query, context: CallbackContext, user: UserPreferences) -> None:
    """Show list of monitored sources."""
    if not user.monitored_chats and not user.monitored_channels:
        await query.edit_message_text("❌ Вы не мониторите ни одного источника.")
        return
    
    list_text = "📋 <b>Список мониторимых источников:</b>\n\n"
    
    if user.monitored_chats:
        list_text += "💬 <b>Чаты:</b>\n"
        for chat_id in user.monitored_chats:
            list_text += f"• {chat_id}\n"
        list_text += "\n"
    
    if user.monitored_channels:
        list_text += "📢 <b>Каналы:</b>\n"
        for channel_id in user.monitored_channels:
            list_text += f"• {channel_id}\n"
    
    await query.edit_message_text(list_text, parse_mode=ParseMode.HTML)

async def show_monitoring_remove(query, context: CallbackContext, user: UserPreferences) -> None:
    """Show interface to remove monitored sources."""
    if not user.monitored_chats and not user.monitored_channels:
        await query.edit_message_text("❌ Нет источников для удаления.")
        return
    
    keyboard = []
    
    # Add chat buttons
    for chat_id in user.monitored_chats:
        keyboard.append([InlineKeyboardButton(f"💬 Чат: {chat_id}", callback_data=f"remove_chat_{chat_id}")])
    
    # Add channel buttons
    for channel_id in user.monitored_channels:
        keyboard.append([InlineKeyboardButton(f"📢 Канал: {channel_id}", callback_data=f"remove_channel_{channel_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🗑️ <b>Выберите источник для удаления:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_keywords_remove(query, context: CallbackContext, user: UserPreferences, keyword_type: str) -> None:
    """Show interface to remove keywords."""
    keywords_list = user.keywords if keyword_type == "important" else user.exclude_keywords
    type_name = "важные" if keyword_type == "important" else "исключаемые"
    
    if not keywords_list:
        await query.edit_message_text(f"❌ Нет {type_name} слов для удаления.")
        return
    
    keyboard = []
    for keyword in keywords_list[:20]:  # Limit to 20 to avoid keyboard size issues
        callback_data = f"delete_keyword_{keyword_type}_{keyword}"
        keyboard.append([InlineKeyboardButton(f"🗑️ {keyword}", callback_data=callback_data)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🗑️ <b>Выберите {type_name} слово для удаления:</b>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

# Help functions
async def show_quickstart_help(query) -> None:
    """Show quickstart help."""
    help_text = (
        "🚀 <b>Быстрый старт</b>\n\n"
        "1️⃣ <b>Перешлите сообщение</b>\n"
        "Перешлите интересное сообщение из любого чата или канала боту\n\n"
        "2️⃣ <b>Добавьте в мониторинг</b>\n"
        "Выберите 'Добавить в мониторинг' в предложенном меню\n\n"
        "3️⃣ <b>Настройте фильтры</b>\n"
        "• Добавьте ключевые слова: +важно\n"
        "• Настройте порог важности: 0.7\n\n"
        "4️⃣ <b>Готово!</b>\n"
        "Получайте уведомления о важных сообщениях"
    )
    
    await query.edit_message_text(help_text, parse_mode=ParseMode.HTML)

async def show_userbot_help(query) -> None:
    """Show userbot help."""
    help_text = (
        "🤖 <b>Настройка Userbot</b>\n\n"
        "🔧 <b>Требования:</b>\n"
        "• API ID и API Hash с my.telegram.org\n"
        "• Отдельный номер телефона\n\n"
        "⚙️ <b>Настройка:</b>\n"
        "1. Добавьте в .env файл:\n"
        "   TELEGRAM_API_ID=your_id\n"
        "   TELEGRAM_API_HASH=your_hash\n"
        "   TELEGRAM_PHONE=+1234567890\n\n"
        "2. Запустите userbot кнопкой '🚀 Запустить'\n"
        "3. Присоединяйтесь к каналам\n\n"
        "🔥 <b>Преимущества:</b>\n"
        "• Полная анонимность\n"
        "• Работает с закрытыми каналами\n"
        "• Анализирует ВСЕ сообщения"
    )
    
    await query.edit_message_text(help_text, parse_mode=ParseMode.HTML)

async def show_tips_help(query) -> None:
    """Show tips help."""
    help_text = (
        "💡 <b>Полезные советы</b>\n\n"
        "🔑 <b>Ключевые слова:</b>\n"
        "• Используйте конкретные термины\n"
        "• Добавляйте синонимы\n"
        "• Исключайте шум (+важно, -реклама)\n\n"
        "📊 <b>Порог важности:</b>\n"
        "• 0.3-0.5: Только критически важные\n"
        "• 0.5-0.7: Сбалансированный режим\n"
        "• 0.7-0.9: Большинство сообщений\n\n"
        "🤖 <b>Userbot:</b>\n"
        "• Лучший способ мониторинга\n"
        "• Работает 24/7 автоматически\n"
        "• Никто не знает о мониторинге\n\n"
        "📝 <b>Посты:</b>\n"
        "• Предлагайте интересный контент\n"
        "• Используйте пересланные сообщения\n"
        "• Следите за уведомлениями о статусе"
    )
    
    await query.edit_message_text(help_text, parse_mode=ParseMode.HTML)

async def show_faq_help(query) -> None:
    """Show FAQ help."""
    help_text = (
        "❓ <b>Часто задаваемые вопросы</b>\n\n"
        "<b>Q: Как добавить закрытый канал?</b>\n"
        "A: Используйте Userbot - он может присоединяться к любым каналам\n\n"
        "<b>Q: Почему не приходят уведомления?</b>\n"
        "A: Проверьте порог важности и ключевые слова\n\n"
        "<b>Q: Можно ли мониторить без добавления бота?</b>\n"
        "A: Да, используйте пассивный мониторинг или Userbot\n\n"
        "<b>Q: Как предложить пост для публикации?</b>\n"
        "A: Используйте кнопку 'Предложить пост' или команду /submit_post\n\n"
        "<b>Q: Бот не отвечает на команды</b>\n"
        "A: Используйте кнопки вместо команд - это удобнее\n\n"
        "<b>Q: Как стать администратором?</b>\n"
        "A: Обратитесь к текущему администратору"
    )
    
    await query.edit_message_text(help_text, parse_mode=ParseMode.HTML)

# ===========================================
# MESSAGE HANDLING FOR FORWARDED MESSAGES
# ===========================================

async def handle_message_forwarded(update: Update, context: CallbackContext) -> None:
    """Handle incoming forwarded messages and monitoring."""
    logger.info(f"Получено сообщение: {update.message.text[:50] if update.message.text else 'Нет текста'}")
    logger.info(f"Сообщение переслано: {hasattr(update.message, 'forward_origin')}")
    logger.info(f"Тип чата: {update.message.chat.type if update.message.chat else 'Нет чата'}")
    logger.info(f"ID чата: {update.message.chat.id if update.message.chat else 'Нет ID'}")
    
    # Handle forwarded messages (PASSIVE MONITORING - no admin rights needed)
    if update.message and hasattr(update.message, 'forward_origin') and update.message.forward_origin:
        user_id = update.effective_user.id
        user = Storage.get_user(user_id)
        
        # Handle different types of forward origins
        chat_id = None
        chat_title = "Неизвестный источник"
        is_channel = False
        
        # Check if forwarded from a chat/channel
        if hasattr(update.message.forward_origin, 'chat') and update.message.forward_origin.chat:
            chat = update.message.forward_origin.chat
            chat_id = chat.id
            chat_title = chat.title or f"Чат {chat_id}"
            is_channel = chat.type == "channel"
        # Check if forwarded from a user (private chat)
        elif hasattr(update.message.forward_origin, 'sender_user') and update.message.forward_origin.sender_user:
            sender = update.message.forward_origin.sender_user
            chat_id = sender.id
            chat_title = f"Личные сообщения от {sender.full_name}"
            is_channel = False
        # Check if forwarded from hidden user
        elif hasattr(update.message.forward_origin, 'sender_user_name'):
            chat_title = f"Пересланное от {update.message.forward_origin.sender_user_name}"
            chat_id = hash(update.message.forward_origin.sender_user_name)  # Create pseudo-ID
            is_channel = False
        
        if chat_id:
            logger.info(f"Обрабатываю пересланное сообщение из {chat_title} (ID: {chat_id}, тип: {'канал' if is_channel else 'чат'})")
            
            # Check if this source is already being monitored (passive or active)
            is_already_monitored = False
            monitoring_type = "неизвестно"
            
            if is_channel:
                is_already_monitored = chat_id in user.monitored_channels
                monitoring_type = "канал"
            else:
                is_already_monitored = chat_id in user.monitored_chats
                monitoring_type = "чат"
            
            # Always analyze forwarded messages from monitored sources
            if is_already_monitored:
                # Process the message to analyze its importance
                message = Message(
                    message_id=update.message.message_id,
                    chat_id=chat_id,
                    chat_title=chat_title,
                    text=update.message.text or update.message.caption or "",
                    date=datetime.now(),
                    is_channel=is_channel
                )
                
                # Extract sender info if available
                if hasattr(update.message.forward_origin, 'sender_user') and update.message.forward_origin.sender_user:
                    message.sender_id = update.message.forward_origin.sender_user.id
                    message.sender_name = update.message.forward_origin.sender_user.full_name
                elif hasattr(update.message.forward_origin, 'sender_user_name'):
                    message.sender_name = update.message.forward_origin.sender_user_name
                
                logger.info(f"Анализирую пересланное сообщение: {message.text[:50]}...")
                
                # Analyze message importance
                importance_score = await evaluate_message_importance(message, user)
                message.importance_score = importance_score
                
                logger.info(f"Оценка важности: {importance_score:.2f}, порог: {user.importance_threshold}")
                
                # Check if the message is important enough to notify the user
                if importance_score >= user.importance_threshold:
                    # Create keyboard with option to submit for publication
                    keyboard = [
                        [InlineKeyboardButton("📝 Предложить для публикации", callback_data=f"submit_forwarded_{update.message.message_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"🔔 <b>ВАЖНОЕ СООБЩЕНИЕ ОБНАРУЖЕНО</b>\n\n"
                        f"{message.to_user_notification()}\n\n"
                        f"📋 <i>Источник: Пассивный мониторинг (пересланное сообщение)</i>\n\n"
                        f"💡 <b>Хотите предложить это сообщение для публикации в канале?</b>",
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                    
                    # Process important message for potential publication
                    try:
                        published = await AdminService.process_important_message(context.bot, message, importance_score)
                        if published:
                            logger.info(f"Важное пересланное сообщение автоматически опубликовано в канале (оценка: {importance_score:.2f})")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке важного сообщения для публикации: {e}")
                else:
                    # Also offer to submit less important messages
                    keyboard = [
                        [InlineKeyboardButton("📝 Всё равно предложить для публикации", callback_data=f"submit_forwarded_{update.message.message_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"📊 <b>Анализ завершен</b>\n\n"
                        f"Сообщение из {chat_title} имеет оценку важности <b>{importance_score:.2f}</b>, "
                        f"что ниже вашего порога <b>{user.importance_threshold}</b>.\n\n"
                        f"💡 Вы можете изменить порог важности в настройках.",
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                return
            
            # Offer to add to passive monitoring
            keyboard = [
                [InlineKeyboardButton("✅ Добавить в мониторинг", callback_data=f"add_passive_monitoring_{chat_id}_{'channel' if is_channel else 'chat'}")],
                [InlineKeyboardButton("🔍 Просто проанализировать", callback_data=f"analyze_once_{chat_id}_{'channel' if is_channel else 'chat'}")],
                [InlineKeyboardButton("❌ Пропустить", callback_data="skip_monitoring")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔍 <b>Обнаружен новый источник:</b> {chat_title}\n\n"
                f"📊 <b>Варианты действий:</b>\n\n"
                f"🟢 <b>Добавить в мониторинг</b>\n"
                f"• Анализ всех пересланных сообщений\n"
                f"• Автоматические уведомления о важных сообщениях\n"
                f"• Не требует прав администратора\n\n"
                f"🔍 <b>Разовый анализ</b>\n"
                f"• Анализ только этого сообщения\n"
                f"• Без сохранения в мониторинг\n\n"
                f"💡 <b>Преимущество:</b> Работает с любыми чатами и каналами, "
                f"даже закрытыми, без необходимости добавления бота!",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return
    
    # Handle direct messages from channels/groups (ACTIVE MONITORING - when bot is added)
    elif update.message and update.message.chat and update.message.chat.type in ["channel", "group", "supergroup"]:
        chat_id = update.message.chat.id
        chat_title = update.message.chat.title or "Неизвестный чат"
        is_channel = update.message.chat.type == "channel"
        
        logger.info(f"Получено прямое сообщение из {'канала' if is_channel else 'чата'}: {chat_title} (ID: {chat_id})")
        
        # Check if this chat/channel is being monitored by any user
        if is_channel:
            monitored_users = Storage.get_users_monitoring_channel(chat_id)
        else:
            monitored_users = Storage.get_users_monitoring_chat(chat_id)
        
        logger.info(f"Пользователи, мониторящие {'канал' if is_channel else 'чат'} {chat_id}: {len(monitored_users)}")
        
        if not monitored_users:
            logger.info(f"Нет пользователей, мониторящих {'канал' if is_channel else 'чат'} {chat_id}")
            return
        
        # Create message object
        message = Message(
            message_id=update.message.message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            text=update.message.text or update.message.caption or "",
            date=datetime.now(),
            is_channel=is_channel
        )
        
        if update.message.from_user:
            message.sender_id = update.message.from_user.id
            message.sender_name = update.message.from_user.full_name
        
        logger.info(f"Анализирую сообщение для {len(monitored_users)} пользователей: {message.text[:50]}...")
        
        # Analyze message for each monitoring user and find highest importance score
        max_importance_score = 0
        notified_users = []
        
        for user in monitored_users:
            try:
                importance_score = await evaluate_message_importance(message, user)
                message.importance_score = importance_score
                max_importance_score = max(max_importance_score, importance_score)
                
                logger.info(f"Оценка важности для пользователя {user.user_id}: {importance_score:.2f}, порог: {user.importance_threshold}")
                
                # If message is important enough, send notification to user
                if importance_score >= user.importance_threshold:
                    notification_text = (
                        f"🔔 <b>ВАЖНОЕ СООБЩЕНИЕ</b>\n\n"
                        f"{message.to_user_notification()}\n\n"
                        f"📋 <i>Источник: Активный мониторинг (бот в чате/канале)</i>"
                    )
                    
                    # Send notification to the user
                    await context.bot.send_message(
                        chat_id=user.user_id,
                        text=notification_text,
                        parse_mode=ParseMode.HTML
                    )
                    
                    notified_users.append(user.user_id)
                    logger.info(f"Отправлено уведомление пользователю {user.user_id} "
                              f"из {chat_title} (оценка: {importance_score:.2f})")
                else:
                    logger.info(f"Сообщение не достаточно важно для пользователя {user.user_id} "
                              f"(оценка: {importance_score:.2f}, порог: {user.importance_threshold})")
                    
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения для пользователя {user.user_id}: {e}")
        
        # If message was important for at least one user, consider it for channel publication
        if notified_users and max_importance_score > 0:
            message.importance_score = max_importance_score
            try:
                published = await AdminService.process_important_message(context.bot, message, max_importance_score)
                if published:
                    logger.info(f"Важное сообщение из {chat_title} автоматически опубликовано в канале (оценка: {max_importance_score:.2f})")
            except Exception as e:
                logger.error(f"Ошибка при обработке важного сообщения для публикации: {e}")

# ===========================================
# MAIN FUNCTION
# ===========================================

def main() -> None:
    """Start the simplified bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add minimal essential command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("submit_post", submit_post_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Add text message handler (handles reply buttons and text input)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    # Add message handler for forwarded messages and monitoring
    application.add_handler(MessageHandler(filters.ALL & ~filters.TEXT, handle_message_forwarded))
    
    # Make application globally available for userbot
    globals()['application'] = application
    
    logger.info("🚀 Упрощенный бот запущен!")
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()