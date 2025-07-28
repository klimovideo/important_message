import logging
import uuid
import html
from datetime import datetime
from typing import List, Optional
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError

from models import Storage, PendingPost, PostStatus, BotConfig
from ai_service import evaluate_message_importance

logger = logging.getLogger(__name__)

class AdminService:
    """Сервис для администрирования бота и управления публикациями"""
    
    @staticmethod
    async def publish_to_channel(bot: Bot, text: str, parse_mode: str = ParseMode.HTML) -> bool:
        """
        Публикует сообщение в канале бота
        
        Args:
            bot: Telegram Bot instance
            text: Текст для публикации
            parse_mode: Режим парсинга текста
            
        Returns:
            bool: True если публикация успешна, False иначе
        """
        config = Storage.bot_config
        
        if not config.publish_channel_id:
            logger.error("ID канала для публикации не настроен")
            return False
        
        try:
            await bot.send_message(
                chat_id=config.publish_channel_id,
                text=text,
                parse_mode=parse_mode
            )
            logger.info(f"Сообщение успешно опубликовано в канале {config.publish_channel_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Ошибка публикации в канал: {e}")
            return False
    
    @staticmethod
    async def submit_post_for_review(user_id: int, message_text: str, source_info: str = None) -> str:
        """
        Отправляет пост на модерацию
        
        Args:
            user_id: ID пользователя, который отправляет пост
            message_text: Текст сообщения
            source_info: Информация об источнике сообщения
            
        Returns:
            str: ID созданного поста
        """
        # Проверяем, может ли пользователь отправлять посты
        user = Storage.get_user(user_id)
        if not user.can_submit_posts:
            raise PermissionError("Пользователь не может отправлять посты на модерацию")
        
        # Создаем уникальный ID поста
        post_id = str(uuid.uuid4())[:8]
        
        # Создаем объект поста
        post = PendingPost(
            post_id=post_id,
            user_id=user_id,
            message_text=message_text,
            source_info=source_info,
            status=PostStatus.PENDING
        )
        
        # Сохраняем пост в очереди
        Storage.add_pending_post(post)
        
        logger.info(f"Пост {post_id} от пользователя {user_id} добавлен в очередь на модерацию")
        return post_id
    
    @staticmethod
    async def evaluate_and_maybe_auto_publish(bot: Bot, post: PendingPost) -> bool:
        """
        Оценивает пост с помощью ИИ и возможно автоматически публикует его
        
        Args:
            bot: Telegram Bot instance
            post: Пост для оценки
            
        Returns:
            bool: True если пост был автоматически опубликован
        """
        config = Storage.bot_config
        
        if not config.auto_publish_enabled or config.require_admin_approval:
            return False
        
        try:
            # Создаем фиктивный объект сообщения для оценки ИИ
            from models import Message
            fake_message = Message(
                message_id=0,
                chat_id=0,
                chat_title="Пост от пользователя",
                text=post.message_text,
                date=post.submitted_at,
                is_channel=False
            )
            
            # Получаем предпочтения пользователя
            user_prefs = Storage.get_user(post.user_id)
            
            # Оцениваем важность
            importance_score = evaluate_message_importance(fake_message, user_prefs)
            post.importance_score = importance_score
            
            # Если оценка выше порога, публикуем автоматически
            if importance_score >= config.importance_threshold:
                # Форматируем текст для публикации
                publish_text = AdminService.format_post_for_publication(post)
                
                # Публикуем
                if await AdminService.publish_to_channel(bot, publish_text):
                    # Обновляем статус поста
                    Storage.update_post_status(post.post_id, PostStatus.PUBLISHED)
                    logger.info(f"Пост {post.post_id} автоматически опубликован (оценка: {importance_score:.2f})")
                    return True
            
            logger.info(f"Пост {post.post_id} не прошел автоматическую публикацию (оценка: {importance_score:.2f})")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при автоматической оценке поста {post.post_id}: {e}")
            return False
    
    @staticmethod
    def format_post_for_publication(post: PendingPost) -> str:
        """
        Форматирует пост для публикации в канале
        
        Args:
            post: Пост для форматирования
            
        Returns:
            str: Отформатированный текст
        """
        # Базовый текст
        text = post.message_text
        
        # Добавляем информацию об источнике, если есть
        if post.source_info:
            text += f"\n\n📋 <i>Источник: {post.source_info}</i>"
        
        # Добавляем оценку важности, если есть
        if post.importance_score:
            text += f"\n⭐ <i>Оценка важности: {post.importance_score:.2f}</i>"
        
        # Добавляем временную метку
        text += f"\n📅 <i>{post.submitted_at.strftime('%d.%m.%Y %H:%M')}</i>"
        
        return text
    
    @staticmethod
    async def approve_post(bot: Bot, post_id: str, admin_id: int, comment: str = None) -> bool:
        """
        Одобряет пост и публикует его
        
        Args:
            bot: Telegram Bot instance
            post_id: ID поста
            admin_id: ID администратора
            comment: Комментарий администратора
            
        Returns:
            bool: True если пост успешно одобрен и опубликован
        """
        post = Storage.get_pending_post(post_id)
        if not post:
            return False
        
        if post.status != PostStatus.PENDING:
            logger.warning(f"Попытка одобрить пост {post_id} со статусом {post.status}")
            return False
        
        # Форматируем текст для публикации
        publish_text = AdminService.format_post_for_publication(post)
        
        # Публикуем в канале
        if await AdminService.publish_to_channel(bot, publish_text):
            # Обновляем статус поста
            Storage.update_post_status(post_id, PostStatus.APPROVED, admin_id, comment)
            
            # Уведомляем пользователя об одобрении
            try:
                notification_text = (
                    f"✅ <b>Ваш пост одобрен и опубликован!</b>\n\n"
                    f"📋 <b>ID поста:</b> {post_id}\n"
                    f"👤 <b>Одобрил:</b> Администратор\n"
                )
                
                if comment:
                    import html
                    notification_text += f"💬 <b>Комментарий:</b> {html.escape(comment)}\n"
                
                notification_text += f"\n📅 <b>Опубликовано:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                
                await bot.send_message(
                    chat_id=post.user_id,
                    text=notification_text,
                    parse_mode=ParseMode.HTML
                )
            except TelegramError as e:
                logger.warning(f"Не удалось уведомить пользователя {post.user_id} об одобрении поста: {e}")
            
            logger.info(f"Пост {post_id} одобрен администратором {admin_id} и опубликован")
            return True
        
        return False
    
    @staticmethod
    async def reject_post(bot: Bot, post_id: str, admin_id: int, comment: str = None) -> bool:
        """
        Отклоняет пост
        
        Args:
            bot: Telegram Bot instance
            post_id: ID поста
            admin_id: ID администратора
            comment: Комментарий администратора
            
        Returns:
            bool: True если пост успешно отклонен
        """
        post = Storage.get_pending_post(post_id)
        if not post:
            return False
        
        if post.status != PostStatus.PENDING:
            logger.warning(f"Попытка отклонить пост {post_id} со статусом {post.status}")
            return False
        
        # Обновляем статус поста
        Storage.update_post_status(post_id, PostStatus.REJECTED, admin_id, comment)
        
        # Уведомляем пользователя об отклонении
        try:
            notification_text = (
                f"❌ <b>Ваш пост отклонен</b>\n\n"
                f"📋 <b>ID поста:</b> {post_id}\n"
                f"👤 <b>Отклонил:</b> Администратор\n"
            )
            
            if comment:
                import html
                notification_text += f"💬 <b>Причина:</b> {html.escape(comment)}\n"
            
            notification_text += f"\n📅 <b>Рассмотрено:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            
            await bot.send_message(
                chat_id=post.user_id,
                text=notification_text,
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.warning(f"Не удалось уведомить пользователя {post.user_id} об отклонении поста: {e}")
        
        logger.info(f"Пост {post_id} отклонен администратором {admin_id}")
        return True
    
    @staticmethod
    def get_posts_for_review() -> List[PendingPost]:
        """
        Получает список постов, ожидающих модерацию
        
        Returns:
            List[PendingPost]: Список постов на модерации
        """
        return Storage.get_pending_posts(PostStatus.PENDING)
    
    @staticmethod
    async def notify_admins_about_new_post(bot: Bot, post: PendingPost) -> None:
        """
        Уведомляет всех администраторов о новом посте на модерации
        
        Args:
            bot: Telegram Bot instance
            post: Новый пост
        """
        config = Storage.bot_config
        
        if not config.admin_ids:
            logger.warning("Нет настроенных администраторов для уведомления")
            return
        
        # Форматируем уведомление
        notification_text = (
            f"📝 <b>Новый пост на модерации</b>\n\n"
            f"📋 <b>ID поста:</b> {post.post_id}\n"
            f"👤 <b>От пользователя:</b> {post.user_id}\n"
            f"📅 <b>Время:</b> {post.submitted_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        if post.source_info:
            import html
            notification_text += f"📋 <b>Источник:</b> {html.escape(post.source_info)}\n"
        
        if post.importance_score:
            notification_text += f"⭐ <b>Оценка ИИ:</b> {post.importance_score:.2f}\n"
        
        notification_text += f"\n📄 <b>Текст:</b>\n{html.escape(post.message_text[:500])}"
        
        if len(post.message_text) > 500:
            notification_text += "..."
        
        # Отправляем уведомления всем администраторам
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=notification_text,
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Уведомление о посте {post.post_id} отправлено администратору {admin_id}")
            except TelegramError as e:
                logger.warning(f"Не удалось уведомить администратора {admin_id}: {e}")
    
    @staticmethod
    async def process_important_message(bot: Bot, message, importance_score: float) -> bool:
        """
        Обрабатывает важное сообщение из мониторинга - может автоматически публиковать
        
        Args:
            bot: Telegram Bot instance
            message: Объект сообщения
            importance_score: Оценка важности
            
        Returns:
            bool: True если сообщение было опубликовано
        """
        config = Storage.bot_config
        
        # Проверяем, включена ли автоматическая публикация важных сообщений
        if not config.auto_publish_enabled:
            return False
        
        # Проверяем, превышает ли важность порог
        if importance_score < config.importance_threshold:
            return False
        
        # Если требуется одобрение администратора, создаем пост на модерацию
        if config.require_admin_approval:
            try:
                post = PendingPost(
                    post_id=str(uuid.uuid4())[:8],
                    user_id=0,  # Системный пост
                    message_text=message.text,
                    source_info=f"Автоматический мониторинг: {message.chat_title}",
                    importance_score=importance_score,
                    status=PostStatus.PENDING
                )
                
                Storage.add_pending_post(post)
                await AdminService.notify_admins_about_new_post(bot, post)
                
                logger.info(f"Важное сообщение добавлено в очередь модерации (оценка: {importance_score:.2f})")
                return False  # Не опубликовано автоматически
                
            except Exception as e:
                logger.error(f"Ошибка создания поста на модерацию: {e}")
                return False
        
        # Автоматическая публикация без модерации
        try:
            publish_text = (
                f"🔔 <b>ВАЖНОЕ СООБЩЕНИЕ</b>\n\n"
                f"{message.text}\n\n"
                f"📋 <i>Источник: {message.chat_title}</i>\n"
                f"⭐ <i>Оценка важности: {importance_score:.2f}</i>\n"
                f"📅 <i>{message.date.strftime('%d.%m.%Y %H:%M')}</i>"
            )
            
            if await AdminService.publish_to_channel(bot, publish_text):
                logger.info(f"Важное сообщение автоматически опубликовано (оценка: {importance_score:.2f})")
                return True
            
        except Exception as e:
            logger.error(f"Ошибка автоматической публикации: {e}")
        
        return False