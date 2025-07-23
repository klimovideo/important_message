#!/usr/bin/env python3
"""
Test script for Important Message Bot
This script tests the basic functionality without running the actual bot.
"""
import asyncio
import json
from datetime import datetime
from models import Message, UserPreferences, Storage
from ai_service import evaluate_message_importance
from utils import setup_logging

async def test_message_analysis():
    """Test message importance analysis"""
    print("🧪 Тестирование анализа важности сообщений...")
    
    # Create test message
    test_message = Message(
        message_id=1,
        chat_id=123456,
        chat_title="Тестовый чат",
        text="Срочно! Важная встреча завтра в 10:00. Все должны присутствовать.",
        date=datetime.now(),
        is_channel=False
    )
    
    # Create test user preferences
    test_user = UserPreferences(
        user_id=789,
        importance_threshold=0.6,
        keywords=["срочно", "важно", "встреча"],
        monitored_chats={123456}
    )
    
    try:
        # Test importance evaluation
        importance_score = await evaluate_message_importance(test_message, test_user)
        print(f"✅ Оценка важности сообщения: {importance_score:.2f}")
        
        if importance_score >= test_user.importance_threshold:
            print("✅ Сообщение будет считаться важным")
        else:
            print("❌ Сообщение будет считаться неважным")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования анализа сообщений: {e}")

def test_storage():
    """Test storage functionality"""
    print("\n🧪 Тестирование функциональности хранилища...")
    
    try:
        # Test user creation
        user = Storage.get_user(12345)
        print(f"✅ Создан пользователь с ID: {user.user_id}")
        
        # Test user update
        user.importance_threshold = 0.8
        user.keywords = ["тест", "важно"]
        Storage.update_user(user)
        print("✅ Обновлены настройки пользователя")
        
        # Test user retrieval
        retrieved_user = Storage.get_user(12345)
        print(f"✅ Получен пользователь с порогом: {retrieved_user.importance_threshold}")
        
        # Test monitoring functions
        users_monitoring = Storage.get_users_monitoring_chat(123456)
        print(f"✅ Пользователи, мониторящие чат 123456: {len(users_monitoring)}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования хранилища: {e}")

def test_utils():
    """Test utility functions"""
    print("\n🧪 Тестирование утилит...")
    
    try:
        from utils import safe_json_parse, validate_chat_id, format_timestamp
        
        # Test JSON parsing
        test_json = '{"score": 0.8, "reason": "тест"}'
        result = safe_json_parse(test_json)
        print(f"✅ Парсинг JSON: {result}")
        
        # Test chat ID validation
        valid_id = validate_chat_id("123456")
        invalid_id = validate_chat_id("неверный")
        print(f"✅ Валидация ID чата: {valid_id}, {invalid_id}")
        
        # Test timestamp formatting
        timestamp = format_timestamp(datetime.now())
        print(f"✅ Форматирование времени: {timestamp}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования утилит: {e}")

async def main():
    """Run all tests"""
    print("🚀 Запуск тестов бота важных сообщений...\n")
    
    # Setup logging
    setup_logging("INFO")
    
    # Test storage
    test_storage()
    
    # Test utilities
    test_utils()
    
    # Test message analysis (requires GigaChat API)
    try:
        await test_message_analysis()
    except Exception as e:
        print(f"⚠️  Тест анализа сообщений пропущен (требуется GigaChat API): {e}")
    
    print("\n✅ Все тесты завершены!")

if __name__ == "__main__":
    asyncio.run(main()) 