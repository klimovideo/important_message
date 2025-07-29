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
    
    if is_admin:
        # Упрощенное меню для администраторов
        keyboard = [
            ["📊 Мониторинг", "📢 Канал публикации"],
            ["👥 Администраторы", "⚙️ Настройки"],
            ["ℹ️ Справка"]
        ]
    else:
        # Ограниченное меню для обычных пользователей
        keyboard = [
            ["📝 Предложить пост", "📢 Предложить канал"],
            ["📬 Канал важных сообщений", "ℹ️ Справка"]
        ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)





# ===========================================
# ESSENTIAL COMMANDS (минимум)
# ===========================================

async def get_bot_admin_channels(bot):
    """Получает список каналов, где бот является администратором"""
    admin_channels = []
    try:
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        bot_id = bot_info.id
        
        checked_channels = set()
        
        # Проверяем все каналы из конфига пользователей
        all_users = Storage.get_all_users()
        for user in all_users.values():
            for channel_id in user.monitored_channels:
                if channel_id not in checked_channels:
                    checked_channels.add(channel_id)
                    try:
                        chat = await bot.get_chat(channel_id)
                        # Проверяем, является ли бот администратором
                        member = await bot.get_chat_member(channel_id, bot_id)
                        if member.status in ['administrator', 'creator']:
                            admin_channels.append({
                                'id': channel_id,
                                'title': chat.title,
                                'username': chat.username
                            })
                    except Exception as e:
                        logger.debug(f"Не удалось проверить канал {channel_id}: {e}")
        
        # Также проверяем канал из конфига, если он есть
        config = Storage.bot_config
        if config.publish_channel_id and config.publish_channel_id not in checked_channels:
            try:
                chat = await bot.get_chat(config.publish_channel_id)
                member = await bot.get_chat_member(config.publish_channel_id, bot_id)
                if member.status in ['administrator', 'creator']:
                    admin_channels.append({
                        'id': config.publish_channel_id,
                        'title': chat.title,
                        'username': chat.username
                    })
            except Exception as e:
                logger.debug(f"Не удалось проверить канал конфига {config.publish_channel_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при получении списка каналов: {e}")
    
    return admin_channels

