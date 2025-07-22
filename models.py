from pydantic import BaseModel
from typing import Dict, List, Optional, Set
from datetime import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

class UserPreferences(BaseModel):
    """User preferences for message filtering"""
    user_id: int
    importance_threshold: float = 0.7
    monitored_chats: Set[int] = set()  # Set of chat IDs to monitor
    monitored_channels: Set[int] = set()  # Set of channel IDs to monitor
    keywords: List[str] = []  # Keywords to prioritize
    exclude_keywords: List[str] = []  # Keywords to deprioritize
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
        source = f"Канал: {self.chat_title}" if self.is_channel else f"Чат: {self.chat_title}"
        sender = f"\nОт: {self.sender_name}" if self.sender_name else ""
        importance = f"\nОценка важности: {self.importance_score:.2f}" if self.importance_score is not None else ""
        
        return f"🔔 *ВАЖНОЕ СООБЩЕНИЕ*\n\n{source}{sender}{importance}\n\n{self.text}"

class Storage:
    """Simple JSON-based storage for user preferences"""
    DB_FILE = "user_preferences.json"
    users: Dict[int, UserPreferences] = {}
    
    @classmethod
    def load_from_file(cls) -> None:
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
            # Start with empty storage if there's an error
            cls.users = {}
    
    @classmethod
    def save_to_file(cls) -> None:
        """Save user preferences to JSON file"""
        try:
            # Convert sets to lists for JSON serialization
            data = {}
            for user_id, user in cls.users.items():
                user_dict = user.dict()
                user_dict['monitored_chats'] = list(user.monitored_chats)
                user_dict['monitored_channels'] = list(user.monitored_channels)
                data[str(user_id)] = user_dict
            
            with open(cls.DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                
            logger.info(f"Сохранено {len(cls.users)} пользователей в базу данных")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения базы данных: {e}")
    
    @classmethod
    def get_user(cls, user_id: int) -> UserPreferences:
        """Get user preferences, create if not exists"""
        if user_id not in cls.users:
            cls.users[user_id] = UserPreferences(user_id=user_id)
            cls.save_to_file()  # Save new user
        return cls.users[user_id]
    
    @classmethod
    def update_user(cls, preferences: UserPreferences) -> None:
        """Update user preferences and save to file"""
        preferences.updated_at = datetime.now()
        cls.users[preferences.user_id] = preferences
        cls.save_to_file()
    
    @classmethod
    def delete_user(cls, user_id: int) -> bool:
        """Delete user preferences"""
        if user_id in cls.users:
            del cls.users[user_id]
            cls.save_to_file()
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

# Initialize storage on import
Storage.load_from_file() 