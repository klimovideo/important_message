import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

from config import TELEGRAM_TOKEN, DEFAULT_IMPORTANCE_THRESHOLD
from models import Message, Storage, UserPreferences
from ai_service import evaluate_message_importance
from utils import setup_logging

# Setup logging
setup_logging()

# Enable logging
logger = logging.getLogger(__name__)

# Command handlers
async def start_command(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    welcome_text = (
        f"🤖 Добро пожаловать в бота важных сообщений!\n\n"
        f"Я буду анализировать сообщения из ваших чатов и каналов с помощью ИИ "
        f"и уведомлять вас только о важных сообщениях.\n\n"
        f"📊 Ваши текущие настройки:\n"
        f"• Порог важности: {user.importance_threshold}\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n\n"
        f"💡 Используйте меню ниже для навигации"
    )
    
    # Create main menu keyboard
    keyboard = [
        [
            InlineKeyboardButton("📋 Справка", callback_data="menu_help"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")
        ],
        [
            InlineKeyboardButton("📊 Мониторинг", callback_data="menu_monitoring"),
            InlineKeyboardButton("🔑 Ключевые слова", callback_data="menu_keywords")
        ],
        [
            InlineKeyboardButton("🚀 Быстрая настройка", callback_data="menu_setup"),
            InlineKeyboardButton("💡 Советы", callback_data="menu_tips")
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="menu_stats"),
            InlineKeyboardButton("🗑️ Очистить данные", callback_data="menu_clear_data")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: CallbackContext) -> None:
    """Send a help message when the command /help is issued."""
    help_text = (
        "🤖 <b>Бот важных сообщений - Справка</b>\n\n"
        "📋 <b>Основные команды:</b>\n"
        "• /start - Запустить бота\n"
        "• /menu - Главное меню (рекомендуется)\n"
        "• /help - Показать эту справку\n"
        "• /settings - Просмотр настроек\n"
        "• /stats - Статистика использования\n"
        "• /setup - Быстрая настройка\n"
        "• /tips - Полезные советы\n\n"
        "📊 <b>Мониторинг:</b>\n"
        "• /monitor - Добавить чат/канал для мониторинга\n"
        "• /unmonitor - Удалить чат/канал из мониторинга\n"
        "• /list - Список мониторимых чатов и каналов\n\n"
        "🔑 <b>Ключевые слова:</b>\n"
        "• /add_keyword - Добавить важное слово\n"
        "• /remove_keyword - Удалить слово\n"
        "• /keywords - Список ваших слов\n\n"
        "⚙️ <b>Настройки:</b>\n"
        "• /threshold - Установить порог важности (0.0-1.0)\n"
        "• /clear_data - Очистить все данные\n\n"
        "💡 <b>Как использовать:</b>\n"
        "1. Добавьте бота в чаты/каналы для мониторинга\n"
        "2. Перешлите сообщение из чата/канала боту\n"
        "3. Ответьте /monitor на пересланное сообщение\n"
        "4. Бот автоматически анализирует и уведомляет о важных сообщениях\n\n"
        "🎛️ <b>Совет:</b> Используйте /menu для удобной навигации по всем функциям!"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def settings_command(update: Update, context: CallbackContext) -> None:
    """Display current settings."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    keywords = ", ".join(user.keywords) if user.keywords else "Не указаны"
    exclude_keywords = ", ".join(user.exclude_keywords) if user.exclude_keywords else "Не указаны"
    
    settings_text = (
        f"⚙️ <b>Ваши настройки:</b>\n\n"
        f"📊 <b>Основные параметры:</b>\n"
        f"• Порог важности: {user.importance_threshold}\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n\n"
        f"🔑 <b>Ключевые слова:</b>\n"
        f"• Важные слова: {keywords}\n"
        f"• Исключаемые слова: {exclude_keywords}\n\n"
        f"💡 Используйте команды для изменения настроек"
    )
    await update.message.reply_text(settings_text, parse_mode=ParseMode.HTML)

async def monitor_command(update: Update, context: CallbackContext) -> None:
    """Add a chat or channel to monitor."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    logger.info(f"Вызвана команда /monitor пользователем {user_id}")
    logger.info(f"Сообщение является ответом: {update.message.reply_to_message is not None}")
    
    # Check if this is a reply to a forwarded message
    if (update.message.reply_to_message and 
        hasattr(update.message.reply_to_message, 'forward_origin') and 
        update.message.reply_to_message.forward_origin):
        
        forward_origin = update.message.reply_to_message.forward_origin
        logger.info(f"Forward origin: {forward_origin}")
        
        # Check if it's from a chat
        if hasattr(forward_origin, 'chat'):
            chat = forward_origin.chat
            chat_id = chat.id
            chat_title = chat.title or "Неизвестный чат"
            is_channel = chat.type == "channel"
            
            logger.info(f"Добавляю {'канал' if is_channel else 'чат'} в мониторинг: {chat_title} (ID: {chat_id})")
            
            # Add the chat/channel to the monitored list
            if is_channel:
                user.monitored_channels.add(chat_id)
                logger.info(f"Добавлен канал {chat_id} в мониторинг для пользователя {user_id}")
            else:
                user.monitored_chats.add(chat_id)
                logger.info(f"Добавлен чат {chat_id} в мониторинг для пользователя {user_id}")
            
            Storage.update_user(user)
            await update.message.reply_text(
                f"✅ Теперь мониторится {chat_title} ({chat_id}).\n"
                f"Я буду уведомлять вас о важных сообщениях из этого {'канала' if is_channel else 'чата'}."
            )
            return
        else:
            logger.info("Forward origin не содержит chat")
    else:
        logger.info("Сообщение не является ответом на пересланное сообщение")
        if update.message.reply_to_message:
            logger.info(f"Reply to message имеет forward_origin: {hasattr(update.message.reply_to_message, 'forward_origin')}")
            if hasattr(update.message.reply_to_message, 'forward_origin'):
                logger.info(f"Forward origin значение: {update.message.reply_to_message.forward_origin}")
    
    # If no forwarded message in reply, show instructions
    await update.message.reply_text(
        "📋 <b>Как добавить чат/канал для мониторинга:</b>\n\n"
        "1️⃣ Добавьте бота в чат или канал\n"
        "2️⃣ Перешлите любое сообщение из этого чата/канала боту\n"
        "3️⃣ Ответьте на пересланное сообщение командой /monitor\n\n"
        "✅ После этого бот будет автоматически анализировать все сообщения "
        "из этого чата/канала и уведомлять вас о важных.",
        parse_mode=ParseMode.HTML
    )

async def unmonitor_command(update: Update, context: CallbackContext) -> None:
    """Remove a chat or channel from monitoring."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Create keyboard with monitored chats/channels
    keyboard = []
    
    # Add chat buttons
    for chat_id in user.monitored_chats:
        keyboard.append([InlineKeyboardButton(f"💬 Чат: {chat_id}", callback_data=f"unmonitor_chat_{chat_id}")])
    
    # Add channel buttons
    for channel_id in user.monitored_channels:
        keyboard.append([InlineKeyboardButton(f"📢 Канал: {channel_id}", callback_data=f"unmonitor_channel_{channel_id}")])
    
    if not keyboard:
        await update.message.reply_text("❌ Вы не мониторите ни один чат или канал.")
        return
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🗑️ Выберите чат или канал для удаления из мониторинга:",
        reply_markup=reply_markup
    )

async def list_command(update: Update, context: CallbackContext) -> None:
    """List all monitored chats and channels."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    if not user.monitored_chats and not user.monitored_channels:
        await update.message.reply_text("❌ Вы не мониторите ни один чат или канал.")
        return
    
    response = "📋 <b>Мониторимые чаты и каналы:</b>\n\n"
    
    if user.monitored_chats:
        response += "💬 <b>Чаты:</b>\n"
        for chat_id in user.monitored_chats:
            response += f"• {chat_id}\n"
        response += "\n"
    
    if user.monitored_channels:
        response += "📢 <b>Каналы:</b>\n"
        for channel_id in user.monitored_channels:
            response += f"• {channel_id}\n"
    
    await update.message.reply_text(response, parse_mode=ParseMode.HTML)

async def add_keyword_command(update: Update, context: CallbackContext) -> None:
    """Add a keyword to prioritize."""
    if not context.args:
        await update.message.reply_text(
            "🔑 <b>Добавление ключевого слова:</b>\n\n"
            "Использование: /add_keyword <слово>\n\n"
            "Примеры:\n"
            "• /add_keyword срочно\n"
            "• /add_keyword важная встреча\n"
            "• /add_keyword дедлайн",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyword = " ".join(context.args).lower()
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    if keyword not in user.keywords:
        user.keywords.append(keyword)
        Storage.update_user(user)
        await update.message.reply_text(f"✅ Добавлено ключевое слово: <b>{keyword}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"⚠️ Слово '<b>{keyword}</b>' уже есть в вашем списке.", parse_mode=ParseMode.HTML)

async def remove_keyword_command(update: Update, context: CallbackContext) -> None:
    """Remove a keyword."""
    if not context.args:
        await update.message.reply_text(
            "🗑️ <b>Удаление ключевого слова:</b>\n\n"
            "Использование: /remove_keyword <слово>\n\n"
            "Примеры:\n"
            "• /remove_keyword срочно\n"
            "• /remove_keyword важная встреча",
            parse_mode=ParseMode.HTML
        )
        return
    
    keyword = " ".join(context.args).lower()
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    if keyword in user.keywords:
        user.keywords.remove(keyword)
        Storage.update_user(user)
        await update.message.reply_text(f"✅ Удалено ключевое слово: <b>{keyword}</b>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Слово '<b>{keyword}</b>' не найдено в вашем списке.", parse_mode=ParseMode.HTML)

async def keywords_command(update: Update, context: CallbackContext) -> None:
    """List all keywords."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    if not user.keywords:
        await update.message.reply_text("❌ У вас нет добавленных ключевых слов.")
        return
    
    keywords_text = "🔑 <b>Ваши ключевые слова:</b>\n\n" + "\n".join(f"• {keyword}" for keyword in user.keywords)
    await update.message.reply_text(keywords_text, parse_mode=ParseMode.HTML)

async def threshold_command(update: Update, context: CallbackContext) -> None:
    """Set importance threshold."""
    if not context.args:
        current_threshold = Storage.get_user(update.effective_user.id).importance_threshold
        await update.message.reply_text(
            f"📊 <b>Порог важности:</b>\n\n"
            f"Текущий порог: <b>{current_threshold}</b>\n\n"
            f"Использование: /threshold <0.0-1.0>\n\n"
            f"💡 <b>Рекомендации:</b>\n"
            f"• 0.3-0.5 - Только очень важные сообщения\n"
            f"• 0.5-0.7 - Важные сообщения (по умолчанию)\n"
            f"• 0.7-0.9 - Большинство сообщений\n\n"
            f"Примеры:\n"
            f"• /threshold 0.5\n"
            f"• /threshold 0.8",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        threshold = float(context.args[0])
        if not 0.0 <= threshold <= 1.0:
            await update.message.reply_text("❌ Порог должен быть от 0.0 до 1.0")
            return
        
        user_id = update.effective_user.id
        user = Storage.get_user(user_id)
        user.importance_threshold = threshold
        Storage.update_user(user)
        
        await update.message.reply_text(f"✅ Порог важности установлен: <b>{threshold}</b>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, укажите число от 0.0 до 1.0")

async def stats_command(update: Update, context: CallbackContext) -> None:
    """Show bot statistics."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    all_users = Storage.get_all_users()
    total_users = len(all_users)
    total_monitored_chats = sum(len(u.monitored_chats) for u in all_users.values())
    total_monitored_channels = sum(len(u.monitored_channels) for u in all_users.values())
    
    stats_text = (
        f"📊 <b>Статистика бота:</b>\n\n"
        f"👤 <b>Ваша статистика:</b>\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n"
        f"• Ключевых слов: {len(user.keywords)}\n"
        f"• Порог важности: {user.importance_threshold}\n\n"
        f"🌐 <b>Общая статистика:</b>\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Всего мониторится чатов: {total_monitored_chats}\n"
        f"• Всего мониторится каналов: {total_monitored_channels}"
    )
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)

async def clear_data_command(update: Update, context: CallbackContext) -> None:
    """Clear all user data."""
    user_id = update.effective_user.id
    
    # Create confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, очистить все данные", callback_data="clear_data_confirm"),
            InlineKeyboardButton("❌ Отмена", callback_data="clear_data_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ <b>Очистка данных</b>\n\n"
        "Вы уверены, что хотите очистить все ваши данные?\n"
        "Это удалит все мониторимые чаты, каналы и ключевые слова.\n"
        "Это действие нельзя отменить.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def setup_command(update: Update, context: CallbackContext) -> None:
    """Quick setup wizard for new users."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Check if user already has some setup
    if user.monitored_chats or user.monitored_channels or user.keywords:
        await update.message.reply_text(
            "⚠️ <b>Быстрая настройка</b>\n\n"
            "У вас уже есть настроенные чаты, каналы или ключевые слова.\n"
            "Используйте /clear_data для очистки всех данных перед новой настройкой.",
            parse_mode=ParseMode.HTML
        )
        return
    
    setup_text = (
        "🚀 <b>Быстрая настройка бота</b>\n\n"
        "Давайте настроим бота за несколько шагов:\n\n"
        "📋 <b>Шаг 1: Добавьте бота в чаты/каналы</b>\n"
        "Добавьте бота в чаты и каналы, которые хотите мониторить.\n\n"
        "📋 <b>Шаг 2: Перешлите сообщение</b>\n"
        "Перешлите любое сообщение из чата/канала боту.\n\n"
        "📋 <b>Шаг 3: Ответьте /monitor</b>\n"
        "Ответьте на пересланное сообщение командой /monitor.\n\n"
        "📋 <b>Шаг 4: Настройте ключевые слова</b>\n"
        "Добавьте важные слова: /add_keyword <слово>\n\n"
        "📋 <b>Шаг 5: Установите порог важности</b>\n"
        "Настройте чувствительность: /threshold 0.7\n\n"
        "💡 <b>Готово!</b> Бот будет автоматически уведомлять вас о важных сообщениях."
    )
    
    await update.message.reply_text(setup_text)

async def tips_command(update: Update, context: CallbackContext) -> None:
    """Show useful tips for using the bot."""
    tips_text = (
        "💡 <b>Полезные советы по использованию бота</b>\n\n"
        "🔑 <b>Ключевые слова:</b>\n"
        "• Добавляйте слова, которые важны для вас\n"
        "• Примеры: срочно, дедлайн, встреча, отчет\n"
        "• Используйте /add_keyword для добавления\n\n"
        "📊 <b>Порог важности:</b>\n"
        "• 0.3-0.5: Только очень важные сообщения\n"
        "• 0.5-0.7: Важные сообщения (рекомендуется)\n"
        "• 0.7-0.9: Большинство сообщений\n\n"
        "📱 <b>Мониторинг:</b>\n"
        "• Бот должен быть добавлен в чат/канал\n"
        "• Перешлите сообщение и ответьте /monitor\n"
        "• Используйте /list для просмотра списка\n\n"
        "⚙️ <b>Настройки:</b>\n"
        "• /settings - просмотр всех настроек\n"
        "• /stats - статистика использования\n"
        "• /clear_data - очистка всех данных\n\n"
        "🆘 <b>Помощь:</b>\n"
        "• /help - полная справка\n"
        "• /setup - быстрая настройка"
    )
    
    await update.message.reply_text(tips_text)

async def debug_command(update: Update, context: CallbackContext) -> None:
    """Debug command to check user settings and bot status."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    debug_text = (
        f"🐛 <b>Отладочная информация:</b>\n\n"
        f"👤 <b>Пользователь:</b>\n"
        f"• ID: {user_id}\n"
        f"• Порог важности: {user.importance_threshold}\n"
        f"• Ключевых слов: {len(user.keywords)}\n\n"
        f"📊 <b>Мониторинг:</b>\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n"
        f"• Список чатов: {list(user.monitored_chats)}\n"
        f"• Список каналов: {list(user.monitored_channels)}\n\n"
        f"🔑 <b>Ключевые слова:</b>\n"
        f"• {', '.join(user.keywords) if user.keywords else 'Нет'}\n\n"
        f"📅 <b>Время:</b>\n"
        f"• Создан: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"• Обновлен: {user.updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await update.message.reply_text(debug_text, parse_mode=ParseMode.HTML)

async def menu_command(update: Update, context: CallbackContext) -> None:
    """Show main menu."""
    keyboard = [
        [
            InlineKeyboardButton("📋 Справка", callback_data="menu_help"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")
        ],
        [
            InlineKeyboardButton("📊 Мониторинг", callback_data="menu_monitoring"),
            InlineKeyboardButton("🔑 Ключевые слова", callback_data="menu_keywords")
        ],
        [
            InlineKeyboardButton("🚀 Быстрая настройка", callback_data="menu_setup"),
            InlineKeyboardButton("💡 Советы", callback_data="menu_tips")
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="menu_stats"),
            InlineKeyboardButton("🗑️ Очистить данные", callback_data="menu_clear_data")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎛️ <b>Главное меню</b>\n\nВыберите нужный раздел:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def callback_handler(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Main menu handlers
    if data == "menu_help":
        help_text = (
            "🤖 <b>Бот важных сообщений - Справка</b>\n\n"
            "📋 <b>Основные команды:</b>\n"
            "• /start - Запустить бота\n"
            "• /menu - Главное меню\n"
            "• /help - Показать эту справку\n"
            "• /settings - Просмотр настроек\n"
            "• /stats - Статистика использования\n"
            "• /setup - Быстрая настройка\n"
            "• /tips - Полезные советы\n\n"
            "📊 <b>Мониторинг:</b>\n"
            "• /monitor - Добавить чат/канал для мониторинга\n"
            "• /unmonitor - Удалить чат/канал из мониторинга\n"
            "• /list - Список мониторимых чатов и каналов\n\n"
            "🔑 <b>Ключевые слова:</b>\n"
            "• /add_keyword - Добавить важное слово\n"
            "• /remove_keyword - Удалить слово\n"
            "• /keywords - Список ваших слов\n\n"
            "⚙️ <b>Настройки:</b>\n"
            "• /threshold - Установить порог важности (0.0-1.0)\n"
            "• /clear_data - Очистить все данные\n\n"
            "💡 <b>Как использовать:</b>\n"
            "1. Добавьте бота в чаты/каналы для мониторинга\n"
            "2. Перешлите сообщение из чата/канала боту\n"
            "3. Ответьте /monitor на пересланное сообщение\n"
            "4. Бот автоматически анализирует и уведомляет о важных сообщениях"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_settings":
        keywords = ", ".join(user.keywords) if user.keywords else "Не указаны"
        exclude_keywords = ", ".join(user.exclude_keywords) if user.exclude_keywords else "Не указаны"
        
        settings_text = (
            f"⚙️ <b>Ваши настройки:</b>\n\n"
            f"📊 <b>Основные параметры:</b>\n"
            f"• Порог важности: {user.importance_threshold}\n"
            f"• Мониторится чатов: {len(user.monitored_chats)}\n"
            f"• Мониторится каналов: {len(user.monitored_channels)}\n\n"
            f"🔑 <b>Ключевые слова:</b>\n"
            f"• Важные слова: {keywords}\n"
            f"• Исключаемые слова: {exclude_keywords}\n\n"
            f"💡 Используйте команды для изменения настроек"
        )
        keyboard = [
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")],
            [InlineKeyboardButton("📊 Изменить порог важности", callback_data="menu_threshold")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(settings_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_monitoring":
        if not user.monitored_chats and not user.monitored_channels:
            monitoring_text = "❌ Вы не мониторите ни один чат или канал."
        else:
            monitoring_text = "📋 <b>Мониторимые чаты и каналы:</b>\n\n"
            if user.monitored_chats:
                monitoring_text += "💬 <b>Чаты:</b>\n"
                for chat_id in user.monitored_chats:
                    monitoring_text += f"• {chat_id}\n"
                monitoring_text += "\n"
            if user.monitored_channels:
                monitoring_text += "📢 <b>Каналы:</b>\n"
                for channel_id in user.monitored_channels:
                    monitoring_text += f"• {channel_id}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")],
            [InlineKeyboardButton("➕ Добавить чат/канал", callback_data="menu_add_monitoring")],
            [InlineKeyboardButton("➖ Удалить чат/канал", callback_data="menu_remove_monitoring")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(monitoring_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_keywords":
        if not user.keywords:
            keywords_text = "❌ У вас нет добавленных ключевых слов."
        else:
            keywords_text = "🔑 <b>Ваши ключевые слова:</b>\n\n" + "\n".join(f"• {keyword}" for keyword in user.keywords)
        
        keyboard = [
            [InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")],
            [InlineKeyboardButton("➕ Добавить слово", callback_data="menu_add_keyword")],
            [InlineKeyboardButton("➖ Удалить слово", callback_data="menu_remove_keyword")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(keywords_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_setup":
        if user.monitored_chats or user.monitored_channels or user.keywords:
            setup_text = (
                "⚠️ <b>Быстрая настройка</b>\n\n"
                "У вас уже есть настроенные чаты, каналы или ключевые слова.\n"
                "Используйте очистку данных перед новой настройкой."
            )
        else:
            setup_text = (
                "🚀 <b>Быстрая настройка бота</b>\n\n"
                "Давайте настроим бота за несколько шагов:\n\n"
                "📋 <b>Шаг 1: Добавьте бота в чаты/каналы</b>\n"
                "Добавьте бота в чаты и каналы, которые хотите мониторить.\n\n"
                "📋 <b>Шаг 2: Перешлите сообщение</b>\n"
                "Перешлите любое сообщение из чата/канала боту.\n\n"
                "📋 <b>Шаг 3: Ответьте /monitor</b>\n"
                "Ответьте на пересланное сообщение командой /monitor.\n\n"
                "📋 <b>Шаг 4: Настройте ключевые слова</b>\n"
                "Добавьте важные слова: /add_keyword <слово>\n\n"
                "📋 <b>Шаг 5: Установите порог важности</b>\n"
                "Настройте чувствительность: /threshold 0.7\n\n"
                "💡 <b>Готово!</b> Бот будет автоматически уведомлять вас о важных сообщениях."
            )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(setup_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_tips":
        tips_text = (
            "💡 <b>Полезные советы по использованию бота</b>\n\n"
            "🔑 <b>Ключевые слова:</b>\n"
            "• Добавляйте слова, которые важны для вас\n"
            "• Примеры: срочно, дедлайн, встреча, отчет\n"
            "• Используйте /add_keyword для добавления\n\n"
            "📊 <b>Порог важности:</b>\n"
            "• 0.3-0.5: Только очень важные сообщения\n"
            "• 0.5-0.7: Важные сообщения (рекомендуется)\n"
            "• 0.7-0.9: Большинство сообщений\n\n"
            "📱 <b>Мониторинг:</b>\n"
            "• Бот должен быть добавлен в чат/канал\n"
            "• Перешлите сообщение и ответьте /monitor\n"
            "• Используйте /list для просмотра списка\n\n"
            "⚙️ <b>Настройки:</b>\n"
            "• /settings - просмотр всех настроек\n"
            "• /stats - статистика использования\n"
            "• /clear_data - очистка всех данных\n\n"
            "🆘 <b>Помощь:</b>\n"
            "• /help - полная справка\n"
            "• /setup - быстрая настройка"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(tips_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_stats":
        all_users = Storage.get_all_users()
        total_users = len(all_users)
        total_monitored_chats = sum(len(u.monitored_chats) for u in all_users.values())
        total_monitored_channels = sum(len(u.monitored_channels) for u in all_users.values())
        
        stats_text = (
            f"📊 <b>Статистика бота:</b>\n\n"
            f"👤 <b>Ваша статистика:</b>\n"
            f"• Мониторится чатов: {len(user.monitored_chats)}\n"
            f"• Мониторится каналов: {len(user.monitored_channels)}\n"
            f"• Ключевых слов: {len(user.keywords)}\n"
            f"• Порог важности: {user.importance_threshold}\n\n"
            f"🌐 <b>Общая статистика:</b>\n"
            f"• Всего пользователей: {total_users}\n"
            f"• Всего мониторится чатов: {total_monitored_chats}\n"
            f"• Всего мониторится каналов: {total_monitored_channels}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(stats_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    elif data == "menu_clear_data":
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, очистить все данные", callback_data="clear_data_confirm"),
                InlineKeyboardButton("❌ Отмена", callback_data="menu_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚠️ <b>Очистка данных</b>\n\n"
            "Вы уверены, что хотите очистить все ваши данные?\n"
            "Это удалит все мониторимые чаты, каналы и ключевые слова.\n"
            "Это действие нельзя отменить.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    elif data == "menu_main":
        # Return to main menu
        keyboard = [
            [
                InlineKeyboardButton("📋 Справка", callback_data="menu_help"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")
            ],
            [
                InlineKeyboardButton("📊 Мониторинг", callback_data="menu_monitoring"),
                InlineKeyboardButton("🔑 Ключевые слова", callback_data="menu_keywords")
            ],
            [
                InlineKeyboardButton("🚀 Быстрая настройка", callback_data="menu_setup"),
                InlineKeyboardButton("💡 Советы", callback_data="menu_tips")
            ],
            [
                InlineKeyboardButton("📈 Статистика", callback_data="menu_stats"),
                InlineKeyboardButton("🗑️ Очистить данные", callback_data="menu_clear_data")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎛️ <b>Главное меню</b>\n\nВыберите нужный раздел:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    # Existing handlers
    elif data == "clear_data_confirm":
        # Clear all user data
        user.monitored_chats = set()
        user.monitored_channels = set()
        user.keywords = []
        user.importance_threshold = DEFAULT_IMPORTANCE_THRESHOLD
        Storage.update_user(user)
        await query.edit_message_text("✅ Все ваши данные очищены.")
    
    elif data == "clear_data_cancel":
        await query.edit_message_text("❌ Очистка данных отменена.")
    
    elif data.startswith("unmonitor_chat_"):
        item_id = int(data.split("_")[2])
        if item_id in user.monitored_chats:
            user.monitored_chats.remove(item_id)
            Storage.update_user(user)
            await query.edit_message_text(f"✅ Удален из мониторинга чат {item_id}")
        else:
            await query.edit_message_text(f"❌ Чат {item_id} не находится в мониторинге.")
    
    elif data.startswith("unmonitor_channel_"):
        item_id = int(data.split("_")[2])
        if item_id in user.monitored_channels:
            user.monitored_channels.remove(item_id)
            Storage.update_user(user)
            await query.edit_message_text(f"✅ Удален из мониторинга канал {item_id}")
        else:
            await query.edit_message_text(f"❌ Канал {item_id} не находится в мониторинге.")

    elif data == "menu_remove_monitoring":
        # Create keyboard with monitored chats/channels
        keyboard = []
        
        # Add chat buttons
        for chat_id in user.monitored_chats:
            keyboard.append([InlineKeyboardButton(f"💬 Чат: {chat_id}", callback_data=f"unmonitor_chat_{chat_id}")])
        
        # Add channel buttons
        for channel_id in user.monitored_channels:
            keyboard.append([InlineKeyboardButton(f"📢 Канал: {channel_id}", callback_data=f"unmonitor_channel_{channel_id}")])
        
        if not keyboard:
            await query.edit_message_text("❌ Вы не мониторите ни один чат или канал.")
            return
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_monitoring")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🗑️ Выберите чат или канал для удаления из мониторинга:",
            reply_markup=reply_markup
        )
    
    elif data == "menu_add_monitoring":
        await query.edit_message_text(
            "📋 <b>Как добавить чат/канал для мониторинга:</b>\n\n"
            "🔧 <b>Способ 1 (Рекомендуемый):</b>\n"
            "1️⃣ Добавьте бота в чат или канал\n"
            "2️⃣ Перешлите любое сообщение из этого чата/канала боту\n"
            "3️⃣ Бот автоматически предложит добавить в мониторинг\n\n"
            "🔧 <b>Способ 2 (Альтернативный):</b>\n"
            "1️⃣ Добавьте бота в чат или канал\n"
            "2️⃣ Перешлите сообщение боту\n"
            "3️⃣ Используйте команду /monitor в ответ на пересланное сообщение\n\n"
            "💡 <b>Важно:</b>\n"
            "• Бот должен быть добавлен в чат/канал\n"
            "• Для каналов бот должен быть администратором\n"
            "• После добавления бот будет анализировать все новые сообщения\n\n"
            "✅ Попробуйте переслать сообщение из нужного чата/канала прямо сейчас!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_monitoring")]]),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "menu_add_keyword":
        await query.edit_message_text(
            "🔑 <b>Добавление ключевого слова:</b>\n\n"
            "Используйте команду: /add_keyword <слово>\n\n"
            "Примеры:\n"
            "• /add_keyword срочно\n"
            "• /add_keyword важная встреча\n"
            "• /add_keyword дедлайн\n\n"
            "💡 Ключевые слова помогают боту лучше определять важные сообщения.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_keywords")]]),
            parse_mode=ParseMode.HTML
        )
    
    elif data == "menu_remove_keyword":
        if not user.keywords:
            await query.edit_message_text(
                "❌ У вас нет добавленных ключевых слов.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_keywords")]])
            )
            return
        
        # Create keyboard with keywords
        keyboard = []
        for keyword in user.keywords:
            keyboard.append([InlineKeyboardButton(f"🗑️ {keyword}", callback_data=f"remove_keyword_{keyword}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="menu_keywords")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🗑️ Выберите ключевое слово для удаления:",
            reply_markup=reply_markup
        )
    
    elif data == "menu_threshold":
        await query.edit_message_text(
            f"📊 <b>Порог важности:</b>\n\n"
            f"Текущий порог: <b>{user.importance_threshold}</b>\n\n"
            f"Использование: /threshold <0.0-1.0>\n\n"
            f"💡 <b>Рекомендации:</b>\n"
            f"• 0.3-0.5 - Только очень важные сообщения\n"
            f"• 0.5-0.7 - Важные сообщения (рекомендуется)\n"
            f"• 0.7-0.9 - Большинство сообщений\n\n"
            f"Примеры:\n"
            f"• /threshold 0.5\n"
            f"• /threshold 0.8",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_settings")]]),
            parse_mode=ParseMode.HTML
        )
    
    elif data.startswith("remove_keyword_"):
        keyword = data.replace("remove_keyword_", "")
        if keyword in user.keywords:
            user.keywords.remove(keyword)
            Storage.update_user(user)
            await query.edit_message_text(
                f"✅ Удалено ключевое слово: <b>{keyword}</b>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_keywords")]]),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                f"❌ Слово '<b>{keyword}</b>' не найдено в вашем списке.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_keywords")]]),
                parse_mode=ParseMode.HTML
            )
    
    elif data.startswith("add_monitoring_"):
        # Parse the callback data: add_monitoring_{chat_id}_{type}
        parts = data.split("_")
        if len(parts) >= 4:
            chat_id = int(parts[2])
            chat_type = parts[3]
            
            if chat_type == "channel":
                user.monitored_channels.add(chat_id)
                logger.info(f"Добавлен канал {chat_id} в мониторинг для пользователя {user_id}")
            else:
                user.monitored_chats.add(chat_id)
                logger.info(f"Добавлен чат {chat_id} в мониторинг для пользователя {user_id}")
            
            Storage.update_user(user)
            await query.edit_message_text(
                f"✅ <b>Добавлено в мониторинг!</b>\n\n"
                f"Теперь бот будет анализировать все сообщения из этого {'канала' if chat_type == 'channel' else 'чата'} "
                f"и уведомлять вас о важных сообщениях.\n\n"
                f"📊 Используйте /menu → Мониторинг для управления списком.",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при добавлении в мониторинг. Попробуйте еще раз.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_monitoring")]])
            )
    
    elif data == "dont_add_monitoring":
        await query.edit_message_text(
            "❌ Канал/чат не добавлен в мониторинг.\n\n"
            "💡 Вы всегда можете добавить его позже через меню или переслав новое сообщение.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu_monitoring")]])
        )

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handle incoming messages."""
    logger.info(f"Получено сообщение: {update.message.text[:50] if update.message.text else 'Нет текста'}")
    logger.info(f"Сообщение переслано: {hasattr(update.message, 'forward_origin')}")
    logger.info(f"Тип чата: {update.message.chat.type if update.message.chat else 'Нет чата'}")
    logger.info(f"ID чата: {update.message.chat.id if update.message.chat else 'Нет ID'}")
    
    # Подробная отладка пересланных сообщений
    if hasattr(update.message, 'forward_origin'):
        logger.info(f"forward_origin: {update.message.forward_origin}")
        if update.message.forward_origin and hasattr(update.message.forward_origin, 'chat'):
            chat = update.message.forward_origin.chat
            logger.info(f"Переслано из чата: {chat.title} (ID: {chat.id}, тип: {chat.type})")
    else:
        logger.info("Сообщение не имеет атрибута forward_origin")
    
    # Проверяем все атрибуты сообщения
    logger.info(f"Атрибуты сообщения: {[attr for attr in dir(update.message) if not attr.startswith('_')]}")
    
    # Handle forwarded messages (for manual monitoring setup)
    if update.message and hasattr(update.message, 'forward_origin') and update.message.forward_origin and hasattr(update.message.forward_origin, 'chat'):
        chat = update.message.forward_origin.chat
        chat_id = chat.id
        chat_title = chat.title or "Неизвестный чат"
        is_channel = chat.type == "channel"
        
        logger.info(f"Обрабатываю пересланное сообщение из {chat_title} (ID: {chat_id}, тип: {'канал' if is_channel else 'чат'})")
        
        user_id = update.effective_user.id
        user = Storage.get_user(user_id)
        
        # Check if the message is replying to a command
        if update.message.reply_to_message and update.message.reply_to_message.text:
            command_text = update.message.reply_to_message.text.split()[0]
            logger.info(f"Сообщение является ответом на команду: {command_text}")
            
            if command_text == "/monitor":
                # Add the chat/channel to the monitored list
                if is_channel:
                    user.monitored_channels.add(chat_id)
                    logger.info(f"Добавлен канал {chat_id} в мониторинг для пользователя {user_id}")
                else:
                    user.monitored_chats.add(chat_id)
                    logger.info(f"Добавлен чат {chat_id} в мониторинг для пользователя {user_id}")
                
                Storage.update_user(user)
                await update.message.reply_text(
                    f"✅ Теперь мониторится {chat_title} ({chat_id}).\n"
                    f"Я буду уведомлять вас о важных сообщениях из этого {'канала' if is_channel else 'чата'}."
                )
                return
        
        # Check if this chat/channel is already being monitored
        is_already_monitored = False
        if is_channel:
            is_already_monitored = chat_id in user.monitored_channels
        else:
            is_already_monitored = chat_id in user.monitored_chats
        
        if not is_already_monitored:
            # Offer to add to monitoring
            keyboard = [
                [InlineKeyboardButton("✅ Добавить в мониторинг", callback_data=f"add_monitoring_{chat_id}_{'channel' if is_channel else 'chat'}")],
                [InlineKeyboardButton("❌ Не добавлять", callback_data="dont_add_monitoring")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🔍 <b>Обнаружен новый {'канал' if is_channel else 'чат'}:</b> {chat_title}\n\n"
                f"Хотите добавить его в мониторинг для анализа важных сообщений?\n\n"
                f"📊 <b>Что это даст:</b>\n"
                f"• Автоматический анализ всех сообщений\n"
                f"• Уведомления о важных сообщениях\n"
                f"• Фильтрация по вашим настройкам",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return
        
        # Process the message to analyze its importance
        message = Message(
            message_id=update.message.message_id,
            chat_id=chat_id,
            chat_title=chat_title,
            text=update.message.text or update.message.caption or "",
            date=datetime.now(),
            is_channel=is_channel
        )
        
        if update.message.forward_origin and hasattr(update.message.forward_origin, 'sender_user'):
            message.sender_id = update.message.forward_origin.sender_user.id
            message.sender_name = update.message.forward_origin.sender_user.full_name
        
        logger.info(f"Анализирую сообщение: {message.text[:50]}...")
        
        # Analyze message importance
        importance_score = await evaluate_message_importance(message, user)
        message.importance_score = importance_score
        
        logger.info(f"Оценка важности: {importance_score:.2f}, порог: {user.importance_threshold}")
        
        # Check if the message is important enough to notify the user
        if importance_score >= user.importance_threshold:
            await update.message.reply_text(
                message.to_user_notification(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"📊 Сообщение из {chat_title} имеет оценку важности {importance_score:.2f}, "
                f"что ниже вашего порога {user.importance_threshold}."
            )
    
    # Handle direct messages from channels/groups (when bot is added to them)
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
        
        # Analyze message for each monitoring user
        for user in monitored_users:
            try:
                importance_score = await evaluate_message_importance(message, user)
                message.importance_score = importance_score
                
                logger.info(f"Оценка важности для пользователя {user.user_id}: {importance_score:.2f}, порог: {user.importance_threshold}")
                
                # If message is important enough, send notification to user
                if importance_score >= user.importance_threshold:
                    notification_text = message.to_user_notification()
                    
                    # Send notification to the user
                    await context.bot.send_message(
                        chat_id=user.user_id,
                        text=notification_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    logger.info(f"Отправлено уведомление пользователю {user.user_id} "
                              f"из {chat_title} (оценка: {importance_score:.2f})")
                else:
                    logger.info(f"Сообщение не достаточно важно для пользователя {user.user_id} "
                              f"(оценка: {importance_score:.2f}, порог: {user.importance_threshold})")
                    
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения для пользователя {user.user_id}: {e}")
    
    # Handle commands in private chat (including /monitor)
    elif update.message and update.message.chat and update.message.chat.type == "private":
        # Check if this is a command
        if update.message.text and update.message.text.startswith('/'):
            command = update.message.text.split()[0]
            logger.info(f"Получена команда в личном чате: {command}")
            
            # Handle /monitor command specifically
            if command == "/monitor":
                # Check if there's a recent forwarded message in the chat
                # For now, we'll show instructions and suggest using the menu
                await update.message.reply_text(
                    "📋 <b>Как добавить чат/канал для мониторинга:</b>\n\n"
                    "1️⃣ Добавьте бота в чат или канал\n"
                    "2️⃣ Перешлите любое сообщение из этого чата/канала боту\n"
                    "3️⃣ Используйте меню для добавления в мониторинг\n\n"
                    "💡 <b>Альтернативный способ:</b>\n"
                    "• Используйте /menu для удобной навигации\n"
                    "• Выберите '📊 Мониторинг' → '➕ Добавить чат/канал'\n\n"
                    "✅ После добавления бот будет автоматически анализировать все сообщения "
                    "из этого чата/канала и уведомлять вас о важных.",
                    parse_mode=ParseMode.HTML
                )
                return
    
    else:
        logger.info("Сообщение не является пересланным или не содержит forward_origin")



def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("monitor", monitor_command))
    application.add_handler(CommandHandler("unmonitor", unmonitor_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("add_keyword", add_keyword_command))
    application.add_handler(CommandHandler("remove_keyword", remove_keyword_command))
    application.add_handler(CommandHandler("keywords", keywords_command))
    application.add_handler(CommandHandler("threshold", threshold_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("clear_data", clear_data_command))
    application.add_handler(CommandHandler("setup", setup_command))
    application.add_handler(CommandHandler("tips", tips_command))
    application.add_handler(CommandHandler("debug", debug_command)) # Add debug command handler
    application.add_handler(CommandHandler("menu", menu_command)) # Add menu command handler
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Add message handlers
    # Handle all messages (forwarded and direct from channels/groups)
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main() 