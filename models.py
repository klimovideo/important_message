from pydantic import BaseModel
from typing import Dict, List, Optional, Set
from datetime import datetime
import json
import os
import logging
import html
from enum import Enum

logger = logging.getLogger(__name__)

class PostCategory(str, Enum):
    """Категории постов"""
    GENERAL = "general"  # Общие новости
    BOOKS = "books"  # Книги и литература
    LLM = "llm"  # LLM и AI
    TECH = "tech"  # Технологии
    SCIENCE = "science"  # Наука

class PostStatus(str, Enum):
    """Статусы постов в очереди"""
    PENDING = "pending"  # Ожидает модерации
    APPROVED = "approved"  # Одобрен
    REJECTED = "rejected"  # Отклонен
    PUBLISHED = "published"  # Опубликован

class ImportanceCriteria(BaseModel):
    """Критерии важности сообщений"""
    keywords_boost: List[str] = []  # Слова, повышающие важность
    keywords_reduce: List[str] = []  # Слова, снижающие важность
    sources_boost: List[int] = []  # ID каналов/чатов с повышенной важностью
    sources_reduce: List[int] = []  # ID каналов/чатов с пониженной важностью
    min_message_length: int = 10  # Минимальная длина сообщения
    max_message_length: int = 4000  # Максимальная длина сообщения
    exclude_forwarded: bool = False  # Исключать пересланные сообщения
    time_sensitivity: bool = True  # Учитывать время публикации

class BotConfig(BaseModel):
    """Глобальная конфигурация бота"""
    admin_ids: Set[int] = set()  # ID администраторов
    publish_channel_id: Optional[int] = None  # ID канала для публикации (основной)
    publish_channel_username: Optional[str] = None  # Username канала
    # Словарь каналов по категориям
    category_channels: Dict[str, Dict[str, Optional[str]]] = {
        PostCategory.GENERAL: {"id": None, "username": None},
        PostCategory.BOOKS: {"id": None, "username": None},
        PostCategory.LLM: {"id": None, "username": None},
        PostCategory.TECH: {"id": None, "username": None},
        PostCategory.SCIENCE: {"id": None, "username": None}
    }
    importance_threshold: float = 0.7  # Глобальный порог важности
    importance_criteria: ImportanceCriteria = ImportanceCriteria()
    auto_publish_enabled: bool = True  # Автоматическая публикация важных постов
    require_admin_approval: bool = True  # Требовать одобрения администратора
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class PendingPost(BaseModel):
    """Пост в очереди на модерацию"""
    post_id: str  # Уникальный ID поста
    user_id: int  # ID пользователя, который отправил
    message_text: str  # Текст сообщения
    category: PostCategory = PostCategory.GENERAL  # Категория поста
    source_info: Optional[str] = None  # Информация об источнике
    importance_score: Optional[float] = None  # Оценка важности ИИ
    status: PostStatus = PostStatus.PENDING
    submitted_at: datetime = datetime.now()
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None  # ID админа, который рассмотрел
    admin_comment: Optional[str] = None  # Комментарий админа
    original_message_id: Optional[int] = None  # ID оригинального сообщения
    original_chat_id: Optional[int] = None  # ID чата источника

class UserPreferences(BaseModel):
    """User preferences for message filtering"""
    user_id: int
    monitored_chats: Set[int] = set()  # Set of chat IDs to monitor
    monitored_channels: Set[int] = set()  # Set of channel IDs to monitor
    keywords: List[str] = []  # Keywords to prioritize
    exclude_keywords: List[str] = []  # Keywords to deprioritize
    can_submit_posts: bool = True  # Может ли пользователь предлагать посты
    current_state: Optional[str] = None  # Текущее состояние пользователя (userbot_join, etc.)
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            set: list
        }

class Message(BaseModel):
    """Message data structure"""
    message_id: int
    chat_id: int
    chat_title: str
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    text: str
    date: datetime
    importance_score: Optional[float] = None
    is_channel: bool = False
    
    def to_prompt(self) -> str:
        """Convert message to a format suitable for AI prompt"""
        source = f"канал '{self.chat_title}'" if self.is_channel else f"чат '{self.chat_title}'"
        sender = f" от {self.sender_name}" if self.sender_name else ""
        return f"Сообщение{sender} в {source} в {self.date.strftime('%d.%m.%Y %H:%M:%S')}:\n\n{self.text}"
    
    def to_user_notification(self) -> str:
        """Format message as a notification to the user"""
        source = f"Канал: {html.escape(self.chat_title)}" if self.is_channel else f"Чат: {html.escape(self.chat_title)}"
        sender = f"\nОт: {html.escape(self.sender_name)}" if self.sender_name else ""
        importance = f"\nОценка важности: {self.importance_score:.2f}" if self.importance_score is not None else ""
        
        return f"🔔 *ВАЖНОЕ СООБЩЕНИЕ*\n\n{source}{sender}{importance}\n\n{html.escape(self.text)}"