async def start_command(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Сбрасываем состояние пользователя
    user.current_state = None
    Storage.update_user(user)
    
    welcome_text = (
        f"🤖 <b>Добро пожаловать!</b>\n\n"
        f"Я анализирую сообщения из ваших чатов и каналов с помощью ИИ "
        f"и уведомляю только о важных сообщениях.\n\n"
        f"📊 <b>Ваши настройки:</b>\n"
        f"• Порог важности: {Storage.bot_config.importance_threshold} (глобальный)\n"
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
    
    # Сбрасываем состояние пользователя
    user = Storage.get_user(user_id)
    user.current_state = None
    Storage.update_user(user)
    
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
    
    reply_markup = get_main_reply_keyboard(user_id)
    
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
    
    # Сбрасываем состояние пользователя при нажатии любой кнопки
    if user.current_state:
        user.current_state = None
        Storage.update_user(user)
    
    # Main menu buttons
    if text == "📊 Мониторинг":
        if Storage.is_admin(user_id):
            await show_monitoring_interface(update, context, user)
        else:
            await update.message.reply_text("❌ Эта функция доступна только администраторам.")
        return True
    
    elif text == "📝 Предложить пост":
        await show_submit_post_interface(update, context)
        return True
    
    elif text == "📢 Предложить канал":
        context.user_data['awaiting_channel_suggestion'] = True
        await update.message.reply_text(
            "📢 <b>Предложение канала для мониторинга</b>\n\n"
            "💡 <b>Отправьте:</b>\n"
            "• Username канала (например: @my_channel)\n"
            "• Ссылку на канал (например: https://t.me/my_channel)\n"
            "• ID канала (например: -1001234567890)\n\n"
            "🔧 <b>Ваше предложение будет рассмотрено администратором.</b>",
            parse_mode=ParseMode.HTML
        )
        return True
    
    elif text == "📬 Канал важных сообщений":
        await show_important_channel_info(update, context)
        return True
    
    elif text == "📈 Статистика":
        user = Storage.get_user(user_id)
        await show_statistics_interface(update, context, user)
        return True
    
    elif text == "⚙️ Настройки":
        if Storage.is_admin(user_id):
            await show_settings_interface(update, context, user)
        else:
            await update.message.reply_text("❌ Эта функция доступна только администраторам.")
        return True
    
    elif text == "ℹ️ Справка":
        await show_help_interface(update, context)
        return True
    
    # Admin buttons
    elif text == "📢 Канал публикации":
        if Storage.is_admin(user_id):
            await show_channel_config(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    
    elif text == "👥 Администраторы":
        if Storage.is_admin(user_id):
            # Устанавливаем состояние для управления администраторами
            user.current_state = "admin_management"
            Storage.update_user(user)
            await show_admins_management(update, context)
        else:
            await update.message.reply_text("❌ У вас нет прав администратора.")
        return True
    


    
    # Back to main menu
    elif text == "🔙 Главное меню":
        # Сбрасываем состояние пользователя
        user = Storage.get_user(user_id)
        user.current_state = None
        Storage.update_user(user)
        
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
    # Подсчитываем все источники мониторинга
    all_sources = set()
    all_sources.update(user.monitored_chats)
    all_sources.update(user.monitored_channels)
    
    if USERBOT_ENABLED:
        userbot = get_userbot()
        if userbot.is_running:
            userbot_sources = userbot.get_monitored_sources()
            all_sources.update(userbot_sources)
    
    total_sources = len(all_sources)
    
    monitoring_text = (
        f"📊 <b>Мониторинг источников</b>\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Всего источников: {total_sources}\n"
        f"• Порог важности: {Storage.bot_config.importance_threshold}\n\n"
        f"💡 <b>Как работает мониторинг:</b>\n"
        f"• Бот автоматически отслеживает все сообщения\n"
        f"• ИИ анализирует важность каждого сообщения\n"
        f"• Вы получаете уведомления о важных событиях\n\n"
        f"➕ <b>Добавить источник можно:</b>\n"
        f"• Переслав сообщение из канала/чата боту\n"
        f"• Отправив ссылку на канал или @username\n"
        f"• Добавив бота в групповой чат"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить источник", callback_data="monitoring_add"),
            InlineKeyboardButton("📋 Список источников", callback_data="monitoring_list")
        ],
        [
            InlineKeyboardButton("🗑️ Удалить источник", callback_data="monitoring_remove"),
            InlineKeyboardButton("🧹 Очистить все", callback_data="monitoring_clear")
        ]
    ]
    
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
        f"• /submit_post текст поста\n\n"
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
    config = Storage.bot_config
    
    settings_text = (
        f"⚙️ <b>Настройки</b>\n\n"
        f"📊 <b>Ваши параметры:</b>\n"
        f"• Порог важности: {Storage.bot_config.importance_threshold} (глобальный)\n"
        f"• Мониторится чатов: {len(user.monitored_chats)}\n"
        f"• Мониторится каналов: {len(user.monitored_channels)}\n"
        f"• Можете предлагать посты: {'Да' if user.can_submit_posts else 'Нет'}\n\n"
        f"🔑 <b>Ключевые слова:</b>\n"
        f"• Важные: {keywords[:100]}{'...' if len(keywords) > 100 else ''}\n"
        f"• Исключаемые: {exclude_keywords[:100]}{'...' if len(exclude_keywords) > 100 else ''}\n"
    )
    
    # Добавляем глобальные настройки для администраторов
    if Storage.is_admin(user.user_id):
        settings_text += (
            f"\n\n🌐 <b>Глобальные настройки:</b>\n"
            f"• Автопубликация: {'Включена' if config.auto_publish_enabled else 'Отключена'}\n"
            f"• Требует одобрения: {'Да' if config.require_admin_approval else 'Нет'}\n"
            f"• Глобальный порог: {config.importance_threshold}\n"
        )
    
    settings_text += "\n\n💡 Используйте кнопки для изменения настроек"
    
    keyboard = [
        [
            InlineKeyboardButton("🔑 Ключевые слова", callback_data="settings_keywords")
        ]
    ]
    
    # Добавляем кнопки глобальных настроек для администраторов
    if Storage.is_admin(user.user_id):
        keyboard.append([
            InlineKeyboardButton(
                f"🤖 Автопубликация: {'✅' if config.auto_publish_enabled else '❌'}", 
                callback_data="admin_toggle_autopublish"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"✋ Требует одобрения: {'✅' if config.require_admin_approval else '❌'}", 
                callback_data="admin_toggle_approval"
            )
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Глобальный порог", callback_data="admin_threshold")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Очистить данные", callback_data="settings_clear"),
        InlineKeyboardButton("🔄 Сброс настроек", callback_data="settings_reset")
    ])
    
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
        f"• Порог важности: {Storage.bot_config.importance_threshold} (глобальный)\n\n"
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

async def show_important_channel_info(update: Update, context: CallbackContext) -> None:
    """Show information about important messages channel."""
    config = Storage.bot_config
    
    if config.publish_channel_username:
        channel_text = (
            f"📬 <b>Канал важных сообщений</b>\n\n"
            f"🔔 В этом канале публикуются самые важные новости и сообщения, "
            f"отобранные искусственным интеллектом и проверенные администраторами.\n\n"
            f"📢 <b>Канал:</b> @{config.publish_channel_username}\n"
            f"🔗 <b>Ссылка:</b> https://t.me/{config.publish_channel_username}\n\n"
            f"💡 <b>Подпишитесь на канал, чтобы не пропустить важные новости!</b>"
        )
        
        keyboard = [
            [InlineKeyboardButton("📢 Перейти в канал", url=f"https://t.me/{config.publish_channel_username}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            channel_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "📬 <b>Канал важных сообщений</b>\n\n"
            "❌ Канал для публикации важных сообщений пока не настроен.\n"
            "Администраторы скоро его настроят!",
            parse_mode=ParseMode.HTML
        )

async def show_help_interface(update: Update, context: CallbackContext) -> None:
    """Show help interface."""
    user_id = update.effective_user.id
    is_admin = Storage.is_admin(user_id)
    
    if is_admin:
        help_text = (
            f"ℹ️ <b>Справка администратора</b>\n\n"
            f"📝 <b>Модерация постов:</b>\n"
            f"• Просматривайте предложенные посты\n"
            f"• Одобряйте или отклоняйте их\n"
            f"• Одобренные посты публикуются в канале\n\n"
            f"📊 <b>Мониторинг:</b>\n"
            f"• Перешлите сообщение из чата/канала\n"
            f"• Добавьте источник в мониторинг\n"
            f"• Настройте ключевые слова\n\n"
            f"⚙️ <b>Настройки:</b>\n"
            f"• Глобальный порог важности: {Storage.bot_config.importance_threshold}\n"
            f"• Канал публикации: @{Storage.bot_config.publish_channel_username or 'не настроен'}\n\n"
            "💡 <b>Совет:</b> Используйте мониторинг для отслеживания закрытых каналов"
        )
    else:
        help_text = (
            f"ℹ️ <b>Справка по боту</b>\n\n"
            f"🤖 <b>Что умеет этот бот:</b>\n"
            f"• Принимает предложения постов для публикации\n"
            f"• Принимает предложения каналов для мониторинга\n\n"
            f"📝 <b>Как предложить пост:</b>\n"
            f"1. Нажмите кнопку '📝 Предложить пост'\n"
            f"2. Отправьте текст вашего поста\n"
            f"3. Подтвердите отправку на модерацию\n\n"
            f"📢 <b>Как предложить канал:</b>\n"
            f"1. Нажмите кнопку '📢 Предложить канал'\n"
            f"2. Отправьте ссылку или username канала\n\n"
            f"💡 <b>Важно:</b>\n"
            f"• Все предложения рассматриваются администраторами\n"
            f"• Вы получите уведомление о решении по вашему посту"
        )
    
    # Inline кнопки только для администраторов
    if is_admin:
        keyboard = [
            [
                InlineKeyboardButton("🚀 Быстрый старт", callback_data="help_quickstart"),
                InlineKeyboardButton("💡 Советы", callback_data="help_tips")
            ],
            [
                InlineKeyboardButton("❓ FAQ", callback_data="help_faq")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Для обычных пользователей без inline кнопок
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML
        )

# ===========================================
# MONITORING INTERFACES
# ===========================================



# ===========================================
# ADMIN INTERFACES
# ===========================================

async def show_admin_config(update: Update, context: CallbackContext) -> None:
    """Show admin configuration interface."""
    config = Storage.bot_config
    
    config_text = (
        f"⚙️ <b>Конфигурация бота</b>\n\n"
        f"📊 <b>Глобальный порог важности:</b> {config.importance_threshold}\n"
        f"📢 <b>Канал публикации:</b> {config.publish_channel_username or 'Не настроен'}\n"
        f"👥 <b>Администраторов:</b> {len(config.admin_ids)}\n\n"
        f"💡 <b>Все посты проходят модерацию перед публикацией</b>"
    )
    
    keyboard = [
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
    
    # Устанавливаем состояние для администратора
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    user.current_state = "channel_setup"
    Storage.update_user(user)
    
    # Получаем список каналов, где бот является администратором
    admin_channels = await get_bot_admin_channels(context.bot)
    
    # Используем простой reply_text
    message_func = update.message.reply_text
    
    channel_text = (
        f"📢 <b>Настройка канала публикации</b>\n\n"
        f"📋 <b>Текущий канал:</b> {channel_info}\n"
        f"🏷️ <b>Username:</b> {username_info}\n\n"
    )
    
    keyboard = []
    
    if admin_channels:
        channel_text += f"📊 <b>Доступные каналы (где бот админ):</b>\n"
        for channel in admin_channels:
            channel_name = channel['title']
            if channel['username']:
                channel_name += f" (@{channel['username']})"
            channel_text += f"• {html.escape(channel_name)}\n"
            
            # Добавляем кнопку для быстрого выбора канала
            button_text = f"📢 {channel['title'][:30]}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"set_channel_{channel['id']}")])
        
        channel_text += "\n💡 <b>Нажмите на канал выше для быстрого выбора</b>\n\n"
    else:
        channel_text += "⚠️ <b>Нет доступных каналов</b>\n"
        channel_text += "Добавьте бота администратором в канал, затем обновите эту страницу\n\n"
    
    channel_text += (
        f"💡 <b>Или отправьте вручную:</b>\n"
        f"• ID канала (например: -1001234567890)\n"
        f"• Username канала (например: @my_channel)\n"
        f"• Ссылку на канал (например: https://t.me/my_channel)\n"
        f"• Короткую ссылку (например: t.me/my_channel)\n\n"
        f"🔧 <b>Просто отправьте любой из этих форматов следующим сообщением!</b>"
    )
    
    keyboard.append([InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_channels")])
    keyboard.append([InlineKeyboardButton("🗑️ Очистить настройки", callback_data="admin_clear_channel")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_channel_setup")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message_func(
        channel_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def show_admins_management(update: Update, context: CallbackContext) -> None:
    """Show admins management interface."""
    config = Storage.bot_config
    
    user_id = update.effective_user.id
    
    admins_text = (
        f"👥 <b>Администраторы бота</b>\n\n"
        f"📊 <b>Всего:</b> {len(config.admin_ids)}\n\n"
        f"📋 <b>Список:</b>\n"
    )
    
    # Получаем информацию о каждом администраторе
    for i, admin_id in enumerate(config.admin_ids, 1):
        try:
            # Пытаемся получить информацию о пользователе
            chat_member = await context.bot.get_chat(admin_id)
            username = chat_member.username
            first_name = chat_member.first_name
            last_name = chat_member.last_name
            
            # Формируем отображаемое имя
            if username:
                display_name = f"@{username}"
            elif first_name:
                display_name = f"{first_name}"
                if last_name:
                    display_name += f" {last_name}"
            else:
                display_name = "Неизвестный пользователь"
            
            admins_text += f"{i}. {display_name} (ID: {admin_id})\n"
        except Exception as e:
            # Если не удалось получить информацию, показываем только ID
            admins_text += f"{i}. ID: {admin_id} (не удалось получить информацию)\n"
    
    admins_text += (
        f"\n💡 <b>Для добавления/удаления отправьте:</b>\n"
        f"• <code>+123456789</code> - добавить админа по ID\n"
        f"• <code>+@username</code> - добавить админа по юзернейму\n"
        f"• <code>-123456789</code> - удалить админа по ID\n"
        f"• <code>-@username</code> - удалить админа по юзернейму\n\n"
        f"🔧 <b>Или используйте команды:</b>\n"
        f"/admin_add user_id_или_@username\n"
        f"/admin_remove user_id_или_@username"
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
# TEXT MESSAGE HANDLERS
# ===========================================

async def handle_text_messages(update: Update, context: CallbackContext) -> None:
    """Handle text messages for various inputs."""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    user = Storage.get_user(user_id)  # Получаем пользователя в начале функции
    
    # Проверяем, не является ли это нажатием кнопки
    if await handle_reply_buttons(update, context):
        return
    
    # Обработка предложения канала
    if context.user_data.get('awaiting_channel_suggestion'):
        context.user_data.pop('awaiting_channel_suggestion', None)
        
        # Отправляем предложение администраторам
        config = Storage.bot_config
        if config.admin_ids:
            notification_text = (
                f"📢 <b>Новое предложение канала</b>\n\n"
                f"👤 <b>От пользователя:</b> {user_id}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"📋 <b>Предложение:</b> {html.escape(text)}"
            )
            
            # Создаем inline кнопки для быстрого добавления
            keyboard = []
            
            # Проверяем формат предложения
            if text.startswith('@') or 't.me/' in text or text.startswith('http'):
                keyboard.append([
                    InlineKeyboardButton("➕ Добавить в мониторинг", callback_data=f"add_suggested_channel_{text}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("❌ Отклонить", callback_data="reject_channel_suggestion")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            
            for admin_id in config.admin_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=notification_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.warning(f"Не удалось уведомить администратора {admin_id}: {e}")
            
            await update.message.reply_text(
                "✅ <b>Ваше предложение отправлено администраторам!</b>\n\n"
                "Они рассмотрят его в ближайшее время.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ К сожалению, в данный момент нет администраторов для рассмотрения вашего предложения.",
                parse_mode=ParseMode.HTML
            )
        return
    
    # Обработка добавления источника мониторинга
    if user.current_state == "awaiting_source_link":
        user.current_state = None
        Storage.update_user(user)
        
        # Обрабатываем ссылку или username
        if text.startswith('@') or 't.me/' in text or text.startswith('http'):
            # Используем функционал юзербота для присоединения
            if USERBOT_ENABLED:
                userbot = get_userbot()
                if userbot.is_running:
                    try:
                        chat_info = await userbot.join_chat(text)
                        if chat_info:
                            await update.message.reply_text(
                                f"✅ <b>Источник добавлен в мониторинг!</b>\n\n"
                                f"📌 <b>Название:</b> {html.escape(chat_info['title'])}\n"
                                f"🆔 <b>ID:</b> {chat_info['id']}\n\n"
                                f"Теперь вы будете получать уведомления о важных сообщениях из этого источника.",
                                parse_mode=ParseMode.HTML
                            )
                        else:
                            await update.message.reply_text(
                                "❌ Не удалось добавить источник. Проверьте правильность ссылки.",
                                parse_mode=ParseMode.HTML
                            )
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ Ошибка при добавлении источника: {str(e)}",
                            parse_mode=ParseMode.HTML
                        )
                else:
                    await update.message.reply_text(
                        "❌ Система мониторинга не активна. Обратитесь к администратору.",
                        parse_mode=ParseMode.HTML
                    )
            else:
                await update.message.reply_text(
                    "❌ Функция мониторинга временно недоступна.",
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.message.reply_text(
                "❌ <b>Неверный формат!</b>\n\n"
                "Отправьте:\n"
                "• @username канала\n"
                "• Ссылку https://t.me/username\n"
                "• Ссылку-приглашение",
                parse_mode=ParseMode.HTML
            )
        return
    
    # Handle keyword additions
    if text.startswith('+') and len(text) > 1:
        if Storage.is_admin(user_id):
            keyword = text[1:].strip().lower()
            if keyword not in user.keywords:
                user.keywords.append(keyword)
                Storage.update_user(user)
                await update.message.reply_text(f"✅ Добавлено важное слово: <b>{html.escape(keyword)}</b>", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(f"⚠️ Слово '<b>{html.escape(keyword)}</b>' уже есть в списке важных.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Эта функция доступна только администраторам.")
        return
    
    # Handle keyword exclusions
    elif text.startswith('-') and len(text) > 1 and not text[1:].isdigit():
        if Storage.is_admin(user_id):
            keyword = text[1:].strip().lower()
            if keyword not in user.exclude_keywords:
                user.exclude_keywords.append(keyword)
                Storage.update_user(user)
                await update.message.reply_text(f"✅ Добавлено исключаемое слово: <b>{html.escape(keyword)}</b>", parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(f"⚠️ Слово '<b>{html.escape(keyword)}</b>' уже есть в списке исключаемых.", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text("❌ Эта функция доступна только администраторам.")
        return
    
    # Handle admin addition (for admins only)
    elif text.startswith('+') and (text[1:].isdigit() or text[1:].startswith('@')):
        if Storage.is_admin(user_id):
            if text[1:].isdigit():
                admin_id = int(text[1:])
            else:
                # Обработка юзернейма
                username = text[1:].lstrip('@')
                try:
                    # Пытаемся получить пользователя по юзернейму
                    chat = await context.bot.get_chat(f"@{username}")
                    admin_id = chat.id
                except Exception as e:
                    await update.message.reply_text(f"❌ Не удалось найти пользователя @{username}")
                    return
            
            if admin_id not in Storage.bot_config.admin_ids:
                Storage.add_admin(admin_id)
                
                # Получаем информацию о добавленном пользователе
                try:
                    chat_member = await context.bot.get_chat(admin_id)
                    username = chat_member.username
                    first_name = chat_member.first_name
                    last_name = chat_member.last_name
                    
                    if username:
                        display_name = f"@{username}"
                    elif first_name:
                        display_name = f"{first_name}"
                        if last_name:
                            display_name += f" {last_name}"
                    else:
                        display_name = "Неизвестный пользователь"
                    
                    await update.message.reply_text(f"✅ Пользователь {display_name} (ID: {admin_id}) добавлен в администраторы.")
                except Exception:
                    await update.message.reply_text(f"✅ Пользователь {admin_id} добавлен в администраторы.")
            else:
                await update.message.reply_text(f"⚠️ Пользователь {admin_id} уже является администратором.")
        else:
            await update.message.reply_text("❌ У вас нет прав для добавления администраторов.")
        return
    
    # Handle admin removal (for admins only)
    elif text.startswith('-') and (text[1:].isdigit() or text[1:].startswith('@')):
        if Storage.is_admin(user_id):
            if text[1:].isdigit():
                admin_id = int(text[1:])
            else:
                # Обработка юзернейма
                username = text[1:].lstrip('@')
                try:
                    # Пытаемся получить пользователя по юзернейму
                    chat = await context.bot.get_chat(f"@{username}")
                    admin_id = chat.id
                except Exception as e:
                    await update.message.reply_text(f"❌ Не удалось найти пользователя @{username}")
                    return
            
            if admin_id in Storage.bot_config.admin_ids:
                Storage.remove_admin(admin_id)
                
                # Получаем информацию об удаленном пользователе
                try:
                    chat_member = await context.bot.get_chat(admin_id)
                    username = chat_member.username
                    first_name = chat_member.first_name
                    last_name = chat_member.last_name
                    
                    if username:
                        display_name = f"@{username}"
                    elif first_name:
                        display_name = f"{first_name}"
                        if last_name:
                            display_name += f" {last_name}"
                    else:
                        display_name = "Неизвестный пользователь"
                    
                    await update.message.reply_text(f"✅ Пользователь {display_name} (ID: {admin_id}) удален из администраторов.")
                except Exception:
                    await update.message.reply_text(f"✅ Пользователь {admin_id} удален из администраторов.")
            else:
                await update.message.reply_text(f"❌ Пользователь {admin_id} не является администратором.")
        else:
            await update.message.reply_text("❌ У вас нет прав для удаления администраторов.")
        return
    
    # Handle admin management in admin interface
    elif Storage.is_admin(user_id) and user.current_state == "admin_management":
        if text.startswith('+') and text[1:].isdigit():
            admin_id = int(text[1:])
            if admin_id not in Storage.bot_config.admin_ids:
                Storage.add_admin(admin_id)
                
                # Получаем информацию о добавленном пользователе
                try:
                    chat_member = await context.bot.get_chat(admin_id)
                    username = chat_member.username
                    first_name = chat_member.first_name
                    last_name = chat_member.last_name
                    
                    if username:
                        display_name = f"@{username}"
                    elif first_name:
                        display_name = f"{first_name}"
                        if last_name:
                            display_name += f" {last_name}"
                    else:
                        display_name = "Неизвестный пользователь"
                    
                    await update.message.reply_text(f"✅ Пользователь {display_name} (ID: {admin_id}) добавлен в администраторы.")
                except Exception:
                    await update.message.reply_text(f"✅ Пользователь {admin_id} добавлен в администраторы.")
            else:
                await update.message.reply_text(f"⚠️ Пользователь {admin_id} уже является администратором.")
        elif text.startswith('-') and text[1:].isdigit():
            admin_id = int(text[1:])
            if admin_id == user_id:
                await update.message.reply_text("❌ Нельзя удалить себя из администраторов.")
            elif admin_id in Storage.bot_config.admin_ids:
                Storage.remove_admin(admin_id)
                
                # Получаем информацию об удаленном пользователе
                try:
                    chat_member = await context.bot.get_chat(admin_id)
                    username = chat_member.username
                    first_name = chat_member.first_name
                    last_name = chat_member.last_name
                    
                    if username:
                        display_name = f"@{username}"
                    elif first_name:
                        display_name = f"{first_name}"
                        if last_name:
                            display_name += f" {last_name}"
                    else:
                        display_name = "Неизвестный пользователь"
                    
                    await update.message.reply_text(f"✅ Пользователь {display_name} (ID: {admin_id}) удален из администраторов.")
                except Exception:
                    await update.message.reply_text(f"✅ Пользователь {admin_id} удален из администраторов.")
            else:
                await update.message.reply_text(f"❌ Пользователь {admin_id} не является администратором.")
        else:
            await update.message.reply_text(
                "❌ Неверный формат. Используйте:\n"
                "• <code>+123456789</code> - добавить админа\n"
                "• <code>-123456789</code> - удалить админа",
                parse_mode=ParseMode.HTML
            )
        return
    
    # Handle channel configuration for admins (highest priority for admins)
    if Storage.is_admin(user_id) and user.current_state == "channel_setup" and (
        text.startswith('@') or 
        text.lstrip('-').isdigit() or 
        't.me/' in text or
        text.startswith('http')
    ):
        await handle_channel_config_text(update, context, text)
        return
    
    # Handle admin threshold setup
    if Storage.is_admin(user_id) and user.current_state == "admin_threshold_setup" and text.replace('.', '').isdigit() and 0 <= float(text) <= 1:
        threshold = float(text)
        config = Storage.bot_config
        config.importance_threshold = threshold
        Storage.update_config(config)
        
        # Сбрасываем состояние пользователя
        user.current_state = None
        Storage.update_user(user)
        
        await update.message.reply_text(
            f"✅ <b>Глобальный порог важности установлен:</b> {threshold}\n\n"
            f"💡 Теперь все пользователи будут получать уведомления о сообщениях с важностью выше {threshold}",
            parse_mode=ParseMode.HTML
        )
        return
    

    

    
    # Handle channel suggestions from regular users
    elif not Storage.is_admin(user_id) and (
        text.startswith('@') or 
        text.lstrip('-').isdigit() or 
        't.me/' in text or
        text.startswith('http')
    ):
        # Уведомляем администраторов о предложении канала
        admin_ids = Storage.bot_config.admin_ids
        if admin_ids:
            suggestion_text = (
                f"📢 <b>Предложение канала для мониторинга</b>\n\n"
                f"👤 <b>От пользователя:</b> {user_id}\n"
                f"📝 <b>Канал:</b> {html.escape(text)}\n"
                f"📅 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                f"💡 <b>Для добавления канала в мониторинг используйте админ-панель.</b>"
            )
            
            for admin_id in admin_ids:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=suggestion_text,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
            
            await update.message.reply_text(
                "✅ <b>Предложение канала отправлено администраторам!</b>\n\n"
                "💡 Мы рассмотрим ваше предложение и добавим канал в мониторинг, если он подходит.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ <b>Нет доступных администраторов</b>\n\n"
                "К сожалению, в данный момент нет администраторов для рассмотрения вашего предложения.",
                parse_mode=ParseMode.HTML
            )
        return
    
    # If nothing matched and it's not a button text, treat as post submission
    # Check if text is not a known button
    known_buttons = [
        "📝 Предложить пост", "📢 Предложить канал", "ℹ️ Справка",
        "📝 Модерация постов", "📢 Канал публикации", "👥 Администраторы",
        "📊 Мониторинг", "🤖 Userbot", "⚙️ Настройки", "📈 Статистика",
        "🔑 Ключевые слова", "🚀 Запустить", "🛑 Остановить", "🔙 Главное меню"
    ]
    
    if text not in known_buttons and len(text) > 10 and not text.startswith('/'):
        await handle_post_submission_text(update, context, text)
        return

async def handle_channel_config_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle channel configuration from text input."""
    config = Storage.bot_config
    user_id = update.effective_user.id
    
    # Сбрасываем состояние пользователя
    user = Storage.get_user(user_id)
    user.current_state = None
    Storage.update_user(user)
    
    # Helper function to extract username from link
    def extract_username_from_link(link: str) -> str:
        link = link.strip()
        
        # Если уже username с @
        if link.startswith('@'):
            return link
            
        # Различные форматы ссылок t.me
        if 't.me/' in link:
            # Извлекаем часть после t.me/
            username = link.split('t.me/')[-1]
            # Убираем параметры после ?
            username = username.split('?')[0]
            # Убираем слеши в конце
            username = username.rstrip('/')
            return f"@{username}"
        
        # Если это просто username без @
        if not link.startswith('@') and not link.startswith('http') and not link.lstrip('-').isdigit():
            return f"@{link}"
            
        return link
    
    async def check_bot_permissions(chat_id):
        """Проверяет права бота в канале"""
        try:
            bot_info = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat_id, bot_info.id)
            return member.status in ['administrator', 'creator']
        except Exception:
            return False
    
    # Process different formats
    if text.startswith('@') or 't.me/' in text or text.startswith('http'):
        # Username or link format
        if 't.me/' in text or text.startswith('http'):
            username = extract_username_from_link(text)
        else:
            username = text if text.startswith('@') else f"@{text}"
            
        try:
            # Try to get channel info to validate and get ID
            chat = await context.bot.get_chat(username)
            
            # Проверяем права бота
            has_permissions = await check_bot_permissions(chat.id)
            
            if not has_permissions:
                await update.message.reply_text(
                    f"⚠️ <b>Внимание!</b> Бот не является администратором в канале.\n\n"
                    f"📝 <b>Название:</b> {html.escape(chat.title)}\n"
                    f"📋 <b>ID:</b> {chat.id}\n\n"
                    f"🔧 <b>Для публикации постов добавьте бота как администратора с правами:</b>\n"
                    f"• Отправка сообщений\n"
                    f"• Редактирование сообщений\n\n"
                    f"❓ <b>Всё равно сохранить этот канал?</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Да, сохранить", callback_data=f"force_set_channel_{chat.id}"),
                            InlineKeyboardButton("❌ Отмена", callback_data="cancel_channel_setup")
                        ]
                    ])
                )
                return
            
            # Сохраняем конфигурацию
            config.publish_channel_id = chat.id
            config.publish_channel_username = chat.username
            Storage.update_config(config)
            
            await update.message.reply_text(
                f"✅ <b>Канал публикации настроен успешно!</b>\n\n"
                f"📝 <b>Название:</b> {html.escape(chat.title)}\n"
                f"📋 <b>ID:</b> {chat.id}\n"
                f"🏷️ <b>Username:</b> @{html.escape(chat.username or 'отсутствует')}\n"
                f"👤 <b>Участников:</b> {getattr(chat, 'member_count', 'неизвестно')}\n\n"
                f"🤖 <b>Бот имеет права администратора</b> ✅\n"
                f"🚀 <b>Готов к публикации постов!</b>",
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            if "chat not found" in error_msg:
                await update.message.reply_text(
                    f"❌ <b>Канал не найден</b>\n\n"
                    f"🔗 <b>Проверьте:</b> {html.escape(text)}\n\n"
                    f"💡 <b>Возможные причины:</b>\n"
                    f"• Неправильная ссылка или username\n"
                    f"• Канал приватный и бот не добавлен\n"
                    f"• Канал не существует",
                    parse_mode=ParseMode.HTML
                )
            elif "forbidden" in error_msg:
                await update.message.reply_text(
                    f"❌ <b>Нет доступа к каналу</b>\n\n"
                    f"🔗 <b>Канал:</b> {html.escape(text)}\n\n"
                    f"🔧 <b>Решение:</b>\n"
                    f"1. Добавьте бота в канал как администратора\n"
                    f"2. Дайте права на отправку сообщений\n"
                    f"3. Попробуйте снова",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"❌ <b>Ошибка настройки канала</b>\n\n"
                    f"🔗 <b>Ввод:</b> {html.escape(text)}\n"
                    f"📋 <b>Ошибка:</b> {html.escape(str(e))}\n\n"
                    f"💡 <b>Попробуйте:</b>\n"
                    f"• Проверить правильность ссылки\n"
                    f"• Убедиться что бот добавлен в канал\n"
                    f"• Использовать ID канала вместо ссылки",
                    parse_mode=ParseMode.HTML
                )
    
    elif text.lstrip('-').isdigit():
        # ID format
        channel_id = int(text)
        
        try:
            # Try to get channel info
            chat = await context.bot.get_chat(channel_id)
            
            # Проверяем права бота
            has_permissions = await check_bot_permissions(channel_id)
            
            config.publish_channel_id = channel_id
            if chat.username:
                config.publish_channel_username = chat.username
            Storage.update_config(config)
            
            permission_status = "✅ Бот имеет права администратора" if has_permissions else "⚠️ Бот НЕ является администратором"
            
            await update.message.reply_text(
                f"✅ <b>Канал настроен успешно!</b>\n\n"
                f"�� <b>Название:</b> {html.escape(chat.title)}\n"
                f"📋 <b>ID:</b> {channel_id}\n"
                f"🏷️ <b>Username:</b> @{html.escape(chat.username or 'отсутствует')}\n\n"
                f"🤖 <b>Статус бота:</b> {permission_status}\n\n"
                f"{'🚀 Готов к публикации!' if has_permissions else '🔧 Добавьте бота как администратора для публикации'}",
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            # Save ID even if we can't get info
            config.publish_channel_id = channel_id
            Storage.update_config(config)
            await update.message.reply_text(
                f"⚠️ <b>Канал настроен</b>, но не удалось получить полную информацию\n\n"
                f"📋 <b>ID канала:</b> {channel_id}\n"
                f"📋 <b>Ошибка:</b> {html.escape(str(e))}\n\n"
                f"💡 <b>Убедитесь что:</b>\n"
                f"• Бот добавлен в канал как администратор\n"
                f"• ID канала правильный\n"
                f"• У бота есть права на отправку сообщений",
                parse_mode=ParseMode.HTML
            )
    else:
        await update.message.reply_text(
            f"❌ <b>Неправильный формат</b>\n\n"
            f"📝 <b>Поддерживаемые форматы:</b>\n"
            f"• ID канала: <code>-1001234567890</code>\n"
            f"• Username: <code>@my_channel</code>\n"
            f"• Полная ссылка: <code>https://t.me/my_channel</code>\n"
            f"• Короткая ссылка: <code>t.me/my_channel</code>\n\n"
            f"🔗 <b>Ваш ввод:</b> {html.escape(text)}",
            parse_mode=ParseMode.HTML
        )



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
    if not query:
        return
        
    await query.answer()
    
    data = query.data
    if not data:
        return
        
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Monitoring callbacks
    if data == "monitoring_add":
        await query.edit_message_text(
            "➕ <b>Добавление источника мониторинга</b>\n\n"
            "📌 <b>Способы добавления:</b>\n\n"
            "1️⃣ <b>Отправьте ссылку на канал:</b>\n"
            "• <code>@channel_username</code>\n"
            "• <code>https://t.me/channel_username</code>\n\n"
            "2️⃣ <b>Перешлите сообщение:</b>\n"
            "• Из любого канала или чата\n"
            "• Бот автоматически предложит добавить источник\n\n"
            "3️⃣ <b>Для закрытых каналов/чатов:</b>\n"
            "• Добавьте бота в канал/чат как администратора\n"
            "• Или пригласите по ссылке-приглашению\n\n"
            "📨 <b>Отправьте ссылку или username прямо сейчас!</b>",
            parse_mode=ParseMode.HTML
        )
        # Устанавливаем состояние ожидания ссылки
        user.current_state = "awaiting_source_link"
        Storage.update_user(user)
    
    elif data == "monitoring_list":
        await show_monitoring_list(query, context, user)
    
    elif data == "monitoring_remove":
        await show_monitoring_remove(query, context, user)
    
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
    elif data == "admin_threshold":
        if Storage.is_admin(user_id):
            # Устанавливаем состояние для администратора
            user = Storage.get_user(user_id)
            user.current_state = "admin_threshold_setup"
            Storage.update_user(user)
            
            await query.edit_message_text(
                "📊 <b>Изменение глобального порога важности</b>\n\n"
                f"Текущий порог: <b>{Storage.bot_config.importance_threshold}</b>\n\n"
                "💡 <b>Отправьте новое значение от 0.0 до 1.0</b>\n"
                "Например: 0.7\n\n"
                "🔍 <b>Рекомендации:</b>\n"
                "• 0.3-0.5 - Только очень важные\n"
                "• 0.5-0.7 - Важные (рекомендуется)\n"
                "• 0.7-0.9 - Большинство сообщений",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text("❌ У вас нет прав администратора.")
    
    elif data == "admin_toggle_autopublish":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            config.auto_publish_enabled = not config.auto_publish_enabled
            Storage.update_config(config)
            
            await query.edit_message_text(
                f"✅ <b>Настройка изменена</b>\n\n"
                f"🤖 Автопубликация: {'Включена' if config.auto_publish_enabled else 'Отключена'}\n\n"
                f"💡 {'Важные сообщения будут публиковаться автоматически' if config.auto_publish_enabled else 'Все посты требуют ручной модерации'}",
                parse_mode=ParseMode.HTML
            )
    
    elif data == "admin_toggle_approval":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            config.require_admin_approval = not config.require_admin_approval
            Storage.update_config(config)
            
            await query.edit_message_text(
                f"✅ <b>Настройка изменена</b>\n\n"
                f"✋ Требует одобрения админа: {'Да' if config.require_admin_approval else 'Нет'}\n\n"
                f"💡 {'Все посты проходят модерацию' if config.require_admin_approval else 'Посты с высокой оценкой публикуются автоматически'}",
                parse_mode=ParseMode.HTML
            )
    
    elif data.startswith("admin_approve_"):
        if Storage.is_admin(user_id):
            post_id = data.replace("admin_approve_", "")
            success = await AdminService.approve_post(context.bot, post_id, user_id)
            
            if success:
                # Проверяем, есть ли еще посты на модерации
                pending_posts = AdminService.get_posts_for_review()
                
                if pending_posts:
                    # Показываем следующий пост
                    await query.edit_message_text(
                        f"✅ Пост {post_id} одобрен и опубликован!\n\n"
                        f"📝 Осталось постов на модерации: {len(pending_posts)}",
                        parse_mode=ParseMode.HTML
                    )
                    
                    # Автоматически показываем следующий пост через 2 секунды
                    await asyncio.sleep(2)
                    
                    # Эмулируем нажатие кнопки "Следующий"
                    query.data = "admin_next_post"
                    await callback_handler(update, context)
                else:
                    await query.edit_message_text(
                        f"✅ Пост {post_id} одобрен и опубликован!\n\n"
                        f"✅ Все посты обработаны!",
                        parse_mode=ParseMode.HTML
                    )
            else:
                await query.edit_message_text(f"❌ Ошибка при одобрении поста {post_id}.")
    
    elif data.startswith("admin_reject_"):
        if Storage.is_admin(user_id):
            post_id = data.replace("admin_reject_", "")
            success = await AdminService.reject_post(context.bot, post_id, user_id, "Отклонен администратором")
            
            if success:
                # Проверяем, есть ли еще посты на модерации
                pending_posts = AdminService.get_posts_for_review()
                
                if pending_posts:
                    # Показываем следующий пост
                    await query.edit_message_text(
                        f"❌ Пост {post_id} отклонен.\n\n"
                        f"📝 Осталось постов на модерации: {len(pending_posts)}",
                        parse_mode=ParseMode.HTML
                    )
                    
                    # Автоматически показываем следующий пост через 2 секунды
                    await asyncio.sleep(2)
                    
                    # Эмулируем нажатие кнопки "Следующий"
                    query.data = "admin_next_post"
                    await callback_handler(update, context)
                else:
                    await query.edit_message_text(
                        f"❌ Пост {post_id} отклонен.\n\n"
                        f"✅ Все посты обработаны!",
                        parse_mode=ParseMode.HTML
                    )
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
    
    elif data == "admin_next_post":
        if Storage.is_admin(user_id):
            # Получаем список постов на модерации
            pending_posts = AdminService.get_posts_for_review()
            
            if len(pending_posts) <= 1:
                await query.edit_message_text(
                    "✅ <b>Больше нет постов на модерации</b>\n\n"
                    "Все предложенные посты обработаны.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Находим следующий пост (пропускаем первый, так как он уже показан)
            next_post = pending_posts[1] if len(pending_posts) > 1 else pending_posts[0]
            
            post_text = (
                f"📝 <b>Пост на модерации</b> (2 из {len(pending_posts)})\n\n"
                f"📋 <b>ID поста:</b> {next_post.post_id}\n"
                f"👤 <b>От пользователя:</b> {next_post.user_id}\n"
                f"📅 <b>Время:</b> {next_post.submitted_at.strftime('%d.%m.%Y %H:%M')}\n"
            )
            
            if next_post.source_info:
                post_text += f"📋 <b>Источник:</b> {next_post.source_info}\n"
            
            if next_post.importance_score:
                post_text += f"⭐ <b>Оценка ИИ:</b> {next_post.importance_score:.2f}\n"
            
            post_text += f"\n📄 <b>Текст:</b>\n{next_post.message_text[:400]}"
            
            if len(next_post.message_text) > 400:
                post_text += "..."
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve_{next_post.post_id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_{next_post.post_id}")
                ],
                [
                    InlineKeyboardButton("📄 Полный текст", callback_data=f"admin_full_{next_post.post_id}"),
                    InlineKeyboardButton("⏭️ Следующий", callback_data="admin_next_post")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                post_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    
    elif data == "admin_clear_channel":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            config.publish_channel_id = None
            config.publish_channel_username = None
            Storage.update_config(config)
            
            # Сбрасываем состояние пользователя
            user = Storage.get_user(user_id)
            user.current_state = None
            Storage.update_user(user)
            
            await query.edit_message_text("✅ Настройки канала публикации очищены.")
    
    elif data == "refresh_channels":
        if Storage.is_admin(user_id):
            # Сохраняем состояние пользователя (не сбрасываем)
            user = Storage.get_user(user_id)
            user.current_state = "channel_setup"
            Storage.update_user(user)
            
            # Обновляем интерфейс с новым списком каналов
            await query.message.delete()
            await show_channel_config(query, context)
    
    elif data.startswith("set_channel_"):
        if Storage.is_admin(user_id):
            channel_id = int(data.replace("set_channel_", ""))
            config = Storage.bot_config
            config.publish_channel_id = channel_id
            
            # Сбрасываем состояние пользователя
            user = Storage.get_user(user_id)
            user.current_state = None
            Storage.update_user(user)
            
            try:
                # Получаем информацию о канале
                chat = await context.bot.get_chat(channel_id)
                if chat.username:
                    config.publish_channel_username = chat.username
                Storage.update_config(config)
                
                await query.edit_message_text(
                    f"✅ <b>Канал настроен успешно!</b>\n\n"
                    f"📋 <b>ID канала:</b> {channel_id}\n"
                    f"📝 <b>Название:</b> {html.escape(chat.title)}\n"
                    f"🏷️ <b>Username:</b> @{html.escape(chat.username) if chat.username else 'отсутствует'}",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                # Сохраняем ID даже если не удалось получить информацию
                Storage.update_config(config)
                await query.edit_message_text(
                    f"⚠️ Канал настроен, но не удалось получить информацию: {html.escape(str(e))}\n\n"
                    f"📋 <b>ID канала:</b> {channel_id}",
                    parse_mode=ParseMode.HTML
                )
    
    elif data.startswith("force_set_channel_"):
        if Storage.is_admin(user_id):
            channel_id = int(data.replace("force_set_channel_", ""))
            config = Storage.bot_config
            config.publish_channel_id = channel_id
            
            # Сбрасываем состояние пользователя
            user = Storage.get_user(user_id)
            user.current_state = None
            Storage.update_user(user)
            
            try:
                chat = await context.bot.get_chat(channel_id)
                if chat.username:
                    config.publish_channel_username = chat.username
                Storage.update_config(config)
                
                await query.edit_message_text(
                    f"✅ <b>Канал сохранен принудительно</b>\n\n"
                    f"📝 <b>Название:</b> {html.escape(chat.title)}\n"
                    f"📋 <b>ID:</b> {channel_id}\n\n"
                    f"⚠️ <b>Внимание:</b> Для публикации постов добавьте бота как администратора",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                Storage.update_config(config)
                await query.edit_message_text(
                    f"✅ <b>Канал сохранен</b>\n\n"
                    f"📋 <b>ID:</b> {channel_id}\n"
                    f"⚠️ <b>Не удалось получить информацию:</b> {html.escape(str(e))}",
                    parse_mode=ParseMode.HTML
                )
    
    elif data == "cancel_channel_setup":
        # Сбрасываем состояние пользователя
        user = Storage.get_user(user_id)
        user.current_state = None
        Storage.update_user(user)
        
        await query.edit_message_text(
            "❌ <b>Настройка канала отменена</b>\n\n"
            "💡 Добавьте бота как администратора в канал и попробуйте снова.",
            parse_mode=ParseMode.HTML
        )
    
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
    
    elif data == "my_submissions":
        # Получаем посты пользователя
        all_posts = Storage.get_pending_posts()
        user_posts = [post for post in all_posts if post.user_id == user_id]
        
        if not user_posts:
            await query.edit_message_text(
                "📄 <b>У вас нет предложенных постов</b>\n\n"
                "Нажмите '📝 Предложить пост' в главном меню, чтобы отправить пост на модерацию.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Сортируем по дате
        user_posts.sort(key=lambda x: x.submitted_at, reverse=True)
        
        text = "📄 <b>Ваши предложенные посты:</b>\n\n"
        
        for post in user_posts[:10]:  # Показываем последние 10
            status_emoji = {
                PostStatus.PENDING: "⏳",
                PostStatus.APPROVED: "✅",
                PostStatus.REJECTED: "❌",
                PostStatus.PUBLISHED: "📢"
            }.get(post.status, "❓")
            
            status_text = {
                PostStatus.PENDING: "Ожидает",
                PostStatus.APPROVED: "Одобрен",
                PostStatus.REJECTED: "Отклонен",
                PostStatus.PUBLISHED: "Опубликован"
            }.get(post.status, "Неизвестно")
            
            text += f"{status_emoji} <b>{status_text}</b> - {post.submitted_at.strftime('%d.%m %H:%M')}\n"
            text += f"   {html.escape(post.message_text[:50])}{'...' if len(post.message_text) > 50 else ''}\n\n"
        
        if len(user_posts) > 10:
            text += f"<i>... и еще {len(user_posts) - 10} постов</i>"
        
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    
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
    
    # Help callbacks
    elif data == "help_quickstart":
        await show_quickstart_help(query)
    
    elif data == "help_tips":
        await show_tips_help(query)
    
    elif data == "help_faq":
        await show_faq_help(query)
    
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
        
        # Синхронизируем с системой мониторинга
        if USERBOT_ENABLED:
            try:
                userbot = get_userbot()
                if userbot.is_running:
                    userbot.add_monitoring_source(chat_id)
            except Exception as e:
                logger.error(f"Ошибка синхронизации с системой мониторинга: {e}")
        
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
        forwarded_msg = None
        if (update.effective_message and 
            hasattr(update.effective_message, 'reply_to_message') and 
            update.effective_message.reply_to_message):
            forwarded_msg = update.effective_message.reply_to_message
        
        if forwarded_msg:
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
            importance_score = evaluate_message_importance(message, user)
            
            result_text = (
                f"🔍 <b>Анализ завершен</b>\n\n"
                f"📊 <b>Оценка важности:</b> {importance_score:.2f}\n"
                f"🎯 <b>Глобальный порог:</b> {Storage.bot_config.importance_threshold}\n\n"
                f"{'✅ Сообщение важное!' if importance_score >= Storage.bot_config.importance_threshold else '❌ Сообщение не достигает порога важности.'}\n\n"
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
    
    # Channel suggestion callbacks
    elif data.startswith("add_suggested_channel_"):
        if Storage.is_admin(user_id):
            channel_text = data.replace("add_suggested_channel_", "")
            
            # Пытаемся добавить канал в мониторинг
            try:
                # Получаем информацию о канале
                chat = await context.bot.get_chat(channel_text)
                
                # Добавляем в мониторинг администратора
                admin_user = Storage.get_user(user_id)
                if chat.type == 'channel':
                    admin_user.monitored_channels.add(chat.id)
                else:
                    admin_user.monitored_chats.add(chat.id)
                Storage.update_user(admin_user)
                
                await query.edit_message_text(
                    f"✅ <b>Канал добавлен в мониторинг!</b>\n\n"
                    f"📝 <b>Название:</b> {html.escape(chat.title)}\n"
                    f"📋 <b>ID:</b> {chat.id}\n"
                    f"🏷️ <b>Username:</b> @{html.escape(chat.username) if chat.username else 'отсутствует'}",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                await query.edit_message_text(
                    f"❌ <b>Не удалось добавить канал</b>\n\n"
                    f"📋 <b>Ошибка:</b> {html.escape(str(e))}\n\n"
                    f"💡 Проверьте корректность ссылки и доступность канала.",
                    parse_mode=ParseMode.HTML
                )
    
    elif data == "reject_channel_suggestion":
        if Storage.is_admin(user_id):
            await query.edit_message_text(
                "❌ <b>Предложение канала отклонено</b>\n\n"
                "Уведомление пользователю не отправляется.",
                parse_mode=ParseMode.HTML
            )

# ===========================================
# HELPER FUNCTIONS FOR CALLBACKS
# ===========================================

async def show_monitoring_list(query, context: CallbackContext, user: UserPreferences) -> None:
    """Show list of monitored sources."""
    # Собираем все источники в один набор
    all_sources = set()
    
    # Добавляем источники пользователя
    all_sources.update(user.monitored_chats)
    all_sources.update(user.monitored_channels)
    
    # Добавляем источники из системы мониторинга если она включена
    if USERBOT_ENABLED:
        userbot = get_userbot()
        if userbot.is_running:
            userbot_sources = userbot.get_monitored_sources()
            all_sources.update(userbot_sources)
    
    if not all_sources:
        await query.edit_message_text("❌ Нет источников в мониторинге.")
        return
    
    list_text = "📋 <b>Список источников мониторинга:</b>\n\n"
    
    # Показываем все источники в едином списке
    for source_id in sorted(all_sources):
        try:
            chat = await context.bot.get_chat(source_id)
            chat_title = html.escape(chat.title or "Без названия")
            chat_link = f"https://t.me/{chat.username}" if chat.username else ""
            
            # Определяем тип источника
            if chat.type == 'channel':
                icon = "📢"
            elif chat.type in ['group', 'supergroup']:
                icon = "💬"
            else:
                icon = "👤"
            
            if chat_link:
                list_text += f"{icon} <a href='{chat_link}'>{chat_title}</a> ({source_id})\n"
            else:
                list_text += f"{icon} {chat_title} ({source_id})\n"
        except Exception:
            list_text += f"❓ Источник ID: {source_id}\n"
    
    list_text += f"\n📊 <b>Всего источников:</b> {len(all_sources)}"
    
    await query.edit_message_text(list_text, parse_mode=ParseMode.HTML)

async def show_monitoring_remove(query, context: CallbackContext, user: UserPreferences) -> None:
    """Show interface to remove monitored sources."""
    if not user.monitored_chats and not user.monitored_channels:
        await query.edit_message_text("❌ Нет источников для удаления.")
        return
    
    keyboard = []
    
    # Add chat buttons
    for chat_id in user.monitored_chats:
        try:
            chat = await context.bot.get_chat(chat_id)
            chat_title = chat.title or "Без названия"
            button_text = f"💬 {chat_title[:30]}{'...' if len(chat_title) > 30 else ''}"
        except Exception:
            button_text = f"💬 Чат: {chat_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"remove_chat_{chat_id}")])
    
    # Add channel buttons
    for channel_id in user.monitored_channels:
        try:
            channel = await context.bot.get_chat(channel_id)
            channel_title = channel.title or "Без названия"
            button_text = f"📢 {channel_title[:30]}{'...' if len(channel_title) > 30 else ''}"
        except Exception:
            button_text = f"📢 Канал: {channel_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"remove_channel_{channel_id}")])
    
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
        "📊 <b>Мониторинг:</b>\n"
        "• Лучший способ отслеживания\n"
        "• Работает 24/7 автоматически\n"
        "• Конфиденциальный анализ\n\n"
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
        "A: Используйте функцию мониторинга - она может работать с любыми каналами\n\n"
        "<b>Q: Почему не приходят уведомления?</b>\n"
        "A: Проверьте порог важности и ключевые слова\n\n"
        "<b>Q: Можно ли мониторить без добавления бота?</b>\n"
        "A: Да, используйте функцию мониторинга или перешлите сообщение\n\n"
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
                importance_score = evaluate_message_importance(message, user)
                message.importance_score = importance_score
                
                logger.info(f"Оценка важности: {importance_score:.2f}, порог: {Storage.bot_config.importance_threshold}")
                
                # Check if the message is important enough to notify the user
                if importance_score >= Storage.bot_config.importance_threshold:
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
                                            f"что ниже глобального порога <b>{Storage.bot_config.importance_threshold}</b>.\n\n"
                    f"💡 Администраторы могут изменить глобальный порог важности.",
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
                importance_score = evaluate_message_importance(message, user)
                message.importance_score = importance_score
                max_importance_score = max(max_importance_score, importance_score)
                
                logger.info(f"Оценка важности для пользователя {user.user_id}: {importance_score:.2f}, порог: {Storage.bot_config.importance_threshold}")
                
                # If message is important enough, send notification to user
                if importance_score >= Storage.bot_config.importance_threshold:
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
                              f"(оценка: {importance_score:.2f}, порог: {Storage.bot_config.importance_threshold})")
                    
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
    import signal
    import sys
    
    # Load storage data
    Storage.load_from_file()
    logger.info("📂 Данные загружены из файлов")
    
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
    
    # Store userbot task for proper cleanup
    userbot_task = None
    
    # Signal handler for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        
        # Stop userbot if running
        if USERBOT_ENABLED and userbot_task:
            try:
                from userbot import stop_userbot
                asyncio.create_task(stop_userbot())
                logger.info("🤖 Userbot остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки userbot: {e}")
        
        # Save data before exit
        try:
            Storage.save_to_file()
            logger.info("📂 Данные сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
        
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("🚀 Упрощенный бот запущен!")
    
    # Запускаем userbot в фоновом режиме
    if USERBOT_ENABLED:
        try:
            import asyncio
            from userbot import start_userbot
            
            # Создаем задачу для запуска userbot
            async def start_userbot_task():
                try:
                    # Передаем ссылку на основного бота
                    await start_userbot(application.bot)
                except Exception as e:
                    logger.error(f"Ошибка запуска userbot: {e}")
            
            # Запускаем userbot в отдельной задаче
            loop = asyncio.get_event_loop()
            userbot_task = loop.create_task(start_userbot_task())
            logger.info("🤖 Userbot запускается в фоновом режиме...")
            
        except Exception as e:
            logger.error(f"Не удалось запустить userbot: {e}")
    
    try:
        # Start the Bot
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания, завершение работы...")
    except Exception as e:
        logger.error(f"Ошибка в основном цикле бота: {e}")
    finally:
        # Cleanup
        if USERBOT_ENABLED and userbot_task:
            try:
                from userbot import stop_userbot
                asyncio.create_task(stop_userbot())
                logger.info("🤖 Userbot остановлен")
            except Exception as e:
                logger.error(f"Ошибка остановки userbot: {e}")
        
        # Save data
        try:
            Storage.save_to_file()
            logger.info("📂 Данные сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")
        
        logger.info("Бот завершил работу")

if __name__ == '__main__':
    main()