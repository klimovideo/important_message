#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности бота
"""
import os
import sys
import asyncio
from datetime import datetime

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Storage, UserPreferences, BotConfig, PendingPost, PostStatus
from ai_service import evaluate_message_importance

def test_storage():
    """Тестируем хранилище данных"""
    print("🧪 Тестирование хранилища...")
    
    # Создаем тестового пользователя
    test_user_id = 123456789
    user = Storage.get_user(test_user_id)
    print(f"✅ Создан пользователь: {user.user_id}")
    
    # Добавляем администратора
    Storage.add_admin(test_user_id)
    print(f"✅ Пользователь добавлен как администратор")
    
    # Проверяем права
    is_admin = Storage.is_admin(test_user_id)
    print(f"✅ Проверка прав администратора: {is_admin}")
    
    # Создаем тестовый пост
    post = PendingPost(
        post_id="test123",
        user_id=test_user_id,
        message_text="Это тестовый пост для проверки функциональности",
        source_info="Тестовый источник",
        importance_score=0.8
    )
    Storage.add_pending_post(post)
    print(f"✅ Создан тестовый пост: {post.post_id}")
    
    # Получаем посты на модерации
    pending_posts = Storage.get_pending_posts(PostStatus.PENDING)
    print(f"✅ Постов на модерации: {len(pending_posts)}")
    
    # Очищаем тестовые данные
    Storage.delete_post("test123")
    Storage.remove_admin(test_user_id)
    Storage.delete_user(test_user_id)
    print("✅ Тестовые данные очищены")
    
    return True

def test_menu_structure():
    """Проверяем структуру меню"""
    print("\n🧪 Тестирование структуры меню...")
    
    # Импортируем функции меню
    from bot import get_main_reply_keyboard
    
    # Тестируем меню администратора
    admin_id = 999999999
    Storage.add_admin(admin_id)
    admin_keyboard = get_main_reply_keyboard(admin_id)
    
    print("📱 Меню администратора:")
    for row in admin_keyboard.keyboard:
        print(f"  {' | '.join(row)}")
    
    # Тестируем меню обычного пользователя
    user_keyboard = get_main_reply_keyboard(123456)
    
    print("\n📱 Меню пользователя:")
    for row in user_keyboard.keyboard:
        print(f"  {' | '.join(row)}")
    
    # Очищаем
    Storage.remove_admin(admin_id)
    
    return True

def test_ai_evaluation():
    """Тестируем оценку важности сообщений"""
    print("\n🧪 Тестирование ИИ оценки...")
    
    # Создаем тестовое сообщение
    from models import Message
    
    test_message = Message(
        message_id=1,
        chat_id=-1001234567890,
        chat_title="Тестовый канал",
        text="СРОЧНО! Важная встреча завтра в 10:00. Всем обязательно присутствовать!",
        date=datetime.now(),
        is_channel=True
    )
    
    # Создаем пользователя с ключевыми словами
    user = UserPreferences(
        user_id=111111,
        keywords=["срочно", "важная", "встреча"],
        exclude_keywords=["реклама", "спам"]
    )
    
    # Оцениваем важность
    try:
        score = evaluate_message_importance(test_message, user)
        print(f"✅ Оценка важности сообщения: {score:.2f}")
        print(f"   Порог: {Storage.bot_config.importance_threshold}")
        print(f"   Важное: {'Да' if score >= Storage.bot_config.importance_threshold else 'Нет'}")
    except Exception as e:
        print(f"❌ Ошибка оценки: {e}")
        return False
    
    return True

def main():
    """Основная функция тестирования"""
    print("🤖 Тестирование бота важных сообщений\n")
    
    tests = [
        ("Хранилище данных", test_storage),
        ("Структура меню", test_menu_structure),
        ("ИИ оценка", test_ai_evaluation)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: ERROR - {e}")
    
    print(f"\n📊 Результаты тестирования:")
    print(f"   ✅ Успешно: {passed}")
    print(f"   ❌ Провалено: {failed}")
    print(f"   📈 Успешность: {(passed/(passed+failed)*100):.1f}%")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)