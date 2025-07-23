import os
import logging
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message as PyrogramMessage
from pyrogram.errors import FloodWait, AuthKeyUnregistered, UserDeactivated

from models import Message, Storage, UserPreferences
from ai_service import evaluate_message_importance
from config import DEFAULT_IMPORTANCE_THRESHOLD

# Setup logging
logger = logging.getLogger(__name__)

class UserBot:
    """
    Userbot для мониторинга каналов и чатов без прав администратора
    Использует фейковый аккаунт Telegram для подписки на каналы и чаты
    """
    
    def __init__(self):
        self.app = None
        self.is_running = False
        self.monitored_sources = set()  # Множество ID каналов/чатов для мониторинга
        
        # Получаем учетные данные из переменных окружения
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone_number = os.getenv("TELEGRAM_PHONE")
        
        if not all([self.api_id, self.api_hash]):
            logger.warning("TELEGRAM_API_ID или TELEGRAM_API_HASH не установлены. Userbot функциональность отключена.")
            return
            
        # Создаем клиент Pyrogram
        self.app = Client(
            "userbot_session",
            api_id=int(self.api_id),
            api_hash=self.api_hash,
            phone_number=self.phone_number,
            workdir="."
        )
        
        # Регистрируем обработчики сообщений
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков сообщений"""
        if not self.app:
            return
            
        @self.app.on_message(filters.all & ~filters.me)
        async def handle_userbot_message(client: Client, message: PyrogramMessage):
            """Обработка всех входящих сообщений в userbot"""
            try:
                await self.process_message(message)
            except Exception as e:
                logger.error(f"Ошибка обработки сообщения в userbot: {e}")
    
    async def process_message(self, message: PyrogramMessage):
        """Обработка сообщения от userbot"""
        if not message.chat:
            return
            
        chat_id = message.chat.id
        
        # Проверяем, мониторится ли этот чат/канал
        if chat_id not in self.monitored_sources:
            return
            
        # Получаем пользователей, которые мониторят этот источник
        if message.chat.type.name in ["CHANNEL", "SUPERGROUP"]:
            is_channel = message.chat.type.name == "CHANNEL"
            if is_channel:
                monitoring_users = Storage.get_users_monitoring_channel(chat_id)
            else:
                monitoring_users = Storage.get_users_monitoring_chat(chat_id)
        else:
            # Обычная группа
            monitoring_users = Storage.get_users_monitoring_chat(chat_id)
            is_channel = False
        
        if not monitoring_users:
            logger.info(f"Нет пользователей, мониторящих источник {chat_id}")
            return
            
        # Создаем объект сообщения
        chat_title = message.chat.title or message.chat.first_name or f"Чат {chat_id}"
        
        msg = Message(
            message_id=message.id,
            chat_id=chat_id,
            chat_title=chat_title,
            text=message.text or message.caption or "",
            date=datetime.fromtimestamp(message.date),
            is_channel=is_channel
        )
        
        # Информация об отправителе
        if message.from_user:
            msg.sender_id = message.from_user.id
            msg.sender_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        
        logger.info(f"Userbot получил сообщение из {chat_title}: {msg.text[:50]}...")
        
        # Анализируем сообщение для каждого пользователя
        for user in monitoring_users:
            try:
                importance_score = await evaluate_message_importance(msg, user)
                msg.importance_score = importance_score
                
                logger.info(f"Userbot: оценка важности для пользователя {user.user_id}: {importance_score:.2f}")
                
                # Если сообщение достаточно важно, отправляем уведомление через основного бота
                if importance_score >= user.importance_threshold:
                    await self.send_notification_to_user(user.user_id, msg)
                    
            except Exception as e:
                logger.error(f"Ошибка анализа сообщения userbot для пользователя {user.user_id}: {e}")
    
    async def send_notification_to_user(self, user_id: int, message: Message):
        """Отправка уведомления пользователю через основного бота"""
        notification_text = (
            f"🤖 <b>USERBOT УВЕДОМЛЕНИЕ</b>\n\n"
            f"🔔 <b>Важное сообщение обнаружено!</b>\n\n"
            f"{message.to_user_notification()}\n\n"
            f"📋 <i>Источник: Скрытый мониторинг (userbot)</i>\n"
            f"🔒 <i>Полная анонимность и приватность</i>"
        )
        
        try:
            # Импортируем здесь, чтобы избежать циклических импортов
            import bot
            if hasattr(bot, 'application') and bot.application:
                await bot.application.bot.send_message(
                    chat_id=user_id,
                    text=notification_text,
                    parse_mode='HTML'
                )
                logger.info(f"Userbot отправил уведомление пользователю {user_id}")
            else:
                logger.error("Application не найден в bot модуле")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления userbot пользователю {user_id}: {e}")
    
    async def start(self):
        """Запуск userbot"""
        if not self.app:
            logger.warning("Userbot не может быть запущен: отсутствуют учетные данные")
            return False
            
        try:
            await self.app.start()
            self.is_running = True
            logger.info("🤖 Userbot успешно запущен!")
            
            # Получаем информацию о текущем пользователе
            me = await self.app.get_me()
            logger.info(f"Userbot работает как: {me.first_name} (@{me.username or 'без_username'})")
            
            return True
            
        except AuthKeyUnregistered:
            logger.error("❌ Userbot: сессия недействительна. Требуется повторная авторизация.")
            return False
        except UserDeactivated:
            logger.error("❌ Userbot: аккаунт заблокирован или деактивирован.")
            return False
        except Exception as e:
            error_msg = str(e)
            if "KeyError: 0" in error_msg or error_msg == "0":
                logger.error("❌ Userbot: ошибка авторизации. Возможно, сессия повреждена или учетные данные неверны.")
                logger.info("💡 Попробуйте удалить файл userbot_session.session и перезапустить бота для повторной авторизации")
            elif "ConnectionResetError" in error_msg:
                logger.error("❌ Userbot: проблемы с сетевым соединением. Проверьте интернет-соединение.")
            elif "FloodWait" in error_msg:
                logger.error("❌ Userbot: превышен лимит запросов к Telegram API. Попробуйте позже.")
            else:
                logger.error(f"❌ Ошибка запуска userbot: {e}")
            return False
    
    async def stop(self):
        """Остановка userbot"""
        if self.app and self.is_running:
            await self.app.stop()
            self.is_running = False
            logger.info("🛑 Userbot остановлен")
    
    def reset_session(self):
        """Сброс сессии userbot (удаление файла сессии)"""
        try:
            session_file = "userbot_session.session"
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info("🔄 Файл сессии userbot удален. При следующем запуске потребуется повторная авторизация.")
                return True
            else:
                logger.warning("⚠️ Файл сессии не найден.")
                return False
        except Exception as e:
            logger.error(f"❌ Ошибка удаления файла сессии: {e}")
            return False
    
    def _extract_username_from_link(self, link: str) -> str:
        """Извлекает username из ссылки Telegram"""
        # Убираем пробелы
        link = link.strip()
        
        # Если это уже username (начинается с @)
        if link.startswith('@'):
            return link
        
        # Если это ссылка t.me
        if 't.me/' in link:
            # Извлекаем часть после t.me/
            username = link.split('t.me/')[-1]
            # Убираем параметры после ?
            username = username.split('?')[0]
            # Убираем слеши в конце
            username = username.rstrip('/')
            return f"@{username}"
        
        # Если это полная ссылка https://t.me/
        if link.startswith('https://t.me/'):
            username = link.replace('https://t.me/', '')
            username = username.split('?')[0]
            username = username.rstrip('/')
            return f"@{username}"
        
        # Если это уже username без @
        if not link.startswith('@') and not link.startswith('http'):
            return f"@{link}"
        
        # Если ничего не подошло, возвращаем как есть
        return link

    async def join_chat(self, chat_username_or_link: str) -> bool:
        """Присоединение к чату или каналу"""
        if not self.app or not self.is_running:
            return False
            
        try:
            # Извлекаем username из ссылки
            username = self._extract_username_from_link(chat_username_or_link)
            logger.info(f"Userbot пытается присоединиться к {username}")
            
            # Попытка присоединиться к чату/каналу
            chat = await self.app.join_chat(username)
            chat_id = chat.id
            
            # Добавляем в список мониторинга
            self.monitored_sources.add(chat_id)
            
            logger.info(f"Userbot присоединился к {chat.title} (ID: {chat_id})")
            return True
            
        except FloodWait as e:
            logger.warning(f"Userbot: флуд-лимит при присоединении к чату. Ожидание {e.x} секунд.")
            await asyncio.sleep(e.x)
            return False
        except Exception as e:
            logger.error(f"Userbot: ошибка присоединения к чату {chat_username_or_link}: {e}")
            return False
    
    async def leave_chat(self, chat_id: int) -> bool:
        """Покидание чата или канала"""
        if not self.app or not self.is_running:
            return False
            
        try:
            await self.app.leave_chat(chat_id)
            
            # Удаляем из списка мониторинга
            self.monitored_sources.discard(chat_id)
            
            logger.info(f"Userbot покинул чат {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Userbot: ошибка при покидании чата {chat_id}: {e}")
            return False
    
    def add_monitoring_source(self, chat_id: int):
        """Добавление источника в мониторинг"""
        self.monitored_sources.add(chat_id)
        logger.info(f"Userbot добавил в мониторинг источник {chat_id}")
    
    def remove_monitoring_source(self, chat_id: int):
        """Удаление источника из мониторинга"""
        self.monitored_sources.discard(chat_id)
        logger.info(f"Userbot удалил из мониторинга источник {chat_id}")
    
    async def get_chat_info(self, chat_username_or_id):
        """Получение информации о чате/канале"""
        if not self.app or not self.is_running:
            return None
            
        try:
            # Извлекаем username из ссылки если это ссылка
            if isinstance(chat_username_or_id, str) and ('t.me/' in chat_username_or_id or chat_username_or_id.startswith('http')):
                chat_username_or_id = self._extract_username_from_link(chat_username_or_id)
            
            chat = await self.app.get_chat(chat_username_or_id)
            return {
                'id': chat.id,
                'title': chat.title,
                'username': chat.username,
                'type': chat.type.name,
                'members_count': getattr(chat, 'members_count', 0)
            }
        except Exception as e:
            logger.error(f"Userbot: ошибка получения информации о чате {chat_username_or_id}: {e}")
            return None
    
    def get_monitored_sources(self) -> set:
        """Получение списка мониторимых источников"""
        return self.monitored_sources.copy()

# Глобальный экземпляр userbot
userbot = UserBot()

async def start_userbot():
    """Запуск userbot"""
    return await userbot.start()

async def stop_userbot():
    """Остановка userbot"""
    await userbot.stop()

def get_userbot() -> UserBot:
    """Получение экземпляра userbot"""
    return userbot