class Storage:
    """Simple JSON-based storage for user preferences"""
    DB_FILE = "user_preferences.json"
    CONFIG_FILE = "bot_config.json"
    POSTS_FILE = "pending_posts.json"
    
    users: Dict[int, UserPreferences] = {}
    bot_config: BotConfig = BotConfig()
    pending_posts: Dict[str, PendingPost] = {}
    
    @classmethod
    def load_from_file(cls) -> None:
        """Load all data from JSON files"""
        cls.ensure_files_exist()
        cls.load_users()
        cls.load_config()
        cls.load_posts()
    
    @classmethod
    def ensure_files_exist(cls) -> None:
        """Ensure all required files exist with default content"""
        # Create user preferences file if not exists
        if not os.path.exists(cls.DB_FILE):
            logger.info(f"Создаю файл {cls.DB_FILE}")
            with open(cls.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        # Create bot config file if not exists
        if not os.path.exists(cls.CONFIG_FILE):
            logger.info(f"Создаю файл {cls.CONFIG_FILE}")
            default_config = BotConfig()
            config_dict = {
                "admin_ids": list(default_config.admin_ids),
                "publish_channel_id": default_config.publish_channel_id,
                "publish_channel_username": default_config.publish_channel_username,
                "importance_threshold": default_config.importance_threshold,
                "importance_criteria": {
                    "keywords_boost": default_config.importance_criteria.keywords_boost,
                    "keywords_reduce": default_config.importance_criteria.keywords_reduce,
                    "sources_boost": default_config.importance_criteria.sources_boost,
                    "sources_reduce": default_config.importance_criteria.sources_reduce,
                    "min_message_length": default_config.importance_criteria.min_message_length,
                    "max_message_length": default_config.importance_criteria.max_message_length,
                    "exclude_forwarded": default_config.importance_criteria.exclude_forwarded,
                    "time_sensitivity": default_config.importance_criteria.time_sensitivity
                },
                "auto_publish_enabled": default_config.auto_publish_enabled,
                "require_admin_approval": default_config.require_admin_approval,
                "created_at": default_config.created_at.isoformat(),
                "updated_at": default_config.updated_at.isoformat()
            }
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
        
        # Create pending posts file if not exists
        if not os.path.exists(cls.POSTS_FILE):
            logger.info(f"Создаю файл {cls.POSTS_FILE}")
            with open(cls.POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_users(cls) -> None:
        """Load user preferences from JSON file"""
        if not os.path.exists(cls.DB_FILE):
            logger.info(f"Файл базы данных {cls.DB_FILE} не найден, начинаем с пустого хранилища")
            return
        
        try:
            with open(cls.DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for user_id_str, user_data in data.items():
                user_id = int(user_id_str)
                # Convert sets back from lists
                if 'monitored_chats' in user_data:
                    user_data['monitored_chats'] = set(user_data['monitored_chats'])
                if 'monitored_channels' in user_data:
                    user_data['monitored_channels'] = set(user_data['monitored_channels'])
                
                # Parse datetime strings
                if 'created_at' in user_data:
                    user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
                if 'updated_at' in user_data:
                    user_data['updated_at'] = datetime.fromisoformat(user_data['updated_at'])
                
                cls.users[user_id] = UserPreferences(**user_data)
                
            logger.info(f"Загружено {len(cls.users)} пользователей из базы данных")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки базы данных: {e}")
            cls.users = {}
    
    @classmethod
    def load_config(cls) -> None:
        """Load bot configuration from JSON file"""
        if not os.path.exists(cls.CONFIG_FILE):
            logger.info(f"Файл конфигурации {cls.CONFIG_FILE} не найден, используем настройки по умолчанию")
            return
        
        try:
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert admin_ids from list to set
            if 'admin_ids' in data:
                data['admin_ids'] = set(data['admin_ids'])
            
            # Parse datetime strings
            if 'created_at' in data:
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            if 'updated_at' in data:
                data['updated_at'] = datetime.fromisoformat(data['updated_at'])
            
            # Parse importance criteria
            if 'importance_criteria' in data:
                data['importance_criteria'] = ImportanceCriteria(**data['importance_criteria'])
            
            cls.bot_config = BotConfig(**data)
            logger.info("Загружена конфигурация бота")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки конфигурации: {e}")
            cls.bot_config = BotConfig()
    
    @classmethod
    def load_posts(cls) -> None:
        """Load pending posts from JSON file"""
        if not os.path.exists(cls.POSTS_FILE):
            logger.info(f"Файл постов {cls.POSTS_FILE} не найден, начинаем с пустой очереди")
            return
        
        try:
            with open(cls.POSTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for post_id, post_data in data.items():
                # Parse datetime strings
                if 'submitted_at' in post_data:
                    post_data['submitted_at'] = datetime.fromisoformat(post_data['submitted_at'])
                if 'reviewed_at' in post_data and post_data['reviewed_at']:
                    post_data['reviewed_at'] = datetime.fromisoformat(post_data['reviewed_at'])
                
                cls.pending_posts[post_id] = PendingPost(**post_data)
            
            logger.info(f"Загружено {len(cls.pending_posts)} постов из очереди")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки постов: {e}")
            cls.pending_posts = {}
    
    @classmethod
    def save_to_file(cls) -> None:
        """Save all data to JSON files"""
        cls.save_users()
        cls.save_config()
        cls.save_posts()
    
    @classmethod
    def save_users(cls) -> None:
        """Save user preferences to JSON file with backup"""
        try:
            # Создаем резервную копию если файл существует
            if os.path.exists(cls.DB_FILE):
                import shutil
                backup_file = f"{cls.DB_FILE}.bak"
                shutil.copy2(cls.DB_FILE, backup_file)
            
            data = {}
            for user_id, user in cls.users.items():
                user_dict = user.dict()
                # Convert sets to lists for JSON serialization
                user_dict['monitored_chats'] = list(user.monitored_chats)
                user_dict['monitored_channels'] = list(user.monitored_channels)
                data[str(user_id)] = user_dict
            
            with open(cls.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
            logger.info(f"Сохранено {len(cls.users)} пользователей в базу данных")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения базы данных: {e}")
            # Восстанавливаем из резервной копии если есть
            backup_file = f"{cls.DB_FILE}.bak"
            if os.path.exists(backup_file):
                import shutil
                shutil.copy2(backup_file, cls.DB_FILE)
                logger.info("Восстановлена резервная копия базы данных")
    
    @classmethod
    def save_config(cls) -> None:
        """Save bot configuration to JSON file"""
        try:
            data = cls.bot_config.dict()
            data['admin_ids'] = list(cls.bot_config.admin_ids)
            
            with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info("Сохранена конфигурация бота")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    @classmethod
    def save_posts(cls) -> None:
        """Save pending posts to JSON file"""
        try:
            data = {}
            for post_id, post in cls.pending_posts.items():
                data[post_id] = post.dict()
            
            with open(cls.POSTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Сохранено {len(cls.pending_posts)} постов в очереди")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения постов: {e}")
    
    @classmethod
    def get_user(cls, user_id: int) -> UserPreferences:
        """Get user preferences, create if not exists"""
        if user_id not in cls.users:
            cls.users[user_id] = UserPreferences(user_id=user_id)
            cls.save_users()
        return cls.users[user_id]
    
    @classmethod
    def update_user(cls, preferences: UserPreferences) -> None:
        """Update user preferences and save to file"""
        preferences.updated_at = datetime.now()
        cls.users[preferences.user_id] = preferences
        cls.save_users()
    
    @classmethod
    def delete_user(cls, user_id: int) -> bool:
        """Delete user preferences"""
        if user_id in cls.users:
            del cls.users[user_id]
            cls.save_users()
            return True
        return False
    
    @classmethod
    def get_all_users(cls) -> Dict[int, UserPreferences]:
        """Get all users"""
        return cls.users.copy()
    
    @classmethod
    def get_users_monitoring_chat(cls, chat_id: int) -> List[UserPreferences]:
        """Get all users monitoring a specific chat"""
        return [user for user in cls.users.values() if chat_id in user.monitored_chats]
    
    @classmethod
    def get_users_monitoring_channel(cls, channel_id: int) -> List[UserPreferences]:
        """Get all users monitoring a specific channel"""
        return [user for user in cls.users.values() if channel_id in user.monitored_channels]
    
    @classmethod
    def update_config(cls, config: BotConfig) -> None:
        """Update bot configuration"""
        config.updated_at = datetime.now()
        cls.bot_config = config
        cls.save_config()
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in cls.bot_config.admin_ids
    
    @classmethod
    def add_admin(cls, user_id: int) -> None:
        """Add admin"""
        cls.bot_config.admin_ids.add(user_id)
        cls.save_config()
    
    @classmethod
    def remove_admin(cls, user_id: int) -> None:
        """Remove admin"""
        cls.bot_config.admin_ids.discard(user_id)
        cls.save_config()
    
    @classmethod
    def add_pending_post(cls, post: PendingPost) -> None:
        """Add post to pending queue"""
        cls.pending_posts[post.post_id] = post
        cls.save_posts()
    
    @classmethod
    def get_pending_post(cls, post_id: str) -> Optional[PendingPost]:
        """Get pending post by ID"""
        return cls.pending_posts.get(post_id)
    
    @classmethod
    def update_post_status(cls, post_id: str, status: PostStatus, admin_id: Optional[int] = None, comment: Optional[str] = None) -> bool:
        """Update post status"""
        if post_id in cls.pending_posts:
            post = cls.pending_posts[post_id]
            post.status = status
            post.reviewed_at = datetime.now()
            post.reviewed_by = admin_id
            post.admin_comment = comment
            cls.save_posts()
            return True
        return False
    
    @classmethod
    def get_pending_posts(cls, status: Optional[PostStatus] = None) -> List[PendingPost]:
        """Get pending posts, optionally filtered by status"""
        if status:
            return [post for post in cls.pending_posts.values() if post.status == status]
        return list(cls.pending_posts.values())
    
    @classmethod
    def delete_post(cls, post_id: str) -> bool:
        """Delete post from queue"""
        if post_id in cls.pending_posts:
            del cls.pending_posts[post_id]
            cls.save_posts()
            return True
        return False

# Initialize storage on import
Storage.load_from_file() 