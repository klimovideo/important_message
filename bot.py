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

async def admin_add_command(update: Update, context: CallbackContext) -> None:
    """Add administrator by username - for compatibility."""
    user_id = update.effective_user.id
    
    if not Storage.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Укажите username</b>\n\n"
            "Использование: /admin_add @username",
            parse_mode=ParseMode.HTML
        )
        return
    
    username = context.args[0].strip().lstrip('@')
    
    try:
        # Пытаемся получить пользователя по username
        chat_member = await context.bot.get_chat(f"@{username}")
        admin_id = chat_member.id
        
        if admin_id not in Storage.bot_config.admin_ids:
            Storage.add_admin(admin_id)
            
            await update.message.reply_text(
                f"✅ <b>Администратор добавлен</b>\n\n"
                f"👤 <b>Username:</b> @{username}\n"
                f"🆔 <b>ID:</b> {admin_id}\n"
                f"📱 <b>Имя:</b> {chat_member.first_name or 'Не указано'}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                f"⚠️ Пользователь @{username} уже является администратором.",
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        await update.message.reply_text(
            f"❌ <b>Не удалось найти пользователя</b>\n\n"
            f"Username: @{username}\n\n"
            f"💡 Убедитесь, что:\n"
            f"• Username написан правильно\n"
            f"• Пользователь существует\n"
            f"• Пользователь взаимодействовал с ботом ранее",
            parse_mode=ParseMode.HTML
        )

async def admin_remove_command(update: Update, context: CallbackContext) -> None:
    """Remove administrator by ID or username - for compatibility."""
    user_id = update.effective_user.id
    
    if not Storage.is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ <b>Укажите ID или username</b>\n\n"
            "Использование: /admin_remove user_id или /admin_remove @username",
            parse_mode=ParseMode.HTML
        )
        return
    
    arg = context.args[0].strip()
    
    # Try to parse as ID
    if arg.isdigit():
        admin_id = int(arg)
        
        if admin_id == user_id:
            await update.message.reply_text("❌ Нельзя удалить себя из администраторов.")
            return
        
        if admin_id in Storage.bot_config.admin_ids:
            Storage.remove_admin(admin_id)
            await update.message.reply_text(
                f"✅ <b>Администратор удален</b>\n\n"
                f"ID: {admin_id}",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(f"❌ Пользователь {admin_id} не является администратором.")
    else:
        # Try as username
        username = arg.lstrip('@')
        
        try:
            chat_member = await context.bot.get_chat(f"@{username}")
            admin_id = chat_member.id
            
            if admin_id == user_id:
                await update.message.reply_text("❌ Нельзя удалить себя из администраторов.")
                return
            
            if admin_id in Storage.bot_config.admin_ids:
                Storage.remove_admin(admin_id)
                await update.message.reply_text(
                    f"✅ <b>Администратор удален</b>\n\n"
                    f"Username: @{username}\n"
                    f"ID: {admin_id}",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(f"❌ Пользователь @{username} не является администратором.")
        except Exception:
            await update.message.reply_text(f"❌ Не удалось найти пользователя @{username}.")

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
    total_sources = len(user.monitored_chats) + len(user.monitored_channels)
    
    monitoring_text = (
        f"📊 <b>Мониторинг источников</b>\n\n"
        f"📈 <b>Статистика:</b>\n"
        f"• Всего источников: {total_sources}\n"
        f"• Чатов: {len(user.monitored_chats)}\n"
        f"• Каналов: {len(user.monitored_channels)}\n"
        f"• Порог важности: {Storage.bot_config.importance_threshold} (глобальный)\n"
    )
    
    # Добавляем информацию о userbot, если включен
    if USERBOT_ENABLED:
        try:
            userbot = get_userbot()
            if userbot.is_running:
                monitored_userbot = userbot.get_monitored_sources()
                monitoring_text += f"\n\n🤖 <b>Скрытый мониторинг (Userbot):</b>\n"
                monitoring_text += f"• Статус: ✅ Активен\n"
                monitoring_text += f"• Источников: {len(monitored_userbot)}\n"
            else:
                monitoring_text += f"\n\n🤖 <b>Скрытый мониторинг (Userbot):</b>\n"
                monitoring_text += f"• Статус: ❌ Неактивен\n"
        except:
            monitoring_text += f"\n\n🤖 <b>Скрытый мониторинг:</b> Недоступен\n"
    
    monitoring_text += (
        f"\n💡 <b>Как добавить источник:</b>\n"
        f"1. Перешлите сообщение из чата/канала боту\n"
        f"2. Выберите действие в предложенном меню"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📋 Список источников", callback_data="monitoring_list"),
            InlineKeyboardButton("🗑️ Удалить источник", callback_data="monitoring_remove")
        ]
    ]
    
    # Добавляем кнопки userbot, если он доступен
    if USERBOT_ENABLED:
        userbot = get_userbot()
        if userbot.is_running:
            keyboard.append([
                InlineKeyboardButton("⏹️ Остановить Userbot", callback_data="userbot_stop"),
                InlineKeyboardButton("➕ Добавить в Userbot", callback_data="userbot_join")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🚀 Запустить Userbot", callback_data="userbot_start")
            ])
    
    keyboard.append([
        InlineKeyboardButton("🧹 Очистить все", callback_data="monitoring_clear")
    ])
    
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
        InlineKeyboardButton("🗑️ Очистить данные", callback_data="settings_clear")
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

async def show_keywords_interface(query, context: CallbackContext, user: UserPreferences) -> None:
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
    
    # Check if this is a callback query or regular message
    if hasattr(query, 'message'):
        # Called from a callback query (button press)
        await query.message.delete()
        await query.message.reply_text(
            keywords_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    else:
        # Called from a regular message
        await query.reply_text(
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
            f"💡 <b>Совет:</b> Используйте Userbot для скрытого мониторинга закрытых каналов"
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
    else:
        # Для обычных пользователей без inline кнопок
        await update.message.reply_text(
            help_text,
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
        f"\n💡 <b>Для добавления администратора отправьте его username</b>\n"
        f"Например: @username или username (без @)\n"
    )
    
    # Создаем инлайн кнопки
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить админа", callback_data="admin_add_start"),
            InlineKeyboardButton("➖ Удалить админа", callback_data="admin_remove_start")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        admins_text,
        reply_markup=reply_markup,
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
    # Устанавливаем состояние пользователя
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    user.current_state = "userbot_join"
    Storage.update_user(user)
    
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
        status_text += f"• Порог важности: {Storage.bot_config.importance_threshold} (глобальный)\n"
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
            except Exception:
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
    
    # Handle admin username input (проверяем в первую очередь для админов с активным состоянием)
    if Storage.is_admin(user_id) and user.current_state == "admin_add_username":
        # Сбрасываем состояние
        user.current_state = None
        Storage.update_user(user)
        
        # Очищаем username от @
        username = text.strip().lstrip('@')
        
        if not username:
            await update.message.reply_text("❌ Username не может быть пустым.")
            return
        
        try:
            # Пытаемся получить пользователя по username
            chat_member = await context.bot.get_chat(f"@{username}")
            admin_id = chat_member.id
            
            if admin_id not in Storage.bot_config.admin_ids:
                Storage.add_admin(admin_id)
                
                await update.message.reply_text(
                    f"✅ <b>Администратор добавлен</b>\n\n"
                    f"👤 <b>Username:</b> @{username}\n"
                    f"🆔 <b>ID:</b> {admin_id}\n"
                    f"📱 <b>Имя:</b> {chat_member.first_name or 'Не указано'}",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Пользователь @{username} уже является администратором.",
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ <b>Не удалось найти пользователя</b>\n\n"
                f"Username: @{username}\n\n"
                f"💡 Убедитесь, что:\n"
                f"• Username написан правильно\n"
                f"• Пользователь существует\n"
                f"• Пользователь взаимодействовал с ботом ранее",
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
    
    # Handle keyword additions
    if text.startswith('+') and len(text) > 1 and not text[1:].isdigit():
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
    
    # Handle admin threshold setup
    if Storage.is_admin(user_id) and user.current_state == "admin_threshold_setup":
        try:
            # Проверяем, что это число
            threshold_text = text.replace(',', '.')  # Поддержка запятой как разделителя
            threshold = float(threshold_text)
            
            if 0 <= threshold <= 1:
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
            else:
                await update.message.reply_text(
                    "❌ <b>Неверное значение</b>\n\n"
                    "Порог должен быть числом от 0.0 до 1.0",
                    parse_mode=ParseMode.HTML
                )
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Неверный формат</b>\n\n"
                "Отправьте число от 0.0 до 1.0\n"
                "Например: 0.7",
                parse_mode=ParseMode.HTML
            )
        return
    
    # Handle threshold input without state (direct number input)
    elif Storage.is_admin(user_id) and text.replace(',', '.').replace('.', '').isdigit() and len(text) <= 4:
        try:
            threshold_text = text.replace(',', '.')
            threshold = float(threshold_text)
            
            if 0 <= threshold <= 1:
                config = Storage.bot_config
                config.importance_threshold = threshold
                Storage.update_config(config)
                
                await update.message.reply_text(
                    f"✅ <b>Глобальный порог важности установлен:</b> {threshold}\n\n"
                    f"💡 Сообщения с оценкой выше {threshold} будут считаться важными",
                    parse_mode=ParseMode.HTML
                )
                return
        except:
            pass  # Продолжаем обработку как обычное сообщение
    
    # Handle userbot join links (priority for userbot functionality)
    if ('t.me/' in text or text.startswith('@')) and USERBOT_ENABLED:
        # Если пользователь в состоянии userbot_join и является админом
        if user.current_state == "userbot_join" and Storage.is_admin(user_id):
            await handle_userbot_join_text(update, context, text)
            return
        # Для обычных пользователей - не обрабатываем как userbot join
        elif not Storage.is_admin(user_id):
            # Обработка будет в следующем блоке для предложений каналов
            pass
    
    # Handle userbot leave (numeric ID)
    elif text.lstrip('-').isdigit() and USERBOT_ENABLED and len(text) > 5:
        if Storage.is_admin(user_id):
            await handle_userbot_leave_text(update, context, text)
        else:
            await update.message.reply_text("❌ Эта функция доступна только администраторам.")
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

async def handle_userbot_join_text(update: Update, context: CallbackContext, text: str) -> None:
    """Handle userbot join from text input."""
    try:
        userbot = get_userbot()
        if not userbot.is_running:
            await update.message.reply_text("❌ Сначала запустите userbot кнопкой '🚀 Запустить'")
            return
        
        # Получаем информацию о канале/чате
        chat_info = await userbot.get_chat_info(text)
        if not chat_info:
            await update.message.reply_text(
                f"❌ <b>Не удалось получить информацию о канале</b>\n\n"
                f"🔗 <b>Ссылка:</b> {text}\n"
                f"💡 Проверьте корректность ссылки.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Try to join the channel/chat
        result = await userbot.join_chat(text)
        if result:
            # Добавляем канал в список мониторимых источников пользователя
            user_id = update.effective_user.id
            user = Storage.get_user(user_id)
            
            # Определяем тип источника и добавляем в соответствующий список
            if chat_info['type'] == 'CHANNEL':
                user.monitored_channels.add(chat_info['id'])
                source_type = "канал"
            else:
                user.monitored_chats.add(chat_info['id'])
                source_type = "чат"
            
            # Сбрасываем состояние пользователя
            user.current_state = None
            Storage.update_user(user)
            
            # Убеждаемся, что userbot также мониторит этот источник
            userbot.add_monitoring_source(chat_info['id'])
            
            await update.message.reply_text(
                f"✅ <b>Успешно присоединился!</b>\n\n"
                f"🔗 <b>Ссылка:</b> {text}\n"
                f"📝 <b>Название:</b> {html.escape(chat_info['title'])}\n"
                f"📊 <b>Тип:</b> {source_type}\n"
                f"📋 <b>ID:</b> {chat_info['id']}\n"
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
        
        # Удаляем из списка мониторимых источников пользователя
        user_id = update.effective_user.id
        user = Storage.get_user(user_id)
        
        # Удаляем из обоих списков (каналы и чаты)
        user.monitored_channels.discard(chat_id)
        user.monitored_chats.discard(chat_id)
        Storage.update_user(user)
        
        result = await userbot.leave_chat(chat_id)
        if result:
            # Обновляем userbot мониторинг
            userbot.remove_monitoring_source(chat_id)
            
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
    if not query:
        return
        
    await query.answer()
    
    data = query.data
    if not data:
        return
        
    user_id = update.effective_user.id
    user = Storage.get_user(user_id)
    
    # Monitoring callbacks
    if data == "monitoring_list":
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
        await show_keywords_interface(query, context, user)
    
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
        f"🏷️ <b>Username:</b> @{html.escape(chat.username or 'отсутствует')}",
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
    
    # Admin management callbacks
    elif data == "admin_add_start":
        if Storage.is_admin(user_id):
            # Устанавливаем состояние для администратора
            user = Storage.get_user(user_id)
            user.current_state = "admin_add_username"
            Storage.update_user(user)
            
            await query.edit_message_text(
                "➕ <b>Добавление администратора</b>\n\n"
                "💡 <b>Отправьте username пользователя:</b>\n"
                "• @username\n"
                "• username (без @)\n\n"
                "❌ Для отмены нажмите /menu",
                parse_mode=ParseMode.HTML
            )
    
    elif data == "admin_remove_start":
        if Storage.is_admin(user_id):
            config = Storage.bot_config
            
            if len(config.admin_ids) <= 1:
                await query.edit_message_text(
                    "❌ <b>Невозможно удалить последнего администратора</b>\n\n"
                    "В системе должен оставаться хотя бы один администратор.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            keyboard = []
            
            # Создаем кнопки для каждого администратора
            for admin_id in config.admin_ids:
                if admin_id == user_id:
                    continue  # Не показываем кнопку для удаления себя
                
                try:
                    chat_member = await context.bot.get_chat(admin_id)
                    if chat_member.username:
                        display_name = f"@{chat_member.username}"
                    elif chat_member.first_name:
                        display_name = chat_member.first_name
                    else:
                        display_name = f"ID: {admin_id}"
                    
                    keyboard.append([
                        InlineKeyboardButton(f"❌ {display_name}", callback_data=f"admin_remove_{admin_id}")
                    ])
                except:
                    keyboard.append([
                        InlineKeyboardButton(f"❌ ID: {admin_id}", callback_data=f"admin_remove_{admin_id}")
                    ])
            
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "➖ <b>Удаление администратора</b>\n\n"
                "💡 Выберите администратора для удаления:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
    
    elif data.startswith("admin_remove_"):
        if Storage.is_admin(user_id):
            admin_to_remove = int(data.replace("admin_remove_", ""))
            
            if admin_to_remove == user_id:
                await query.edit_message_text("❌ Нельзя удалить себя из администраторов.")
                return
            
            if admin_to_remove in Storage.bot_config.admin_ids:
                Storage.remove_admin(admin_to_remove)
                await query.edit_message_text(
                    f"✅ <b>Администратор удален</b>\n\n"
                    f"ID: {admin_to_remove}",
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.edit_message_text("❌ Пользователь не является администратором.")
    
    elif data == "admin_back":
        if Storage.is_admin(user_id):
            await query.message.delete()
            # Создаем фиктивный update для show_admins_management
            await show_admins_management(update, context)
    
    # Userbot callbacks from monitoring interface
    elif data == "userbot_start":
        if USERBOT_ENABLED and Storage.is_admin(user_id):
            try:
                userbot = get_userbot()
                if userbot.is_running:
                    await query.answer("⚠️ Userbot уже запущен.")
                    return
                
                await start_userbot()
                await query.answer("✅ Userbot запущен!")
                
                # Обновляем интерфейс мониторинга
                await query.message.delete()
                await show_monitoring_interface(update, context, user)
                
            except Exception as e:
                logger.error(f"Ошибка запуска userbot: {e}")
                await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        else:
            await query.answer("❌ Недоступно", show_alert=True)
    
    elif data == "userbot_stop":
        if USERBOT_ENABLED and Storage.is_admin(user_id):
            try:
                userbot = get_userbot()
                if not userbot.is_running:
                    await query.answer("⚠️ Userbot уже остановлен.")
                    return
                
                await stop_userbot()
                await query.answer("⏹️ Userbot остановлен!")
                
                # Обновляем интерфейс мониторинга
                await query.message.delete()
                await show_monitoring_interface(update, context, user)
                
            except Exception as e:
                logger.error(f"Ошибка остановки userbot: {e}")
                await query.answer(f"❌ Ошибка: {str(e)}", show_alert=True)
        else:
            await query.answer("❌ Недоступно", show_alert=True)
    
    elif data == "userbot_join":
        if USERBOT_ENABLED and Storage.is_admin(user_id):
            # Устанавливаем состояние пользователя для ввода ссылки
            user.current_state = "userbot_join"
            Storage.update_user(user)
            
            await query.edit_message_text(
                "➕ <b>Добавление источника в скрытый мониторинг</b>\n\n"
                "💡 <b>Отправьте ссылку на канал или чат:</b>\n"
                "• https://t.me/channel_name\n"
                "• @channel_name\n"
                "• Ссылку-приглашение\n\n"
                "🔒 <b>Поддерживаются:</b>\n"
                "• Публичные каналы\n"
                "• Приватные каналы (по ссылке-приглашению)\n"
                "• Группы и супергруппы\n\n"
                "❌ Для отмены нажмите /menu",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.answer("❌ Недоступно", show_alert=True)
    
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
        
        # Синхронизируем с userbot если он запущен
        if USERBOT_ENABLED:
            try:
                userbot = get_userbot()
                if userbot.is_running:
                    userbot.add_monitoring_source(chat_id)
            except Exception as e:
                logger.error(f"Ошибка синхронизации с userbot: {e}")
        
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
    
    elif data.startswith("submit_forwarded_") or data.startswith("submit_for_moderation_"):
        # Get message text from the replied message
        message_text = ""
        source_info = "Пересланное сообщение"
        
        if query.message and query.message.reply_to_message:
            if query.message.reply_to_message.text:
                message_text = query.message.reply_to_message.text
            elif query.message.reply_to_message.caption:
                message_text = query.message.reply_to_message.caption
                
            # Get source info if available
            if hasattr(query.message.reply_to_message, 'forward_origin') and query.message.reply_to_message.forward_origin:
                if hasattr(query.message.reply_to_message.forward_origin, 'chat'):
                    source_chat = query.message.reply_to_message.forward_origin.chat
                    source_info = f"Пересланное из: {source_chat.title or 'Неизвестный чат'}"
                elif hasattr(query.message.reply_to_message.forward_origin, 'sender_user'):
                    sender = query.message.reply_to_message.forward_origin.sender_user
                    source_info = f"Пересланное от: {sender.full_name}"
                elif hasattr(query.message.reply_to_message.forward_origin, 'sender_user_name'):
                    source_info = f"Пересланное от: {query.message.reply_to_message.forward_origin.sender_user_name}"
        
        if message_text:
            try:
                post_id = await AdminService.submit_post_for_review(user_id, message_text, source_info)
                
                # Notify admins
                post = Storage.get_pending_post(post_id)
                if post:
                    await AdminService.notify_admins_about_new_post(context.bot, post)
                
                await query.edit_message_text(
                    f"✅ <b>Пост отправлен на модерацию!</b>\n\n"
                    f"📋 <b>ID поста:</b> {post_id}\n"
                    f"⏳ <b>Статус:</b> Ожидает рассмотрения\n\n"
                    f"💡 Вы получите уведомление о результатах модерации.",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке поста на модерацию: {e}")
                await query.edit_message_text(f"❌ Ошибка при отправке поста: {html.escape(str(e))}")
        else:
            await query.edit_message_text("❌ Не удалось получить текст сообщения.")
    
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
    has_regular_monitoring = user.monitored_chats or user.monitored_channels
    has_userbot_monitoring = False
    
    # Проверяем userbot мониторинг
    userbot_sources = []
    if USERBOT_ENABLED:
        try:
            userbot = get_userbot()
            if userbot.is_running:
                userbot_sources = list(userbot.get_monitored_sources())
                has_userbot_monitoring = bool(userbot_sources)
        except:
            pass
    
    if not has_regular_monitoring and not has_userbot_monitoring:
        await query.edit_message_text("❌ Нет источников в мониторинге.")
        return
    
    list_text = "📋 <b>Список мониторимых источников:</b>\n\n"
    
    # Обычный мониторинг (пересылка сообщений)
    if has_regular_monitoring:
        list_text += "📱 <b>Обычный мониторинг (пересылка):</b>\n\n"
        
        if user.monitored_chats:
            list_text += "💬 <b>Чаты:</b>\n"
            for chat_id in user.monitored_chats:
                try:
                    chat = await context.bot.get_chat(chat_id)
                    chat_title = html.escape(chat.title or "Без названия")
                    chat_link = f"https://t.me/{chat.username}" if chat.username else ""
                    if chat_link:
                        list_text += f"• <a href='{chat_link}'>{chat_title}</a> ({chat_id})\n"
                    else:
                        list_text += f"• {chat_title} ({chat_id})\n"
                except Exception:
                    list_text += f"• {chat_id}\n"
            list_text += "\n"
        
        if user.monitored_channels:
            list_text += "📢 <b>Каналы:</b>\n"
            for channel_id in user.monitored_channels:
                try:
                    channel = await context.bot.get_chat(channel_id)
                    channel_title = html.escape(channel.title or "Без названия")
                    channel_link = f"https://t.me/{channel.username}" if channel.username else ""
                    if channel_link:
                        list_text += f"• <a href='{channel_link}'>{channel_title}</a> ({channel_id})\n"
                    else:
                        list_text += f"• {channel_title} ({channel_id})\n"
                except Exception:
                    list_text += f"• {channel_id}\n"
            list_text += "\n"
    
    # Userbot мониторинг
    if has_userbot_monitoring:
        list_text += "🤖 <b>Скрытый мониторинг (Userbot):</b>\n"
        list_text += f"<i>Всего источников: {len(userbot_sources)}</i>\n\n"
        
        # Показываем первые 10 источников
        for source_id in userbot_sources[:10]:
            try:
                chat = await context.bot.get_chat(source_id)
                chat_title = html.escape(chat.title or "Без названия")
                chat_link = f"https://t.me/{chat.username}" if chat.username else ""
                if chat_link:
                    list_text += f"• <a href='{chat_link}'>{chat_title}</a> ({source_id})\n"
                else:
                    list_text += f"• {chat_title} ({source_id})\n"
            except Exception:
                list_text += f"• ID: {source_id}\n"
        
        if len(userbot_sources) > 10:
            list_text += f"\n<i>... и еще {len(userbot_sources) - 10} источников</i>"
    
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
            
            # Always analyze forwarded messages (both monitored and non-monitored)
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
            
            # Prepare message for the user
            analysis_text = (
                f"🤖 <b>Анализ сообщения от ИИ</b>\n\n"
                f"📋 <b>Источник:</b> {html.escape(chat_title)}\n"
                f"📊 <b>Оценка важности:</b> {importance_score:.2f}\n"
                f"🎯 <b>Глобальный порог:</b> {Storage.bot_config.importance_threshold}\n\n"
            )
            
            # Create keyboard
            keyboard = []
            
            # If not monitored, offer to add to monitoring
            if not is_already_monitored:
                keyboard.append(
                    [InlineKeyboardButton("✅ Добавить в мониторинг", callback_data=f"add_passive_monitoring_{chat_id}_{'channel' if is_channel else 'chat'}")]
                )
            
            # Always offer to submit for moderation
            keyboard.append(
                [InlineKeyboardButton("📝 Отправить админу на модерацию", callback_data=f"submit_for_moderation_{update.message.message_id}")]
            )
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Check if the message is important enough
            if importance_score >= Storage.bot_config.importance_threshold:
                analysis_text += "✅ <b>Сообщение превышает порог важности!</b>\n\n"
                
                # Process important message for potential publication
                try:
                    published = await AdminService.process_important_message(context.bot, message, importance_score)
                    if published:
                        analysis_text += "📢 <i>Сообщение автоматически опубликовано в канале.</i>\n\n"
                        logger.info(f"Важное пересланное сообщение автоматически опубликовано в канале (оценка: {importance_score:.2f})")
                except Exception as e:
                    logger.error(f"Ошибка при обработке важного сообщения для публикации: {e}")
            else:
                analysis_text += "❌ <b>Сообщение ниже порога важности.</b>\n\n"
                
                # If message was rejected by AI, notify admins
                if importance_score < 0.3:  # Very low score
                    try:
                        # Create a pending post for admin review
                        post_id = await AdminService.submit_post_for_review(
                            user_id,
                            message.text,
                            f"Автоматическая модерация: отклонено ИИ (оценка: {importance_score:.2f})"
                        )
                        
                        # Get the post and notify admins
                        post = Storage.get_pending_post(post_id)
                        if post:
                            post.importance_score = importance_score
                            await AdminService.notify_admins_about_new_post(context.bot, post)
                            
                        analysis_text += "📨 <i>Сообщение отправлено администраторам для проверки отклонения.</i>\n\n"
                        logger.info(f"Сообщение с низкой оценкой ({importance_score:.2f}) отправлено админам")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке сообщения админам: {e}")
            
            analysis_text += f"📄 <b>Текст сообщения:</b>\n{html.escape(message.text[:300])}"
            if len(message.text) > 300:
                analysis_text += "..."
            
            await update.message.reply_text(
                analysis_text,
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
    application.add_handler(CommandHandler("admin_add", admin_add_command))
    application.add_handler(CommandHandler("admin_remove", admin_remove_command))
    
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